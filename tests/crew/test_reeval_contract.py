#!/usr/bin/env python3
"""tests/crew/test_reeval_contract.py

Tests for the re-eval contract strengthening (#475 + #482).

- #475: ``agents/crew/phase-executor.md`` must mandate invocation of the
  ``wicked-garden:propose-process`` skill in ``re-evaluate`` mode at both
  phase-start (Step 1) and phase-end (Step 3), and the returned mutations
  must be appended via ``reeval_addendum.append()``. Snapshot-only JSON
  is bootstrap-only — the authoritative record is the JSONL append.
  ``skills/propose-process/refs/re-evaluation.md`` must codify the
  skill-call invocation shape.
- #482: ``phase_manager.execute`` must sample the project-level
  ``process-plan.addendum.jsonl`` line count before and after the
  executor-status pass. If no new record was appended, it must emit a
  warning (soft enforcement — does not fail the phase).

Stdlib-only; single-assertion-per-test where practical (T4);
descriptive names (T5).
"""

import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PHASE_EXECUTOR_MD = _REPO_ROOT / "agents" / "crew" / "phase-executor.md"
_REEVAL_MD = (
    _REPO_ROOT
    / "skills"
    / "propose-process"
    / "refs"
    / "re-evaluation.md"
)


# ---------------------------------------------------------------------------
# #475 — Agent contract documentation
# ---------------------------------------------------------------------------


class TestPhaseExecutorSkillCallContract(unittest.TestCase):
    """#475 — phase-executor.md must describe Skill() invocation at both bookends."""

    def setUp(self):
        self.doc_text = _PHASE_EXECUTOR_MD.read_text(encoding="utf-8")

    def test_phase_executor_doc_mentions_propose_process_skill(self):
        """Contract names the exact skill identifier."""
        self.assertIn("wicked-garden:propose-process", self.doc_text)

    def test_phase_executor_doc_mentions_reevaluate_mode(self):
        """Contract calls out re-evaluate mode for the skill invocation."""
        self.assertIn("re-evaluate", self.doc_text)

    def test_phase_executor_doc_mentions_skill_invocation_syntax(self):
        """Contract shows the Skill(...) invocation for the phase-executor."""
        self.assertIn("Skill(", self.doc_text)

    def test_phase_executor_doc_references_addendum_append(self):
        """Contract points at the reeval_addendum.append write path."""
        self.assertIn("reeval_addendum.append", self.doc_text)

    def test_phase_executor_doc_references_addendum_jsonl_file(self):
        """Contract names process-plan.addendum.jsonl as the authoritative record."""
        self.assertIn("process-plan.addendum.jsonl", self.doc_text)


class TestReEvaluationSkillRef(unittest.TestCase):
    """#475 — re-evaluation.md must codify the skill-call invocation."""

    def setUp(self):
        self.doc_text = _REEVAL_MD.read_text(encoding="utf-8")

    def test_re_evaluation_ref_shows_skill_call_shape(self):
        """Ref doc includes the Skill(skill='wicked-garden:propose-process') form."""
        self.assertIn("wicked-garden:propose-process", self.doc_text)

    def test_re_evaluation_ref_mentions_reevaluate_mode(self):
        """Ref doc names the re-evaluate mode parameter."""
        self.assertIn("re-evaluate", self.doc_text)

    def test_re_evaluation_ref_points_to_reeval_addendum_append(self):
        """Ref doc names reeval_addendum as the persistence helper."""
        self.assertIn("reeval_addendum", self.doc_text)


# ---------------------------------------------------------------------------
# #482 — Code-level re-eval addendum growth verification
# ---------------------------------------------------------------------------


class TestCountAddendumLines(unittest.TestCase):
    """``_count_addendum_lines`` returns the JSONL line count, fail-open."""

    def test_returns_zero_when_file_absent(self):
        """Missing file → 0 lines (fail-open read)."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            count = phase_manager._count_addendum_lines(project_dir)
            self.assertEqual(count, 0)

    def test_counts_non_empty_lines(self):
        """Only non-blank JSONL lines are counted."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            addendum = project_dir / "process-plan.addendum.jsonl"
            addendum.write_text(
                '{"chain_id": "p.design"}\n\n{"chain_id": "p.build"}\n',
                encoding="utf-8",
            )
            count = phase_manager._count_addendum_lines(project_dir)
            self.assertEqual(count, 2)


