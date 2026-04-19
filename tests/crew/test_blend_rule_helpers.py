#!/usr/bin/env python3
"""tests/crew/test_blend_rule_helpers.py

Unit tests for the BLEND-RULE gate-dispatch helpers added to phase_manager.py
(design §3, FR-α3.1..FR-α3.5). Covers the five helpers:

  - _dispatch_fast_evaluator        (self-check / advisory / empty reviewers)
  - _dispatch_sequential            (stops on first REJECT)
  - _dispatch_parallel_and_merge    (REJECT > CONDITIONAL > APPROVE merge)
  - _dispatch_council               (plurality with min-concurrence threshold)
  - _dispatch_gate_reviewer         (main entry — dispatch by mode)

Stdlib-only; no sleep-based sync (T2); single-assertion focus where
practical (T4); descriptive names (T5).
"""

import unittest
from pathlib import Path
import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


def _mock_dispatcher_factory(verdict_map):
    """Return a dispatcher callable that looks up verdicts by reviewer name.

    `verdict_map` is a dict
       reviewer_name -> {verdict, score, reason, conditions}
    When the subagent_type starts with `wicked-garden:crew:` we parse the
    suffix as the reviewer name. `_parallel_batch` is treated as a batched
    dispatch — we return the list of per-reviewer verdicts from context.
    """
    calls = []

    def dispatcher(subagent_type, prompt, context):
        calls.append({"subagent_type": subagent_type, "context": context})
        # Parallel batch sentinel: return the list of reviewer verdicts.
        if subagent_type.endswith("_parallel_batch"):
            reviewers = context.get("reviewers") or []
            return [
                verdict_map.get(
                    r, {"verdict": "CONDITIONAL", "score": 0.0, "reason": "unknown"}
                )
                for r in reviewers
            ]
        # Single reviewer dispatch.
        name = subagent_type.split(":")[-1]
        return verdict_map.get(
            name, {"verdict": "CONDITIONAL", "score": 0.0, "reason": "unknown"}
        )

    dispatcher.calls = calls
    return dispatcher


# ---------------------------------------------------------------------------
# _dispatch_fast_evaluator
# ---------------------------------------------------------------------------


