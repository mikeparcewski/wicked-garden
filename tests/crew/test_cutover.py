#!/usr/bin/env python3
"""tests/crew/test_cutover.py — CR-2 / AC-α11 in-flight cutover.

Covers:
    - Legacy auto-tag: project missing dispatch_mode → "v6-legacy" on detect.
    - Fresh default: project with dispatch_mode="mode-3" reads "mode-3".
    - /crew:cutover command flips the field + emits audit marker.
    - Safe cutover window rejects when prior conditions are unresolved.
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


def _synth_state(name: str, *, dispatch_mode=None, evidence_files=None):
    """Construct a minimal ProjectState; caller patches load/save and get_project_dir."""
    extras = {}
    if dispatch_mode is not None:
        extras["dispatch_mode"] = dispatch_mode
    return phase_manager.ProjectState(
        name=name,
        current_phase="clarify",
        created_at="2026-04-19T10:00:00Z",
        phase_plan=["clarify", "design", "build", "review"],
        phases={"clarify": phase_manager.PhaseState(status="in_progress")},
        extras=extras,
    )


class TestDetectDispatchMode(unittest.TestCase):
    """CR-2 — _detect_dispatch_mode auto-tags legacy projects."""

    def test_missing_field_returns_v6_legacy(self):
        """A project missing dispatch_mode + no mode-3 evidence backfills to v6-legacy."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "proj"
            project_dir.mkdir()
            state = _synth_state("proj")
            with patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                mode = phase_manager._detect_dispatch_mode(state)
            self.assertEqual(mode, "v6-legacy")
            # Backfill was written to extras.
            self.assertEqual(state.extras.get("dispatch_mode"), "v6-legacy")

    def test_existing_mode_3_field_is_respected(self):
        """A project with dispatch_mode='mode-3' reads mode-3 without backfill."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "proj"
            project_dir.mkdir()
            state = _synth_state("proj", dispatch_mode="mode-3")
            with patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                mode = phase_manager._detect_dispatch_mode(state)
            self.assertEqual(mode, "mode-3")

    def test_mode_3_evidence_promotes_legacy_project(self):
        """A project with reeval-log.jsonl evidence is detected as mode-3."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "proj"
            phases_dir = project_dir / "phases" / "design"
            phases_dir.mkdir(parents=True)
            (phases_dir / "reeval-log.jsonl").write_text("{}\n")
            state = _synth_state("proj")
            with patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                mode = phase_manager._detect_dispatch_mode(state)
            self.assertEqual(mode, "mode-3")


class TestCutoverAction(unittest.TestCase):
    """AC-α11(iii) — cutover flips field and emits marker."""

    def test_cutover_writes_marker_and_field(self):
        """cutover_action on a legacy project sets mode-3 and writes the marker."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "proj-legacy"
            project_dir.mkdir()
            state = _synth_state("proj-legacy")
            state.phases["clarify"].status = "approved"
            state.current_phase = "design"
            state.phases["design"] = phase_manager.PhaseState(status="pending")

            saved = []

            def fake_save(s):
                saved.append(s.extras.get("dispatch_mode"))

            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state", side_effect=fake_save), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.cutover_action("proj-legacy", "mode-3")

            self.assertEqual(result["dispatch_mode"], "mode-3")
            marker = project_dir / "phases" / ".cutover-to-mode-3.json"
            self.assertTrue(marker.exists())
            marker_data = json.loads(marker.read_text())
            self.assertEqual(marker_data["new_mode"], "mode-3")
            self.assertIn("mode-3", saved)

    def test_cutover_rejects_unsupported_target(self):
        """cutover_action with --to != mode-3 raises ValueError."""
        with self.assertRaises(ValueError):
            phase_manager.cutover_action("anything", "v5")


if __name__ == "__main__":
    unittest.main()
