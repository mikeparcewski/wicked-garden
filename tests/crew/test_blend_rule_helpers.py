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


if __name__ == "__main__":
    unittest.main()
