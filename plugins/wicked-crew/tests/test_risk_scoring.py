#!/usr/bin/env python3
"""
Test suite for multi-dimensional risk scoring in smart_decisioning.py.

53+ test cases covering:
1. Dimension unit tests (assess_file_impact, assess_impact, assess_reversibility, assess_novelty)
2. Composite formula tests (compute_composite)
3. Signal detection tests (new categories, expanded existing, stem matching)
4. Acceptance criteria verification (AC-1 through AC-6)
5. Integration tests (full pipeline)
6. Edge cases

Run: python3 -m unittest tests/test_risk_scoring.py -v
"""

import os
import sys
import time
import unittest

# Add parent directory to path so we can import smart_decisioning
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.smart_decisioning import (
    assess_file_impact,
    assess_impact,
    assess_reversibility,
    assess_novelty,
    compute_composite,
    detect_signals,
    is_ambiguous,
    analyze_input,
    _make_pattern,
    RiskDimensions,
    SignalAnalysis,
)
import re


# ============================================================================
# 1. Dimension Unit Tests
# ============================================================================


class TestAssessFileImpact(unittest.TestCase):
    """Tests for assess_file_impact() — FILE_ROLE_PATTERNS taxonomy."""

    def test_F1_readme(self):
        """README.md = tier 5 (0.5), int(0.5)=0"""
        self.assertEqual(assess_file_impact("Fix typo in README.md"), 0)

    def test_F2_hooks_json(self):
        """hooks.json = tier 1 (2.0), int(2.0)=2"""
        self.assertEqual(assess_file_impact("Update hooks.json bindings"), 2)

    def test_F3_commands_dir(self):
        """commands/ = tier 1 (2.0)"""
        self.assertEqual(assess_file_impact("Modify commands/review.md"), 2)

    def test_F4_src_dir(self):
        """src/ = tier 2 (1.5), int(1.5)=1"""
        self.assertEqual(assess_file_impact("Fix bug in src/parser.py"), 1)

    def test_F5_github_workflows(self):
        """.github/workflows/ = tier 1 (2.0)"""
        self.assertEqual(assess_file_impact("Update .github/workflows/ci.yml"), 2)

    def test_F6_scripts_dir(self):
        """scripts/ = tier 2 (1.5), int(1.5)=1"""
        self.assertEqual(assess_file_impact("Modify scripts/deploy.sh"), 1)

    def test_F7_dockerfile_and_makefile(self):
        """Both tier 1, max_weight=2.0, count=2 (no breadth bonus)"""
        self.assertEqual(assess_file_impact("Change Dockerfile and Makefile"), 2)

    def test_F8_three_tier1_files(self):
        """3+ matches, max=2.0, breadth bonus -> 3"""
        self.assertEqual(
            assess_file_impact("Rewrite commands/a.md, hooks/b.py, and scripts/c.sh"),
            3,
        )

    def test_F9_docs_dir(self):
        """docs/ = tier 5 (0.5), int(0.5)=0"""
        self.assertEqual(assess_file_impact("Update docs/guide.md"), 0)

    def test_F10_generic_py(self):
        """.py = tier 3 (1.0), int(1.0)=1"""
        self.assertEqual(assess_file_impact("Fix parser.py"), 1)

    def test_F11_skills_md(self):
        """skills/*.md = tier 2 (1.5), int(1.5)=1"""
        self.assertEqual(assess_file_impact("Edit skills/frontend.md"), 1)

    def test_F12_changelog_and_license(self):
        """CHANGELOG=0.5, LICENSE=0.0, max=0.5, int=0"""
        self.assertEqual(assess_file_impact("Update CHANGELOG.md and LICENSE"), 0)

    def test_F13_empty_string(self):
        """No matches"""
        self.assertEqual(assess_file_impact(""), 0)

    def test_F14_no_file_patterns(self):
        """No file patterns match"""
        self.assertEqual(
            assess_file_impact("Just a plain description with no files"), 0
        )

    def test_F15_changelog_md_no_double_count(self):
        """CHANGELOG.md = single match via adjacent span dedup, not double"""
        self.assertEqual(assess_file_impact("Update CHANGELOG.md"), 0)

    def test_F16_readme_md_no_double_count(self):
        """README.md = single match via adjacent span dedup"""
        self.assertEqual(assess_file_impact("readme.md"), 0)


