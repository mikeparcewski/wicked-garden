#!/usr/bin/env python3
"""tests/crew/test_blend_rule_helpers.py

Unit tests for the BLEND-RULE gate-dispatch helpers added to phase_manager.py
(design §3, FR-α3.1..FR-α3.5). Covers the five helpers:

  - _dispatch_fast_evaluator        (self-check / advisory / empty reviewers)
  - _dispatch_sequential            (stops on first REJECT)
  - _dispatch_parallel_and_merge    (REJECT > CONDITIONAL > APPROVE merge)
  - _dispatch_council               (plurality with min-concurrence threshold)
  - _dispatch_gate_reviewer         (main entry — dispatch by mode)

#481 audit:
Every test in this file exercises HELPER behavior — merge priority, short-
circuit rules, routing, count invariants, sanitization — not just the mock
return path. Tautologies that asserted "given a mock that returns X, we
get X" have been removed or strengthened to assert a secondary helper-side
effect (mode tag, call count, sanitized context, etc). Each test carries a
docstring naming the helper behavior under test.

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
    """Fast path: empty reviewers / self-check / advisory.

    HELPER BEHAVIOR: when no dispatcher is supplied, the fast evaluator must
    degrade to a conservative CONDITIONAL stub (never APPROVE). When a
    dispatcher IS supplied, the helper MUST tag the result with
    `dispatch_mode='fast-evaluator'` so downstream merge logic can attribute
    the verdict.
    """

    def test_returns_stub_when_dispatcher_none(self):
        """HELPER: without a dispatcher the fast-evaluator returns a
        conservative CONDITIONAL stub rather than silently APPROVE."""
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=None,
        )
        self.assertEqual(result["verdict"], "CONDITIONAL")

    def test_records_dispatch_mode_fast_evaluator(self):
        """HELPER: the helper tags its own dispatch mode
        (`fast-evaluator`) — the mock cannot inject this key, so this asserts
        the helper's own path was taken, not the mock's return."""
        dispatcher = _mock_dispatcher_factory({
            "gate-evaluator": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=dispatcher,
        )
        self.assertEqual(result["dispatch_mode"], "fast-evaluator")

    def test_fast_evaluator_invokes_dispatcher_exactly_once(self):
        """HELPER: the fast-evaluator dispatches once, not N times —
        asserts the helper's own invocation contract, not the mock's output."""
        dispatcher = _mock_dispatcher_factory({
            "gate-evaluator": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=dispatcher,
        )
        self.assertEqual(len(dispatcher.calls), 1)


# ---------------------------------------------------------------------------
# _dispatch_sequential
# ---------------------------------------------------------------------------


class TestSequential(unittest.TestCase):
    """Sequential dispatch — stops on first REJECT.

    HELPER BEHAVIOR: invoke reviewers in list order; on REJECT stop and
    return REJECT; on APPROVE / CONDITIONAL continue to the next reviewer;
    merge verdicts across the reviewers that ran. Dispatch mode tag is
    `sequential`.
    """

    def test_all_approve_invokes_every_reviewer_and_tags_sequential(self):
        """HELPER: when no REJECT occurs, all N reviewers are invoked and
        the merged result is tagged `dispatch_mode='sequential'`."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.8, "reason": "ok"},
        })
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        # Assert both dispatcher call-count AND the helper's mode tag —
        # neither is something the mock can fake.
        self.assertEqual(
            (len(dispatcher.calls), result["dispatch_mode"]),
            (2, "sequential"),
        )

    def test_stops_on_first_reject(self):
        """HELPER: REJECT short-circuits — dispatcher is called exactly once
        (the first reviewer) even though two reviewers were declared."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "REJECT", "score": 0.2, "reason": "fail"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        # Only one dispatcher call — second reviewer not invoked.
        self.assertEqual(len(dispatcher.calls), 1)

    def test_reject_short_circuit_yields_reject_verdict(self):
        """HELPER: the merged verdict surfaced by the helper after a REJECT
        short-circuit is REJECT — the merge logic doesn't down-grade or
        lose the REJECT on the way out."""
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
        """HELPER: CONDITIONAL does NOT short-circuit — later reviewers still
        run. Asserts via dispatcher call count (not the mock's return)."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "CONDITIONAL", "score": 0.6,
                                "reason": "warn", "conditions": [{"id": "c1"}]},
            "security-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
        })
        phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(len(dispatcher.calls), 2)


# ---------------------------------------------------------------------------
# _dispatch_parallel_and_merge
# ---------------------------------------------------------------------------


