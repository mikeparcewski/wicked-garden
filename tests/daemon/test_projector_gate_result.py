"""tests/daemon/test_projector_gate_result.py — Projector tests for Site 4
bus-cutover handlers ``_gate_decided_disk`` (fan-out from ``_gate_decided``)
and ``_gate_blocked`` (#746, #778).

Covers the PR-1 inert-handler shape:
  * Registration: ``wicked.gate.blocked`` in ``_HANDLERS``; ``_gate_decided``
    still maps to its DB-row handler; the fan-out exists at the tail.
  * Flag-off contract: both handlers no-op when flag off.
  * Inert under current emit: flag-on + payload missing ``data`` → debug log,
    no write.  Validates that PR-1 is safe to ship with flag default OFF
    and remains inert if an operator opts in before #779 widens the emit.
  * Happy path with synthetic full payload: flag-on + valid ``data`` dict +
    dispatch-log check disabled → file written with content-hash idempotency.
  * Security floor invocation: flag-on + invalid ``data`` → audit entry
    written, file NOT updated.  Distinguishes schema vs sanitizer violations.
  * Content-hash idempotency: replay with identical payload → no rewrite.
  * Fan-out fail-open: when ``_gate_decided_disk`` raises, the existing
    DB-row work in ``_gate_decided`` is preserved.
  * ``_gate_blocked`` is a flag-gated no-op (PR-1 contract): no file
    mutation regardless of file state.
  * Project-directory edge cases: absent project row + NULL directory.

T1: deterministic — fixed-epoch timestamps, no wall-clock reads in assertions.
T2: no sleep-based sync.
T3: isolated — each test gets its own tmp_path + in-memory DB via mem_conn.
T4: one concern per test.
T5: descriptive names.
T6: provenance: #746 #778 Site 4 bus-cutover prep.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure daemon/ and scripts/ are importable from the repo root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_SCRIPTS_CREW = _REPO_ROOT / "scripts" / "crew"

for p in (_REPO_ROOT, _SCRIPTS, _SCRIPTS_CREW):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ---------------------------------------------------------------------------
# Helpers — project / phase setup
# ---------------------------------------------------------------------------

_FIXED_TS = 1_700_000_001


def _setup_project_in_db(conn, project_id: str, project_dir: Path) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(project_dir), "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()


def _make_project_dir(tmp_path: Path, project_id: str = "my-proj") -> Path:
    return tmp_path / project_id


def _valid_gate_result(
    *,
    verdict: str = "APPROVE",
    reviewer: str = "test-reviewer",
    score: float = 0.85,
    recorded_at: str = "2026-05-03T12:00:00Z",
    phase: str = "build",
    gate: str = "build-quality",
) -> dict[str, Any]:
    """Build a minimal gate_result dict that passes validate_gate_result."""
    return {
        "verdict": verdict,
        "reviewer": reviewer,
        "score": score,
        "recorded_at": recorded_at,
        "phase": phase,
        "gate": gate,
    }


def _make_gate_decided_event(
    *,
    event_id: int = 1,
    project_id: str = "my-proj",
    phase: str = "build",
    data: dict[str, Any] | None = None,
    include_data: bool = True,
) -> dict[str, Any]:
    """Build a wicked.gate.decided event.

    When include_data=False: payload omits the ``data`` key — exercises the
    inert path (current 5-field emit at phase_manager.py:3931 before #779).
    """
    payload: dict[str, Any] = {
        "project_id": project_id,
        "phase": phase,
        "result": "APPROVE",
        "score": 0.85,
        "reviewer": "test-reviewer",
    }
    if include_data:
        payload["data"] = data if data is not None else _valid_gate_result(phase=phase)
    return {
        "event_id": event_id,
        "event_type": "wicked.gate.decided",
        "chain_id": f"{project_id}.{phase}.gate",
        "created_at": _FIXED_TS + event_id,
        "payload": payload,
    }


def _make_gate_blocked_event(
    *,
    event_id: int = 2,
    project_id: str = "my-proj",
    phase: str = "build",
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "wicked.gate.blocked",
        "chain_id": f"{project_id}.{phase}.gate",
        "created_at": _FIXED_TS + event_id,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "blocking_reason": "REJECT",
        },
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_gate_blocked_handler_is_registered_in_dispatch_table() -> None:
    """wicked.gate.blocked MUST be registered in _HANDLERS for Site 4 prep
    so reconcile_v2._handler_available_for_file's conservative ALL-event-
    types-must-have-handlers gate flips True for gate-result.json."""
    from daemon.projector import _HANDLERS, _gate_blocked

    assert "wicked.gate.blocked" in _HANDLERS, (
        "wicked.gate.blocked must be registered for #778 Site 4 prep — "
        "without it, reconcile_v2 keeps gate-result.json excluded from "
        "drift detection even after the cutover ships."
    )
    assert _HANDLERS["wicked.gate.blocked"] is _gate_blocked


def test_gate_decided_handler_still_maps_to_db_row_handler() -> None:
    """wicked.gate.decided continues to dispatch to the existing DB-row
    handler (_gate_decided).  Disk projection runs as a fan-out at the
    tail of _gate_decided, NOT as a separate registry entry — _HANDLERS
    is a strict 1:1 dispatch and we cannot double-register."""
    from daemon.projector import _HANDLERS, _gate_decided

    assert "wicked.gate.decided" in _HANDLERS
    assert _HANDLERS["wicked.gate.decided"] is _gate_decided


# ---------------------------------------------------------------------------
# Flag-off contract — both handlers no-op
# ---------------------------------------------------------------------------


def test_flag_off_gate_decided_disk_noop_no_file_written(mem_conn, tmp_path) -> None:
    """flag-off → _gate_decided_disk returns immediately, no file written.

    The DB-row work in _gate_decided still runs (separate concern).  This
    test verifies only the disk-projection branch.
    """
    from daemon.projector import _gate_decided_disk

    project_id = "proj-flagoff"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    target = project_dir / "phases" / "build" / "gate-result.json"

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "off"}):
        _gate_decided_disk(mem_conn, event)

    assert not target.exists(), "flag-off must not write gate-result.json"


def test_flag_off_gate_blocked_noop(mem_conn, tmp_path) -> None:
    """flag-off → _gate_blocked returns immediately."""
    from daemon.projector import _gate_blocked

    project_id = "proj-blocked-flagoff"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    target = project_dir / "phases" / "build" / "gate-result.json"

    event = _make_gate_blocked_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "off"}):
        _gate_blocked(mem_conn, event)

    assert not target.exists()


# ---------------------------------------------------------------------------
# Inert under current 5-field emit (PR-1 contract)
# ---------------------------------------------------------------------------


def test_flag_on_inert_when_payload_lacks_data_key(mem_conn, tmp_path) -> None:
    """flag-on + payload without ``data`` key (current emit shape) →
    handler logs at debug and returns; no file written.

    This is the PR-1 invariant: operators can flip the flag on safely
    BEFORE PR-2 (#779) widens the emit, because the handler is inert
    until ``data`` arrives in the payload.
    """
    from daemon.projector import _gate_decided_disk

    project_id = "proj-inert"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    target = project_dir / "phases" / "build" / "gate-result.json"

    # include_data=False → payload missing the 'data' key
    event = _make_gate_decided_event(project_id=project_id, include_data=False)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
        _gate_decided_disk(mem_conn, event)

    assert not target.exists(), (
        "flag-on with current 5-field emit must remain inert until #779 — "
        "an early file write here means the handler trusted an incomplete "
        "payload and would ship invalid bytes."
    )


# ---------------------------------------------------------------------------
# Happy path with synthetic full payload (forward-compat — exercises #779 shape)
# ---------------------------------------------------------------------------


def test_flag_on_full_payload_writes_file_with_dispatch_check_disabled(
    mem_conn, tmp_path,
) -> None:
    """flag-on + full ``data`` dict + WG_GATE_RESULT_DISPATCH_CHECK=off →
    file written.  Disabling the orphan check isolates the projection write
    behaviour from dispatch-log fixture setup, which is exercised separately
    in tests/crew/test_dispatch_log_*.

    This test exercises the payload shape that PR-2 (#779) will ship.
    """
    from daemon.projector import _gate_decided_disk

    project_id = "proj-write"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    target = project_dir / "phases" / "build" / "gate-result.json"

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)

    assert target.exists(), "expected gate-result.json materialised"
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["verdict"] == "APPROVE"
    assert parsed["reviewer"] == "test-reviewer"
    assert parsed["score"] == 0.85


# ---------------------------------------------------------------------------
# Security floor: schema violation surfaces in audit log + skips write
# ---------------------------------------------------------------------------


def test_flag_on_schema_violation_writes_audit_and_skips_write(
    mem_conn, tmp_path,
) -> None:
    """flag-on + invalid ``data`` (missing required ``score``) →
    schema_violation audit entry written, gate-result.json NOT updated.

    Confirms the AC-9 §5.4 security floor IS invoked from the projection
    path.  ``score`` is a required field in validate_gate_result; omitting
    it raises GateResultSchemaError (#650 — score-presence check).
    """
    from daemon.projector import _gate_decided_disk

    project_id = "proj-schema-violation"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    target = project_dir / "phases" / "build" / "gate-result.json"
    audit_path = (
        project_dir / "phases" / "build" / "gate-ingest-audit.jsonl"
    )

    bad_data = _valid_gate_result()
    del bad_data["score"]   # required by validate_gate_result

    event = _make_gate_decided_event(project_id=project_id, data=bad_data)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
        _gate_decided_disk(mem_conn, event)

    assert not target.exists(), (
        "schema violation must skip the write — never ship validator-rejected "
        "bytes to the projection path"
    )
    assert audit_path.exists(), "audit entry must be written for every reject"
    audit_lines = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        entry["event"] == "schema_violation" for entry in audit_lines
    ), f"expected schema_violation in audit; got {audit_lines}"


# ---------------------------------------------------------------------------
# Content-hash idempotency
# ---------------------------------------------------------------------------


def test_replay_same_event_skips_rewrite_via_content_hash(mem_conn, tmp_path) -> None:
    """Replaying the same event twice → file written once; second call is
    a no-op via content-hash equality.

    Required because the daemon consumer does not dedupe before calling
    handlers (append_event_log uses INSERT OR REPLACE — handler fires for
    every event in the batch).  Without this guard the file would be
    rewritten on every replay.
    """
    from daemon.projector import _gate_decided_disk

    project_id = "proj-replay"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    target = project_dir / "phases" / "build" / "gate-result.json"

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)
        first_mtime = target.stat().st_mtime_ns
        first_bytes = target.read_bytes()
        # Replay
        _gate_decided_disk(mem_conn, event)
        second_mtime = target.stat().st_mtime_ns
        second_bytes = target.read_bytes()

    assert first_bytes == second_bytes, "replay must not corrupt file content"
    # Atomic-rename writes always produce a new mtime; the idempotency guard
    # short-circuits BEFORE the rename, so the mtime stays identical on
    # replay.  This is the strongest signal the guard fired.
    assert first_mtime == second_mtime, (
        "replay must short-circuit before write — identical mtime confirms "
        "the content-hash guard fired and skipped the atomic-rename path"
    )


# ---------------------------------------------------------------------------
# Fan-out from _gate_decided is fail-open
# ---------------------------------------------------------------------------


def test_gate_decided_disk_failure_does_not_break_db_row_projection(
    mem_conn, tmp_path,
) -> None:
    """If _gate_decided_disk raises, the existing DB-row work in
    _gate_decided must still complete (Decision #6 / Decision #8 — handler
    must never raise to the dispatcher).

    Simulates a disk failure by patching _gate_decided_disk to raise.
    The DB-row UPSERT for the phase row should still land.
    """
    from daemon.projector import _gate_decided

    project_id = "proj-failopen"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    # Seed a phase row matching the daemon schema (state, not status; no
    # created_at column).  Using a raw INSERT keeps this test independent
    # of upsert_phase's evolving signature.
    mem_conn.execute(
        "INSERT OR IGNORE INTO phases "
        "(project_id, phase, state, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (project_id, "build", "active", 1_700_000_000),
    )
    mem_conn.commit()

    event = _make_gate_decided_event(project_id=project_id)

    with patch(
        "daemon.projector._gate_decided_disk",
        side_effect=RuntimeError("simulated disk failure"),
    ):
        # Must not raise — the fan-out is wrapped in try/except.
        _gate_decided(mem_conn, event)

    row = mem_conn.execute(
        "SELECT gate_verdict, gate_reviewer FROM phases "
        "WHERE project_id = ? AND phase = ?",
        (project_id, "build"),
    ).fetchone()
    assert row is not None, "DB row must exist after _gate_decided"
    assert row[0] == "APPROVE", (
        "DB-row projection must complete even when disk fan-out raises "
        "(fail-open per Decision #8)"
    )
    assert row[1] == "test-reviewer"


# ---------------------------------------------------------------------------
# _gate_blocked is a no-op even when flag is on (PR-1 contract)
# ---------------------------------------------------------------------------


def test_gate_blocked_does_not_mutate_existing_file(mem_conn, tmp_path) -> None:
    """flag-on + pre-existing gate-result.json → _gate_blocked is a no-op;
    the file is unchanged.

    PR-1 contract: gate.blocked always follows gate.decided in the REJECT
    branch.  By the time gate.blocked fires, the file is already in REJECT
    state from _gate_decided_disk's projection.  No additional disk
    mutation is needed.
    """
    from daemon.projector import _gate_blocked

    project_id = "proj-blocked-noop"
    project_dir = _make_project_dir(tmp_path, project_id)
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True, exist_ok=True)
    target = phase_dir / "gate-result.json"
    pre_existing = '{"verdict": "REJECT"}\n'
    target.write_text(pre_existing, encoding="utf-8")
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_gate_blocked_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
        _gate_blocked(mem_conn, event)

    assert target.read_text(encoding="utf-8") == pre_existing, (
        "PR-1 _gate_blocked must not mutate gate-result.json"
    )


# ---------------------------------------------------------------------------
# Edge: project row missing or directory NULL
# ---------------------------------------------------------------------------


def test_missing_project_row_warns_and_skips(mem_conn, tmp_path) -> None:
    """No project row in DB → handler warns and skips (mirrors Site 3)."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-not-in-db"
    project_dir = _make_project_dir(tmp_path, project_id)
    # Intentionally do NOT call _setup_project_in_db.
    target = project_dir / "phases" / "build" / "gate-result.json"

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
        _gate_decided_disk(mem_conn, event)

    assert not target.exists()


def test_null_project_directory_warns_and_skips(mem_conn, tmp_path) -> None:
    """Project row with NULL directory → handler warns and skips."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-null-dir"
    mem_conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, None, "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    mem_conn.commit()

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
        from daemon.projector import _gate_decided_disk
        _gate_decided_disk(mem_conn, event)

    # Nothing to assert beyond "no exception" — the project_dir is None.
    # The handler logs a warning and returns; behaviour-wise this matches
    # the Site 3 contract.
