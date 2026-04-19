"""Unit tests for augment-cap enforcement in _run_checkpoint_reanalysis (AC-9).

Scenario: scenarios/crew/phase-boundary-reeval.md Case 3 — at most 2 augment
mutations may be applied per phase across the project lifetime.  Excess
augments are deferred with why="augment-cap-exceeded" and become open
questions only (no TaskCreate calls).

All tests are deterministic (no wall-clock, no random, no sleep).
Stdlib-only.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import phase_manager as pm
from phase_manager import (
    ProjectState,
    _apply_augment_cap,
    _count_prior_augments_for_phase,
    _run_checkpoint_reanalysis,
    _AUGMENT_CAP_PER_PHASE,
    _AUGMENT_CAP_DEFER_REASON,
)


def _make_state(name="augment-cap-test") -> ProjectState:
    state = ProjectState(
        name=name,
        current_phase="design",
        created_at="2026-04-18T00:00:00Z",
    )
    state.phase_plan = ["clarify", "design", "build", "review"]
    state.extras["phase_plan_mode"] = "facilitator"
    return state


# ---------------------------------------------------------------------------
# Pure helper: _apply_augment_cap
# ---------------------------------------------------------------------------


class TestApplyAugmentCapHelper(unittest.TestCase):
    """_apply_augment_cap is the pure splitter — no I/O, no globals."""

    def test_under_cap_all_applied(self):
        mutations = [
            {"op": "augment", "task_id": "a", "why": "A"},
            {"op": "augment", "task_id": "b", "why": "B"},
        ]
        applied, deferred = _apply_augment_cap(mutations, prior_count=0)
        self.assertEqual(len(applied), 2)
        self.assertEqual(deferred, [])

    def test_over_cap_extras_deferred_with_reason(self):
        mutations = [
            {"op": "augment", "task_id": "a", "why": "A"},
            {"op": "augment", "task_id": "b", "why": "B"},
            {"op": "augment", "task_id": "c", "why": "C"},
            {"op": "augment", "task_id": "d", "why": "D"},
        ]
        applied, deferred = _apply_augment_cap(mutations, prior_count=0)
        self.assertEqual(len(applied), 2)
        self.assertEqual(len(deferred), 2)
        for m in deferred:
            self.assertEqual(m["why"], _AUGMENT_CAP_DEFER_REASON)
        # Order preserved: first two fill the budget
        self.assertEqual([m["task_id"] for m in applied], ["a", "b"])
        self.assertEqual([m["task_id"] for m in deferred], ["c", "d"])

    def test_prior_count_eats_budget(self):
        """If 2 augments already applied historically, all new augments defer."""
        mutations = [
            {"op": "augment", "task_id": "x", "why": "X"},
            {"op": "augment", "task_id": "y", "why": "Y"},
        ]
        applied, deferred = _apply_augment_cap(mutations, prior_count=2)
        self.assertEqual(applied, [])
        self.assertEqual(len(deferred), 2)
        for m in deferred:
            self.assertEqual(m["why"], _AUGMENT_CAP_DEFER_REASON)

    def test_non_augment_mutations_pass_through(self):
        """re_tier and prune mutations are not counted against the cap."""
        mutations = [
            {"op": "re_tier", "new_rigor_tier": "standard", "why": "R"},
            {"op": "prune", "task_id": "p", "why": "P"},
            {"op": "augment", "task_id": "a", "why": "A"},
            {"op": "augment", "task_id": "b", "why": "B"},
            {"op": "augment", "task_id": "c", "why": "C"},
        ]
        applied, deferred = _apply_augment_cap(mutations, prior_count=0)
        # 2 non-augments + 2 capped augments = 4 applied
        self.assertEqual(len(applied), 4)
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0]["task_id"], "c")
        self.assertEqual(deferred[0]["why"], _AUGMENT_CAP_DEFER_REASON)

    def test_partial_budget_from_prior(self):
        """prior_count=1 leaves room for 1 more; excess defers."""
        mutations = [
            {"op": "augment", "task_id": "a", "why": "A"},
            {"op": "augment", "task_id": "b", "why": "B"},
        ]
        applied, deferred = _apply_augment_cap(mutations, prior_count=1)
        self.assertEqual(len(applied), 1)
        self.assertEqual(len(deferred), 1)
        self.assertEqual(applied[0]["task_id"], "a")
        self.assertEqual(deferred[0]["task_id"], "b")
        self.assertEqual(deferred[0]["why"], _AUGMENT_CAP_DEFER_REASON)


# ---------------------------------------------------------------------------
# Prior-count reader: _count_prior_augments_for_phase
# ---------------------------------------------------------------------------


class TestCountPriorAugments(unittest.TestCase):
    """_count_prior_augments_for_phase reads process-plan.addendum.jsonl."""

    def test_missing_file_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            count = _count_prior_augments_for_phase(Path(tmp), "design")
            self.assertEqual(count, 0)

    def test_none_project_dir_returns_zero(self):
        self.assertEqual(_count_prior_augments_for_phase(None, "design"), 0)

    def test_counts_applied_augments_only(self):
        """Only mutations_applied entries with op=='augment' count."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            addendum = project_dir / "process-plan.addendum.jsonl"
            records = [
                {
                    "chain_id": "p.design",
                    "triggered_at": "2026-04-18T10:00:00Z",
                    "trigger": "phase-end",
                    "prior_rigor_tier": "standard",
                    "new_rigor_tier": "standard",
                    "mutations": [],
                    "mutations_applied": [
                        {"op": "augment", "task_id": "a", "why": "A"},
                        {"op": "re_tier", "new_rigor_tier": "full", "why": "R"},
                    ],
                    "mutations_deferred": [],
                    "validator_version": "1.0.0",
                },
                {
                    "chain_id": "p.design",
                    "triggered_at": "2026-04-18T11:00:00Z",
                    "trigger": "phase-end",
                    "prior_rigor_tier": "standard",
                    "new_rigor_tier": "standard",
                    "mutations": [],
                    "mutations_applied": [
                        {"op": "augment", "task_id": "b", "why": "B"},
                    ],
                    # Deferred augments must NOT count
                    "mutations_deferred": [
                        {"op": "augment", "task_id": "c", "why": _AUGMENT_CAP_DEFER_REASON},
                    ],
                    "validator_version": "1.0.0",
                },
            ]
            addendum.write_text(
                "\n".join(json.dumps(r) for r in records) + "\n"
            )
            self.assertEqual(
                _count_prior_augments_for_phase(project_dir, "design"),
                2,
            )

    def test_other_phase_augments_not_counted(self):
        """A phase filter means another phase's augments don't leak in."""
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            addendum = project_dir / "process-plan.addendum.jsonl"
            record = {
                "chain_id": "p.build",
                "triggered_at": "2026-04-18T12:00:00Z",
                "trigger": "phase-end",
                "prior_rigor_tier": "standard",
                "new_rigor_tier": "standard",
                "mutations": [],
                "mutations_applied": [
                    {"op": "augment", "task_id": "z", "why": "Z"},
                ],
                "mutations_deferred": [],
                "validator_version": "1.0.0",
            }
            addendum.write_text(json.dumps(record) + "\n")
            # Asking about design — build's augment does not count
            self.assertEqual(
                _count_prior_augments_for_phase(project_dir, "design"),
                0,
            )


