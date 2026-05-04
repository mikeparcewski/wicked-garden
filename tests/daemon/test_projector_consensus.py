"""tests/daemon/test_projector_consensus.py — Projector tests for the
Site 2 bus-cutover handlers `_consensus_report_created` and
`_consensus_evidence_recorded` (#746).

Covers Council Conditions C2-C7 + C10:
  * flag-off (default): both handlers no-op; event_log row is `applied` but
    the projection table stays empty (C2 byte-identity contract).
  * flag-on: INSERT OR IGNORE writes one row per event_id, raw_payload stored
    verbatim from emit payload (C10).
  * idempotent on duplicate event_id (Decision #6).
  * malformed event payload (missing required fields) is logged and ignored;
    no row written; never raises.
  * raw_payload round-trips byte-for-byte (the projector reproduces the
    on-disk file from raw_payload under flag-on).
  * the two flags are independent — flipping one does not flip the other.
  * FK + ON DELETE CASCADE on event_id → event_log enforced.

Pattern reuse note: `_insert_event_log_parent` mirrors the helper from
test_projector_dispatch_log.py (PR #755).  The new FK requires a parent
event_log row before the projection insert can land.

T1: deterministic — fixed-epoch timestamps.
T2: no sleep-based sync.
T3: isolated — each test gets its own in-memory DB via mem_conn fixture.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #746 Site 2.
"""
from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import patch

import pytest


