"""tests/daemon/test_projector_conditions_manifest.py — Site 5 bus-cutover
projector tests for ``conditions-manifest.json`` (#746).

Covers:
  * ``_conditions_manifest_from_gate_decided`` fan-out from
    ``_gate_decided_disk``: flag off → no write; non-CONDITIONAL verdicts
    → no write; CONDITIONAL with empty conditions → no write;
    CONDITIONAL with conditions → manifest materialised; content-hash
    idempotency on replay.
  * Fan-out fail-open: a manifest-write failure does NOT taint the
    gate-result.json projection that ran successfully before it.
  * ``_condition_marked_cleared`` handler: flag off; missing payload
    fields; absent manifest; condition not in manifest; idempotent
    skip when already cleared with matching resolution; happy path
    (sidecar written + manifest flipped to verified=True).
  * Resolver-driven projection paths: ``_materialize_projection_paths``
    correctly returns gate-result + manifest for CONDITIONAL gate.decided
    events and only gate-result for APPROVE/REJECT.

T1: deterministic — fixed-epoch timestamps; no wall-clock-dependent assertions.
T2: no sleep-based sync.
T3: isolated — each test gets its own tmp_path + in-memory DB.
T4: one concern per test.
T5: descriptive names.
T6: provenance: #746 Site 5 cutover.
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
# Helpers
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


def _conditional_gate_data(
    *,
    verdict: str = "CONDITIONAL",
    conditions: "list[dict] | None" = None,
    reviewer: str = "test-reviewer",
    score: float = 0.55,
    recorded_at: str = "2026-05-03T12:00:00Z",
    phase: str = "build",
    gate: str = "build-quality",
) -> dict:
    """Build a gate_result dict with conditions for the CONDITIONAL branch."""
    if conditions is None:
        conditions = [
            {"description": "Add unit tests for module X"},
            {"description": "Document the new public API"},
        ]
    return {
        "verdict": verdict,
        "result": verdict,
        "reviewer": reviewer,
        "score": score,
        "recorded_at": recorded_at,
        "phase": phase,
        "gate": gate,
        "conditions": conditions,
    }


def _make_gate_decided_event(
    *,
    event_id: int = 1,
    project_id: str = "my-proj",
    phase: str = "build",
    data: "dict | None" = None,
) -> dict:
    payload: dict = {
        "project_id": project_id,
        "phase": phase,
        "result": (data or {}).get("result", "CONDITIONAL"),
        "score": (data or {}).get("score", 0.55),
        "reviewer": (data or {}).get("reviewer", "test-reviewer"),
    }
    if data is not None:
        payload["data"] = data
    else:
        payload["data"] = _conditional_gate_data(phase=phase)
    return {
        "event_id": event_id,
        "event_type": "wicked.gate.decided",
        "chain_id": f"{project_id}.{phase}.gate",
        "created_at": _FIXED_TS + event_id,
        "payload": payload,
    }


def _make_marked_cleared_event(
    *,
    event_id: int = 1,
    project_id: str = "my-proj",
    phase: str = "build",
    condition_id: str = "CONDITION-1",
    resolution_ref: str = "commits/abc123",
    note: "str | None" = "fixed in PR #999",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": "wicked.condition.marked_cleared",
        "chain_id": f"{project_id}.{phase}.{condition_id}",
        "created_at": _FIXED_TS + event_id,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "condition_id": condition_id,
            "resolution_ref": resolution_ref,
            "note": note,
            "verified_at": "2026-05-03T13:00:00Z",
        },
    }


# ---------------------------------------------------------------------------
# _PROJECTION_RESOLVERS — payload-aware projection-path resolution
# ---------------------------------------------------------------------------


def test_resolver_gate_decided_approve_returns_only_gate_result() -> None:
    """APPROVE verdict → conditions-manifest.json must NOT be expected."""
    import reconcile_v2  # type: ignore[import]

    payload = {"data": {"result": "APPROVE", "conditions": []}}
    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"), "wicked.gate.decided", "proj.build.gate", payload,
    )
    names = {p.name for p in paths}
    assert names == {"gate-result.json"}, (
        "APPROVE verdict must not require conditions-manifest.json — "
        f"resolver returned: {names}"
    )


def test_resolver_gate_decided_reject_returns_only_gate_result() -> None:
    """REJECT verdict → conditions-manifest.json must NOT be expected."""
    import reconcile_v2  # type: ignore[import]

    payload = {"data": {"result": "REJECT", "conditions": []}}
    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"), "wicked.gate.decided", "proj.build.gate", payload,
    )
    names = {p.name for p in paths}
    assert names == {"gate-result.json"}


def test_resolver_gate_decided_conditional_with_conditions_returns_both() -> None:
    """CONDITIONAL + non-empty conditions → both files expected."""
    import reconcile_v2  # type: ignore[import]

    payload = {
        "data": {
            "result": "CONDITIONAL",
            "conditions": [{"description": "fix X"}],
        },
    }
    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"), "wicked.gate.decided", "proj.build.gate", payload,
    )
    names = {p.name for p in paths}
    assert names == {"gate-result.json", "conditions-manifest.json"}


def test_resolver_gate_decided_conditional_empty_conditions_returns_only_gate_result() -> None:
    """CONDITIONAL but empty conditions list → only gate-result expected.

    Degenerate case — the projector wouldn't write a manifest with no
    conditions, so it's not a tracked projection.
    """
    import reconcile_v2  # type: ignore[import]

    payload = {"data": {"result": "CONDITIONAL", "conditions": []}}
    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"), "wicked.gate.decided", "proj.build.gate", payload,
    )
    names = {p.name for p in paths}
    assert names == {"gate-result.json"}


def test_resolver_gate_decided_no_payload_returns_only_gate_result() -> None:
    """Legacy / payload-less call → only the always-produced file."""
    import reconcile_v2  # type: ignore[import]

    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"), "wicked.gate.decided", "proj.build.gate", None,
    )
    names = {p.name for p in paths}
    assert names == {"gate-result.json"}


def test_resolver_marked_cleared_returns_conditions_manifest() -> None:
    """wicked.condition.marked_cleared maps to conditions-manifest.json."""
    import reconcile_v2  # type: ignore[import]

    paths = reconcile_v2._materialize_projection_paths(
        Path("/tmp/proj"),
        "wicked.condition.marked_cleared",
        "proj.build.CONDITION-1",
        {"project_id": "proj", "phase": "build", "condition_id": "CONDITION-1"},
    )
    names = {p.name for p in paths}
    assert names == {"conditions-manifest.json"}


# ---------------------------------------------------------------------------
# _conditions_manifest_from_gate_decided fan-out
# ---------------------------------------------------------------------------


def test_flag_off_conditions_manifest_not_written(mem_conn, tmp_path) -> None:
    """flag-off → no conditions-manifest.json produced even on CONDITIONAL."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-cm-flagoff"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    manifest_target = (
        project_dir / "phases" / "build" / "conditions-manifest.json"
    )

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "off",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)

    assert not manifest_target.exists(), (
        "CONDITIONS_MANIFEST flag off must suppress manifest projection "
        "even when GATE_RESULT is on"
    )


