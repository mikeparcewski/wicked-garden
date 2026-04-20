#!/usr/bin/env python3
"""
Unit tests for the spec quality rubric (issue #446).

Covers:
  T-R1.1 — rubric has 10 dimensions, 20 max points, grade table correct
  T-R1.2 — validate_breakdown rejects malformed input
  T-R1.3 — total_score sums dimensions (missing dims treated as 0)
  T-R1.4 — grade_for_score returns A/B/C/D/F bands
  T-R1.5 — evaluate_verdict at-or-above threshold keeps base verdict
  T-R2.1 — minimal rigor score 11 yields CONDITIONAL (acceptance case)
  T-R2.2 — full rigor score 17 yields CONDITIONAL (graduated response)
  T-R2.4 — hard-reject floor (<12) yields REJECT at every tier
  T-R2.3 — base REJECT is preserved regardless of score
  T-R3.1 — score_breakdown_to_grid renders all 10 rows
  T-P1.1 — phase_manager._apply_spec_rubric skips non-clarify phases
  T-P1.2 — phase_manager._apply_spec_rubric is no-op when breakdown absent
  T-P1.3 — phase_manager._apply_spec_rubric downgrades APPROVE to CONDITIONAL
           at standard rigor below 15
  T-P1.4 — phase_manager._apply_spec_rubric escalates to REJECT at full rigor
           below 18
  T-P1.5 — phase_manager._apply_spec_rubric preserves APPROVE when score
           meets tier threshold
  T-P1.6 — phase_manager._apply_spec_rubric annotates rubric_score fields
  T-P1.7 — malformed breakdown is logged-and-skipped, not raised

Run with:
    uv run pytest tests/crew/test_spec_rubric.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = _REPO_ROOT / "scripts"
CREW_SCRIPTS_DIR = SCRIPTS_DIR / "crew"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(CREW_SCRIPTS_DIR))


import spec_rubric  # noqa: E402
import phase_manager  # noqa: E402


# ---------------------------------------------------------------------------
# Rubric catalog invariants
# ---------------------------------------------------------------------------


class TestRubricCatalog(unittest.TestCase):
    """T-R1.1: catalog shape is correct."""

    def test_ten_dimensions(self):
        self.assertEqual(
            len(spec_rubric.DIMENSION_DEFINITIONS),
            10,
            "Rubric must have exactly 10 dimensions",
        )

    def test_max_score_is_twenty(self):
        self.assertEqual(spec_rubric.MAX_SCORE, 20)

    def test_each_dimension_max_is_two(self):
        for dim in spec_rubric.DIMENSION_DEFINITIONS:
            self.assertEqual(dim["max"], 2, f"{dim['id']} max should be 2")

    def test_tier_thresholds(self):
        self.assertEqual(spec_rubric.TIER_THRESHOLDS["minimal"], 12)
        self.assertEqual(spec_rubric.TIER_THRESHOLDS["standard"], 15)
        self.assertEqual(spec_rubric.TIER_THRESHOLDS["full"], 18)

    def test_dimension_ids_unique(self):
        ids = [d["id"] for d in spec_rubric.DIMENSION_DEFINITIONS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_dimension_ids_present(self):
        required = {
            "user_story",
            "context_framed",
            "numbered_functional_requirements",
            "measurable_nfrs",
            "acceptance_criteria",
            "gherkin_scenarios",
            "test_plan_outline",
            "api_contract",
            "dependencies_identified",
            "design_section",
        }
        got = {d["id"] for d in spec_rubric.DIMENSION_DEFINITIONS}
        self.assertEqual(got, required)


# ---------------------------------------------------------------------------
# validate_breakdown
# ---------------------------------------------------------------------------


class TestValidateBreakdown(unittest.TestCase):
    """T-R1.2: breakdown validation rejects malformed input."""

    def test_non_dict_rejected(self):
        ok, err = spec_rubric.validate_breakdown([1, 2, 3])  # type: ignore[arg-type]
        self.assertFalse(ok)
        self.assertIn("dict", err or "")

    def test_empty_dict_accepted(self):
        ok, err = spec_rubric.validate_breakdown({})
        self.assertTrue(ok, f"empty breakdown should be valid (scored 0): {err}")

    def test_unknown_dimension_rejected(self):
        ok, err = spec_rubric.validate_breakdown(
            {"unknown_dimension": {"score": 1}}
        )
        self.assertFalse(ok)
        self.assertIn("unknown rubric dimension", err or "")

    def test_score_out_of_range_rejected(self):
        ok, err = spec_rubric.validate_breakdown(
            {"user_story": {"score": 3}}
        )
        self.assertFalse(ok)
        self.assertIn("out of range", err or "")

    def test_negative_score_rejected(self):
        ok, err = spec_rubric.validate_breakdown(
            {"user_story": {"score": -1}}
        )
        self.assertFalse(ok)
        self.assertIn("out of range", err or "")

    def test_non_integer_score_rejected(self):
        ok, err = spec_rubric.validate_breakdown(
            {"user_story": {"score": 1.5}}
        )
        self.assertFalse(ok)

    def test_boolean_score_rejected(self):
        # bools are subclasses of int in Python — guard against accidental accept.
        ok, err = spec_rubric.validate_breakdown(
            {"user_story": {"score": True}}
        )
        self.assertFalse(ok)

    def test_entry_not_a_dict_rejected(self):
        ok, err = spec_rubric.validate_breakdown(
            {"user_story": 2}  # type: ignore[dict-item]
        )
        self.assertFalse(ok)

    def test_missing_score_field_rejected(self):
        ok, err = spec_rubric.validate_breakdown(
            {"user_story": {"notes": "ok"}}
        )
        self.assertFalse(ok)
        self.assertIn("missing 'score'", err or "")

    def test_valid_full_breakdown_accepted(self):
        breakdown = {dim["id"]: {"score": 2} for dim in spec_rubric.DIMENSION_DEFINITIONS}
        ok, err = spec_rubric.validate_breakdown(breakdown)
        self.assertTrue(ok, f"full breakdown should validate: {err}")


# ---------------------------------------------------------------------------
# total_score
# ---------------------------------------------------------------------------


class TestTotalScore(unittest.TestCase):
    """T-R1.3: totaling sums dimensions, missing = 0."""

    def test_full_score(self):
        breakdown = {dim["id"]: {"score": 2} for dim in spec_rubric.DIMENSION_DEFINITIONS}
        self.assertEqual(spec_rubric.total_score(breakdown), 20)

    def test_zero_score(self):
        breakdown = {dim["id"]: {"score": 0} for dim in spec_rubric.DIMENSION_DEFINITIONS}
        self.assertEqual(spec_rubric.total_score(breakdown), 0)

    def test_empty_breakdown_is_zero(self):
        self.assertEqual(spec_rubric.total_score({}), 0)

    def test_partial_breakdown_sums_declared_only(self):
        breakdown = {
            "user_story": {"score": 2},
            "acceptance_criteria": {"score": 1},
        }
        self.assertEqual(spec_rubric.total_score(breakdown), 3)

    def test_bad_score_type_treated_as_zero(self):
        # validate_breakdown will reject these, but total_score is resilient.
        breakdown = {"user_story": {"score": "2"}}  # type: ignore[dict-item]
        self.assertEqual(spec_rubric.total_score(breakdown), 0)


# ---------------------------------------------------------------------------
# grade_for_score
# ---------------------------------------------------------------------------


class TestGrade(unittest.TestCase):
    """T-R1.4: letter grade bands."""

    def test_a_at_18(self):
        self.assertEqual(spec_rubric.grade_for_score(18), "A")
        self.assertEqual(spec_rubric.grade_for_score(20), "A")

    def test_b_at_15(self):
        self.assertEqual(spec_rubric.grade_for_score(15), "B")
        self.assertEqual(spec_rubric.grade_for_score(17), "B")

    def test_c_at_12(self):
        self.assertEqual(spec_rubric.grade_for_score(12), "C")
        self.assertEqual(spec_rubric.grade_for_score(14), "C")

    def test_d_at_9(self):
        self.assertEqual(spec_rubric.grade_for_score(9), "D")
        self.assertEqual(spec_rubric.grade_for_score(11), "D")

    def test_f_below_9(self):
        self.assertEqual(spec_rubric.grade_for_score(0), "F")
        self.assertEqual(spec_rubric.grade_for_score(8), "F")


# ---------------------------------------------------------------------------
# evaluate_verdict
# ---------------------------------------------------------------------------


def _make_breakdown(scores: dict) -> dict:
    """Build a breakdown from a {dim_id: int} map, defaulting unspecified dims to 0."""
    bd = {}
    for dim in spec_rubric.DIMENSION_DEFINITIONS:
        bd[dim["id"]] = {"score": scores.get(dim["id"], 0)}
    return bd


class TestEvaluateVerdict(unittest.TestCase):

    def test_above_threshold_preserves_approve(self):
        """T-R1.5: score >= threshold keeps APPROVE."""
        verdict, reason, conds = spec_rubric.evaluate_verdict(
            score=15, rigor_tier="standard", base_verdict="APPROVE"
        )
        self.assertEqual(verdict, "APPROVE")
        self.assertIsNone(reason)
        self.assertEqual(conds, [])

    def test_acceptance_minimal_11_is_conditional(self):
        """T-R2.1 (ISSUE AC-1): minimal project scoring 11 yields CONDITIONAL."""
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2, "acceptance_criteria": 2,
            "gherkin_scenarios": 1, "test_plan_outline": 1, "design_section": 1,
            "api_contract": 2,
            # NFRs, FRs, dependencies all zero -> three failing dims
        })
        self.assertEqual(spec_rubric.total_score(breakdown), 11)
        verdict, reason, conds = spec_rubric.evaluate_verdict(
            score=11, rigor_tier="minimal",
            base_verdict="APPROVE", breakdown=breakdown,
        )
        self.assertEqual(
            verdict, "CONDITIONAL",
            "Issue AC-1: minimal project with rubric score 11 must be CONDITIONAL",
        )
        self.assertIn("minimal", (reason or "").lower())
        self.assertTrue(len(conds) >= 1, "Must surface condition(s) from failing dims")

    def test_acceptance_full_17_is_conditional(self):
        """T-R2.2 (ISSUE AC-2): full-rigor project scoring 17 -> CONDITIONAL.

        Graduated response: 17 sits above the HARD_REJECT_FLOOR (12) but below
        the full tier threshold (18), so the rubric downgrades APPROVE to
        CONDITIONAL with conditions naming the 1-point-missing dimension(s).
        Reserved REJECT for <12 (grade D/F) — spec fundamentally incomplete."""
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2,
            "numbered_functional_requirements": 2, "measurable_nfrs": 2,
            "acceptance_criteria": 2, "gherkin_scenarios": 2,
            "test_plan_outline": 1, "api_contract": 2,
            "dependencies_identified": 1, "design_section": 1,
        })
        self.assertEqual(spec_rubric.total_score(breakdown), 17)
        verdict, reason, conds = spec_rubric.evaluate_verdict(
            score=17, rigor_tier="full",
            base_verdict="APPROVE", breakdown=breakdown,
        )
        self.assertEqual(verdict, "CONDITIONAL")
        self.assertIn("full", (reason or "").lower())

    def test_hard_reject_floor_at_full_tier_only(self):
        """T-R2.4: score < HARD_REJECT_FLOOR (12) yields REJECT only at FULL
        rigor. minimal/standard max out at CONDITIONAL — the tier floor is
        already soft there."""
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2,
            "acceptance_criteria": 2, "design_section": 2,
            # 8 total; below full hard-reject floor
        })
        self.assertEqual(spec_rubric.total_score(breakdown), 8)
        # full rigor: REJECT
        verdict, reason, _ = spec_rubric.evaluate_verdict(
            score=8, rigor_tier="full",
            base_verdict="APPROVE", breakdown=breakdown,
        )
        self.assertEqual(verdict, "REJECT")
        self.assertIn("hard-reject", (reason or "").lower())
        # minimal/standard: CONDITIONAL (not REJECT)
        for tier in ("minimal", "standard"):
            verdict, _, _ = spec_rubric.evaluate_verdict(
                score=8, rigor_tier=tier,
                base_verdict="APPROVE", breakdown=breakdown,
            )
            self.assertEqual(
                verdict, "CONDITIONAL",
                f"score 8 at tier={tier} must be CONDITIONAL (only full REJECTS)",
            )

    def test_standard_below_15_is_conditional(self):
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2,
            "numbered_functional_requirements": 2,
            "acceptance_criteria": 2,
            "api_contract": 2, "design_section": 2,
            # 12 total; missing NFRs, gherkin, test-plan, deps
        })
        self.assertEqual(spec_rubric.total_score(breakdown), 12)
        verdict, reason, conds = spec_rubric.evaluate_verdict(
            score=12, rigor_tier="standard",
            base_verdict="APPROVE", breakdown=breakdown,
        )
        self.assertEqual(verdict, "CONDITIONAL")
        self.assertGreaterEqual(len(conds), 3)

    def test_base_reject_preserved(self):
        """T-R2.3: If the reviewer already rejected, a passing score doesn't upgrade."""
        verdict, reason, conds = spec_rubric.evaluate_verdict(
            score=20, rigor_tier="full", base_verdict="REJECT"
        )
        self.assertEqual(verdict, "REJECT")

    def test_unknown_tier_defaults_to_standard(self):
        verdict, reason, conds = spec_rubric.evaluate_verdict(
            score=14, rigor_tier="experimental", base_verdict="APPROVE",
            breakdown=_make_breakdown({"user_story": 2}),
        )
        self.assertEqual(verdict, "CONDITIONAL")

    def test_conditional_base_preserved_when_above_hard_floor(self):
        """Base CONDITIONAL is preserved when 12 <= score < tier_threshold."""
        verdict, _reason, _conds = spec_rubric.evaluate_verdict(
            score=13, rigor_tier="standard", base_verdict="CONDITIONAL"
        )
        self.assertEqual(verdict, "CONDITIONAL")

    def test_hard_floor_overrides_conditional_base_at_full_tier(self):
        """At FULL rigor, base CONDITIONAL is overridden to REJECT when
        score < HARD_REJECT_FLOOR — too many dimensions missing for the
        reviewer's CONDITIONAL to stick. Minimal/standard preserve CONDITIONAL."""
        # full: REJECT
        verdict, reason, _ = spec_rubric.evaluate_verdict(
            score=10, rigor_tier="full", base_verdict="CONDITIONAL"
        )
        self.assertEqual(verdict, "REJECT")
        self.assertIn("hard-reject", (reason or "").lower())
        # standard: stays CONDITIONAL
        verdict, _, _ = spec_rubric.evaluate_verdict(
            score=10, rigor_tier="standard", base_verdict="CONDITIONAL"
        )
        self.assertEqual(verdict, "CONDITIONAL")