def _insert_event_log_parent(conn, event: dict) -> None:
    """Insert the matching event_log row before calling the handler.

    Required because consensus_reports.event_id and consensus_evidence.event_id
    both FK → event_log.event_id with ON DELETE CASCADE.

    Skips the insert when event_id is not a positive int — those events are
    deliberately malformed test inputs (e.g. proving the handler fails-soft
    on bad payloads), so attempting to parent them would invert the test's
    intent.  Mirrors the helper in test_projector_dispatch_log.py.
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
            event.get("created_at", 1_700_000_000)
                if isinstance(event.get("created_at"), int) else 1_700_000_000,
        ),
    )


# ---------------------------------------------------------------------------
# Event-builder helpers
# ---------------------------------------------------------------------------


def _make_report_event(
    event_id: int = 1,
    project_id: str = "demo-project",
    phase: str = "design",
    decision: str = "APPROVE",
    eval_id: str = "abcdef123456",
    raw_payload: str | None = None,
    extra_payload: dict | None = None,
) -> dict[str, Any]:
    """Build a wicked.consensus.report_created event matching the real emit
    from `consensus_gate._write_consensus_report`."""
    if raw_payload is None:
        raw_payload = json.dumps({
            "phase": phase,
            "decision": decision,
            "confidence": 0.85,
            "agreement_ratio": 0.85,
            "participants": 3,
            "rounds": 1,
            "consensus_points": [],
            "dissenting_views": [],
            "open_questions": [],
        }, indent=2)
    payload = {
        "project_id": project_id,
        "phase": phase,
        "decision": decision,
        "confidence": 0.85,
        "agreement_ratio": 0.85,
        "participants": 3,
        "rounds": 1,
        "eval_id": eval_id,
        "raw_payload": raw_payload,
    }
    if extra_payload:
        payload.update(extra_payload)
    return {
        "event_id": event_id,
        "event_type": "wicked.consensus.report_created",
        "chain_id": f"{project_id}.{phase}.consensus.{eval_id}",
        "created_at": 1_700_000_000 + event_id,
        "payload": payload,
    }


def _make_evidence_event(
    event_id: int = 1,
    project_id: str = "demo-project",
    phase: str = "design",
    result: str = "REJECT",
    eval_id: str = "abcdef123456",
    raw_payload: str | None = None,
    extra_payload: dict | None = None,
) -> dict[str, Any]:
    """Build a wicked.consensus.evidence_recorded event."""
    if raw_payload is None:
        raw_payload = json.dumps({
            "type": "consensus-rejection",
            "phase": phase,
            "result": result,
            "reason": "Strong dissent",
            "consensus_confidence": 0.45,
            "agreement_ratio": 0.45,
            "dissenting_views": [],
            "participants": 5,
        }, indent=2)
    payload = {
        "project_id": project_id,
        "phase": phase,
        "result": result,
        "reason": "Strong dissent",
        "consensus_confidence": 0.45,
        "agreement_ratio": 0.45,
        "participants": 5,
        "eval_id": eval_id,
        "raw_payload": raw_payload,
    }
    if extra_payload:
        payload.update(extra_payload)
    return {
        "event_id": event_id,
        "event_type": "wicked.consensus.evidence_recorded",
        "chain_id": f"{project_id}.{phase}.consensus.{eval_id}.evidence",
        "created_at": 1_700_000_000 + event_id,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Handler registration (Council Condition C5)
# ---------------------------------------------------------------------------


def test_both_handlers_are_registered_in_dispatch_table() -> None:
    """C5 contract — both handlers MUST be registered always so the
    `_HANDLERS` map stays static and inspectable.  Gating happens INSIDE
    each handler, not by removing it from the table."""
    from daemon.projector import (
        _HANDLERS,
        _consensus_report_created,
        _consensus_evidence_recorded,
    )

    assert "wicked.consensus.report_created" in _HANDLERS
    assert _HANDLERS["wicked.consensus.report_created"] is _consensus_report_created
    assert "wicked.consensus.evidence_recorded" in _HANDLERS
    assert _HANDLERS["wicked.consensus.evidence_recorded"] is _consensus_evidence_recorded


# ---------------------------------------------------------------------------
# Flag-off contract (Council Condition C3)
# ---------------------------------------------------------------------------


def test_report_flag_off_returns_applied_without_writing_table(mem_conn) -> None:
    """C3 — explicit ``"off"`` → handler is a no-op.  Wrapper still returns
    'applied' so the event_log row is recorded; only the projection table is skipped.

    After the flag-fold (PR #777), CONSENSUS_REPORT is a shipped/default-ON site,
    so an unset env var now → True.  This test uses explicit ``"off"`` to
    exercise the opt-out path."""
    from daemon.projector import project_event

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "off"}):
        status = project_event(mem_conn, _make_report_event())

    assert status == "applied"
    rows = mem_conn.execute("SELECT COUNT(*) FROM consensus_reports").fetchone()
    assert rows[0] == 0


def test_evidence_flag_off_returns_applied_without_writing_table(mem_conn) -> None:
    """C3 — same explicit ``"off"`` opt-out contract for the evidence handler."""
    from daemon.projector import project_event

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "off"}):
        status = project_event(mem_conn, _make_evidence_event())

    assert status == "applied"
    rows = mem_conn.execute("SELECT COUNT(*) FROM consensus_evidence").fetchone()
    assert rows[0] == 0


def test_report_flag_explicit_off_value_is_treated_as_off(mem_conn) -> None:
    """C2/C3 — ``"off"`` is the canonical opt-out value (case/whitespace normalised).

    Pre-fold, ``"dry-run"`` was used as a proxy.  After the flag-fold (PR #777),
    ``"dry-run"`` for a shipped token falls through to the default-ON map → True.
    The canonical opt-out is now the literal ``"off"``."""
    from daemon.projector import project_event

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "off"}):
        status = project_event(mem_conn, _make_report_event())

    assert status == "applied"
    assert mem_conn.execute("SELECT COUNT(*) FROM consensus_reports").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Flag independence (Council Condition C5 — two flags, two handlers)
# ---------------------------------------------------------------------------


def test_report_flag_on_does_not_enable_evidence_handler(mem_conn) -> None:
    """C5 — the two flags are INDEPENDENT.  Operators may flip one without
    the other.  This test pins that contract: enabling
    ``WG_BUS_AS_TRUTH_CONSENSUS_REPORT`` MUST NOT cause the evidence handler
    to start writing rows when ``WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE`` is off.

    Uses explicit ``"off"`` for the companion flag so the test is unambiguous
    after the flag-fold (PR #777) which made unset → default-ON for shipped sites."""
    from daemon.projector import project_event

    with patch.dict(
        os.environ,
        {
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "off",
        },
        clear=False,
    ):
        # Project an evidence event.  The evidence handler's flag is OFF, so
        # nothing should land in consensus_evidence.
        evt = _make_evidence_event(event_id=42)
        _insert_event_log_parent(mem_conn, evt)
        project_event(mem_conn, evt)

    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_evidence WHERE event_id = 42"
    ).fetchone()[0]
    assert rows == 0, (
        "C5 violation: enabling the report flag also enabled the evidence "
        "handler.  The two flags MUST be independent."
    )


def test_evidence_flag_on_does_not_enable_report_handler(mem_conn) -> None:
    """C5 — symmetric flag independence test.

    Uses explicit ``"off"`` for the companion flag so the test is unambiguous
    after the flag-fold (PR #777) which made unset → default-ON for shipped sites."""
    from daemon.projector import project_event

    with patch.dict(
        os.environ,
        {
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "off",
        },
        clear=False,
    ):
        evt = _make_report_event(event_id=43)
        _insert_event_log_parent(mem_conn, evt)
        project_event(mem_conn, evt)

    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_reports WHERE event_id = 43"
    ).fetchone()[0]
    assert rows == 0


# ---------------------------------------------------------------------------
# Flag-on writes (Council Conditions C5 + C10)
# ---------------------------------------------------------------------------


def test_report_flag_on_inserts_row_with_raw_payload(mem_conn) -> None:
    """C5/C10 — flag-on INSERT OR IGNORE writes one row keyed on event_id.
    raw_payload stored verbatim from emit payload."""
    from daemon.projector import project_event

    raw = json.dumps({"phase": "design", "decision": "APPROVE",
                      "confidence": 0.9, "marker": "round-trip"}, indent=2)
    event = _make_report_event(event_id=42, raw_payload=raw)

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"
    rows = mem_conn.execute(
        "SELECT event_id, project_id, phase, decision, confidence, "
        "agreement_ratio, participants, rounds, created_at, raw_payload "
        "FROM consensus_reports"
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["event_id"] == 42
    assert row["project_id"] == "demo-project"
    assert row["phase"] == "design"
    assert row["decision"] == "APPROVE"
    assert row["confidence"] == pytest.approx(0.85)
    assert row["agreement_ratio"] == pytest.approx(0.85)
    assert row["participants"] == 3
    assert row["rounds"] == 1
    # raw_payload round-trips byte-for-byte
    assert row["raw_payload"] == raw
    parsed = json.loads(row["raw_payload"])
    assert parsed["marker"] == "round-trip"


def test_evidence_flag_on_inserts_row_with_raw_payload(mem_conn) -> None:
    """C5/C10 — same contract for the evidence handler."""
    from daemon.projector import project_event

    raw = json.dumps({"type": "consensus-rejection", "result": "REJECT",
                      "marker": "evidence-round-trip"}, indent=2)
    event = _make_evidence_event(event_id=99, raw_payload=raw)

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on"}):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"
    row = mem_conn.execute(
        "SELECT event_id, project_id, phase, result, reason, "
        "consensus_confidence, agreement_ratio, participants, "
        "created_at, raw_payload FROM consensus_evidence WHERE event_id = 99"
    ).fetchone()
    assert row is not None
    assert row["result"] == "REJECT"
    assert row["reason"] == "Strong dissent"
    assert row["consensus_confidence"] == pytest.approx(0.45)
    assert row["agreement_ratio"] == pytest.approx(0.45)
    assert row["participants"] == 5
    assert row["raw_payload"] == raw


# ---------------------------------------------------------------------------
# Idempotency (Decision #6)
# ---------------------------------------------------------------------------


def test_report_flag_on_idempotent_on_duplicate_event_id(mem_conn) -> None:
    """Decision #6 — replaying the same event yields identical row state."""
    from daemon.projector import project_event

    event = _make_report_event(event_id=99)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _insert_event_log_parent(mem_conn, event)
        s1 = project_event(mem_conn, event)
        _insert_event_log_parent(mem_conn, event)
        s2 = project_event(mem_conn, event)
        _insert_event_log_parent(mem_conn, event)
        s3 = project_event(mem_conn, event)

    assert s1 == s2 == s3 == "applied"
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_reports WHERE event_id = 99"
    ).fetchone()
    assert rows[0] == 1


def test_evidence_flag_on_idempotent_on_duplicate_event_id(mem_conn) -> None:
    """Decision #6 — same idempotency contract for the evidence handler."""
    from daemon.projector import project_event

    event = _make_evidence_event(event_id=88)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on"}):
        _insert_event_log_parent(mem_conn, event)
        project_event(mem_conn, event)
        _insert_event_log_parent(mem_conn, event)
        project_event(mem_conn, event)

    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_evidence WHERE event_id = 88"
    ).fetchone()
    assert rows[0] == 1


