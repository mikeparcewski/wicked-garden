"""Unit tests for scripts/crew/guide.py — crew:guide command inspector.

Tests:
    test_no_active_project_returns_start_suggestion        — no project → start suggestion
    test_active_stale_phase_returns_execute_suggestion     — stalled phase → execute suggestion
    test_open_conditional_gate_returns_gate_suggestion     — unresolved conditions → gate suggestion
    test_uncommitted_work_returns_commit_suggestion        — dirty git tree → commit suggestion
    test_no_uncommitted_work_no_git_signal                 — clean tree → no git suggestion
    test_output_capped_at_max_suggestions                  — never exceeds MAX_SUGGESTIONS
    test_format_output_numbered_list                       — format_output shape check
    test_format_output_empty_list                          — empty list fallback message
    test_conditional_gate_ranks_above_stale_phase          — gate signal priority > phase staleness
    test_open_conditions_only_when_unverified              — verified conditions not flagged

All tests are deterministic (no wall-clock, no sleep).
Stdlib-only — no external dependencies.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import guide  # noqa: E402 — must follow path setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RECENT_TS = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
_STALE_TS = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()


def _make_project(name: str = "test-proj", phase: str = "build", updated_at: str = _STALE_TS) -> dict:
    return {
        "name": name,
        "current_phase": phase,
        "updated_at": updated_at,
        "workspace": "test-workspace",
    }


def _make_conditions_manifest(tmp_dir: Path, phase: str, verified: bool = False) -> None:
    """Write a conditions-manifest.json under tmp_dir/phases/{phase}/."""
    phase_dir = tmp_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "conditions": [
            {
                "id": "c-001",
                "description": "test condition",
                "verified": verified,
            }
        ]
    }
    (phase_dir / "conditions-manifest.json").write_text(json.dumps(manifest))


# ---------------------------------------------------------------------------
# Test: no active project
# ---------------------------------------------------------------------------

class TestNoActiveProject(unittest.TestCase):
    """No crew project → should suggest crew:start."""

    def test_no_active_project_returns_start_suggestion(self) -> None:
        with patch.object(guide, "_find_active_project", return_value={"project": None, "project_dir": None}):
            with patch.object(guide, "_probe_uncommitted_work", return_value=[]):
                with patch.object(guide, "_probe_brain_context", return_value=[]):
                    result = guide.build_suggestions()

        self.assertEqual(len(result), 1)
        self.assertIn("crew:start", result[0]["command"])
        self.assertEqual(result[0]["rank"], 1)


# ---------------------------------------------------------------------------
# Test: stale phase
# ---------------------------------------------------------------------------

class TestStalePhase(unittest.TestCase):
    """Active project stalled for > STALE_HOURS → should suggest crew:execute."""

    def test_active_stale_phase_returns_execute_suggestion(self) -> None:
        project = _make_project(updated_at=_STALE_TS)
        with patch.object(guide, "_find_active_project", return_value={"project": project, "project_dir": None}):
            with patch.object(guide, "_probe_open_conditions", return_value=[]):
                with patch.object(guide, "_probe_uncommitted_work", return_value=[]):
                    with patch.object(guide, "_probe_brain_context", return_value=[]):
                        result = guide.build_suggestions()

        commands = [s["command"] for s in result]
        self.assertTrue(
            any("execute" in c for c in commands),
            f"Expected execute suggestion, got: {commands}",
        )

    def test_recent_phase_no_stale_signal(self) -> None:
        project = _make_project(updated_at=_RECENT_TS)
        with tempfile.TemporaryDirectory() as tmp:
            suggestions = guide._probe_stale_phase(project, tmp)
        self.assertEqual(suggestions, [])


# ---------------------------------------------------------------------------
# Test: open CONDITIONAL gate
# ---------------------------------------------------------------------------

class TestOpenConditionalGate(unittest.TestCase):
    """Unresolved conditions-manifest.json → should suggest crew:gate."""

    def test_open_conditional_gate_returns_gate_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_conditions_manifest(Path(tmp), "design", verified=False)
            result = guide._probe_open_conditions({}, tmp)

        self.assertEqual(len(result), 1)
        self.assertIn("gate", result[0]["command"])
        self.assertEqual(result[0]["rank"], 1)

    def test_open_conditions_only_when_unverified(self) -> None:
        """Fully verified conditions should not trigger the gate signal."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_conditions_manifest(Path(tmp), "design", verified=True)
            result = guide._probe_open_conditions({}, tmp)

        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Test: uncommitted work
