"""Tests for yolo + CONDITIONAL gate override fix (issue #531).

Verifies that:
- approve_phase(override_gate=True, override_reason=...) succeeds when yolo is
  granted AND gate result is CONDITIONAL, and records a yolo-audit entry with
  event="user-override-conditional"
- Without override_gate, yolo + CONDITIONAL still raises (existing behavior)
- override_reason="" still raises even with override_gate=True (reason required)

Deterministic. Stdlib-only.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "platform"))

import phase_manager as pm  # noqa: E402
from phase_manager import ProjectState, PhaseState, approve_phase  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_CONDITIONAL_GATE_RESULT = {
    "result": "CONDITIONAL",
    "verdict": "CONDITIONAL",
    "score": 0.65,
    "reviewer": "senior-engineer",
    "recorded_at": "2026-04-19T00:00:00Z",
    "reason": "AC-2 coverage divergent",
    "summary": "Gate passed conditionally — see conditions.",
    "conditions": [{"condition": "Address divergent AC-2 coverage", "description": "AC-2 not found in tests"}],
}


def _make_review_ready_state_with_yolo(name: str = "yolo-conditional-test") -> ProjectState:
    """Minimal ProjectState in review phase with yolo_approved_by_user=True."""
    state = ProjectState(
        name=name,
        current_phase="review",
        created_at="2026-04-19T00:00:00Z",
    )
    state.phase_plan = ["clarify", "design", "build", "review"]
    state.phases["clarify"] = PhaseState(status="approved")
    state.phases["design"] = PhaseState(status="approved")
    state.phases["build"] = PhaseState(status="approved")
    state.phases["review"] = PhaseState(
        status="in_progress",
        started_at="2026-04-19T01:00:00Z",
    )
    state.extras = {"yolo_approved_by_user": True}
    return state


class _YoloConditionalBase(unittest.TestCase):
    """Base: isolated tmpdir + patched phase_manager helpers."""

    def setUp(self):
        self._tempdir_obj = tempfile.TemporaryDirectory()
        self._tempdir = Path(self._tempdir_obj.name)
        self._env = patch.dict(os.environ, {
            "TMPDIR": str(self._tempdir),
            "CLAUDE_SESSION_ID": f"test-531-{id(self)}",
        })
        self._env.start()

        # Build a project dir that looks like it already ran the gate.
        self._proj_dir = self._tempdir / "projects" / "yolo-conditional-test"
        phase_dir = self._proj_dir / "phases" / "review"
        phase_dir.mkdir(parents=True, exist_ok=True)

        # Write a CONDITIONAL gate-result.json so _check_gate_run returns True.
        (phase_dir / "gate-result.json").write_text(
            json.dumps(_CONDITIONAL_GATE_RESULT, indent=2)
        )

        # Patch out storage + unrelated checks so we reach the yolo branch.
        self._patches = [
            patch.object(pm, "get_project_dir", return_value=self._proj_dir),
            patch.object(pm, "save_project_state"),
            patch.object(pm, "_sm"),
            patch.object(pm, "_check_addendum_freshness", return_value=None),
            patch.object(pm, "_check_phase_deliverables", return_value=[]),
            patch.object(pm, "load_phases_config", return_value={
                "review": {
                    "gate_required": True,
                    "depends_on": [],
                    "min_gate_score": 0.6,
                },
            }),
            patch.object(pm, "_load_session_dispatches", return_value=[]),
            patch.object(pm, "_run_checkpoint_reanalysis", return_value=([], [])),
            patch.object(pm, "get_phase_order", return_value=[
                "clarify", "design", "build", "review",
            ]),
            # Skip semantic alignment — not the subject of these tests.
            patch.object(pm, "_check_semantic_alignment_gate", return_value=(None, [])),
            # Skip consensus gate (optional feature).
            patch.object(pm, "_get_consensus_gate", return_value={}),
            # Skip spec rubric adjustment.
            patch.object(pm, "_apply_spec_rubric", side_effect=lambda gr, *a, **kw: gr),
            # Skip min-gate-score validation (score=0.65 would fail at 0.6 due
            # to the phase config we set above — irrelevant to what we test).
            patch.object(pm, "_validate_min_gate_score", return_value=None),
            # Skip reviewer validation.
            patch.object(pm, "_validate_gate_reviewer", return_value=None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._env.stop()
        self._tempdir_obj.cleanup()

    def _read_yolo_audit(self) -> list:
        audit_path = self._proj_dir / "yolo-audit.jsonl"
        if not audit_path.exists():
            return []
        return [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# AC-1: override_gate=True + CONDITIONAL + yolo succeeds + writes audit entry
# ---------------------------------------------------------------------------

class TestYoloConditionalWithOverride(_YoloConditionalBase):

    def test_override_gate_true_advances_and_writes_audit(self):
        """AC-1: approve with override_gate=True, CONDITIONAL, yolo -> succeeds."""
        state = _make_review_ready_state_with_yolo()
        result_state, next_phase = approve_phase(
            state,
            "review",
            override_gate=True,
            override_reason="QA lead signed off manually",
            approver="qe-lead",
        )

        # advance should have happened (no exception raised)
        self.assertIsNotNone(result_state, "approve_phase should return a state")

        # yolo-audit.jsonl must have a user-override-conditional entry
        audit_entries = self._read_yolo_audit()
        override_entries = [
            e for e in audit_entries
            if e.get("event") == "user-override-conditional"
        ]
        self.assertGreaterEqual(
            len(override_entries), 1,
            "Expected at least one 'user-override-conditional' audit entry",
        )
        entry = override_entries[0]
        self.assertEqual(entry["event"], "user-override-conditional")
        self.assertIn("CONDITIONAL", entry.get("reason", ""))
        self.assertEqual(entry.get("verdict"), "CONDITIONAL")
        self.assertEqual(entry.get("override_reason"), "QA lead signed off manually")


# ---------------------------------------------------------------------------
# AC-2: WITHOUT override_gate, yolo + CONDITIONAL still raises
# ---------------------------------------------------------------------------

class TestYoloConditionalWithoutOverride(_YoloConditionalBase):

    def test_no_override_gate_raises(self):
        """AC-2: yolo + CONDITIONAL without --override-gate raises ValueError."""
        state = _make_review_ready_state_with_yolo()
        with self.assertRaises(ValueError) as ctx:
            approve_phase(
                state,
                "review",
                override_gate=False,
                override_reason="",
                approver="user",
            )
        self.assertIn("CONDITIONAL", str(ctx.exception))
        self.assertIn("override-gate", str(ctx.exception))


# ---------------------------------------------------------------------------
# AC-3: override_reason="" still raises even with override_gate=True
# ---------------------------------------------------------------------------

class TestYoloConditionalEmptyReason(_YoloConditionalBase):

    def test_empty_override_reason_raises(self):
        """AC-3: override_gate=True + empty reason must raise (reason is required)."""
        state = _make_review_ready_state_with_yolo()
        with self.assertRaises(ValueError) as ctx:
            approve_phase(
                state,
                "review",
                override_gate=True,
                override_reason="",
                approver="user",
            )
        # Error must mention reason requirement
        self.assertIn("reason", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