# ---------------------------------------------------------------------------
# Defensive: missing required fields, bad event_id (Decision #8)
# ---------------------------------------------------------------------------


def test_report_flag_on_missing_raw_payload_skips_table_write(mem_conn) -> None:
    """Defensive: missing `raw_payload` (Council C10 — REQUIRED) MUST NOT
    crash the projector.  The handler logs and skips."""
    from daemon.projector import project_event

    event = _make_report_event(event_id=10)
    del event["payload"]["raw_payload"]

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"  # wrapper still returns applied; handler logs
    rows = mem_conn.execute("SELECT COUNT(*) FROM consensus_reports").fetchone()[0]
    assert rows == 0


def test_evidence_flag_on_missing_raw_payload_skips_table_write(mem_conn) -> None:
    """Defensive: missing `raw_payload` on the evidence emit also skips."""
    from daemon.projector import project_event

    event = _make_evidence_event(event_id=11)
    del event["payload"]["raw_payload"]

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on"}):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"
    rows = mem_conn.execute("SELECT COUNT(*) FROM consensus_evidence").fetchone()[0]
    assert rows == 0


def test_report_flag_on_handler_never_raises_on_bad_event_id(mem_conn) -> None:
    """Decision #8 — projector never propagates exceptions."""
    from daemon.projector import project_event

    event = _make_report_event()
    event["event_id"] = "not-an-int"  # type: ignore[assignment]

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _insert_event_log_parent(mem_conn, event)
        status = project_event(mem_conn, event)

    assert status == "applied"
    assert mem_conn.execute("SELECT COUNT(*) FROM consensus_reports").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# C9 — chain_id uniqueness across two evals (regression for the latent dedup
