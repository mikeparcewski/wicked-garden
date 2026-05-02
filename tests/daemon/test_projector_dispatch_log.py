"""tests/daemon/test_projector_dispatch_log.py — Projector tests for the
Site 1 bus-cutover handler `_dispatch_log_appended` (#746).

Covers:
  * flag-off (default): handler is a no-op; event_log row is `applied` but
    `dispatch_log_entries` table stays empty.  This is the C2 byte-identity
    contract on the projector side — the disk JSONL is source of truth and
    the projection table is intentionally untouched until the cutover flips.
  * flag-on: INSERT OR IGNORE writes one row per event_id with HMAC fields
    stored verbatim (Council Condition C7 — emitter signs, projector stores).
  * idempotent on duplicate event_id (Decision #6).
  * malformed event payload (missing required fields) is logged and ignored;
    no row written; never raises.
  * dispatched_at ISO string is normalised to INTEGER epoch seconds before
    insertion (council schema note).

T1: deterministic — fixed-epoch timestamps, no wall-clock dependency.
T2: no sleep-based sync.
T3: isolated — each test gets its own in-memory DB via mem_conn fixture.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #746 Site 1.
"""
from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import patch

import pytest

# sys.path and daemon imports provided by tests/daemon/conftest.py.


def _make_event(
    event_id: int = 1,
    project_id: str = "demo-proj",
    phase: str = "design",
    gate: str = "design-quality",
    reviewer: str = "security-engineer",
    dispatch_id: str = "d-1",
    dispatched_at: str = "2026-04-19T10:00:00+00:00",
    hmac_value: str | None = "deadbeef" * 8,
    hmac_present: bool = True,
    raw_payload: str | None = None,
    extra_payload: dict | None = None,
) -> dict[str, Any]:
    """Build a wicked.dispatch.log_entry_appended event matching the
    real emit-side payload from `dispatch_log.append`."""
    record = {
        "reviewer": reviewer,
        "phase": phase,
        "gate": gate,
        "dispatched_at": dispatched_at,
        "dispatcher_agent": "wicked-garden:crew:phase-manager",
        "expected_result_path": "phases/design/gate-result.json",
        "dispatch_id": dispatch_id,
    }
    if hmac_value is not None:
        record["hmac"] = hmac_value
    if raw_payload is None:
        raw_payload = json.dumps(record, separators=(",", ":"))
    payload = {
        "project_id": project_id,
        "phase": phase,
        "gate": gate,
        "reviewer": reviewer,
        "dispatch_id": dispatch_id,
        "dispatcher_agent": "wicked-garden:crew:phase-manager",
        "expected_result_path": "phases/design/gate-result.json",
        "dispatched_at": dispatched_at,
        "hmac": hmac_value,
        "hmac_present": hmac_present,
        "raw_payload": raw_payload,
    }
    if extra_payload:
        payload.update(extra_payload)
    return {
        "event_id": event_id,
        "event_type": "wicked.dispatch.log_entry_appended",
        "chain_id": f"{project_id}.{phase}.{gate}.{dispatch_id}",
        "created_at": 1_700_000_000 + event_id,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Flag-off contract (Council Condition C2)
# ---------------------------------------------------------------------------





def _insert_event_log_parent(conn, event: dict) -> None:
    """Insert the matching event_log row before calling the handler.

    Required after #754 added FK + ON DELETE CASCADE on
    dispatch_log_entries.event_id → event_log.event_id. Without this,
    handler-direct calls hit FOREIGN KEY constraint failed.

    Skips the insert when event_id is not a positive int — those events
    are deliberately malformed test inputs (e.g. proving the handler
    fails-soft on bad payloads), so attempting to parent them would
    invert the test's intent.
    """
    eid = event.get("event_id")
    if not isinstance(eid, int) or eid <= 0:
        return
    conn.execute(
        "INSERT OR IGNORE INTO event_log "
        "(event_id, event_type, chain_id, payload_json, projection_status, ingested_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            eid,
            event["event_type"],
            event.get("chain_id", ""),
            json.dumps(event.get("payload", {})),
            "pending",
            event.get("created_at", 1_700_000_000) if isinstance(event.get("created_at"), int) else 1_700_000_000,
        ),
    )