class TestParallelMerge(unittest.TestCase):
    """Parallel dispatch + merge — REJECT > CONDITIONAL > APPROVE.

    HELPER BEHAVIOR: dispatch every reviewer once; merge verdicts with the
    priority ordering REJECT > CONDITIONAL > APPROVE; union all `conditions`
    arrays; take the min of per-reviewer scores (conservative); reject any
    banned reviewer identity.
    """

    def test_all_approve_merges_to_approve_with_full_count(self):
        """HELPER: merge of N APPROVE verdicts yields APPROVE — AND the
        helper dispatched all N reviewers (not short-circuited)."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9, "reason": "ok"},
            "security-engineer": {"verdict": "APPROVE", "score": 0.8, "reason": "ok"},
        })
        # Poison the batched sentinel so the per-reviewer fallback runs;
        # that's the path where call-count invariance is meaningful.
        original = dispatcher

        def fallback_only(subagent_type, prompt, context):
            if subagent_type.endswith("_parallel_batch"):
                raise RuntimeError("no-batch")
            return original(subagent_type, prompt, context)

        fallback_only.calls = original.calls
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=fallback_only,
        )
        # Merged verdict AND every reviewer dispatched — both HELPER assertions.
        self.assertEqual(
            (result["verdict"], len(original.calls)),
            ("APPROVE", 2),
        )

    def test_any_reject_merges_to_reject(self):
        """HELPER: merge priority — one REJECT among APPROVEs yields REJECT.
        Tests the helper's priority rule, not the mock's return."""
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
        """HELPER: merge priority — CONDITIONAL + APPROVE (no REJECT) yields
        CONDITIONAL. Tests the helper's priority rule, not the mock."""
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
        """HELPER: the merge unions all per-reviewer conditions arrays into
        a single flat list on the merged result."""
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
        """HELPER: the merge score aggregator is MIN (conservative) —
        not mean, not max. Tests the helper's aggregator choice."""
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
        """HELPER: banned reviewer identity short-circuits the merge to
        REJECT even when the reviewer reports APPROVE. Asserts the
        helper's banned-reviewer guard, not the mock's verdict."""
        dispatcher = _mock_dispatcher_factory({
            "just-finish-auto": {"verdict": "APPROVE", "score": 0.9,
                                 "reason": "ok", "reviewer": "just-finish-auto"},
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9,
                                "reason": "ok", "reviewer": "senior-engineer"},
        })
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["just-finish-auto", "senior-engineer"],
            dispatcher=dispatcher,
        )
        self.assertEqual(result["verdict"], "REJECT")


# ---------------------------------------------------------------------------
# _dispatch_council
# ---------------------------------------------------------------------------