# bug fixed by threading eval_id into the chain_id)
# ---------------------------------------------------------------------------


def test_two_evals_on_same_phase_land_as_two_distinct_rows(mem_conn) -> None:
    """C9 regression — two consensus evals on the same (project, phase) with
    distinct eval_ids MUST land as TWO separate rows in `consensus_reports`.

    The OLD chain_id format (`f"{project_id}.{phase}"`) would have collided
    on the bus dedupe ledger and dropped the second emit.  The NEW format
    (`f"{project_id}.{phase}.consensus.{eval_id}"`) keeps them distinct,
    and at the projector level the two distinct event_ids result in two
    distinct rows."""
    from daemon.projector import project_event

    e1 = _make_report_event(event_id=1, eval_id="aaaaaaaaaaaa")
    e2 = _make_report_event(event_id=2, eval_id="bbbbbbbbbbbb")

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _insert_event_log_parent(mem_conn, e1)
        project_event(mem_conn, e1)
        _insert_event_log_parent(mem_conn, e2)
        project_event(mem_conn, e2)

    rows = mem_conn.execute(
        "SELECT event_id FROM consensus_reports "
        "WHERE project_id = 'demo-project' AND phase = 'design' "
        "ORDER BY event_id"
    ).fetchall()
    assert [r["event_id"] for r in rows] == [1, 2]


# ---------------------------------------------------------------------------
# FK + ON DELETE CASCADE (#754 contract inherited at Site 2)
# ---------------------------------------------------------------------------