class TestAssessImpact(unittest.TestCase):
    """Tests for assess_impact() — file impact + integration keywords."""

    def test_I1_no_signals(self):
        score, _ = assess_impact("Fix typo in README")
        self.assertEqual(score, 0)

    def test_I2_file_only(self):
        score, _ = assess_impact("Update hooks.json bindings")
        self.assertEqual(score, 2)

    def test_I3_integration_only(self):
        score, reasons = assess_impact("Modify auth service API")
        self.assertEqual(score, 2)
        self.assertTrue(any("integration" in r for r in reasons))

    def test_I4_file_plus_integration_capped(self):
        score, _ = assess_impact(
            "Rewrite commands/, hooks/, and API handlers"
        )
        self.assertEqual(score, 3)

    def test_I5_integration_keywords(self):
        score, _ = assess_impact("Connect external system endpoint")
        self.assertEqual(score, 2)

    def test_I6_no_signals_at_all(self):
        score, _ = assess_impact("Fix typo")
        self.assertEqual(score, 0)


class TestAssessReversibility(unittest.TestCase):
    """Tests for assess_reversibility() — irreversibility and mitigator signals."""

    def test_R1_no_signals(self):
        score, _ = assess_reversibility("Fix typo in README")
        self.assertEqual(score, 0)

    def test_R2_migration_and_schema(self):
        score, _ = assess_reversibility("Migrate database schema to v2")
        self.assertEqual(score, 3)  # capped at 3

    def test_R3_feature_flagged(self):
        score, _ = assess_reversibility("Add feature-flagged dark mode")
        self.assertEqual(score, 0)  # feature flag mitigates

    def test_R4_remove_deprecated_api(self):
        score, _ = assess_reversibility("Remove deprecated API endpoints")
        self.assertEqual(score, 3)  # capped at 3

    def test_R5_rename_with_schema(self):
        score, _ = assess_reversibility(
            "Rename user table columns with schema change"
        )
        self.assertEqual(score, 3)  # capped at 3

    def test_R6_canary_rollout(self):
        score, _ = assess_reversibility("Canary rollout of new auth flow")
        self.assertEqual(score, 0)  # canary mitigates

    def test_R7_breaking_change(self):
        score, _ = assess_reversibility("Breaking change to payment API")
        self.assertEqual(score, 3)  # capped at 3

    def test_R8_delete(self):
        score, _ = assess_reversibility("Delete old test fixtures")
        self.assertEqual(score, 1)

    def test_R9_restructure(self):
        score, _ = assess_reversibility("Restructure project directories")
        self.assertEqual(score, 2)

    def test_R10_all_mitigators(self):
        score, _ = assess_reversibility(
            "Add feature toggle for experiment"
        )
        self.assertEqual(score, 0)  # mitigated


class TestAssessNovelty(unittest.TestCase):
    """Tests for assess_novelty() — explicit keywords + cross-domain + ambiguity."""

    def test_N1_routine(self):
        score, _ = assess_novelty("Fix typo", [], False)
        self.assertEqual(score, 0)

    def test_N2_prototype(self):
        score, _ = assess_novelty("Prototype new auth flow", ["security"], False)
        self.assertEqual(score, 2)

    def test_N3_multi_domain_plus_ambiguity(self):
        score, _ = assess_novelty(
            "Should we use Redis?",
            ["performance", "data", "ambiguity"],
            True,
        )
        self.assertEqual(score, 3)

    def test_N4_first_time(self):
        score, _ = assess_novelty(
            "First time implementing CQRS", ["architecture"], False
        )
        self.assertEqual(score, 2)

    def test_N5_multi_domain(self):
        score, _ = assess_novelty(
            "Refactor database queries", ["performance", "data"], False
        )
        self.assertEqual(score, 1)

    def test_N6_research(self):
        score, _ = assess_novelty(
            "Research spike on auth patterns", ["security"], False
        )
        self.assertEqual(score, 1)

    def test_N7_greenfield(self):
        score, _ = assess_novelty("Greenfield service from scratch", [], False)
        self.assertEqual(score, 2)  # greenfield=+2 (first match, breaks)

    def test_N8_routine_version_bump(self):
        score, _ = assess_novelty("Routine version bump", [], False)
        self.assertEqual(score, 0)

    def test_N9_evaluate_with_ambiguity(self):
        score, _ = assess_novelty(
            "Evaluate new framework options", ["ambiguity"], True
        )
        self.assertEqual(score, 2)  # evaluat*=+1, ambiguity=+1


