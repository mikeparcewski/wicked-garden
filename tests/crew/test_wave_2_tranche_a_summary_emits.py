"""tests/crew/test_wave_2_tranche_a_summary_emits.py — Wave-2 Tranche A
audit-marker summary emits (#746 W2/W3/W4).

Each of the three migration/maintenance scripts is EXEMPT from full
bus-cutover (per docs/v9/wave-2-cutover-plan.md §W2/W3/W4) but emits
a summary marker after successful operation so future forensics can
identify projects that went through legacy adoption / qe-evaluator
rename / log rotation.

Covers:
  * adopt_legacy.apply_transformations → wicked.crew.legacy_adopted
    (fires on actual application, not dry-run, only when markers
    were processed; fail-open on bus error)
  * migrate_qe_evaluator_name._scan_and_migrate →
    wicked.crew.qe_evaluator_migrated (fires when migrated > 0 and
    not dry-run; fail-open on bus error)
  * log_retention.rotate_if_needed → wicked.log.rotated (fires when
    rotation actually happened — file was over threshold; fail-open
    on bus error)

T1: deterministic — no wall-clock-dependent assertions.
T3: isolated — each test gets its own tmp_path.
T6: provenance: #746 wave-2 Tranche A.
"""
from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# adopt_legacy.apply_transformations → wicked.crew.legacy_adopted
# ---------------------------------------------------------------------------


def test_adopt_legacy_emits_summary_after_apply(tmp_path) -> None:
    """apply_transformations(dry_run=False) with markers → fires emit."""
    import adopt_legacy  # type: ignore[import]

    project_dir = tmp_path / "legacy-proj"
    project_dir.mkdir()
    # Minimum project.json with NO phase_plan_mode key — that triggers
    # the missing-phase_plan_mode marker.
    (project_dir / "project.json").write_text(
        json.dumps({"id": "legacy-proj", "name": "legacy-proj"}),
    )

    captured: list = []

    def _fake_emit(event_type, payload, *, chain_id=None):
        captured.append({
            "event_type": event_type,
            "payload": payload,
            "chain_id": chain_id,
        })

    with patch("_bus.emit_event", _fake_emit):
        outcomes = adopt_legacy.apply_transformations(
            project_dir, ["missing-phase_plan_mode"], dry_run=False,
        )

    assert outcomes, "transformation must produce at least one outcome line"
    assert len(captured) == 1, f"exactly one summary emit expected, got {captured}"
    emit = captured[0]
    assert emit["event_type"] == "wicked.crew.legacy_adopted"
    assert emit["payload"]["project_id"] == "legacy-proj"
    assert emit["payload"]["marker_count"] == 1
    assert emit["payload"]["outcome_count"] == 1
    assert emit["payload"]["markers_applied"] == ["missing-phase_plan_mode"]
    assert emit["chain_id"] == "legacy-proj.root"


def test_adopt_legacy_does_not_emit_on_dry_run(tmp_path) -> None:
    """dry_run=True must NOT fire the summary emit (no real change happened)."""
    import adopt_legacy  # type: ignore[import]

    project_dir = tmp_path / "legacy-proj-dry"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps({"id": "legacy-proj-dry"}),
    )

    captured: list = []

    def _fake_emit(event_type, payload, *, chain_id=None):
        captured.append(event_type)

    with patch("_bus.emit_event", _fake_emit):
        adopt_legacy.apply_transformations(
            project_dir, ["missing-phase_plan_mode"], dry_run=True,
        )

    assert captured == [], "dry_run must not emit — no actual change happened"


def test_adopt_legacy_does_not_emit_when_no_markers(tmp_path) -> None:
    """No markers → no transformations → no emit."""
    import adopt_legacy  # type: ignore[import]

    project_dir = tmp_path / "legacy-proj-clean"
    project_dir.mkdir()

    captured: list = []

    with patch("_bus.emit_event", lambda et, p, **kw: captured.append(et)):
        outcomes = adopt_legacy.apply_transformations(
            project_dir, [], dry_run=False,
        )

    assert outcomes == []
    assert captured == []