# ---------------------------------------------------------------------------

class TestUncommittedWork(unittest.TestCase):
    """Git dirty tree → should suggest commit."""

    def test_uncommitted_work_returns_commit_suggestion(self) -> None:
        with patch.object(guide, "_run", return_value=(0, "M  scripts/foo.py\n?? bar.txt", "")):
            result = guide._probe_uncommitted_work(cwd="/tmp")

        self.assertEqual(len(result), 1)
        self.assertIn("commit", result[0]["command"])

    def test_no_uncommitted_work_no_git_signal(self) -> None:
        with patch.object(guide, "_run", return_value=(0, "", "")):
            result = guide._probe_uncommitted_work(cwd="/tmp")

        self.assertEqual(result, [])

    def test_git_error_returns_empty(self) -> None:
        """Non-zero git exit → no suggestion (not in a git repo, etc.)."""
        with patch.object(guide, "_run", return_value=(128, "", "not a git repo")):
            result = guide._probe_uncommitted_work(cwd="/tmp")

        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Test: output cap
# ---------------------------------------------------------------------------

class TestOutputCap(unittest.TestCase):
    """build_suggestions must never return more than MAX_SUGGESTIONS items."""

    def test_output_capped_at_max_suggestions(self) -> None:
        # Manufacture more signals than the cap by patching each probe.
        large_set = [
            {"rank": i, "command": f"/cmd-{i}", "rationale": f"reason {i}"}
            for i in range(1, 20)
        ]
        project = _make_project(updated_at=_STALE_TS)
        with patch.object(guide, "_find_active_project", return_value={"project": project, "project_dir": None}):
            with patch.object(guide, "_probe_open_conditions", return_value=large_set[:3]):
                with patch.object(guide, "_probe_stale_phase", return_value=large_set[3:6]):
                    with patch.object(guide, "_probe_uncommitted_work", return_value=large_set[6:9]):
                        with patch.object(guide, "_probe_brain_context", return_value=large_set[9:12]):
                            result = guide.build_suggestions()

        self.assertLessEqual(len(result), guide.MAX_SUGGESTIONS)


# ---------------------------------------------------------------------------
# Test: signal priority ordering
# ---------------------------------------------------------------------------

class TestSignalPriority(unittest.TestCase):
    """Gate signal (rank 1) should appear before stale phase (rank 2)."""

    def test_conditional_gate_ranks_above_stale_phase(self) -> None:
        gate_signal = [{"rank": 1, "command": guide._GATE_CMD, "rationale": "gate"}]
        stale_signal = [{"rank": 2, "command": guide._PHASE_ADVANCE_CMD, "rationale": "stale"}]

        project = _make_project(updated_at=_STALE_TS)
        with patch.object(guide, "_find_active_project", return_value={"project": project, "project_dir": None}):
            with patch.object(guide, "_probe_open_conditions", return_value=gate_signal):
                with patch.object(guide, "_probe_stale_phase", return_value=stale_signal):
                    with patch.object(guide, "_probe_uncommitted_work", return_value=[]):
                        with patch.object(guide, "_probe_brain_context", return_value=[]):
                            result = guide.build_suggestions()

        self.assertEqual(result[0]["command"], guide._GATE_CMD)
        self.assertEqual(result[1]["command"], guide._PHASE_ADVANCE_CMD)


# ---------------------------------------------------------------------------
# Test: format_output
# ---------------------------------------------------------------------------

class TestFormatOutput(unittest.TestCase):
    """format_output should produce a numbered list."""

    def test_format_output_numbered_list(self) -> None:
        suggestions = [
            {"rank": 1, "command": "/wicked-garden:crew:gate", "rationale": "open conditions"},
            {"rank": 2, "command": "/wicked-garden:crew:execute", "rationale": "stale phase"},
        ]
        output = guide.format_output(suggestions)
        self.assertIn("1.", output)
        self.assertIn("2.", output)
        self.assertIn("`/wicked-garden:crew:gate`", output)
        self.assertIn("open conditions", output)

    def test_format_output_empty_list(self) -> None:
        output = guide.format_output([])
        self.assertIn("clear", output.lower())


if __name__ == "__main__":
    unittest.main()