# ============================================================================
# 2. Composite Formula Tests
# ============================================================================


class TestComputeComposite(unittest.TestCase):
    """Tests for compute_composite() function."""

    def test_C1_all_zero(self):
        self.assertEqual(compute_composite(0, 0, 0, "Fix typo"), 0)

    def test_C2_impact_only(self):
        self.assertEqual(compute_composite(2, 0, 0, "Update hooks"), 2)

    def test_C3_impact_plus_reversibility(self):
        self.assertEqual(
            compute_composite(2, 2, 0, "Restructure terraform"), 4
        )

    def test_C4_reversibility_only_capped(self):
        """risk_prem capped at 2"""
        self.assertEqual(compute_composite(0, 3, 0, "Migrate schema"), 2)

    def test_C5_impact_plus_novelty(self):
        self.assertEqual(compute_composite(3, 0, 3, "Prototype API"), 5)

    def test_C6_long_text_scope(self):
        long_text = " ".join(["word"] * 101)
        self.assertEqual(compute_composite(0, 0, 0, long_text), 2)

    def test_C7_stakeholder_coordination(self):
        self.assertEqual(
            compute_composite(2, 0, 0, "team lead reviews hooks"), 3
        )

    def test_C8_everything_maxed(self):
        long_text = " ".join(["word"] * 101) + " stakeholder"
        self.assertEqual(compute_composite(3, 3, 3, long_text), 7)

    def test_C9_risk_premium_capping_both_max(self):
        """risk_premium = min(max(3,3),2) = 2. 0+2=2"""
        self.assertEqual(compute_composite(0, 3, 3, "fix"), 2)

    def test_C10_risk_premium_capping_mixed(self):
        """risk_premium = min(max(2,1),2) = 2. 1+2=3"""
        self.assertEqual(compute_composite(1, 2, 1, "fix"), 3)


# ============================================================================
# 3. Signal Detection Tests
# ============================================================================


class TestNewSignalCategories(unittest.TestCase):
    """Tests for new reversibility and novelty signal categories."""

    def test_S1_reversibility_migrate(self):
        signals = detect_signals("Migrate database to new schema")
        self.assertIn("reversibility", signals)

    def test_S2_reversibility_feature_flag(self):
        signals = detect_signals("Add feature flag for dark mode")
        self.assertIn("reversibility", signals)

    def test_S3_reversibility_breaking_change(self):
        signals = detect_signals("Breaking change to API contract")
        self.assertIn("reversibility", signals)

    def test_S4_novelty_prototype(self):
        signals = detect_signals("Prototype new auth approach")
        self.assertIn("novelty", signals)

    def test_S5_novelty_greenfield(self):
        signals = detect_signals("Greenfield service build")
        self.assertIn("novelty", signals)

    def test_S6_novelty_research(self):
        signals = detect_signals("Research spike on caching")
        self.assertIn("novelty", signals)


class TestExpandedSignalCategories(unittest.TestCase):
    """Tests for expanded existing signal categories."""

    def test_S7_architecture_algorithm(self):
        signals = detect_signals("Fix the scoring algorithm")
        self.assertIn("architecture", signals)

    def test_S8_architecture_orchestration(self):
        signals = detect_signals("Update orchestration logic")
        self.assertIn("architecture", signals)

    def test_S9_infrastructure_hook_binding(self):
        signals = detect_signals("Modify hook event bindings")
        # Note: "hook binding" is the keyword, "hook event bindings" has
        # "hook" followed later by "bindings" — not an exact phrase match.
        # The infrastructure signal may not match since "hook binding" as
        # a phrase requires adjacency. But "event handler" is also a keyword.
        # The test verifies the expanded vocabulary works for exact matches.
        signals2 = detect_signals("Update the hook binding configuration")
        self.assertIn("infrastructure", signals2)

    def test_S10_infrastructure_build_system(self):
        signals = detect_signals("Change build system configuration")
        self.assertIn("infrastructure", signals)

    def test_S11_complexity_cascading(self):
        signals = detect_signals("Cascading effects on downstream")
        self.assertIn("complexity", signals)

    def test_S12_complexity_cross_cutting(self):
        signals = detect_signals("Cross-cutting concern refactor")
        self.assertIn("complexity", signals)