class TestFastEvaluator(unittest.TestCase):
    """Fast path: empty reviewers / self-check / advisory."""

    def test_returns_stub_when_dispatcher_none(self):
        """Without a dispatcher, fast-evaluator returns a CONDITIONAL stub."""
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=None,
        )
        self.assertEqual(result["verdict"], "CONDITIONAL")

    def test_uses_dispatcher_when_provided(self):
        """With a dispatcher, fast-evaluator returns its verdict."""
        dispatcher = _mock_dispatcher_factory({
            "gate-evaluator": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "APPROVE")

    def test_records_dispatch_mode_fast_evaluator(self):
        """Fast evaluator sets dispatch_mode='fast-evaluator'."""
        dispatcher = _mock_dispatcher_factory({
            "gate-evaluator": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=dispatcher,
        )
        self.assertEqual(result["dispatch_mode"], "fast-evaluator")


# ---------------------------------------------------------------------------
# _dispatch_sequential
# ---------------------------------------------------------------------------


class TestSequential(unittest.TestCase):
    """Sequential dispatch — stops on first REJECT."""

    def test_all_approve_returns_approve(self):
        """Sequential over two APPROVEs merges to APPROVE."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.8, "reason": "ok"},
        })
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "APPROVE")

    def test_stops_on_first_reject(self):
        """Sequential short-circuits on REJECT; later reviewers not called."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "REJECT", "score": 0.2, "reason": "fail"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        # Only one dispatcher call — second reviewer not invoked.
        self.assertEqual(len(dispatcher.calls), 1)

    def test_reject_short_circuit_yields_reject_verdict(self):
        """After short-circuit, merged verdict is REJECT."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "REJECT", "score": 0.2, "reason": "fail"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "REJECT")

    def test_conditional_does_not_short_circuit(self):
        """CONDITIONAL does NOT short-circuit — later reviewers still run."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "CONDITIONAL", "score": 0.6,
                                "reason": "warn", "conditions": [{"id": "c1"}]},
            "security-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(len(dispatcher.calls), 2)


# ---------------------------------------------------------------------------
# _dispatch_parallel_and_merge
# ---------------------------------------------------------------------------


class TestParallelMerge(unittest.TestCase):
    """Parallel dispatch + merge — REJECT > CONDITIONAL > APPROVE."""

    def test_all_approve_merges_to_approve(self):
        """All-APPROVE merge yields APPROVE."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.8, "reason": "ok"},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "APPROVE")

    def test_any_reject_merges_to_reject(self):
        """Any-REJECT merge yields REJECT even with APPROVE peers."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "security-engineer": {"verdict": "REJECT", "score": 0.1,
                                  "reason": "vuln"},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "REJECT")

    def test_any_conditional_merges_to_conditional(self):
        """CONDITIONAL + APPROVE (no REJECT) merges to CONDITIONAL."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "security-engineer": {"verdict": "CONDITIONAL", "score": 0.7,
                                  "reason": "warn",
                                  "conditions": [{"id": "c1", "desc": "fix"}]},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "CONDITIONAL")

    def test_conditional_unions_all_conditions(self):
        """All CONDITIONAL's `conditions` arrays union into the merged result."""
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "CONDITIONAL", "score": 0.7,
                   "conditions": [{"id": "c1"}]},
            "r2": {"verdict": "CONDITIONAL", "score": 0.6,
                   "conditions": [{"id": "c2"}]},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality", ["r1", "r2"],
            dispatcher=dispatcher,
        )
        self.assertEqual(len(result["conditions"]), 2)

    def test_merged_score_is_min_of_reviewer_scores(self):
        """Merged score is the minimum across reviewer scores (conservative)."""
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "r2": {"verdict": "APPROVE", "score": 0.7, "reason": "ok"},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality", ["r1", "r2"],
            dispatcher=dispatcher,
        )
        self.assertAlmostEqual(result["score"], 0.7)

    def test_banned_reviewer_yields_reject(self):
        """A banned reviewer identity short-circuits to REJECT."""
        dispatcher = _mock_dispatcher_factory({
            "just-finish-auto": {"verdict": "APPROVE", "score": 0.9,
                                 "reason": "ok"},
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9,
                                "reason": "ok"},
        })
        # The mock returns `reviewer` as the key; the merge helper inspects
        # reviewer name. Ensure the mock echoes the reviewer identity.
        dispatcher2 = _mock_dispatcher_factory({
            "just-finish-auto": {"verdict": "APPROVE", "score": 0.9,
                                 "reason": "ok", "reviewer": "just-finish-auto"},
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9,
                                "reason": "ok", "reviewer": "senior-engineer"},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["just-finish-auto", "senior-engineer"],
            dispatcher=dispatcher2,
        )
        self.assertEqual(result["verdict"], "REJECT")


# ---------------------------------------------------------------------------
# _dispatch_council
# ---------------------------------------------------------------------------