def test_flag_off_returns_applied_without_writing_table(mem_conn) -> None:
    """Flag-off (env unset) → handler is a no-op.  The projector wrapper
    still records the event_log row as `applied` (Decision #6 contract)
    but `dispatch_log_entries` stays empty.  This is the C2 byte-identity
    contract on the projector side."""
    from daemon.projector import project_event  # type: ignore[import]

    # Ensure flag is unset, not just empty.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)
        status = project_event(mem_conn, _make_event())

    assert status == "applied", (
        "C2 contract: flag-off must still return 'applied' so the event "
        "is recorded in event_log; only the projection table is skipped."
    )
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries"
    ).fetchone()
    assert rows[0] == 0, (
        "C2 violation: flag-off wrote a row to dispatch_log_entries. "
        "The projection table MUST stay empty until the cutover flips."
    )


def test_flag_off_dry_run_value_is_treated_as_off(mem_conn) -> None:
    """Council C1 — only the literal `on` enables the cutover.  Pinned
    here so a future maintainer cannot expand the truthy values without
    a council re-evaluation."""
    from daemon.projector import project_event  # type: ignore[import]

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "dry-run"},
    ):
        status = project_event(mem_conn, _make_event())

    assert status == "applied"
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries"
    ).fetchone()
    assert rows[0] == 0


# ---------------------------------------------------------------------------
# Flag-on contract (Council Conditions C6 + C7)
# ---------------------------------------------------------------------------


def test_flag_on_inserts_row_with_hmac_stored_verbatim(mem_conn) -> None:
    """C6 — INSERT OR IGNORE writes one row keyed on event_id.
    C7 — HMAC stored verbatim from emit payload (no re-sign).
    """
    from daemon.projector import project_event  # type: ignore[import]

    event = _make_event(event_id=42, hmac_value="cafef00d" * 8)

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
    ):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"
    rows = mem_conn.execute(
        "SELECT event_id, project_id, phase, gate, reviewer, dispatch_id, "
        "dispatcher_agent, expected_result_path, dispatched_at, hmac, "
        "hmac_present, raw_payload "
        "FROM dispatch_log_entries"
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["event_id"] == 42
    assert row["project_id"] == "demo-proj"
    assert row["phase"] == "design"
    assert row["gate"] == "design-quality"
    assert row["reviewer"] == "security-engineer"
    assert row["dispatch_id"] == "d-1"
    assert row["dispatcher_agent"] == "wicked-garden:crew:phase-manager"
    assert row["expected_result_path"] == "phases/design/gate-result.json"
    # ISO string normalised to epoch seconds (council schema note).
    # Recompute the expected epoch to avoid a hand-arithmetic error.
    from datetime import datetime
    expected_epoch = int(
        datetime.fromisoformat("2026-04-19T10:00:00+00:00").timestamp()
    )
    assert row["dispatched_at"] == expected_epoch
    assert row["hmac"] == "cafef00d" * 8
    assert row["hmac_present"] == 1
    assert row["raw_payload"]
    # raw_payload round-trips to the canonical record.
    record = json.loads(row["raw_payload"])
    assert record["dispatch_id"] == "d-1"
    assert record["reviewer"] == "security-engineer"


def test_flag_on_idempotent_on_duplicate_event_id(mem_conn) -> None:
    """Decision #6 — replaying the same event yields identical row state."""
    from daemon.projector import project_event  # type: ignore[import]

    event = _make_event(event_id=99)

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
    ):
        _insert_event_log_parent(mem_conn, event)
        status_first = project_event(mem_conn, event)
        _insert_event_log_parent(mem_conn, event)
        status_second = project_event(mem_conn, event)
        _insert_event_log_parent(mem_conn, event)
        status_third = project_event(mem_conn, event)

    assert status_first == status_second == status_third == "applied"
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries WHERE event_id = 99"
    ).fetchone()
    assert rows[0] == 1, (
        "Decision #6 violation: replay produced duplicate rows. "
        "INSERT OR IGNORE keyed on event_id must collapse re-projects."
    )