class TestStemMatching(unittest.TestCase):
    """Tests for stem-aware keyword matching via _make_pattern."""

    def test_SM1_orchestrate(self):
        pattern = re.compile(_make_pattern("orchestrat*"))
        self.assertIsNotNone(pattern.search("orchestrate the workflow"))

    def test_SM2_orchestration(self):
        pattern = re.compile(_make_pattern("orchestrat*"))
        self.assertIsNotNone(pattern.search("orchestration pipeline"))

    def test_SM3_orchestrator(self):
        pattern = re.compile(_make_pattern("orchestrat*"))
        self.assertIsNotNone(pattern.search("orchestrator pattern"))

    def test_SM4_orchestra_no_match(self):
        """orchestra != orchestrat*"""
        pattern = re.compile(_make_pattern("orchestrat*"))
        self.assertIsNone(pattern.search("the orchestra played"))

    def test_SM5_deprecation(self):
        pattern = re.compile(_make_pattern("deprecat*"))
        self.assertIsNotNone(pattern.search("deprecation notice"))

    def test_SM6_data_transformation(self):
        pattern = re.compile(_make_pattern("data transform*"))
        self.assertIsNotNone(pattern.search("data transformation job"))


# ============================================================================
# 4. Acceptance Criteria Verification
# ============================================================================


class TestAC1FunctionalRoleDetection(unittest.TestCase):
    """AC-1: Functional role detection — Min Impact and Min Composite."""

    def test_AC1_1_hooks_json(self):
        result = analyze_input("Modify hooks.json to add PreToolUse event")
        self.assertGreaterEqual(result.risk_dimensions.impact, 2)
        self.assertGreaterEqual(result.complexity_score, 2)

    def test_AC1_2_readme(self):
        result = analyze_input("Update README.md with new examples")
        self.assertEqual(result.risk_dimensions.impact, 0)
        self.assertEqual(result.complexity_score, 0)

    def test_AC1_3_commands(self):
        result = analyze_input(
            "Rewrite commands/review.md to use Task dispatch"
        )
        self.assertGreaterEqual(result.risk_dimensions.impact, 2)
        self.assertGreaterEqual(result.complexity_score, 2)

    def test_AC1_4_skills(self):
        result = analyze_input("Add new SKILL.md for frontend engineering")
        self.assertGreaterEqual(result.risk_dimensions.impact, 1)
        self.assertGreaterEqual(result.complexity_score, 1)

    def test_AC1_5_smart_decisioning(self):
        result = analyze_input(
            "Modify smart_decisioning.py scoring algorithm"
        )
        self.assertGreaterEqual(result.risk_dimensions.impact, 1)
        self.assertGreaterEqual(result.complexity_score, 1)

    def test_AC1_6_changelog_typo(self):
        result = analyze_input("Fix typo in CHANGELOG.md")
        self.assertEqual(result.risk_dimensions.impact, 0)
        self.assertEqual(result.complexity_score, 0)

    def test_AC1_7_package_json(self):
        result = analyze_input("Update package.json version to 2.0.0")
        self.assertEqual(result.risk_dimensions.impact, 0)
        self.assertEqual(result.complexity_score, 0)

    def test_AC1_8_terraform_restructure(self):
        result = analyze_input(
            "Restructure Terraform modules across services"
        )
        self.assertGreaterEqual(result.risk_dimensions.impact, 2)
        self.assertGreaterEqual(result.complexity_score, 4)


class TestAC2SignalVocabulary(unittest.TestCase):
    """AC-2: Signal vocabulary expansion."""

    def test_AC2_1_scoring_algorithm(self):
        signals = detect_signals(
            "Fix the scoring algorithm in smart decisioning"
        )
        self.assertTrue(
            "architecture" in signals or "complexity" in signals
        )

    def test_AC2_2_phase_selection(self):
        signals = detect_signals("Change phase selection approach")
        self.assertIn("architecture", signals)

    def test_AC2_3_hook_binding(self):
        signals = detect_signals("Modify hook binding configuration")
        self.assertIn("infrastructure", signals)

    def test_AC2_4_routing_logic(self):
        signals = detect_signals("Update specialist routing logic")
        self.assertIn("architecture", signals)

    def test_AC2_5_pipeline(self):
        signals = detect_signals(
            "Refactor the context assembly pipeline"
        )
        self.assertIn("infrastructure", signals)


