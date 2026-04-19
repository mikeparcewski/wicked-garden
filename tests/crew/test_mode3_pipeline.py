#!/usr/bin/env python3
"""tests/crew/test_mode3_pipeline.py — AC-α7 integration tests.

Four sub-cases (a)..(d) per AC-α7 + happy-path / scope-revoke exercise.
Stdlib-only, no sleep-based sync (T2), single-assertion focus (T4).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


def _synth_state(name: str, *, dispatch_mode="mode-3", yolo=False):
    extras = {
        "dispatch_mode": dispatch_mode,
        "rigor_tier": "full",
    }
    if yolo:
        extras["yolo_approved_by_user"] = True
    return phase_manager.ProjectState(
        name=name,
        current_phase="build",
        created_at="2026-04-19T10:00:00Z",
        phase_plan=["clarify", "design", "build", "review"],
        phases={
            "clarify": phase_manager.PhaseState(status="approved"),
            "design": phase_manager.PhaseState(status="approved"),
            "build": phase_manager.PhaseState(status="in_progress"),
            "review": phase_manager.PhaseState(status="pending"),
        },
        extras=extras,
    )


def _write_executor_status(project_dir: Path, phase: str, *, deliverables, plan_mutations=None, parallelization_check=None):
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    for d in deliverables:
        rel = phase_dir / Path(d).name
        rel.write_text("x" * 200)  # >= 100 bytes
    status = {
        "executor_task_id": "task-test-1",
        "phase": phase,
        "deliverables": [str(phase_dir / Path(d).name) for d in deliverables],
        "plan_mutations": plan_mutations or [],
        "parallelization_check": parallelization_check or {
            "sub_task_count": 0, "dispatched_in_parallel": True, "serial_reason": None,
        },
    }
    (phase_dir / "executor-status.json").write_text(json.dumps(status))
    return status


class TestExecuteHappyPath(unittest.TestCase):
    """AC-α7(a) — happy-path execute returns ok."""

    def test_execute_ok_when_status_present(self):
        """execute() returns status=ok when executor-status.json is valid."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "happy"
            project_dir.mkdir()
            state = _synth_state("happy")
            _write_executor_status(project_dir, "build", deliverables=["impl.md"])
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                result = phase_manager.execute("happy", "build")
            self.assertEqual(result["status"], "ok")


class TestExecuteLegacySkip(unittest.TestCase):
    """AC-α11 — v6-legacy dispatch_mode short-circuits mode-3 execute()."""

    def test_execute_returns_skipped_for_legacy_project(self):
        """A v6-legacy project's execute() returns status=skipped."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "legacy"
            project_dir.mkdir()
            state = _synth_state("legacy", dispatch_mode="v6-legacy")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                result = phase_manager.execute("legacy", "build")
            self.assertEqual(result["status"], "skipped")


class TestYoloAutoRevoke(unittest.TestCase):
    """AC-α7(d) — yolo auto-revoke on scope-increase augment."""

    def test_augment_mutation_revokes_yolo(self):
        """Plan mutation op=augment flips yolo_approved_by_user to False."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-revoke"
            project_dir.mkdir()
            state = _synth_state("yolo-revoke", yolo=True)

            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                plan_mutations=[{"op": "augment", "task_id": "t-new", "why": "scope creep"}],
            )

            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                phase_manager.execute("yolo-revoke", "build")

            self.assertFalse(state.extras.get("yolo_approved_by_user"))

    def test_retier_down_does_not_revoke_yolo(self):
        """Plan mutation op=re_tier to 'standard' does NOT revoke yolo."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-keep"
            project_dir.mkdir()
            state = _synth_state("yolo-keep", yolo=True)
            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                plan_mutations=[{"op": "re_tier", "task_id": "t1",
                                 "new_rigor_tier": "standard", "why": "simplify"}],
            )
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                phase_manager.execute("yolo-keep", "build")
            self.assertTrue(state.extras.get("yolo_approved_by_user"))


class TestParallelizationFailure(unittest.TestCase):
    """AC-α7(c) relates — failure mode when parallelization_check is missing."""

    def test_execute_fails_when_serial_without_reason(self):
        """execute() returns status=failed with parallelization-check-missing."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "par-fail"
            project_dir.mkdir()
            state = _synth_state("par-fail")
            _write_executor_status(
                project_dir, "build",
                deliverables=["impl.md"],
                parallelization_check={
                    "sub_task_count": 3,
                    "dispatched_in_parallel": False,
                    "serial_reason": "",
                },
            )
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir), \
                 patch.object(phase_manager, "_validate_gate_policy_full_rigor"):
                result = phase_manager.execute("par-fail", "build")
            self.assertEqual(result["status"], "failed")


class TestYoloActionAudit(unittest.TestCase):
    """AC-α5 — yolo_action writes audit line."""

    def test_yolo_approve_writes_audit(self):
        """yolo_action('approve') sets flag and writes yolo-audit.jsonl."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "yolo-grant"
            project_dir.mkdir()
            state = _synth_state("yolo-grant", yolo=False)
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                phase_manager.yolo_action("yolo-grant", "approve", reason="unit-test")
            audit = project_dir / "yolo-audit.jsonl"
            self.assertTrue(audit.exists())


if __name__ == "__main__":
    unittest.main()