# ---------------------------------------------------------------------------
# score_breakdown_to_grid
# ---------------------------------------------------------------------------


class TestGridRendering(unittest.TestCase):
    """T-R3.1: grid contains all ten dimensions + score + tier annotations."""

    def test_grid_has_all_rows(self):
        breakdown = _make_breakdown({d["id"]: 1 for d in spec_rubric.DIMENSION_DEFINITIONS})
        grid = spec_rubric.score_breakdown_to_grid(breakdown, rigor_tier="standard")
        for dim in spec_rubric.DIMENSION_DEFINITIONS:
            self.assertIn(str(dim["name"]), grid,
                          f"grid missing dimension {dim['name']}")
        self.assertIn("10/20", grid)
        self.assertIn("standard", grid)

    def test_grid_flags_below_threshold(self):
        breakdown = _make_breakdown({"user_story": 2, "context_framed": 2})
        grid = spec_rubric.score_breakdown_to_grid(breakdown, rigor_tier="standard")
        self.assertIn("CONDITIONAL", grid)

    def test_grid_flags_full_reject(self):
        breakdown = _make_breakdown({d["id"]: 1 for d in spec_rubric.DIMENSION_DEFINITIONS})
        grid = spec_rubric.score_breakdown_to_grid(breakdown, rigor_tier="full")
        self.assertIn("REJECT", grid)

    def test_grid_flags_pass(self):
        breakdown = _make_breakdown({d["id"]: 2 for d in spec_rubric.DIMENSION_DEFINITIONS})
        grid = spec_rubric.score_breakdown_to_grid(breakdown, rigor_tier="full")
        self.assertIn("Meets `full` threshold", grid)