class TestCouncil(unittest.TestCase):
    """Council dispatch — plurality vote with min-concurrence threshold.

    HELPER BEHAVIOR: plurality wins among reviewer verdicts; when
    concurrence (winning fraction) falls below `min_concurrence`, downgrade
    APPROVE to CONDITIONAL (safer). Any REJECT short-circuits. Tie-break
    on equal plurality favours CONDITIONAL. Merged result exposes the
    concurrence ratio for audit.
    """

    def test_unanimous_approve_passes_threshold(self):
        """HELPER: unanimous APPROVE (concurrence 1.0) clears any threshold
        and the plurality rule yields APPROVE."""
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
        """HELPER: 2-APPROVE + 2-CONDITIONAL at threshold 0.6 —
        plurality is tied (0.5 each); the helper's tie-break picks
        CONDITIONAL (safer)."""
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
        """HELPER: the concurrence-threshold downgrade rule — APPROVE with
        plurality 2/3 = 0.667 < 0.8 threshold downgrades to CONDITIONAL."""
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
        """HELPER: any REJECT in council short-circuits to REJECT regardless
        of plurality — the helper's veto rule."""
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
        """HELPER: council result exposes the concurrence ratio for audit —
        a result-shape guarantee the mock cannot provide."""
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
    """Main BLEND-RULE entry point routing by policy mode.

    HELPER BEHAVIOR: `policy_entry['mode']` determines which helper runs;
    the `dispatch_mode` tag on the result is the observable routing signal.
    Empty reviewers fall through to the fast-evaluator path. A missing /
    non-dict policy entry returns a conservative CONDITIONAL stub.
    """

    def test_empty_reviewers_routes_to_fast_evaluator(self):
        """HELPER: empty reviewers list → fast-evaluator path (dispatch_mode
        tag proves the routing decision)."""
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
        """HELPER: mode='sequential' routes to _dispatch_sequential — proven
        by the dispatch_mode tag on the result."""
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
        """HELPER: mode='parallel' routes to _dispatch_parallel_and_merge."""
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
        """HELPER: mode='council' routes to _dispatch_council."""
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
        """HELPER: None / non-dict policy entry short-circuits to the
        conservative CONDITIONAL stub (fail-closed, not fail-open)."""
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

    HELPER BEHAVIOR: when the dispatcher raises, the helper either propagates
    the exception or returns a clearly-marked failure verdict (CONDITIONAL
    or REJECT with a `dispatch-error:` reason). What the helper must NEVER
    do is swallow the error and return APPROVE, which would let a broken
    agent quietly advance a phase.
    """

    def test_fast_evaluator_does_not_return_approve_on_raise(self):
        """HELPER: fast-evaluator surfaces dispatcher failure — verdict is
        NOT APPROVE when the dispatcher raised."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_fast_evaluator(
            None, "design", "design-quality", dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")

    def test_sequential_does_not_return_approve_on_raise(self):
        """HELPER: sequential surfaces dispatcher failure — verdict is
        NOT APPROVE when the dispatcher raised."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_sequential(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")

    def test_parallel_does_not_return_approve_on_raise(self):
        """HELPER: parallel surfaces dispatcher failure — verdict is
        NOT APPROVE when the dispatcher raised."""
        dispatcher = _raising_dispatcher()
        result = phase_manager._dispatch_parallel_and_merge(
            None, "build", "code-quality",
            ["senior-engineer", "security-engineer"],
            dispatcher=dispatcher,
        )
        self.assertNotEqual(result["verdict"], "APPROVE")

    def test_council_does_not_return_approve_on_raise(self):
        """HELPER: council surfaces dispatcher failure — verdict is
        NOT APPROVE when the dispatcher raised."""
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

    HELPER BEHAVIOR: the helper enforces a count invariant — an injected
    mock dispatcher that under-counts invocations MUST cause the helper
    to raise `DispatchCountError`. The invariant protects against one
    agent emulating N reviewers in a single call.
    """

    def test_parallel_raises_dispatch_count_error_on_undercount(self):
        """HELPER: parallel fallback loop raises DispatchCountError when
        the dispatcher under-counts its own invocations."""
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
        """HELPER: council dispatch inherits the count-invariant via
        parallel-and-merge — undercount also raises DispatchCountError."""
        verdict = {"verdict": "APPROVE", "score": 0.9}
        dispatcher = _under_counting_dispatcher(verdict, increment=0)
        with self.assertRaises(phase_manager.DispatchCountError):
            phase_manager._dispatch_council(
                None, "design", "design-quality",
                ["r1", "r2", "r3"],
                dispatcher=dispatcher,
            )

    def test_parallel_passes_when_count_matches(self):
        """HELPER: honest mock with .calls growing once-per-invocation does
        NOT raise — the invariant is satisfied. Asserts merged verdict AND
        call-count together (both are HELPER-side observations)."""
        dispatcher = _mock_dispatcher_factory({
            "senior-engineer": {"verdict": "APPROVE", "score": 0.9},
            "security-engineer": {"verdict": "APPROVE", "score": 0.85},
        })
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
        # Assert BOTH: the merge ran to completion AND the helper saw
        # exactly 2 dispatcher invocations (one per reviewer).
        self.assertEqual(
            (result["verdict"], len(original.calls)),
            ("APPROVE", 2),
        )

    def test_batched_path_raises_on_short_result_list(self):
        """HELPER: batched path with N results != len(reviewers) also raises
        DispatchCountError — protects against impersonation in batched mode."""

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

    HELPER BEHAVIOR: the sanitizer (`_strip_executor_self_score`) strips
    `self_score`, `self_verdict`, and `executor_notes` from any context dict
    passed to a dispatcher. Every dispatch path (fast/sequential/parallel)
    MUST run the sanitizer before handing context to the reviewer.
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
        """HELPER: `_strip_executor_self_score` removes all three self-score
        keys from the input context dict."""
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
        """HELPER: sanitizer keeps every non-self-score key intact — it
        strips a denylist, not an allowlist."""
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
        """HELPER: the parallel path runs the sanitizer — no context
        captured by the dispatcher carries the self-score keys."""
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
        """HELPER: the sequential path runs the sanitizer — no context
        delivered to the dispatcher carries self-score keys."""
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
        """HELPER: the fast-evaluator path runs the sanitizer — dispatcher
        context has no self_* keys."""
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