def test_flag_on_approve_verdict_no_manifest_written(mem_conn, tmp_path) -> None:
    """APPROVE verdict → no manifest write regardless of flag state."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-cm-approve"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    manifest_target = (
        project_dir / "phases" / "build" / "conditions-manifest.json"
    )

    approve_data = _conditional_gate_data(verdict="APPROVE", conditions=[])
    event = _make_gate_decided_event(project_id=project_id, data=approve_data)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)

    assert not manifest_target.exists()


def test_flag_on_conditional_empty_conditions_no_manifest(mem_conn, tmp_path) -> None:
    """CONDITIONAL but empty conditions list → no manifest (degenerate case)."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-cm-empty"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    manifest_target = (
        project_dir / "phases" / "build" / "conditions-manifest.json"
    )

    cond_data = _conditional_gate_data(verdict="CONDITIONAL", conditions=[])
    event = _make_gate_decided_event(project_id=project_id, data=cond_data)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)

    assert not manifest_target.exists()


def test_flag_on_conditional_with_conditions_writes_manifest(mem_conn, tmp_path) -> None:
    """Happy path: CONDITIONAL + conditions → manifest written with correct shape."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-cm-happy"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    manifest_target = (
        project_dir / "phases" / "build" / "conditions-manifest.json"
    )

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)

    assert manifest_target.exists(), "CONDITIONAL with conditions must write manifest"
    parsed = json.loads(manifest_target.read_text(encoding="utf-8"))
    assert parsed["source_gate"] == "build"
    assert len(parsed["conditions"]) == 2
    assert parsed["conditions"][0]["id"] == "CONDITION-1"
    assert parsed["conditions"][0]["verified"] is False
    assert parsed["conditions"][0]["description"] == "Add unit tests for module X"
    assert parsed["conditions"][1]["id"] == "CONDITION-2"


def test_conditions_manifest_idempotent_on_replay(mem_conn, tmp_path) -> None:
    """Replay same event → mtime + bytes unchanged (content-hash short-circuit)."""
    from daemon.projector import _gate_decided_disk

    project_id = "proj-cm-replay"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)
    manifest_target = (
        project_dir / "phases" / "build" / "conditions-manifest.json"
    )

    event = _make_gate_decided_event(project_id=project_id)
    with patch.dict(os.environ, {
        "WG_BUS_AS_TRUTH_GATE_RESULT": "on",
        "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on",
        "WG_GATE_RESULT_DISPATCH_CHECK": "off",
    }):
        _gate_decided_disk(mem_conn, event)
        first_mtime = manifest_target.stat().st_mtime_ns
        first_bytes = manifest_target.read_bytes()
        _gate_decided_disk(mem_conn, event)
        second_mtime = manifest_target.stat().st_mtime_ns
        second_bytes = manifest_target.read_bytes()

    assert first_bytes == second_bytes
    assert first_mtime == second_mtime, (
        "replay must short-circuit before write — identical mtime confirms "
        "the content-hash guard fired"
    )


# ---------------------------------------------------------------------------
# _condition_marked_cleared handler
# ---------------------------------------------------------------------------


def test_marked_cleared_handler_is_registered() -> None:
    """wicked.condition.marked_cleared MUST be in _HANDLERS for Site 5."""
    from daemon.projector import _HANDLERS, _condition_marked_cleared

    assert "wicked.condition.marked_cleared" in _HANDLERS
    assert _HANDLERS["wicked.condition.marked_cleared"] is _condition_marked_cleared


def test_marked_cleared_flag_off_noop(mem_conn, tmp_path) -> None:
    """flag-off → handler returns immediately."""
    from daemon.projector import _condition_marked_cleared

    project_id = "proj-mc-flagoff"
    project_dir = _make_project_dir(tmp_path, project_id)
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    manifest_path.write_text(json.dumps({
        "source_gate": "build",
        "conditions": [
            {"id": "CONDITION-1", "verified": False, "resolution": None,
             "verified_at": None, "description": "x"},
        ],
    }))
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_marked_cleared_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "off"}):
        _condition_marked_cleared(mem_conn, event)

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["conditions"][0]["verified"] is False, (
        "flag-off handler must not mutate the manifest"
    )


def test_marked_cleared_absent_manifest_noop(mem_conn, tmp_path) -> None:
    """No manifest on disk → handler logs at debug and returns (gate.decided
    materialisation likely pending; replay catches up)."""
    from daemon.projector import _condition_marked_cleared

    project_id = "proj-mc-noman"
    project_dir = _make_project_dir(tmp_path, project_id)
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_marked_cleared_event(project_id=project_id)
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on"}):
        _condition_marked_cleared(mem_conn, event)

    manifest_path = (
        project_dir / "phases" / "build" / "conditions-manifest.json"
    )
    assert not manifest_path.exists()


def test_marked_cleared_unknown_condition_id_noop(mem_conn, tmp_path) -> None:
    """Manifest exists but the condition_id isn't in it → warn + skip."""
    from daemon.projector import _condition_marked_cleared

    project_id = "proj-mc-unknown"
    project_dir = _make_project_dir(tmp_path, project_id)
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    original_manifest = {
        "source_gate": "build",
        "conditions": [
            {"id": "CONDITION-1", "verified": False, "resolution": None,
             "verified_at": None, "description": "x"},
        ],
    }
    manifest_path.write_text(json.dumps(original_manifest))
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_marked_cleared_event(
        project_id=project_id, condition_id="CONDITION-99",
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on"}):
        _condition_marked_cleared(mem_conn, event)

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed == original_manifest, "unknown condition_id must not mutate manifest"


def test_marked_cleared_happy_path_writes_sidecar_and_flips_manifest(
    mem_conn, tmp_path,
) -> None:
    """Happy path: sidecar written, manifest flipped to verified=True."""
    from daemon.projector import _condition_marked_cleared

    project_id = "proj-mc-happy"
    project_dir = _make_project_dir(tmp_path, project_id)
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    manifest_path.write_text(json.dumps({
        "source_gate": "build",
        "conditions": [
            {"id": "CONDITION-1", "verified": False, "resolution": None,
             "verified_at": None, "description": "x"},
        ],
    }))
    _setup_project_in_db(mem_conn, project_id, project_dir)

    event = _make_marked_cleared_event(
        project_id=project_id,
        resolution_ref="commits/abc123",
        note="fix",
    )
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on"}):
        _condition_marked_cleared(mem_conn, event)

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["conditions"][0]["verified"] is True
    assert parsed["conditions"][0]["resolution"] == "commits/abc123"
    assert parsed["conditions"][0]["verified_at"] == "2026-05-03T13:00:00Z"
    assert parsed["conditions"][0]["resolution_note"] == "fix"

    sidecar_path = phase_dir / "conditions-manifest.CONDITION-1.resolution.json"
    assert sidecar_path.exists(), "sidecar must land before manifest flip (crash safety)"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["condition_id"] == "CONDITION-1"
    assert sidecar["resolution_ref"] == "commits/abc123"


def test_marked_cleared_idempotent_when_already_cleared(mem_conn, tmp_path) -> None:
    """Replay with the same resolution_ref on an already-cleared condition →
    no rewrite (mtime unchanged)."""
    from daemon.projector import _condition_marked_cleared

    project_id = "proj-mc-idempotent"
    project_dir = _make_project_dir(tmp_path, project_id)
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    # Pre-cleared manifest with the same resolution_ref the event will carry.
    manifest_path.write_text(json.dumps({
        "source_gate": "build",
        "conditions": [
            {"id": "CONDITION-1", "verified": True,
             "resolution": "commits/abc123",
             "verified_at": "2026-05-03T12:00:00Z", "description": "x"},
        ],
    }))
    _setup_project_in_db(mem_conn, project_id, project_dir)
    sidecar_path = phase_dir / "conditions-manifest.CONDITION-1.resolution.json"

    event = _make_marked_cleared_event(
        project_id=project_id,
        resolution_ref="commits/abc123",
    )

    first_manifest_mtime = manifest_path.stat().st_mtime_ns
    with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "on"}):
        _condition_marked_cleared(mem_conn, event)
    second_manifest_mtime = manifest_path.stat().st_mtime_ns

    assert first_manifest_mtime == second_manifest_mtime, (
        "idempotent replay must short-circuit before sidecar+manifest writes"
    )
    assert not sidecar_path.exists(), (
        "idempotent replay must not write a sidecar"
    )