# ---------------------------------------------------------------------------
# phase_manager integration
# ---------------------------------------------------------------------------


class TestPhaseManagerIntegration(unittest.TestCase):
    """Tests for phase_manager._apply_spec_rubric."""

    def test_non_clarify_phase_passthrough(self):
        """T-P1.1: non-clarify phase returns result unchanged."""
        gate_result = {"result": "APPROVE", "rubric_breakdown": {"user_story": {"score": 0}}}
        out = phase_manager._apply_spec_rubric(gate_result, "design", "full")
        self.assertEqual(out, gate_result)

    def test_missing_breakdown_passthrough(self):
        """T-P1.2: clarify phase with no rubric_breakdown is no-op."""
        gate_result = {"result": "APPROVE", "reviewer": "wicked-garden:product:requirements-analyst"}
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "standard")
        self.assertEqual(out, gate_result)

    def test_standard_below_threshold_downgrades(self):
        """T-P1.3: standard rigor, score 12 (below 15) -> CONDITIONAL + conditions."""
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2,
            "numbered_functional_requirements": 2, "acceptance_criteria": 2,
            "api_contract": 2, "design_section": 2,
        })
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:product:requirements-analyst",
            "rubric_breakdown": breakdown,
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "standard")
        self.assertEqual(out["result"], "CONDITIONAL")
        self.assertEqual(out["rubric_score"], 12)
        self.assertEqual(out["rubric_grade"], "C")
        self.assertEqual(out["rubric_threshold"], 15)
        self.assertIn("rubric_adjustment", out)
        self.assertEqual(out["rubric_adjustment"]["from"], "APPROVE")
        self.assertEqual(out["rubric_adjustment"]["to"], "CONDITIONAL")
        self.assertTrue(len(out.get("conditions", [])) > 0)
        # Original not mutated
        self.assertEqual(gate_result["result"], "APPROVE")

    def test_full_below_threshold_conditional(self):
        """T-P1.4 (graduated): full rigor, score 17 -> CONDITIONAL (not REJECT).

        17 sits above HARD_REJECT_FLOOR (12) but below the full threshold (18),
        so the rubric downgrades APPROVE to CONDITIONAL with per-dimension
        conditions. REJECT is reserved for <12 at full rigor."""
        # Shape: 1 dim missing (0), 1 dim weak (1), 8 dims perfect (2) = 17
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2,
            "numbered_functional_requirements": 2, "measurable_nfrs": 2,
            "acceptance_criteria": 2, "gherkin_scenarios": 2,
            "test_plan_outline": 1, "api_contract": 2,
            "dependencies_identified": 0, "design_section": 2,
        })
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:product:requirements-analyst",
            "rubric_breakdown": breakdown,
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "full")
        self.assertEqual(out["result"], "CONDITIONAL")
        self.assertEqual(out["rubric_score"], 17)
        self.assertEqual(out["rubric_grade"], "B")
        self.assertEqual(out["rubric_threshold"], 18)
        self.assertEqual(out["rubric_adjustment"]["to"], "CONDITIONAL")
        self.assertTrue(len(out.get("conditions", [])) > 0)

    def test_above_threshold_preserves_approve(self):
        """T-P1.5: score at or above tier threshold keeps APPROVE and still
        annotates rubric_* fields."""
        breakdown = _make_breakdown({d["id"]: 2 for d in spec_rubric.DIMENSION_DEFINITIONS})
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:product:requirements-analyst",
            "rubric_breakdown": breakdown,
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "full")
        self.assertEqual(out["result"], "APPROVE")
        self.assertEqual(out["rubric_score"], 20)
        self.assertEqual(out["rubric_grade"], "A")
        self.assertNotIn("rubric_adjustment", out)

    def test_minimal_11_is_conditional_via_phase_manager(self):
        """T-P1.3 (ISSUE AC-1 E2E): minimal project score 11 -> CONDITIONAL."""
        breakdown = _make_breakdown({
            "user_story": 2, "context_framed": 2, "acceptance_criteria": 2,
            "gherkin_scenarios": 1, "test_plan_outline": 1, "design_section": 1,
            "api_contract": 2,
        })
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:product:requirements-analyst",
            "rubric_breakdown": breakdown,
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "minimal")
        self.assertEqual(out["result"], "CONDITIONAL")
        self.assertEqual(out["rubric_score"], 11)

    def test_malformed_breakdown_skipped(self):
        """T-P1.7: malformed breakdown is logged-and-skipped, not raised."""
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:product:requirements-analyst",
            # score 99 is invalid; validate_breakdown rejects.
            "rubric_breakdown": {"user_story": {"score": 99}},
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "standard")
        # Verdict unchanged; no rubric_score annotation
        self.assertEqual(out["result"], "APPROVE")
        self.assertNotIn("rubric_score", out)

    def test_rubric_score_annotates_all_fields(self):
        """T-P1.6: annotation fields all present when rubric runs."""
        breakdown = _make_breakdown({d["id"]: 2 for d in spec_rubric.DIMENSION_DEFINITIONS})
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:product:requirements-analyst",
            "rubric_breakdown": breakdown,
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "standard")
        for key in ("rubric_score", "rubric_max_score", "rubric_grade",
                    "rubric_rigor_tier", "rubric_threshold"):
            self.assertIn(key, out)

    def test_conditional_downgrades_below_threshold(self):
        """CONDITIONAL base + low score stays CONDITIONAL, annotations still added."""
        breakdown = _make_breakdown({"user_story": 2, "context_framed": 2})
        gate_result = {
            "result": "CONDITIONAL",
            "reviewer": "wicked-garden:product:requirements-analyst",
            "rubric_breakdown": breakdown,
            "conditions": ["Original condition"],
        }
        out = phase_manager._apply_spec_rubric(gate_result, "clarify", "standard")
        self.assertEqual(out["result"], "CONDITIONAL")
        # Original condition preserved, rubric conditions merged in
        self.assertIn("Original condition", out["conditions"])
        self.assertGreater(len(out["conditions"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