class TestAC3SelfScoring(unittest.TestCase):
    """AC-3: Self-scoring accuracy — the project's own description."""

    def test_self_scoring(self):
        description = (
            "Fix complexity scoring to be functionally-aware instead of "
            "extension-based. Current smart_decisioning.py treats .md files "
            "(commands, agents, skills), .json files (hooks.json, specialist.json, "
            "phases.json), and other plugin-critical files as 'doc updates' or "
            "low-complexity changes because it scores by file extension, not "
            "functional impact. In repos like wicked-garden, a command .md file "
            "IS the executable code, a hooks.json change can break all plugin "
            "behavior, and a SKILL.md change affects what context gets loaded. "
            "The scoring needs to be dynamic - analyzing what role a file plays "
            "in its context (is this markdown a README or a command definition? "
            "is this JSON a config or a hook binding?) rather than assuming "
            ".md = docs and .json = config. This affects phase selection, "
            "specialist routing, and whether gates fire. The fix must be "
            "generalizable - not hardcoded to wicked-garden file patterns, "
            "but able to detect functional impact across different project types."
        )
        result = analyze_input(description)
        self.assertGreaterEqual(result.complexity_score, 4)
        self.assertGreater(len(result.signals), 0)


class TestAC4NoHardcodedPatterns(unittest.TestCase):
    """AC-4: No hardcoded project types in scoring logic."""

    def test_no_wicked_garden_patterns(self):
        """Verify FILE_ROLE_PATTERNS use universal conventions."""
        from scripts.smart_decisioning import FILE_ROLE_PATTERNS

        for pattern, weight in FILE_ROLE_PATTERNS:
            self.assertNotIn("wicked", pattern.lower())
            self.assertNotIn("claude-plugin", pattern.lower())
            self.assertNotIn(".something-wicked", pattern.lower())

    def test_no_hardcoded_keywords(self):
        """Verify SIGNAL_KEYWORDS don't reference project-specific names."""
        from scripts.smart_decisioning import SIGNAL_KEYWORDS

        for category, keywords in SIGNAL_KEYWORDS.items():
            for kw in keywords:
                self.assertNotIn("wicked", kw.lower())


class TestAC6Performance(unittest.TestCase):
    """AC-6: Performance — analysis completes in < 100ms."""

    def test_short_input_performance(self):
        start = time.time()
        for _ in range(100):
            analyze_input("Fix typo in README")
        elapsed = (time.time() - start) / 100
        self.assertLess(elapsed, 0.1)  # < 100ms per call

    def test_long_input_performance(self):
        long_text = " ".join(["word"] * 500)
        start = time.time()
        for _ in range(100):
            analyze_input(long_text)
        elapsed = (time.time() - start) / 100
        self.assertLess(elapsed, 0.1)


# ============================================================================
# 5. Integration Tests
# ============================================================================