class TestVerifyReevalAddendumGrowth(unittest.TestCase):
    """``_verify_reeval_addendum_growth`` soft-enforces the #475 contract."""

    def test_returns_none_when_addendum_grew(self):
        """Growth between before/after counts → contract honored, no warning."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            addendum = project_dir / "process-plan.addendum.jsonl"
            addendum.write_text('{"chain_id": "p.design"}\n', encoding="utf-8")
            warning = phase_manager._verify_reeval_addendum_growth(
                project_dir, phase="design", before_count=0
            )
            self.assertIsNone(warning)

    def test_returns_warning_string_when_addendum_did_not_grow(self):
        """No growth → warning string mentioning the violation."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            warning = phase_manager._verify_reeval_addendum_growth(
                project_dir, phase="design", before_count=0
            )
            self.assertIsNotNone(warning)

    def test_warning_names_the_phase(self):
        """Warning string identifies the phase for downstream triage."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            warning = phase_manager._verify_reeval_addendum_growth(
                project_dir, phase="design", before_count=0
            )
            self.assertIn("design", warning or "")

    def test_warning_references_the_contract_issue(self):
        """Warning string points back to the #475 skill-call contract."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            warning = phase_manager._verify_reeval_addendum_growth(
                project_dir, phase="design", before_count=0
            )
            self.assertIn("#475", warning or "")


# ---------------------------------------------------------------------------
# #482 — execute() surfaces the warning on the result dict
# ---------------------------------------------------------------------------


class _StubProjectState:
    """Minimal stand-in for ProjectState used by execute() on the CLI path."""

    def __init__(self, name: str, phase: str = "design"):
        self.name = name
        self.current_phase = phase
        self.phases = {}
        self.extras = {"dispatch_mode": "mode-3"}


class TestExecuteReevalWarningSurface(unittest.TestCase):
    """``execute()`` attaches reeval_warning when addendum did not grow."""

    def test_execute_records_reeval_warning_when_addendum_static(self):
        """Processing an executor-status.json without appending to the
        addendum yields ``reeval_warning`` on the result dict.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            phase_dir = project_dir / "phases" / "design"
            phase_dir.mkdir(parents=True)

            # Deliverable >= 100 bytes under phases/design/.
            deliverable = phase_dir / "design.md"
            deliverable.write_text("x" * 200, encoding="utf-8")

            status_doc = {
                "deliverables": ["phases/design/design.md"],
                "executor_task_id": "t-1",
                "parallelization_check": {
                    "sub_task_count": 0,
                    "dispatched_in_parallel": True,
                    "serial_reason": None,
                },
                "plan_mutations": [],
            }
            (phase_dir / "executor-status.json").write_text(
                json.dumps(status_doc), encoding="utf-8"
            )

            state = _StubProjectState(name="p1", phase="design")

            with patch.object(
                phase_manager, "_validate_gate_policy_full_rigor",
                lambda: None,
            ), patch.object(
                phase_manager, "load_project_state", lambda _n: state,
            ), patch.object(
                phase_manager, "get_project_dir", lambda _n: project_dir,
            ), patch.object(
                phase_manager, "_detect_dispatch_mode", lambda _s: "mode-3",
            ), patch.object(
                phase_manager, "_apply_scope_increase_revoke",
                lambda *a, **kw: None,
            ), patch.object(
                phase_manager, "save_project_state", lambda _s: None,
            ):
                result = phase_manager.execute("p1", "design")

            self.assertIn("reeval_warning", result)

    def test_execute_clears_warning_when_addendum_grew(self):
        """When the addendum line count grows during the executor pass,
        no ``reeval_warning`` is attached to the result.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            phase_dir = project_dir / "phases" / "design"
            phase_dir.mkdir(parents=True)

            deliverable = phase_dir / "design.md"
            deliverable.write_text("x" * 200, encoding="utf-8")

            status_doc = {
                "deliverables": ["phases/design/design.md"],
                "executor_task_id": "t-1",
                "parallelization_check": {
                    "sub_task_count": 0,
                    "dispatched_in_parallel": True,
                    "serial_reason": None,
                },
                "plan_mutations": [],
            }
            (phase_dir / "executor-status.json").write_text(
                json.dumps(status_doc), encoding="utf-8"
            )

            # Patch _apply_scope_increase_revoke to append a line to the
            # addendum, simulating the phase-executor honoring #475. This
            # lets us exercise the positive path without running the real
            # propose-process skill.
            def _append_addendum(*_a, **_kw):
                addendum = project_dir / "process-plan.addendum.jsonl"
                with open(addendum, "a", encoding="utf-8") as fh:
                    fh.write('{"chain_id": "p1.design"}\n')

            state = _StubProjectState(name="p1", phase="design")

            with patch.object(
                phase_manager, "_validate_gate_policy_full_rigor",
                lambda: None,
            ), patch.object(
                phase_manager, "load_project_state", lambda _n: state,
            ), patch.object(
                phase_manager, "get_project_dir", lambda _n: project_dir,
            ), patch.object(
                phase_manager, "_detect_dispatch_mode", lambda _s: "mode-3",
            ), patch.object(
                phase_manager, "_apply_scope_increase_revoke",
                _append_addendum,
            ), patch.object(
                phase_manager, "save_project_state", lambda _s: None,
            ):
                result = phase_manager.execute("p1", "design")

            self.assertNotIn("reeval_warning", result)


if __name__ == "__main__":
    unittest.main()