def test_flag_on_distinct_dispatch_ids_yield_distinct_rows(mem_conn) -> None:
    """Council C5 contract — two retry dispatches with distinct
    dispatch_id MUST land as separate rows.  This pairs with the
    chain_id discriminator fix in scripts/crew/dispatch_log.py."""
    from daemon.projector import project_event  # type: ignore[import]

    event_a = _make_event(event_id=1, dispatch_id="dispatch-A")
    event_b = _make_event(event_id=2, dispatch_id="dispatch-B")

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
    ):
        _insert_event_log_parent(mem_conn, event_a)
        project_event(mem_conn, event_a)
        _insert_event_log_parent(mem_conn, event_b)
        project_event(mem_conn, event_b)

    rows = mem_conn.execute(
        "SELECT event_id, dispatch_id FROM dispatch_log_entries "
        "ORDER BY event_id"
    ).fetchall()
    assert [(r["event_id"], r["dispatch_id"]) for r in rows] == [
        (1, "dispatch-A"),
        (2, "dispatch-B"),
    ]


def test_flag_on_missing_required_field_skips_table_write(mem_conn) -> None:
    """Defensive: missing `raw_payload` (a council-mandated field) MUST
    NOT crash the projector.  The handler logs and skips."""
    from daemon.projector import project_event  # type: ignore[import]

    event = _make_event(event_id=10)
    del event["payload"]["raw_payload"]

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
    ):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    # Wrapper still returns 'applied' (warning is logged via _require).
    assert status == "applied"
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries"
    ).fetchone()
    assert rows[0] == 0, (
        "Missing-field path must not write a partial row."
    )


def test_flag_on_handler_never_raises_on_bad_event_id(mem_conn) -> None:
    """Decision #8 — projector never propagates exceptions.  An event
    arriving without an integer `event_id` must be ignored, not crash."""
    from daemon.projector import project_event  # type: ignore[import]

    event = _make_event()
    event["event_id"] = "not-an-int"  # type: ignore[assignment]

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
    ):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries"
    ).fetchone()
    assert rows[0] == 0


def test_flag_on_dispatched_at_int_passthrough(mem_conn) -> None:
    """If `dispatched_at` arrives as an integer (forward-compat) the
    handler should accept it as epoch seconds without conversion."""
    from daemon.projector import project_event  # type: ignore[import]

    event = _make_event(event_id=5)
    sentinel_epoch = 1_776_500_000
    event["payload"]["dispatched_at"] = sentinel_epoch  # type: ignore[assignment]

    with patch.dict(
        os.environ,
        {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
    ):
        _insert_event_log_parent(mem_conn, event)
        project_event(mem_conn, event)

    row = mem_conn.execute(
        "SELECT dispatched_at FROM dispatch_log_entries WHERE event_id = 5"
    ).fetchone()
    assert row is not None
    assert row["dispatched_at"] == sentinel_epoch


def test_handler_is_registered_in_dispatch_table(mem_conn) -> None:
    """C6 contract — handler MUST be registered always so the _HANDLERS
    map stays static and inspectable.  Gating happens INSIDE the handler,
    not by removing it from the table."""
    from daemon.projector import _HANDLERS, _dispatch_log_appended  # type: ignore[import]

    assert "wicked.dispatch.log_entry_appended" in _HANDLERS
    assert _HANDLERS["wicked.dispatch.log_entry_appended"] is _dispatch_log_appended



# ---------------------------------------------------------------------------
# #753 — _bus ImportError observability (WARN once per process)
# ---------------------------------------------------------------------------


def test_bus_import_error_logs_warn_once(mem_conn, caplog) -> None:
    """First call into _dispatch_log_appended with _bus unimportable emits one
    WARN; subsequent calls under the same condition do NOT re-log (would spam
    on sustained traffic). The handler still falls back to flag-off behavior
    and counts as `_APPLIED` so the event_log audit row is preserved.
    """
    import logging
    import sys
    from daemon import projector

    # Reset the module-level latch so this test is order-independent.
    projector._BUS_IMPORT_WARNED = False

    # Mask the _bus module so the lazy import inside the handler raises.
    saved = sys.modules.pop("_bus", None)
    sys.modules["_bus"] = None  # type: ignore[assignment]
    try:
        caplog.set_level(logging.WARNING, logger=projector.logger.name)
        event = _make_event(event_id=1)
        # Insert event_log row first so the wrapper has something to mark applied.
        mem_conn.execute(
            "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, "
            "projection_status, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
            (1, event["event_type"], event["chain_id"], json.dumps(event["payload"]),
             "pending", 1700000001),
        )
        projector._dispatch_log_appended(mem_conn, event)
        # Second call — must NOT produce another WARN.
        mem_conn.execute(
            "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, "
            "projection_status, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
            (2, event["event_type"], event["chain_id"], json.dumps(event["payload"]),
             "pending", 1700000002),
        )
        projector._dispatch_log_appended(mem_conn, _make_event(event_id=2))
    finally:
        if saved is not None:
            sys.modules["_bus"] = saved
        else:
            sys.modules.pop("_bus", None)
        projector._BUS_IMPORT_WARNED = False  # leave clean for sibling tests

    warns = [r for r in caplog.records
             if r.levelno == logging.WARNING
             and "_bus import failed" in r.getMessage()]
    assert len(warns) == 1, (
        f"expected exactly one WARN on _bus ImportError; got {len(warns)}: "
        f"{[r.getMessage() for r in warns]}"
    )


def test_bus_import_error_falls_back_to_flag_off(mem_conn) -> None:
    """When _bus is unimportable, the handler treats the flag as off:
    no row in dispatch_log_entries, no exception propagated."""
    import sys
    from daemon import projector

    projector._BUS_IMPORT_WARNED = False  # silence the WARN side-effect for this test

    saved = sys.modules.pop("_bus", None)
    sys.modules["_bus"] = None  # type: ignore[assignment]
    try:
        event = _make_event(event_id=42)
        mem_conn.execute(
            "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, "
            "projection_status, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
            (42, event["event_type"], event["chain_id"], json.dumps(event["payload"]),
             "pending", 1700000042),
        )
        # Must not raise.
        projector._dispatch_log_appended(mem_conn, event)
    finally:
        if saved is not None:
            sys.modules["_bus"] = saved
        else:
            sys.modules.pop("_bus", None)

    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries WHERE event_id = 42"
    ).fetchone()[0]
    assert rows == 0, "flag-off fallback must not write the projection table"