class TestCouncil(unittest.TestCase):
    """Council dispatch — plurality vote with min-concurrence threshold."""

    def test_unanimous_approve_passes_threshold(self):
        """Unanimous APPROVE yields APPROVE (concurrence = 1.0)."""
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9},
            "r2": {"verdict": "APPROVE", "score": 0.8},
            "r3": {"verdict": "APPROVE", "score": 0.85},
        })
        result = phase_manager._dispatch_council(
            None, "design", "design-quality", ["r1", "r2", "r3"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "APPROVE")

    def test_split_verdicts_below_threshold_downgrade(self):
        """2-APPROVE + 2-CONDITIONAL at threshold 0.6 downgrades to CONDITIONAL.

        Plurality is a tie — 2/4 = 0.5 for either APPROVE or CONDITIONAL. Our
        tie-break picks CONDITIONAL (safer). Concurrence 0.5 < 0.6 threshold
        downgrades APPROVE paths, but CONDITIONAL plurality remains CONDITIONAL.
        """
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9},
            "r2": {"verdict": "APPROVE", "score": 0.8},
            "r3": {"verdict": "CONDITIONAL", "score": 0.6,
                   "conditions": [{"id": "c1"}]},
            "r4": {"verdict": "CONDITIONAL", "score": 0.5,
                   "conditions": [{"id": "c2"}]},
        })
        result = phase_manager._dispatch_council(
            None, "design", "design-quality", ["r1", "r2", "r3", "r4"],
            dispatcher=dispatcher, min_concurrence=0.6,
        )
        self.assertEqual(result["verdict"], "CONDITIONAL")

    def test_low_concurrence_approve_downgrades_to_conditional(self):
        """2-APPROVE + 1-CONDITIONAL at threshold 0.8 downgrades APPROVE.

        Concurrence 2/3 = 0.667 < 0.8 threshold → downgrade to CONDITIONAL.
        """
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9},
            "r2": {"verdict": "APPROVE", "score": 0.8},
            "r3": {"verdict": "CONDITIONAL", "score": 0.6,
                   "conditions": [{"id": "c1"}]},
        })
        result = phase_manager._dispatch_council(
            None, "design", "design-quality", ["r1", "r2", "r3"],
            dispatcher=dispatcher, min_concurrence=0.8,
        )
        self.assertEqual(result["verdict"], "CONDITIONAL")

    def test_reject_short_circuits_council(self):
        """Any REJECT in council short-circuits to REJECT regardless of plurality."""
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9},
            "r2": {"verdict": "APPROVE", "score": 0.85},
            "r3": {"verdict": "REJECT", "score": 0.1, "reason": "veto"},
        })
        result = phase_manager._dispatch_council(
            None, "design", "design-quality", ["r1", "r2", "r3"],
            dispatcher=dispatcher, min_concurrence=0.5,
        )
        self.assertEqual(result["verdict"], "REJECT")

    def test_council_records_concurrence_score(self):
        """Council result exposes the concurrence ratio for audit."""
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9},
            "r2": {"verdict": "APPROVE", "score": 0.85},
            "r3": {"verdict": "APPROVE", "score": 0.8},
        })
        result = phase_manager._dispatch_council(
            None, "design", "design-quality", ["r1", "r2", "r3"],
            dispatcher=dispatcher, min_concurrence=0.6,
        )
        self.assertAlmostEqual(result["concurrence"], 1.0)


# ---------------------------------------------------------------------------
# _dispatch_gate_reviewer (main entry)
# ---------------------------------------------------------------------------