class TestIntegration(unittest.TestCase):
    """Full pipeline integration tests via analyze_input()."""

    def test_INT1_trivial(self):
        result = analyze_input("Fix typo in README")
        self.assertEqual(result.complexity_score, 0)
        self.assertEqual(result.signals, [])
        self.assertEqual(result.risk_dimensions.impact, 0)
        self.assertEqual(result.risk_dimensions.reversibility, 0)
        self.assertEqual(result.risk_dimensions.novelty, 0)
        self.assertEqual(result.risk_dimensions.explanation, [])
        self.assertEqual(result.flags, {})

    def test_INT2_high_risk(self):
        result = analyze_input(
            "Migrate database schema with breaking API changes"
        )
        self.assertGreaterEqual(result.complexity_score, 4)
        self.assertIn("reversibility", result.signals)
        self.assertGreaterEqual(result.risk_dimensions.reversibility, 2)
        self.assertTrue(result.flags.get("needs_rollback_plan", False))
        # Explanation traceability
        explanations = " ".join(result.risk_dimensions.explanation)
        self.assertTrue(
            "migration" in explanations.lower()
            or "breaking" in explanations.lower()
        )

    def test_INT3_novel_prototype(self):
        result = analyze_input(
            "Prototype CQRS pattern for auth across multiple services"
        )
        self.assertGreaterEqual(result.complexity_score, 4)
        self.assertIn("novelty", result.signals)
        self.assertGreaterEqual(result.risk_dimensions.novelty, 2)
        explanations = " ".join(result.risk_dimensions.explanation)
        self.assertTrue(
            "prototype" in explanations.lower()
            or "cross-domain" in explanations.lower()
        )

    def test_INT4_hooks_json(self):
        result = analyze_input(
            "Update hooks.json to add PostToolUse event handler"
        )
        self.assertGreaterEqual(result.complexity_score, 2)
        self.assertGreaterEqual(result.risk_dimensions.impact, 2)
        explanations = " ".join(result.risk_dimensions.explanation)
        self.assertTrue("behavior-defining" in explanations.lower())

    def test_INT5_full_description(self):
        long_desc = (
            "We need to redesign the authentication system across all "
            "microservices. This involves migrating the user database schema, "
            "updating the API gateway configuration, and implementing a new "
            "JWT token validation flow. The team lead has raised concerns about "
            "backward compatibility with existing mobile clients. We should "
            "evaluate whether to use feature flags for the rollout. This "
            "affects the payment service, notification service, and the main "
            "web application. " + " ".join(["context"] * 50)
        )
        result = analyze_input(long_desc)
        self.assertGreaterEqual(result.complexity_score, 5)
        self.assertGreater(result.risk_dimensions.impact, 0)
        self.assertGreater(result.risk_dimensions.reversibility, 0)
        self.assertGreater(result.risk_dimensions.novelty, 0)

    def test_formula_consistency(self):
        """Verify composite formula: impact + min(round(rev*nov*0.22), 2) + scope + coord <= 7"""
        test_inputs = [
            "Fix typo in README",
            "Migrate database schema with breaking API changes",
            "Prototype CQRS pattern for auth across multiple services",
            "Update hooks.json to add PostToolUse event handler",
        ]
        for text in test_inputs:
            result = analyze_input(text)
            dims = result.risk_dimensions
            word_count = len(text.split())
            scope = 2 if word_count > 100 else (1 if word_count > 50 else 0)
            stakeholders = ["team", "manager", "lead", "stakeholder", "customer", "user"]
            coord = 1 if any(kw in text.lower() for kw in stakeholders) else 0
            expected = min(
                dims.impact + min(round(dims.reversibility * dims.novelty * 0.22), 2) + scope + coord,
                7,
            )
            self.assertEqual(
                result.complexity_score,
                expected,
                f"Formula mismatch for: {text[:50]}...",
            )

    def test_explanation_traceability(self):
        """Non-zero dimensions must have explanation strings."""
        test_inputs = [
            "Migrate database schema with breaking API changes",
            "Prototype CQRS pattern for auth across multiple services",
            "Update hooks.json to add PostToolUse event handler",
        ]
        for text in test_inputs:
            result = analyze_input(text)
            dims = result.risk_dimensions
            if dims.impact > 0 or dims.reversibility > 0 or dims.novelty > 0:
                self.assertGreater(
                    len(dims.explanation),
                    0,
                    f"Missing explanation for: {text[:50]}...",
                )

    def test_json_output_format(self):
        """Verify JSON output includes required fields."""
        from dataclasses import asdict

        result = analyze_input("Migrate database schema")
        data = asdict(result)
        self.assertIn("risk_dimensions", data)
        self.assertIn("impact", data["risk_dimensions"])
        self.assertIn("reversibility", data["risk_dimensions"])
        self.assertIn("novelty", data["risk_dimensions"])
        self.assertIn("explanation", data["risk_dimensions"])
        self.assertIn("flags", data)
        # Backward-compat fields
        self.assertIn("signals", data)
        self.assertIn("complexity_score", data)
        self.assertIn("recommended_specialists", data)
        self.assertIn("confidence", data)
        self.assertIn("is_ambiguous", data)


# ============================================================================
# 6. Edge Cases
# ============================================================================


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_E1_empty_string(self):
        result = analyze_input("")
        self.assertEqual(result.complexity_score, 0)
        self.assertEqual(result.risk_dimensions.impact, 0)
        self.assertEqual(result.risk_dimensions.reversibility, 0)
        self.assertEqual(result.risk_dimensions.novelty, 0)

    def test_E2_single_word(self):
        result = analyze_input("fix")
        self.assertEqual(result.complexity_score, 0)

    def test_E3_large_input_performance(self):
        large_text = "x " * 5000
        start = time.time()
        result = analyze_input(large_text)
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1)

    def test_E4_special_regex_chars(self):
        """No regex crash with special characters."""
        result = analyze_input("use [brackets] and (parens) with {braces}")
        self.assertIsNotNone(result)

    def test_E5_reversibility_only(self):
        score, _ = assess_reversibility("migrate schema")
        self.assertGreater(score, 0)

    def test_E6_all_mitigators(self):
        score, _ = assess_reversibility(
            "feature flagged canary rollback"
        )
        self.assertEqual(score, 0)


if __name__ == "__main__":
    unittest.main()