def test_consensus_reports_cascades_on_event_log_delete(mem_conn) -> None:
    """Pruning event_log MUST cascade to consensus_reports via FK ON DELETE
    CASCADE — otherwise retention workflows leak orphan projection rows."""
    mem_conn.execute(
        "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, "
        "projection_status, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
        (777, "wicked.consensus.report_created", "p.d.consensus.x", "{}",
         "applied", 1_700_000_777),
    )
    mem_conn.execute(
        "INSERT INTO consensus_reports "
        "(event_id, project_id, phase, decision, confidence, agreement_ratio, "
        "participants, rounds, created_at, raw_payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (777, "p", "design", "APPROVE", 0.9, 0.9, 3, 1, 1_700_000_777, "{}"),
    )
    mem_conn.commit()

    assert mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_reports WHERE event_id = 777"
    ).fetchone()[0] == 1

    mem_conn.execute("DELETE FROM event_log WHERE event_id = 777")
    mem_conn.commit()

    assert mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_reports WHERE event_id = 777"
    ).fetchone()[0] == 0, (
        "FK ON DELETE CASCADE failed for consensus_reports — event_log prune "
        "is leaking orphan projection rows."
    )


def test_consensus_evidence_cascades_on_event_log_delete(mem_conn) -> None:
    """Same cascade contract for consensus_evidence."""
    mem_conn.execute(
        "INSERT INTO event_log (event_id, event_type, chain_id, payload_json, "
        "projection_status, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
        (888, "wicked.consensus.evidence_recorded", "p.d.consensus.x.evidence",
         "{}", "applied", 1_700_000_888),
    )
    mem_conn.execute(
        "INSERT INTO consensus_evidence "
        "(event_id, project_id, phase, result, reason, consensus_confidence, "
        "agreement_ratio, participants, created_at, raw_payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (888, "p", "design", "REJECT", "dissent", 0.4, 0.4, 5,
         1_700_000_888, "{}"),
    )
    mem_conn.commit()

    mem_conn.execute("DELETE FROM event_log WHERE event_id = 888")
    mem_conn.commit()

    assert mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_evidence WHERE event_id = 888"
    ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Site 2 disk projection — added by PR #798 (legacy direct-write deletion)
# ---------------------------------------------------------------------------
#
# Background: prior to PR #798, `consensus_gate._write_consensus_report` and
# `_write_consensus_evidence` wrote the JSON files directly.  The projector
# handlers above only populated the SQL projection tables.  PR #798 deleted
# the legacy direct-writes — the projector handlers are now the canonical
# disk writers via `_consensus_disk_write()`.
#
# These tests assert the new disk-projection behaviour: file materialised on
# flag-on, content-hash idempotency on replay, fail-open on missing project
# row, fail-open isolation between SQL projection and disk side-effect.


def _setup_project_in_db_for_disk(
    conn, project_id: str, project_dir
) -> None:
    """Add the project row required for daemon/projector disk-write path."""
    from pathlib import Path  # noqa: PLC0415 — keep test imports local
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(Path(project_dir)), "active", "design",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()


def test_report_flag_on_writes_consensus_report_json_to_disk(
    mem_conn, tmp_path,
) -> None:
    """flag-on + valid event → consensus-report.json materialised on disk
    via the projector's `_consensus_disk_write` helper.
    """
    from daemon.projector import _consensus_report_created  # noqa: PLC0415

    project_id = "disk-write-proj"
    project_dir = tmp_path / project_id
    _setup_project_in_db_for_disk(mem_conn, project_id, project_dir)

    raw = json.dumps({
        "phase": "design",
        "decision": "APPROVE",
        "confidence": 0.9,
        "agreement_ratio": 0.9,
        "participants": 3,
        "rounds": 1,
        "consensus_points": [],
        "dissenting_views": [],
        "open_questions": [],
    }, indent=2)

    event = _make_report_event(
        event_id=42, project_id=project_id, raw_payload=raw,
    )
    _insert_event_log_parent(mem_conn, event)

    target = project_dir / "phases" / "design" / "consensus-report.json"
    assert not target.exists()  # baseline

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _consensus_report_created(mem_conn, event)

    assert target.exists(), (
        "PR #798 contract: projector handler must materialise "
        "consensus-report.json from raw_payload"
    )
    on_disk = target.read_text(encoding="utf-8")
    assert on_disk == raw, (
        "C11 byte-identity contract: projector writes raw_payload verbatim"
    )