class TestGateReviewerEntry(unittest.TestCase):
    """Main BLEND-RULE entry point routing by policy mode."""

    def test_empty_reviewers_routes_to_fast_evaluator(self):
        """Empty reviewers → fast-evaluator path."""
        dispatcher = _mock_dispatcher_factory({
            "gate-evaluator": {"verdict": "APPROVE", "score": 0.8, "reason": "ok"},
        })
        policy_entry = {
            "reviewers": [], "mode": "self-check", "fallback": "gate-evaluator",
        }
        result = phase_manager._dispatch_gate_reviewer(
            None, "design", "design-quality", policy_entry,
            dispatcher=dispatcher,
        )
        self.assertEqual(result["dispatch_mode"], "fast-evaluator")

    def test_sequential_mode_routes_to_sequential(self):
        """mode=sequential → _dispatch_sequential path."""
        dispatcher = _mock_dispatcher_factory({
            "solution-architect": {"verdict": "APPROVE", "score": 0.9,
                                   "reason": "ok"},
        })
        policy_entry = {
            "reviewers": ["solution-architect"],
            "mode": "sequential",
            "fallback": "senior-engineer",
        }
        result = phase_manager._dispatch_gate_reviewer(
            None, "design", "design-quality", policy_entry,
            dispatcher=dispatcher,
        )
        self.assertEqual(result["dispatch_mode"], "sequential")

    def test_parallel_mode_routes_to_parallel(self):
        """mode=parallel → _dispatch_parallel_and_merge path."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9},
            "security-engineer": {"verdict": "APPROVE", "score": 0.9},
        })
        policy_entry = {
            "reviewers": ["senior-engineer", "security-engineer"],
            "mode": "parallel", "fallback": "senior-engineer",
        }
        result = phase_manager._dispatch_gate_reviewer(
            None, "build", "code-quality", policy_entry,
            dispatcher=dispatcher,
        )
        self.assertEqual(result["dispatch_mode"], "parallel")

    def test_council_mode_routes_to_council(self):
        """mode=council → _dispatch_council path."""
        dispatcher = _mock_dispatcher_factory({
            "r1": {"verdict": "APPROVE", "score": 0.9},
            "r2": {"verdict": "APPROVE", "score": 0.85},
            "r3": {"verdict": "APPROVE", "score": 0.8},
        })
        policy_entry = {
            "reviewers": ["r1", "r2", "r3"],
            "mode": "council", "fallback": "senior-engineer",
        }
        result = phase_manager._dispatch_gate_reviewer(
            None, "design", "design-quality", policy_entry,
            dispatcher=dispatcher,
        )
        self.assertEqual(result["dispatch_mode"], "council")

    def test_missing_policy_entry_returns_stub(self):
        """A None or non-dict policy entry returns a conservative stub."""
        result = phase_manager._dispatch_gate_reviewer(
            None, "design", "design-quality", None,  # type: ignore[arg-type]
            dispatcher=None,
        )
        self.assertEqual(result["verdict"], "CONDITIONAL")


# ---------------------------------------------------------------------------
# COND-TG-3 — BLEND dispatcher failures must surface, not silently APPROVE
# ---------------------------------------------------------------------------


def _raising_dispatcher(exc_factory=lambda: RuntimeError("simulated agent failure")):
    """Return a dispatcher callable that unconditionally raises.

    Used to verify that BLEND-RULE helpers never return a silent APPROVE
    verdict when the underlying dispatch call fails.
    """
    calls = []

    def dispatcher(subagent_type, prompt, context):
        calls.append({"subagent_type": subagent_type, "context": context})
        raise exc_factory()

    dispatcher.calls = calls
    return dispatcher


class TestBlendHelpersPropagateOrSurfaceFailure(unittest.TestCase):
    """COND-TG-3 — every BLEND helper must refuse to silently APPROVE on error.

    The helpers either propagate the exception or return a clearly-marked
    failure verdict (CONDITIONAL or REJECT with a `dispatch-error:` reason).
    What they must NEVER do is swallow the error and return APPROVE, which
    would let a broken agent quietly advance a phase.
    """

    def test_fast_evaluator_does_not_return_approve_on_raise(self):
        """_dispatch_fast_evaluator surfaces dispatcher failure, not APPROVE."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")

    def test_sequential_does_not_return_approve_on_raise(self):
        """_dispatch_sequential surfaces dispatcher failure, not APPROVE."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")

    def test_parallel_does_not_return_approve_on_raise(self):
        """_dispatch_parallel_and_merge surfaces dispatcher failure, not APPROVE."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")

    def test_council_does_not_return_approve_on_raise(self):
        """_dispatch_council surfaces dispatcher failure, not APPROVE."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_council(
            None, "design", "design-quality",
            ["r1", "r2", "r3"],
            dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")


# ---------------------------------------------------------------------------
# #473 — Multi-reviewer dispatch-count invariant
# ---------------------------------------------------------------------------


def _under_counting_dispatcher(verdict, *, increment: int = 0):
    """Return a dispatcher that reports fewer calls than it actually made.

    When ``increment == 0`` (default), the ``.calls`` attribute never grows
    regardless of how many times the dispatcher is called — simulating one
    agent emulating N reviewers without dispatching N Agent calls.
    """
    calls_visible = []

    def dispatcher(subagent_type, prompt, context):
        # Intentionally do NOT append every invocation — simulate undercounting.
        if increment and (len(calls_visible) < increment):
            calls_visible.append({"subagent_type": subagent_type})
        return verdict

    dispatcher.calls = calls_visible
    return dispatcher


class TestMultiReviewerDispatchCountInvariant(unittest.TestCase):
    """#473 — Parallel / council must dispatch N calls for N reviewers.

    An injected mock dispatcher that under-counts invocations must cause
    the helper to raise ``DispatchCountError``. The invariant protects
    against one agent emulating N reviewers in a single call.
    """

    def test_parallel_raises_dispatch_count_error_on_undercount(self):
        """Parallel fallback loop raises DispatchCountError when undercounted."""
        # No batched path — dispatcher raises on the sentinel so we fall
        # through to the per-reviewer loop, where the undercount is visible.
        verdict = {"verdict": "APPROVE", "score": 0.9, "reason": "ok"}
        dispatcher = _under_counting_dispatcher(verdict, increment=0)
        with self.assertRaises(phase_manager.DispatchCountError):
            phase_manager._dispatch_parallel_and_merge(
                None, "build", "code-quality",
                ["senior-engineer", "security-engineer", "devsecops-engineer"],
                dispatcher=dispatcher,
            )

    def test_council_raises_dispatch_count_error_on_undercount(self):
        """Council dispatch inherits the invariant via parallel-and-merge."""
        verdict = {"verdict": "APPROVE", "score": 0.9}
        dispatcher = _under_counting_dispatcher(verdict, increment=0)
        with self.assertRaises(phase_manager.DispatchCountError):
            phase_manager._dispatch_council(
                None, "design", "design-quality",
                ["r1", "r2", "r3"],
                dispatcher=dispatcher,
            )

    def test_parallel_passes_when_count_matches(self):
        """Honest mock with .calls growing once-per-invocation does not raise."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9},
            "security-engineer": {"verdict": "APPROVE", "score": 0.85},
        })
        # Poison the batched path so the fallback loop runs. We do this
        # by wrapping the dispatcher — the batched call raises, subsequent
        # per-reviewer calls return honest verdicts.
        original = dispatcher

        def fallback_only(subagent_type, prompt, context):
            if subagent_type.endswith("_parallel_batch"):
                raise RuntimeError("no-batch-support")
            return original(subagent_type, prompt, context)

        fallback_only.calls = original.calls
        # Should NOT raise — each reviewer got its own dispatcher call.
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=fallback_only,
        )
        self.assertEqual(result["verdict"], "APPROVE")

    def test_batched_path_raises_on_short_result_list(self):
        """Batched path with N results != len(reviewers) also raises."""

        def short_batched_dispatcher(subagent_type, prompt, context):
            if subagent_type.endswith("_parallel_batch"):
                # Return only 1 result for 3 reviewers — impersonation attempt.
                return [{"verdict": "APPROVE", "score": 0.9}]
            return {"verdict": "APPROVE", "score": 0.9}

        short_batched_dispatcher.calls = []
        with self.assertRaises(phase_manager.DispatchCountError):
            phase_manager._dispatch_parallel_and_merge(
                None, "build", "code-quality",
                ["r1", "r2", "r3"],
                dispatcher=short_batched_dispatcher,
            )