# ---------------------------------------------------------------------------
# mark_cleared() emit wiring
# ---------------------------------------------------------------------------


def test_mark_cleared_emits_event_with_condition_chain_id(tmp_path) -> None:
    """conditions_manifest.mark_cleared() must fire wicked.condition.marked_cleared
    with chain_id including condition_id (per-condition uniqueness gotcha)."""
    import conditions_manifest  # type: ignore[import]

    project_dir = tmp_path / "proj-emit"
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    manifest_path.write_text(json.dumps({
        "source_gate": "build",
        "conditions": [
            {"id": "CONDITION-1", "verified": False, "resolution": None,
             "verified_at": None, "description": "x"},
        ],
    }))

    captured: "list[dict]" = []

    def _fake_emit(event_type: str, payload: dict, *, chain_id=None):
        captured.append({"event_type": event_type, "payload": payload, "chain_id": chain_id})

    with patch("_bus.emit_event", _fake_emit):
        conditions_manifest.mark_cleared(
            manifest_path, "CONDITION-1", "commits/abc123", note="fix",
        )

    assert len(captured) == 1
    emit = captured[0]
    assert emit["event_type"] == "wicked.condition.marked_cleared"
    assert emit["payload"]["project_id"] == "proj-emit"
    assert emit["payload"]["phase"] == "build"
    assert emit["payload"]["condition_id"] == "CONDITION-1"
    assert emit["payload"]["resolution_ref"] == "commits/abc123"
    assert emit["chain_id"] == "proj-emit.build.CONDITION-1", (
        "chain_id must include condition_id (per-condition uniqueness gotcha)"
    )


def test_mark_cleared_disk_writes_run_when_emit_fails(tmp_path) -> None:
    """A bus-emit failure must NOT block the legacy disk writes (fail-open)."""
    import conditions_manifest  # type: ignore[import]

    project_dir = tmp_path / "proj-emit-fail"
    phase_dir = project_dir / "phases" / "build"
    phase_dir.mkdir(parents=True)
    manifest_path = phase_dir / "conditions-manifest.json"
    manifest_path.write_text(json.dumps({
        "source_gate": "build",
        "conditions": [
            {"id": "CONDITION-1", "verified": False, "resolution": None,
             "verified_at": None, "description": "x"},
        ],
    }))

    def _raising_emit(event_type, payload, *, chain_id=None):
        raise RuntimeError("simulated bus failure")

    with patch("_bus.emit_event", _raising_emit):
        conditions_manifest.mark_cleared(
            manifest_path, "CONDITION-1", "commits/xyz789",
        )

    # Disk writes must still have completed.
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["conditions"][0]["verified"] is True
    assert parsed["conditions"][0]["resolution"] == "commits/xyz789"
    sidecar = phase_dir / "conditions-manifest.CONDITION-1.resolution.json"
    assert sidecar.exists()