def test_adopt_legacy_emit_failure_does_not_break_migration(tmp_path) -> None:
    """A bus-emit failure must NOT raise out of apply_transformations."""
    import adopt_legacy  # type: ignore[import]

    project_dir = tmp_path / "legacy-proj-busfail"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps({"id": "legacy-proj-busfail"}),
    )

    def _raising_emit(event_type, payload, *, chain_id=None):
        raise RuntimeError("simulated bus failure")

    with patch("_bus.emit_event", _raising_emit):
        # Must not raise.
        outcomes = adopt_legacy.apply_transformations(
            project_dir, ["missing-phase_plan_mode"], dry_run=False,
        )

    # Migration outcomes still produced — fail-open invariant.
    assert outcomes
    # And the disk transformation actually landed.
    parsed = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert parsed.get("phase_plan_mode") == "facilitator"


# ---------------------------------------------------------------------------
# migrate_qe_evaluator_name._scan_and_migrate → wicked.crew.qe_evaluator_migrated
# ---------------------------------------------------------------------------


def _seed_legacy_jsonl(project_dir: Path, phase: str = "design") -> Path:
    """Seed a single phases/{phase}/reeval-log.jsonl with a legacy entry."""
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    p = phase_dir / "reeval-log.jsonl"
    p.write_text(
        json.dumps({"reviewer": "qe-evaluator", "verdict": "APPROVE"}) + "\n",
    )
    return p


def test_migrate_qe_evaluator_emits_summary_when_migrations_happen(tmp_path) -> None:
    """_scan_and_migrate(project_dir, dry_run=False) with at least one
    legacy file → fires wicked.crew.qe_evaluator_migrated."""
    import migrate_qe_evaluator_name as mig  # type: ignore[import]

    project_dir = tmp_path / "migrate-proj"
    project_dir.mkdir()
    _seed_legacy_jsonl(project_dir)

    captured: list = []

    def _fake_emit(event_type, payload, *, chain_id=None):
        captured.append({
            "event_type": event_type,
            "payload": payload,
            "chain_id": chain_id,
        })

    with patch("_bus.emit_event", _fake_emit):
        rc = mig._scan_and_migrate(
            projects_root=None, project_dir=project_dir, dry_run=False,
        )

    assert rc == 0
    assert len(captured) == 1
    emit = captured[0]
    assert emit["event_type"] == "wicked.crew.qe_evaluator_migrated"
    assert emit["payload"]["project_id"] == "migrate-proj"
    assert emit["payload"]["scope"] == "single-project"
    assert emit["payload"]["migrated"] >= 1
    assert emit["payload"]["errors"] == 0
    assert emit["chain_id"] == "migrate-proj.root"


def test_migrate_qe_evaluator_does_not_emit_on_dry_run(tmp_path) -> None:
    """dry_run=True must NOT fire the summary emit."""
    import migrate_qe_evaluator_name as mig  # type: ignore[import]

    project_dir = tmp_path / "migrate-proj-dry"
    project_dir.mkdir()
    _seed_legacy_jsonl(project_dir)

    captured: list = []

    with patch("_bus.emit_event", lambda et, p, **kw: captured.append(et)):
        mig._scan_and_migrate(
            projects_root=None, project_dir=project_dir, dry_run=True,
        )

    assert captured == []


def test_migrate_qe_evaluator_does_not_emit_when_zero_migrated(tmp_path) -> None:
    """No legacy entries to migrate → no emit (skipped count != migrated)."""
    import migrate_qe_evaluator_name as mig  # type: ignore[import]

    project_dir = tmp_path / "migrate-proj-clean"
    project_dir.mkdir()
    # File exists but has no legacy entries.
    phase_dir = project_dir / "phases" / "design"
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "reeval-log.jsonl").write_text(
        json.dumps({"reviewer": "gate-adjudicator"}) + "\n",
    )

    captured: list = []

    with patch("_bus.emit_event", lambda et, p, **kw: captured.append(et)):
        mig._scan_and_migrate(
            projects_root=None, project_dir=project_dir, dry_run=False,
        )

    assert captured == [], (
        "no legacy entries → no migration → no emit "
        "(audit marker only fires when something changed)"
    )