# ---------------------------------------------------------------------------
# #476 — Blind-reviewer context sanitization
# ---------------------------------------------------------------------------


class TestBlindReviewerContext(unittest.TestCase):
    """#476 — Reviewer briefs must not carry the executor's self-assessment.

    The sanitizer strips ``self_score``, ``self_verdict``, and
    ``executor_notes`` from any context dict passed to a dispatcher. Tests
    use the capture-all mock to inspect what the dispatcher actually
    received.
    """

    def _capture_dispatcher(self, verdict_map):
        """Return a dispatcher that records (subagent, prompt, context)."""
        calls = []

        def dispatcher(subagent_type, prompt, context):
            # Deep-copy context so the test sees exactly what was passed.
            import copy
            calls.append({
                "subagent_type": subagent_type,
                "prompt": prompt,
                "context": copy.deepcopy(context),
            })
            if subagent_type.endswith("_parallel_batch"):
                reviewers = context.get("reviewers") or []
                return [
                    verdict_map.get(r, {"verdict": "CONDITIONAL", "score": 0.0})
                    for r in reviewers
                ]
            name = subagent_type.split(":")[-1]
            return verdict_map.get(
                name, {"verdict": "CONDITIONAL", "score": 0.0},
            )

        dispatcher.calls = calls
        return dispatcher

    def test_strip_helper_removes_known_keys(self):
        """_strip_executor_self_score removes all three self-score keys."""
        raw = {
            "gate_name": "code-quality",
            "phase": "build",
            "self_score": 0.95,
            "self_verdict": "APPROVE",
            "executor_notes": "lgtm",
            "reviewer": "senior-engineer",
        }
        clean = phase_manager._strip_executor_self_score(raw)
        self.assertNotIn("self_score", clean)
        self.assertNotIn("self_verdict", clean)
        self.assertNotIn("executor_notes", clean)

    def test_strip_helper_preserves_allowed_keys(self):
        """_strip_executor_self_score keeps every non-self-score key intact."""
        raw = {
            "gate_name": "code-quality",
            "phase": "build",
            "self_score": 0.95,
            "reviewer": "senior-engineer",
        }
        clean = phase_manager._strip_executor_self_score(raw)
        self.assertEqual(clean.get("gate_name"), "code-quality")
        self.assertEqual(clean.get("reviewer"), "senior-engineer")

    def test_parallel_dispatcher_receives_no_self_score(self):
        """No context delivered to the dispatcher in parallel mode carries self_score."""
        dispatcher = self._capture_dispatcher({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9},
            "security-engineer": {"verdict": "APPROVE", "score": 0.85},
        })
        # Poison the batched path so we exercise the per-reviewer fallback.
        original = dispatcher

        def fallback_only(subagent_type, prompt, context):
            if subagent_type.endswith("_parallel_batch"):
                raise RuntimeError("no-batch")
            return original(subagent_type, prompt, context)

        fallback_only.calls = original.calls
        phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=fallback_only,
        )
        for entry in original.calls:
            ctx = entry["context"] or {}
            self.assertNotIn("self_score", ctx)
            self.assertNotIn("self_verdict", ctx)
            self.assertNotIn("executor_notes", ctx)

    def test_sequential_dispatcher_receives_no_self_score(self):
        """No context delivered to the dispatcher in sequential mode carries self_score."""
        dispatcher = self._capture_dispatcher({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9},
        })
        phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer"],
            dispatcher=dispatcher,
        )
        for entry in dispatcher.calls:
            ctx = entry["context"] or {}
            self.assertNotIn("self_score", ctx)
            self.assertNotIn("self_verdict", ctx)
            self.assertNotIn("executor_notes", ctx)

    def test_fast_evaluator_dispatcher_receives_no_self_score(self):
        """Fast-evaluator dispatcher context has no self_* keys."""
        dispatcher = self._capture_dispatcher({
            "gate-evaluator": {"verdict": "APPROVE", "score": 0.9},
        })
        phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality",
            dispatcher=dispatcher,
        )
        for entry in dispatcher.calls:
            ctx = entry["context"] or {}
            self.assertNotIn("self_score", ctx)
            self.assertNotIn("self_verdict", ctx)
            self.assertNotIn("executor_notes", ctx)


if __name__ == "__main__":
    unittest.main()
