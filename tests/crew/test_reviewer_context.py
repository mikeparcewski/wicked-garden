#!/usr/bin/env python3
"""
Unit tests for shared reviewer-context.md injection (issue #474).

Covers:
    - ensure_reviewer_context writes a stub when missing, leaves existing
      content alone.
    - _dispatch_fast_evaluator passes shared_context_path into the ctx
      dict and embeds it in the reviewer prompt.
    - _dispatch_sequential and _dispatch_parallel_and_merge propagate
      shared_context_path to every reviewer dispatch.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "crew"))


import phase_manager  # noqa: E402  (path setup above)


class EnsureReviewerContextTests(unittest.TestCase):
    """ensure_reviewer_context writes a stub + is idempotent."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project_dir = Path(self.tmp.name) / "my-proj"
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def _make_state(self, name: str = "proj"):
        state = mock.Mock()
        state.name = name
        return state

    def test_writes_stub_when_missing(self) -> None:
        state = self._make_state("proj-1")
        with mock.patch.object(
            phase_manager, "get_project_dir", return_value=self.project_dir
        ):
            path = phase_manager.ensure_reviewer_context(
                state, "design", "design-quality"
            )
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("proj-1", content)
        self.assertIn("design", content)
        self.assertIn("design-quality", content)

    def test_idempotent_when_present(self) -> None:
        state = self._make_state("proj-2")
        # User-written context file — the helper must NOT overwrite.
        ctx_path = self.project_dir / "phases" / "design" / "reviewer-context.md"
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        ctx_path.write_text("# Human-authored reviewer-context\n")

        with mock.patch.object(
            phase_manager, "get_project_dir", return_value=self.project_dir
        ):
            result = phase_manager.ensure_reviewer_context(
                state, "design", "design-quality"
            )
        self.assertEqual(result, ctx_path)
        self.assertIn("Human-authored", ctx_path.read_text())

    def test_returns_none_when_state_is_none(self) -> None:
        self.assertIsNone(
            phase_manager.ensure_reviewer_context(None, "design", "design-quality")
        )

    def test_returns_none_when_state_has_no_name(self) -> None:
        state = mock.Mock()
        state.name = None
        self.assertIsNone(
            phase_manager.ensure_reviewer_context(state, "design", "design-quality")
        )


class DispatchInjectsContextTests(unittest.TestCase):
    """Every dispatch helper must forward the shared_context_path."""

    def setUp(self) -> None:
        self.pm = phase_manager

    def test_fast_evaluator_injects_path_into_ctx(self) -> None:
        captured: dict = {}

        def dispatcher(subagent_type, prompt, context):
            captured["ctx"] = context
            captured["prompt"] = prompt
            return {"verdict": "APPROVE", "score": 0.9, "conditions": []}

        shared = Path("/tmp/fake-phase/reviewer-context.md")
        self.pm._dispatch_fast_evaluator(
            None, "design", "design-quality",
            dispatcher=dispatcher,
            shared_context_path=shared,
        )
        self.assertEqual(
            captured["ctx"].get("shared_context_path"), str(shared)
        )
        self.assertIn("reviewer-context.md", captured["prompt"])

    def test_sequential_injects_path_into_every_reviewer(self) -> None:
        captured_ctxs: list = []

        def dispatcher(subagent_type, prompt, context):
            captured_ctxs.append(context)
            return {"verdict": "APPROVE", "score": 0.9, "conditions": []}

        shared = Path("/tmp/fake-phase/reviewer-context.md")
        self.pm._dispatch_sequential(
            None, "design", "design-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
            shared_context_path=shared,
        )
        self.assertEqual(len(captured_ctxs), 2)
        for ctx in captured_ctxs:
            self.assertEqual(ctx.get("shared_context_path"), str(shared))

    def test_parallel_injects_path_into_batch_and_per_reviewer(self) -> None:
        captured: list = []

        def dispatcher(subagent_type, prompt, context):
            captured.append({"type": subagent_type, "ctx": context})
            # Return None for the batch sentinel so we fall through to
            # per-reviewer dispatch, exercising both code paths.
            if subagent_type.endswith("_parallel_batch"):
                return None
            return {"verdict": "APPROVE", "score": 0.9, "conditions": []}

        shared = Path("/tmp/fake-phase/reviewer-context.md")
        self.pm._dispatch_parallel_and_merge(
            None, "design", "design-quality",
            ["senior-engineer", "qe-lead"],
            dispatcher=dispatcher,
            shared_context_path=shared,
        )
        # One batch call + two per-reviewer fallback calls.
        self.assertGreaterEqual(len(captured), 3)
        for entry in captured:
            self.assertEqual(
                entry["ctx"].get("shared_context_path"), str(shared)
            )

    def test_path_is_omitted_when_none(self) -> None:
        """When no shared_context_path is supplied, ctx should not
        carry the key at all (keeps the old behavior intact)."""
        captured: dict = {}

        def dispatcher(subagent_type, prompt, context):
            captured["ctx"] = context
            return {"verdict": "APPROVE", "score": 0.9, "conditions": []}

        self.pm._dispatch_fast_evaluator(
            None, "design", "design-quality",
            dispatcher=dispatcher,
        )
        self.assertNotIn("shared_context_path", captured["ctx"])


class DispatchGateReviewerIntegrationTests(unittest.TestCase):
    """_dispatch_gate_reviewer materializes reviewer-context.md and passes
    the path into the selected helper."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project_dir = Path(self.tmp.name) / "integration-proj"
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def test_materializes_context_and_forwards_to_fast_evaluator(self) -> None:
        state = mock.Mock()
        state.name = "integration-proj"

        captured: dict = {}

        def dispatcher(subagent_type, prompt, context):
            captured["ctx"] = context
            return {"verdict": "APPROVE", "score": 0.9, "conditions": []}

        with mock.patch.object(
            phase_manager, "get_project_dir", return_value=self.project_dir
        ):
            # Empty reviewers list -> fast-evaluator path.
            phase_manager._dispatch_gate_reviewer(
                state, "design", "design-quality",
                {"reviewers": [], "mode": "self-check",
                 "fallback": "gate-evaluator"},
                dispatcher=dispatcher,
            )
        # File on disk after dispatch.
        ctx_path = self.project_dir / "phases" / "design" / "reviewer-context.md"
        self.assertTrue(ctx_path.exists())
        # Path injected into reviewer context dict.
        self.assertEqual(
            captured["ctx"].get("shared_context_path"), str(ctx_path)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