# ---------------------------------------------------------------------------
# Integration: _run_checkpoint_reanalysis with _reeval_fn (AC-9)
# ---------------------------------------------------------------------------


class TestRunCheckpointReanalysisAugmentCap(unittest.TestCase):
    """AC-9: 4 incoming augments → 2 applied, 2 deferred with the cap reason."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._patch_phases = patch.object(
            pm, "load_phases_config",
            return_value={"design": {"checkpoint": True}},
        )
        self._patch_phases.start()
        self._patch_proj = patch.object(
            pm, "get_project_dir", return_value=Path(self.tmpdir)
        )
        self._patch_proj.start()

    def tearDown(self):
        self._patch_phases.stop()
        self._patch_proj.stop()

    def test_four_augments_two_applied_two_deferred(self):
        state = _make_state()
        record = {
            "chain_id": "augment-cap-test.design",
            "triggered_at": "2026-04-18T12:00:00Z",
            "trigger": "phase-end",
            "prior_rigor_tier": "standard",
            "new_rigor_tier": "standard",
            "mutations": [
                {"op": "augment", "task_id": "ta", "why": "A"},
                {"op": "augment", "task_id": "tb", "why": "B"},
                {"op": "augment", "task_id": "tc", "why": "C"},
                {"op": "augment", "task_id": "td", "why": "D"},
            ],
            "mutations_applied": [],
            "mutations_deferred": [],
            "validator_version": "1.0.0",
        }

        def _fake_reeval(_state, _phase):
            return record

        injected, warnings = _run_checkpoint_reanalysis(
            state, "design", _reeval_fn=_fake_reeval,
        )

        # Post-cap: exactly 2 applied, 2 deferred with cap reason
        self.assertEqual(len(record["mutations_applied"]), 2)
        self.assertEqual(len(record["mutations_deferred"]), 2)
        for m in record["mutations_deferred"]:
            self.assertEqual(m["why"], _AUGMENT_CAP_DEFER_REASON)
        self.assertTrue(
            any("augment-cap-exceeded" in w for w in warnings),
            f"Expected a cap-exceeded warning in {warnings}",
        )

    def test_cap_counts_across_invocations(self):
        """Second re-eval with 1 prior augment applied can only apply 1 more."""
        state = _make_state()
        # Seed the addendum with one prior applied augment
        addendum = Path(self.tmpdir) / "process-plan.addendum.jsonl"
        prior = {
            "chain_id": "augment-cap-test.design",
            "triggered_at": "2026-04-18T10:00:00Z",
            "trigger": "phase-end",
            "prior_rigor_tier": "standard",
            "new_rigor_tier": "standard",
            "mutations": [],
            "mutations_applied": [
                {"op": "augment", "task_id": "prev", "why": "prior"},
            ],
            "mutations_deferred": [],
            "validator_version": "1.0.0",
        }
        addendum.write_text(json.dumps(prior) + "\n")

        record = {
            "chain_id": "augment-cap-test.design",
            "triggered_at": "2026-04-18T12:00:00Z",
            "trigger": "phase-end",
            "prior_rigor_tier": "standard",
            "new_rigor_tier": "standard",
            "mutations": [
                {"op": "augment", "task_id": "new1", "why": "N1"},
                {"op": "augment", "task_id": "new2", "why": "N2"},
                {"op": "augment", "task_id": "new3", "why": "N3"},
            ],
            "mutations_applied": [],
            "mutations_deferred": [],
            "validator_version": "1.0.0",
        }

        _run_checkpoint_reanalysis(
            state, "design", _reeval_fn=lambda s, p: record,
        )

        # Remaining budget was 2-1=1 → only 1 applied, 2 deferred
        self.assertEqual(len(record["mutations_applied"]), 1)
        self.assertEqual(len(record["mutations_deferred"]), 2)
        for m in record["mutations_deferred"]:
            self.assertEqual(m["why"], _AUGMENT_CAP_DEFER_REASON)

    def test_non_checkpoint_phase_does_not_run_cap(self):
        """Non-checkpoint phases short-circuit before cap logic."""
        # Override the phases_config patch to mark 'design' as non-checkpoint
        self._patch_phases.stop()
        self._patch_phases = patch.object(
            pm, "load_phases_config",
            return_value={"design": {"checkpoint": False}},
        )
        self._patch_phases.start()

        state = _make_state()
        called = {"n": 0}

        def _counter(_s, _p):
            called["n"] += 1
            return {"mutations": [{"op": "augment", "task_id": "x", "why": "x"}]}

        injected, warnings = _run_checkpoint_reanalysis(
            state, "design", _reeval_fn=_counter,
        )
        self.assertEqual(called["n"], 0)  # reeval_fn never invoked
        self.assertEqual(injected, [])
        self.assertEqual(warnings, [])

    def test_reeval_fn_exception_is_fail_open(self):
        """A raising _reeval_fn must not block phase advance — cap logic skips."""
        state = _make_state()

        def _boom(_s, _p):
            raise RuntimeError("boom")

        # Should not raise; should return ordinary validate_phase_plan output
        injected, warnings = _run_checkpoint_reanalysis(
            state, "design", _reeval_fn=_boom,
        )
        # No cap warnings because _reeval_fn raised
        self.assertFalse(
            any("augment-cap-exceeded" in w for w in warnings),
            f"Expected no cap warning when _reeval_fn raises, got {warnings}",
        )


class TestAugmentCapConstant(unittest.TestCase):
    """Sanity: cap constant is exactly 2 per AC-9."""

    def test_cap_is_two(self):
        self.assertEqual(_AUGMENT_CAP_PER_PHASE, 2)

    def test_defer_reason_is_augment_cap_exceeded(self):
        self.assertEqual(_AUGMENT_CAP_DEFER_REASON, "augment-cap-exceeded")


if __name__ == "__main__":
    unittest.main()
