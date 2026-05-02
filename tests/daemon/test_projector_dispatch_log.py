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
        status_first = project_event(mem_conn, event)
        status_second = project_event(mem_conn, event)
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
        project_event(mem_conn, event_a)
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