def test_evidence_flag_on_writes_consensus_evidence_json_to_disk(
    mem_conn, tmp_path,
) -> None:
    """flag-on + valid event → consensus-evidence.json materialised on disk."""
    from daemon.projector import _consensus_evidence_recorded  # noqa: PLC0415

    project_id = "disk-write-proj-2"
    project_dir = tmp_path / project_id
    _setup_project_in_db_for_disk(mem_conn, project_id, project_dir)

    raw = json.dumps({
        "type": "consensus-rejection",
        "phase": "design",
        "result": "REJECT",
        "reason": "Strong dissent on credential rotation",
        "consensus_confidence": 0.45,
        "agreement_ratio": 0.45,
        "dissenting_views": [],
        "participants": 5,
    }, indent=2)

    event = _make_evidence_event(
        event_id=43, project_id=project_id, raw_payload=raw,
    )
    _insert_event_log_parent(mem_conn, event)

    target = project_dir / "phases" / "design" / "consensus-evidence.json"
    assert not target.exists()

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on"}):
        _consensus_evidence_recorded(mem_conn, event)

    assert target.exists()
    assert target.read_text(encoding="utf-8") == raw


def test_report_replay_skips_disk_rewrite_via_content_hash(
    mem_conn, tmp_path,
) -> None:
    """Replaying the same event twice → file written once, second call is
    a content-hash no-op (mirrors Site 4/5 idempotency semantics).
    """
    from daemon.projector import _consensus_report_created  # noqa: PLC0415

    project_id = "disk-write-proj-3"
    project_dir = tmp_path / project_id
    _setup_project_in_db_for_disk(mem_conn, project_id, project_dir)

    event = _make_report_event(event_id=44, project_id=project_id)
    _insert_event_log_parent(mem_conn, event)

    target = project_dir / "phases" / "design" / "consensus-report.json"

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        _consensus_report_created(mem_conn, event)
        first_mtime_ns = target.stat().st_mtime_ns

        # Replay — second handler call with the same payload.
        _consensus_report_created(mem_conn, event)
        second_mtime_ns = target.stat().st_mtime_ns

    # Content-hash short-circuit means tmp+rename never fires the second
    # time, so mtime must be unchanged.  This is the test that actually
    # exercises the idempotency branch (vs SQL INSERT OR IGNORE which
    # already covers the table-write side).
    assert first_mtime_ns == second_mtime_ns, (
        "content-hash idempotency failed — replay rewrote the file"
    )


def test_report_disk_write_skipped_when_project_row_missing(
    mem_conn, tmp_path,
) -> None:
    """Project absent in DB → SQL projection still applied, disk write
    skipped (logged warning).  Fail-open: handler does not raise.
    """
    from daemon.projector import _consensus_report_created  # noqa: PLC0415

    # Deliberately do NOT call _setup_project_in_db_for_disk — project row
    # is missing.  We expect the SQL projection to land but the disk write
    # to skip with a warning.
    project_id = "no-such-project"
    event = _make_report_event(event_id=45, project_id=project_id)
    _insert_event_log_parent(mem_conn, event)

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        # Must not raise.
        _consensus_report_created(mem_conn, event)

    # SQL projection still landed.
    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_reports WHERE event_id = 45"
    ).fetchone()
    assert rows[0] == 1, (
        "SQL projection must complete even when disk write is skipped"
    )


def test_report_disk_write_failure_does_not_taint_sql_projection(
    mem_conn, tmp_path,
) -> None:
    """A disk-side exception MUST NOT prevent the SQL projection from
    succeeding.  The fail-open envelope around _consensus_disk_write is
    explicit so retention/audit consumers always see the SQL row.
    """
    from daemon import projector as projector_mod  # noqa: PLC0415

    project_id = "disk-write-proj-4"
    project_dir = tmp_path / project_id
    _setup_project_in_db_for_disk(mem_conn, project_id, project_dir)

    event = _make_report_event(event_id=46, project_id=project_id)
    _insert_event_log_parent(mem_conn, event)

    def _boom(*args, **kwargs):
        raise OSError("simulated disk full")

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}):
        with patch.object(
            projector_mod, "_consensus_disk_write", side_effect=_boom,
        ):
            # Must not raise.
            projector_mod._consensus_report_created(mem_conn, event)

    rows = mem_conn.execute(
        "SELECT COUNT(*) FROM consensus_reports WHERE event_id = 46"
    ).fetchone()
    assert rows[0] == 1, (
        "SQL projection must succeed even when disk-side projection raises"
    )