# ---------------------------------------------------------------------------
# #754 — FK + ON DELETE CASCADE on dispatch_log_entries.event_id
# ---------------------------------------------------------------------------


def test_dispatch_log_entries_cascades_on_event_log_delete(mem_conn) -> None:
    """Deleting an event_log row removes its dispatch_log_entries projection
    automatically — proves the FK CASCADE is wired AND enforced (PRAGMA
    foreign_keys=ON at connect-time)."""
    # Insert event_log row + matching projection row.
    mem_conn.execute(
        "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, "
        "projection_status, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
        (777, "wicked.dispatch.log_entry_appended", "p.b.g.d-777", "{}",
         "applied", 1700000777),
    )
    mem_conn.execute(
        "INSERT INTO dispatch_log_entries (event_id, project_id, phase, gate, "
        "reviewer, dispatch_id, dispatcher_agent, expected_result_path, "
        "dispatched_at, hmac, hmac_present, raw_payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (777, "p", "b", "g", "rev-1", "d-777",
         "wicked-garden:crew:phase-manager",
         "phases/b/gate-result.json", 1700000777, "ab" * 32, 1, "{}"),
    )
    mem_conn.commit()

    # Sanity: both rows present.
    assert mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries WHERE event_id = 777"
    ).fetchone()[0] == 1

    # Delete the parent → cascade removes the child.
    mem_conn.execute("DELETE FROM event_log WHERE event_id = 777")
    mem_conn.commit()

    cascaded = mem_conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries WHERE event_id = 777"
    ).fetchone()[0]
    assert cascaded == 0, (
        "FK ON DELETE CASCADE must remove the dispatch_log_entries row "
        "when its parent event_log row is deleted (#754). If this fails: "
        "either the FK is missing from the schema or PRAGMA foreign_keys=ON "
        "is not set at connect-time."
    )


def test_foreign_keys_pragma_is_on(mem_conn) -> None:
    """connect() must set PRAGMA foreign_keys=ON or the FK is parsed-but-not-enforced."""
    rows = mem_conn.execute("PRAGMA foreign_keys").fetchall()
    # PRAGMA returns a single row with a single column; SQLite returns 1 when on.
    val = rows[0][0] if not hasattr(rows[0], "keys") else rows[0]["foreign_keys"]
    assert val == 1, (
        f"PRAGMA foreign_keys must be ON for the dispatch_log_entries CASCADE "
        f"to enforce; got {val}. Check daemon/db.py::connect()."
    )
