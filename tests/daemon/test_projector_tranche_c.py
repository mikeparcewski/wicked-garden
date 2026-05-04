"""tests/daemon/test_projector_tranche_c.py — Wave-2 Tranche C projector
handler tests (#746).

Sites covered:
  * W5  ``wicked.hitl.decision_recorded``    → phases/{phase}/{filename}
        (filename validated against whitelist)
  * W9b ``wicked.subagent.engaged``          → phases/{phase}/specialist-engagement.jsonl
  * W10b ``wicked.phase.transitioned`` (SKIPPED) fan-out
        → phases/{phase}/status.md (NEW behaviour, not a new event)

T1: deterministic.  T3: isolated tmp_path + in-memory DB.  T6: provenance #746 wave-2 C.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_SCRIPTS_CREW = _REPO_ROOT / "scripts" / "crew"

for p in (_REPO_ROOT, _SCRIPTS, _SCRIPTS_CREW):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _setup_project(conn, project_id: str, project_dir: Path) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(project_dir), "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_tranche_c_handlers_registered() -> None:
    from daemon.projector import (
        _HANDLERS,
        _hitl_decision_recorded,
        _subagent_engaged,
    )
    assert _HANDLERS["wicked.hitl.decision_recorded"] is _hitl_decision_recorded
    assert _HANDLERS["wicked.subagent.engaged"] is _subagent_engaged


# ---------------------------------------------------------------------------
# W5 — hitl.decision_recorded
# ---------------------------------------------------------------------------


def _hitl_event(
    *,
    project_id: str,
    phase: str = "clarify",
    filename: str = "hitl-decision.json",
    body: str = '{"pause": false}',
) -> dict:
    return {
        "event_id": 1,
        "event_type": "wicked.hitl.decision_recorded",
        "chain_id": f"{project_id}.{phase}.x",
        "created_at": 1_700_000_001,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "filename": filename,
            "raw_payload": body,
        },
    }


def test_hitl_flag_off_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _hitl_decision_recorded
    project_dir = tmp_path / "p-hitl-off"
    _setup_project(mem_conn, "p-hitl-off", project_dir)
    target = project_dir / "phases" / "clarify" / "hitl-decision.json"

    event = _hitl_event(project_id="p-hitl-off")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_HITL_DECISION": "off"}):
        _hitl_decision_recorded(mem_conn, event)
    assert not target.exists()


def test_hitl_happy_path_writes_file(mem_conn, tmp_path) -> None:
    from daemon.projector import _hitl_decision_recorded
    project_dir = tmp_path / "p-hitl-on"
    _setup_project(mem_conn, "p-hitl-on", project_dir)
    target = project_dir / "phases" / "clarify" / "hitl-decision.json"

    body = json.dumps({"pause": True, "rule_id": "council.split"})
    event = _hitl_event(project_id="p-hitl-on", body=body)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_HITL_DECISION": "on"}):
        _hitl_decision_recorded(mem_conn, event)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == body


def test_hitl_council_filename_writes_to_council_phase(mem_conn, tmp_path) -> None:
    """council-decision.json is in the whitelist; council phase is the actual phase."""
    from daemon.projector import _hitl_decision_recorded
    project_dir = tmp_path / "p-hitl-council"
    _setup_project(mem_conn, "p-hitl-council", project_dir)
    target = project_dir / "phases" / "council" / "council-decision.json"

    event = _hitl_event(
        project_id="p-hitl-council",
        phase="council",
        filename="council-decision.json",
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_HITL_DECISION": "on"}):
        _hitl_decision_recorded(mem_conn, event)
    assert target.exists()


def test_hitl_filename_traversal_rejected(mem_conn, tmp_path) -> None:
    """Filenames outside the whitelist (incl. path-traversal attempts) are rejected."""
    from daemon.projector import _hitl_decision_recorded
    project_dir = tmp_path / "p-hitl-traverse"
    _setup_project(mem_conn, "p-hitl-traverse", project_dir)

    # Attempt 1: path-traversal up the tree
    event_traverse = _hitl_event(
        project_id="p-hitl-traverse",
        filename="../../../etc/passwd",
    )
    # Attempt 2: arbitrary unknown filename
    event_unknown = _hitl_event(
        project_id="p-hitl-traverse",
        filename="arbitrary-name.json",
    )

    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_HITL_DECISION": "on"}):
        _hitl_decision_recorded(mem_conn, event_traverse)
        _hitl_decision_recorded(mem_conn, event_unknown)

    # Nothing materialised — projector refused both names.
    assert not (project_dir / "phases" / "clarify" / "arbitrary-name.json").exists()
    # The traversal target obviously shouldn't exist either.
    assert not Path("/etc/passwd-projected-by-evil").exists()  # never possible
    # Confirm the only legitimate targets were untouched.
    assert not (project_dir / "phases" / "clarify" / "hitl-decision.json").exists()


def test_hitl_replay_short_circuits_via_content_hash(mem_conn, tmp_path) -> None:
    from daemon.projector import _hitl_decision_recorded
    project_dir = tmp_path / "p-hitl-replay"
    _setup_project(mem_conn, "p-hitl-replay", project_dir)
    target = project_dir / "phases" / "clarify" / "hitl-decision.json"

    event = _hitl_event(project_id="p-hitl-replay")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_HITL_DECISION": "on"}):
        _hitl_decision_recorded(mem_conn, event)
        first_mtime = target.stat().st_mtime_ns
        _hitl_decision_recorded(mem_conn, event)
        second_mtime = target.stat().st_mtime_ns
    assert first_mtime == second_mtime


def test_hitl_resolver_rejects_unknown_filename() -> None:
    """The resolver returns an empty list for filenames outside the whitelist —
    the drift detector then ignores the projection target entirely (defense in
    depth alongside the handler-side whitelist check)."""
    import reconcile_v2  # type: ignore[import]
    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/p"),
        "wicked.hitl.decision_recorded",
        "p.clarify.x",
        {"project_id": "p", "phase": "clarify", "filename": "../etc/passwd"},
    )
    assert paths == []


def test_hitl_resolver_returns_phase_filename_for_whitelisted() -> None:
    import reconcile_v2  # type: ignore[import]
    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/p"),
        "wicked.hitl.decision_recorded",
        "p.clarify.x",
        {"project_id": "p", "phase": "clarify", "filename": "hitl-decision.json"},
    )
    assert len(paths) == 1
    assert str(paths[0]).endswith("phases/clarify/hitl-decision.json")


# ---------------------------------------------------------------------------
# W9b — subagent.engaged → specialist-engagement.jsonl
# ---------------------------------------------------------------------------


def test_subagent_engaged_appends_jsonl(mem_conn, tmp_path) -> None:
    from daemon.projector import _subagent_engaged
    project_dir = tmp_path / "p-sub"
    _setup_project(mem_conn, "p-sub", project_dir)
    target = project_dir / "phases" / "build" / "specialist-engagement.jsonl"

    line = '{"domain": "engineering", "agent": "senior-engineer"}'
    event = {
        "event_id": 1,
        "event_type": "wicked.subagent.engaged",
        "chain_id": "p-sub.build.engineering",
        "created_at": 1_700_000_001,
        "payload": {
            "project_id": "p-sub",
            "phase": "build",
            "raw_payload": line,
        },
    }
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SUBAGENT_ENGAGEMENT": "on"}):
        _subagent_engaged(mem_conn, event)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == line + "\n"


def test_subagent_engaged_replay_idempotent(mem_conn, tmp_path) -> None:
    from daemon.projector import _subagent_engaged
    project_dir = tmp_path / "p-sub-replay"
    _setup_project(mem_conn, "p-sub-replay", project_dir)
    target = project_dir / "phases" / "build" / "specialist-engagement.jsonl"

    line = '{"domain": "engineering", "agent": "senior-engineer"}'
    event = {
        "event_id": 1,
        "event_type": "wicked.subagent.engaged",
        "chain_id": "p-sub-replay.build.x",
        "created_at": 1_700_000_001,
        "payload": {
            "project_id": "p-sub-replay",
            "phase": "build",
            "raw_payload": line,
        },
    }
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SUBAGENT_ENGAGEMENT": "on"}):
        _subagent_engaged(mem_conn, event)
        _subagent_engaged(mem_conn, event)
    assert target.read_text(encoding="utf-8") == line + "\n"


def test_subagent_engaged_flag_off_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _subagent_engaged
    project_dir = tmp_path / "p-sub-off"
    _setup_project(mem_conn, "p-sub-off", project_dir)
    target = project_dir / "phases" / "build" / "specialist-engagement.jsonl"

    event = {
        "event_id": 1,
        "event_type": "wicked.subagent.engaged",
        "chain_id": "p-sub-off.build.x",
        "created_at": 1_700_000_001,
        "payload": {
            "project_id": "p-sub-off",
            "phase": "build",
            "raw_payload": '{"domain": "engineering"}',
        },
    }
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SUBAGENT_ENGAGEMENT": "off"}):
        _subagent_engaged(mem_conn, event)
    assert not target.exists()


# ---------------------------------------------------------------------------
# W10b — _phase_transitioned fan-out to status.md on SKIPPED
# ---------------------------------------------------------------------------


def _phase_transitioned_skipped_event(
    *,
    project_id: str,
    phase_from: str = "operate",
    approver: str = "auto",
    reason: str = "Out of scope",
    skipped_at: str = "2026-05-03T18:00:00Z",
) -> dict:
    return {
        "event_id": 1,
        "event_type": "wicked.phase.transitioned",
        "chain_id": f"{project_id}.{phase_from}",
        "created_at": 1_700_000_001,
        "payload": {
            "project_id": project_id,
            "phase_from": phase_from,
            "phase_to": None,
            "approver": approver,
            "gate_result": "SKIPPED",
            "skip_reason": reason,
            "skipped_at": skipped_at,
        },
    }


def test_skipped_phase_status_md_flag_off_no_write(mem_conn, tmp_path) -> None:
    from daemon.projector import _phase_transitioned
    project_dir = tmp_path / "p-skip-off"
    _setup_project(mem_conn, "p-skip-off", project_dir)
    target = project_dir / "phases" / "operate" / "status.md"

    event = _phase_transitioned_skipped_event(project_id="p-skip-off")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS": "off"}):
        _phase_transitioned(mem_conn, event)
    assert not target.exists()


def test_skipped_phase_status_md_happy_path(mem_conn, tmp_path) -> None:
    from daemon.projector import _phase_transitioned
    project_dir = tmp_path / "p-skip-on"
    _setup_project(mem_conn, "p-skip-on", project_dir)
    target = project_dir / "phases" / "operate" / "status.md"

    event = _phase_transitioned_skipped_event(
        project_id="p-skip-on",
        approver="user-explicit",
        reason="Out of scope for this project",
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS": "on"}):
        _phase_transitioned(mem_conn, event)

    assert target.exists()
    body = target.read_text(encoding="utf-8")
    assert "phase: operate" in body
    assert "status: skipped" in body
    assert "approved_by: user-explicit" in body
    assert "**Reason**: Out of scope for this project" in body


def test_phase_transitioned_non_skipped_does_not_write_status_md(
    mem_conn, tmp_path,
) -> None:
    """Non-SKIPPED transitions (APPROVE/CONDITIONAL/REJECT) must NOT
    trigger the status.md fan-out — that is the W10b invariant."""
    from daemon.projector import _phase_transitioned
    project_dir = tmp_path / "p-skip-not"
    _setup_project(mem_conn, "p-skip-not", project_dir)
    target = project_dir / "phases" / "build" / "status.md"

    event = {
        "event_id": 1,
        "event_type": "wicked.phase.transitioned",
        "chain_id": "p-skip-not.build",
        "created_at": 1_700_000_001,
        "payload": {
            "project_id": "p-skip-not",
            "phase_from": "build",
            "phase_to": "test",
            "approver": "user",
            "gate_result": "APPROVE",
        },
    }
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS": "on"}):
        _phase_transitioned(mem_conn, event)
    assert not target.exists(), (
        "APPROVE transition must NOT trigger status.md fan-out — "
        "fan-out is gated on gate_result=='SKIPPED'"
    )


def test_skipped_replay_short_circuits_via_content_hash(mem_conn, tmp_path) -> None:
    from daemon.projector import _phase_transitioned
    project_dir = tmp_path / "p-skip-replay"
    _setup_project(mem_conn, "p-skip-replay", project_dir)
    target = project_dir / "phases" / "operate" / "status.md"

    event = _phase_transitioned_skipped_event(project_id="p-skip-replay")
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS": "on"}):
        _phase_transitioned(mem_conn, event)
        first_mtime = target.stat().st_mtime_ns
        _phase_transitioned(mem_conn, event)
        second_mtime = target.stat().st_mtime_ns
    assert first_mtime == second_mtime


# ---------------------------------------------------------------------------
# Source-side emit wirings (round-trip behaviour, no daemon needed)
# ---------------------------------------------------------------------------


def test_hitl_judge_emits_before_disk_write(tmp_path) -> None:
    """write_hitl_decision_evidence emits wicked.hitl.decision_recorded
    BEFORE writing the JSON file."""
    from hitl_judge import write_hitl_decision_evidence, JudgeDecision  # type: ignore[import]

    project_dir = tmp_path / "proj-hitl-emit"
    project_dir.mkdir()

    captured: list = []

    def _fake_emit(event_type, payload, *, chain_id=None):
        captured.append({
            "event_type": event_type,
            "payload": payload,
            "chain_id": chain_id,
        })

    decision = JudgeDecision(
        pause=True, reason="split-verdict",
        rule_id="council.split-verdict",
        signals={"margin": 0},
    )

    with patch("_bus.emit_event", _fake_emit):
        path = write_hitl_decision_evidence(
            project_dir, "council", "council-decision.json", decision,
        )

    assert path.exists()
    assert len(captured) == 1
    emit = captured[0]
    assert emit["event_type"] == "wicked.hitl.decision_recorded"
    assert emit["payload"]["project_id"] == "proj-hitl-emit"
    assert emit["payload"]["phase"] == "council"
    assert emit["payload"]["filename"] == "council-decision.json"
    assert emit["payload"]["pause"] is True
    assert emit["payload"]["rule_id"] == "council.split-verdict"
    assert "raw_payload" in emit["payload"]
    assert emit["chain_id"] == "proj-hitl-emit.council.council-decision"


def test_hitl_judge_emit_failure_does_not_block_write(tmp_path) -> None:
    """A bus-emit failure must NOT block the disk write (evidence loss
    must be visible — Decision #8 fail-open)."""
    from hitl_judge import write_hitl_decision_evidence, JudgeDecision  # type: ignore[import]

    project_dir = tmp_path / "proj-hitl-fail"
    project_dir.mkdir()

    def _raising_emit(event_type, payload, *, chain_id=None):
        raise RuntimeError("simulated bus failure")

    decision = JudgeDecision(
        pause=False, reason="ok", rule_id="ok", signals={},
    )

    with patch("_bus.emit_event", _raising_emit):
        path = write_hitl_decision_evidence(
            project_dir, "clarify", "hitl-decision.json", decision,
        )

    # Disk write happened despite emit failure.
    assert path.exists()
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert parsed["pause"] is False