# ---------------------------------------------------------------------------
# log_retention.rotate_if_needed → wicked.log.rotated
# ---------------------------------------------------------------------------


def test_rotate_if_needed_emits_summary_when_rotation_fires(tmp_path) -> None:
    """rotate_if_needed with file over threshold → fires wicked.log.rotated."""
    import log_retention  # type: ignore[import]

    # Path shape mirrors production: <project_dir>/phases/<phase>/<log>
    log_dir = tmp_path / "proj" / "phases" / "build"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "dispatch-log.jsonl"
    # Write enough bytes to trigger rotation at a small explicit threshold.
    log_path.write_text("x" * 1024, encoding="utf-8")

    captured: list = []

    def _fake_emit(event_type, payload, *, chain_id=None):
        captured.append({
            "event_type": event_type,
            "payload": payload,
            "chain_id": chain_id,
        })

    with patch("_bus.emit_event", _fake_emit):
        archive = log_retention.rotate_if_needed(
            log_path, max_size_bytes=512,
        )

    assert archive is not None and archive.exists()
    assert len(captured) == 1
    emit = captured[0]
    assert emit["event_type"] == "wicked.log.rotated"
    assert emit["payload"]["log_path"] == str(log_path)
    assert emit["payload"]["archive_path"] == str(archive)
    assert emit["payload"]["size_bytes"] == 1024
    assert emit["payload"]["threshold_bytes"] == 512
    # Truncate happened.
    assert log_path.read_text(encoding="utf-8") == ""


def test_rotate_if_needed_does_not_emit_when_below_threshold(tmp_path) -> None:
    """File below threshold → no rotation → no emit."""
    import log_retention  # type: ignore[import]

    log_dir = tmp_path / "proj" / "phases" / "build"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "dispatch-log.jsonl"
    log_path.write_text("small", encoding="utf-8")

    captured: list = []

    with patch("_bus.emit_event", lambda et, p, **kw: captured.append(et)):
        result = log_retention.rotate_if_needed(
            log_path, max_size_bytes=10_000,
        )

    assert result is None
    assert captured == []


def test_rotate_if_needed_emit_failure_does_not_break_rotation(tmp_path) -> None:
    """A bus-emit failure must NOT undo the rotation."""
    import log_retention  # type: ignore[import]

    log_dir = tmp_path / "proj" / "phases" / "build"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "dispatch-log.jsonl"
    log_path.write_text("x" * 1024, encoding="utf-8")

    def _raising_emit(event_type, payload, *, chain_id=None):
        raise RuntimeError("simulated bus failure")

    with patch("_bus.emit_event", _raising_emit):
        archive = log_retention.rotate_if_needed(log_path, max_size_bytes=512)

    # Rotation completed despite emit failure.
    assert archive is not None and archive.exists()
    assert log_path.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# Bus event catalog — confirm all three Tranche A summary events registered
# ---------------------------------------------------------------------------


def test_all_tranche_a_events_in_catalog() -> None:
    """All three summary events must be in BUS_EVENT_MAP for the lint."""
    import _bus  # type: ignore[import]

    expected = {
        "wicked.crew.legacy_adopted",
        "wicked.crew.qe_evaluator_migrated",
        "wicked.log.rotated",
    }
    for evt in expected:
        assert evt in _bus.BUS_EVENT_MAP, (
            f"{evt} missing from _bus.BUS_EVENT_MAP — emits will fail "
            f"the bus_emit_lint and downstream consumers cannot subscribe"
        )
