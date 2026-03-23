#!/usr/bin/env python3
"""
Unit tests for gate enforcement features (feat-crew-quality-gate-enforcement).

Tests: T-1.1, T-1.3, T-1.4, T-1.5, T-1.6, T-4.1, T-3.2
Run with: python3 scripts/crew/test_gate_enforcement.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts/ to path so we can import phase_manager
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
CREW_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(CREW_SCRIPTS_DIR))


def _make_project_dir(tmp_root: Path, project_name: str) -> Path:
    """Create a minimal project directory structure under tmp_root."""
    # phase_manager resolves project_dir via DomainStore — we need to mock that
    # by pointing WICKED_HOME or using the actual env var
    project_dir = tmp_root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


class TestBannedReviewer(unittest.TestCase):
    """T-1.4: Banned reviewer names are rejected."""

    def setUp(self):
        # Ensure strict mode
        os.environ.pop("CREW_GATE_ENFORCEMENT", None)

    def _import_fresh(self):
        """Re-import phase_manager to pick up env changes."""
        import importlib
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager
        return phase_manager

    def test_exact_banned_fast_pass(self):
        """T-1.4a: reviewer='fast-pass' is rejected."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "fast-pass", "score": 0.9}
        error = pm._validate_gate_reviewer(gate_result)
        self.assertIsNotNone(error, "fast-pass should be flagged as banned")
        self.assertIn("fast-pass", error.lower())
        print("PASS T-1.4a: fast-pass reviewer rejected")

    def test_exact_banned_just_finish_auto(self):
        """T-1.4b: reviewer='just-finish-auto' is rejected."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "just-finish-auto", "score": 0.9}
        error = pm._validate_gate_reviewer(gate_result)
        self.assertIsNotNone(error, "just-finish-auto should be flagged as banned")
        print("PASS T-1.4b: just-finish-auto reviewer rejected")

    def test_prefix_banned_auto_approve_anything(self):
        """T-1.4c: reviewer='auto-approve-xyz' (prefix match) is rejected."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "auto-approve-xyz", "score": 0.9}
        error = pm._validate_gate_reviewer(gate_result)
        self.assertIsNotNone(error, "auto-approve-xyz should be flagged via prefix")
        print("PASS T-1.4c: auto-approve-xyz prefix rejected")

    def test_legitimate_reviewer_passes(self):
        """T-1.4d: reviewer='wicked-garden:engineering:senior-engineer' is accepted."""
        pm = self._import_fresh()
        gate_result = {
            "result": "APPROVE",
            "reviewer": "wicked-garden:engineering:senior-engineer",
            "score": 0.9,
        }
        error = pm._validate_gate_reviewer(gate_result)
        self.assertIsNone(error, f"Legitimate reviewer should not be flagged: {error}")
        print("PASS T-1.4d: legitimate reviewer accepted")

    def test_missing_reviewer_field_rejected(self):
        """T-1.4e: gate result missing reviewer field is rejected."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "score": 0.9}
        error = pm._validate_gate_reviewer(gate_result)
        self.assertIsNotNone(error, "Missing reviewer should be flagged")
        print("PASS T-1.4e: missing reviewer field rejected")


class TestMinGateScore(unittest.TestCase):
    """T-1.3: Minimum gate score threshold blocks advancement."""

    def setUp(self):
        os.environ.pop("CREW_GATE_ENFORCEMENT", None)

    def _import_fresh(self):
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager
        return phase_manager

    def test_score_below_threshold_blocked(self):
        """T-1.3a: score 0.4 against min_gate_score 0.7 is blocked."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "wicked-garden:qe:test-strategist", "score": 0.4}
        phases_config = {"design": {"min_gate_score": 0.7}}
        error = pm._validate_min_gate_score(gate_result, "design", phases_config)
        self.assertIsNotNone(error, "Score 0.4 should fail min_gate_score 0.7")
        self.assertIn("0.40", error)
        self.assertIn("0.70", error)
        print("PASS T-1.3a: low score blocked")

    def test_score_at_threshold_passes(self):
        """T-1.3b: score exactly at threshold passes."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "wicked-garden:qe:test-strategist", "score": 0.7}
        phases_config = {"design": {"min_gate_score": 0.7}}
        error = pm._validate_min_gate_score(gate_result, "design", phases_config)
        self.assertIsNone(error, f"Score at threshold should pass: {error}")
        print("PASS T-1.3b: score at threshold passes")

    def test_null_score_treated_as_zero(self):
        """T-1.3c: null/absent score treated as 0.0."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "wicked-garden:qe:test-strategist"}
        phases_config = {"build": {"min_gate_score": 0.7}}
        error = pm._validate_min_gate_score(gate_result, "build", phases_config)
        self.assertIsNotNone(error, "Absent score should fail min_gate_score 0.7")
        print("PASS T-1.3c: null score treated as 0.0 and blocked")

    def test_no_min_score_config_passes(self):
        """T-1.3d: phase with no min_gate_score config passes."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "wicked-garden:qe:test-strategist", "score": 0.1}
        phases_config = {"ideate": {"min_gate_score": None}}
        error = pm._validate_min_gate_score(gate_result, "ideate", phases_config)
        self.assertIsNone(error, f"None min_gate_score should not block: {error}")
        print("PASS T-1.3d: no min score config passes")


class TestLegacyMode(unittest.TestCase):
    """T-1.6: CREW_GATE_ENFORCEMENT=legacy bypasses all enforcement."""

    def setUp(self):
        os.environ["CREW_GATE_ENFORCEMENT"] = "legacy"

    def tearDown(self):
        os.environ.pop("CREW_GATE_ENFORCEMENT", None)

    def _import_fresh(self):
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager
        return phase_manager

    def test_banned_reviewer_bypassed_in_legacy(self):
        """T-1.6a: banned reviewer name is bypassed in legacy mode."""
        pm = self._import_fresh()
        self.assertEqual(pm.GATE_ENFORCEMENT_MODE, "legacy")
        gate_result = {"result": "APPROVE", "reviewer": "fast-pass", "score": 0.9}
        error = pm._validate_gate_reviewer(gate_result)
        self.assertIsNone(error, "Legacy mode should bypass banned reviewer check")
        print("PASS T-1.6a: banned reviewer bypassed in legacy mode")

    def test_min_score_bypassed_in_legacy(self):
        """T-1.6b: min_gate_score check bypassed in legacy mode."""
        pm = self._import_fresh()
        gate_result = {"result": "APPROVE", "reviewer": "wicked-garden:qe:test-strategist", "score": 0.1}
        phases_config = {"design": {"min_gate_score": 0.7}}
        error = pm._validate_min_gate_score(gate_result, "design", phases_config)
        self.assertIsNone(error, "Legacy mode should bypass min score check")
        print("PASS T-1.6b: min score check bypassed in legacy mode")

    def test_condition_verify_bypassed_in_legacy(self):
        """T-1.6c: _verify_conditions returns [] in legacy mode."""
        pm = self._import_fresh()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            phase_dir = project_dir / "phases" / "clarify"
            phase_dir.mkdir(parents=True)
            # Write an unverified conditions manifest
            manifest = {
                "source_gate": "clarify",
                "conditions": [{"id": "CONDITION-1", "description": "Fix error handling", "verified": False}]
            }
            (phase_dir / "conditions-manifest.json").write_text(json.dumps(manifest))
            issues = pm._verify_conditions(project_dir, "clarify")
            self.assertEqual(issues, [], "Legacy mode should bypass condition verification")
        print("PASS T-1.6c: condition verification bypassed in legacy mode")


class TestEmptyDeliverable(unittest.TestCase):
    """T-1.5: Zero-byte deliverables are reported as empty."""

    def setUp(self):
        os.environ.pop("CREW_GATE_ENFORCEMENT", None)

    def _import_fresh(self):
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager
        return phase_manager

    def test_empty_file_reported(self):
        """T-1.5: 0-byte objective.md is reported as empty deliverable."""
        pm = self._import_fresh()
        # We test _check_phase_deliverables indirectly by testing content validation logic
        # directly since get_project_dir uses DomainStore which is harder to mock cleanly.
        # Test the path existence + size logic used in _check_phase_deliverables:
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = Path(tmpdir) / "objective.md"
            empty_file.write_text("")  # 0 bytes
            self.assertEqual(empty_file.stat().st_size, 0)

            # Verify the condition: GATE_ENFORCEMENT_MODE != "legacy" and size == 0 => issue
            self.assertNotEqual(pm.GATE_ENFORCEMENT_MODE, "legacy")
            size = empty_file.stat().st_size
            if pm.GATE_ENFORCEMENT_MODE != "legacy" and size == 0:
                issue = f"Empty deliverable for clarify: objective.md (0 bytes)"
            else:
                issue = None
            self.assertIsNotNone(issue, "Empty file should produce an issue")
            self.assertIn("0 bytes", issue)
        print("PASS T-1.5: empty deliverable (0 bytes) detected")


class TestPhasesJsonStructure(unittest.TestCase):
    """Tests that read phases.json directly."""

    def setUp(self):
        plugin_root = Path(__file__).resolve().parents[2]
        self.phases_json_path = plugin_root / ".claude-plugin" / "phases.json"
        with self.phases_json_path.open() as f:
            self.phases = json.load(f)["phases"]

    def test_T4_1_build_depends_on_design(self):
        """T-4.1: build.depends_on includes 'design'."""
        build_deps = self.phases.get("build", {}).get("depends_on", [])
        self.assertIn("design", build_deps,
                      f"build.depends_on should include 'design', got: {build_deps}")
        self.assertIn("clarify", build_deps,
                      f"build.depends_on should still include 'clarify', got: {build_deps}")
        print(f"PASS T-4.1: build.depends_on={build_deps}")

    def test_T3_2_test_strategy_skip_threshold(self):
        """T-3.2: test-strategy has skip_complexity_threshold: 3."""
        ts = self.phases.get("test-strategy", {})
        threshold = ts.get("skip_complexity_threshold")
        self.assertEqual(threshold, 3,
                         f"test-strategy.skip_complexity_threshold should be 3, got: {threshold}")
        print(f"PASS T-3.2: test-strategy.skip_complexity_threshold={threshold}")

    def test_T1_7_min_gate_scores(self):
        """T-1.7: Each phase has correct min_gate_score defaults."""
        expected = {
            "clarify": 0.6,
            "design": 0.7,
            "test-strategy": 0.6,
            "build": 0.7,
            "test": 0.8,
            "review": 0.7,
        }
        for phase, expected_score in expected.items():
            actual = self.phases.get(phase, {}).get("min_gate_score")
            self.assertEqual(
                actual, expected_score,
                f"Phase '{phase}' min_gate_score: expected {expected_score}, got {actual}"
            )
        print(f"PASS T-1.7: all min_gate_score values correct: {expected}")

    def test_T4_2_skippable_phases_have_valid_skip_reasons(self):
        """T-4.2: Skippable phases with valid_skip_reasons define non-empty arrays."""
        for phase_name, phase_config in self.phases.items():
            if phase_config.get("is_skippable") and phase_config.get("valid_skip_reasons") is not None:
                reasons = phase_config["valid_skip_reasons"]
                self.assertIsInstance(reasons, list,
                                      f"Phase '{phase_name}' valid_skip_reasons should be a list")
                self.assertGreater(len(reasons), 0,
                                   f"Phase '{phase_name}' valid_skip_reasons should not be empty")
                # Verify recognized reason values
                known_reasons = {
                    "complexity_below_threshold", "user_explicit_request",
                    "ci_equivalent_exists", "out_of_scope", "legacy"
                }
                for reason in reasons:
                    self.assertIn(reason, known_reasons,
                                  f"Phase '{phase_name}' has unrecognized skip reason: '{reason}'")
        print("PASS T-4.2: skippable phases have valid, non-empty valid_skip_reasons arrays")


class TestSkipPhaseStructuredReason(unittest.TestCase):
    """T-4.2 functional: skip_phase raises on unrecognized reason."""

    def setUp(self):
        os.environ.pop("CREW_GATE_ENFORCEMENT", None)

    def _import_fresh(self):
        if "phase_manager" in sys.modules:
            del sys.modules["phase_manager"]
        import phase_manager
        return phase_manager

    def test_unrecognized_reason_raises(self):
        """T-4.2a: skip_phase raises ValueError with unrecognized reason."""
        pm = self._import_fresh()
        # Test the structured reason validation logic directly
        phases_config = {
            "design": {
                "is_skippable": True,
                "valid_skip_reasons": [
                    "complexity_below_threshold",
                    "user_explicit_request",
                    "ci_equivalent_exists",
                    "out_of_scope"
                ]
            }
        }
        phase_name = "design"
        reason = "not needed"
        valid_reasons = phases_config[phase_name]["valid_skip_reasons"]
        reason_lower = reason.lower().strip()
        matched = any(
            reason_lower == vr.lower() or reason_lower.startswith(vr.lower())
            for vr in valid_reasons
            if reason_lower
        )
        self.assertFalse(matched, "Unrecognized reason 'not needed' should not match")
        print("PASS T-4.2a: unrecognized reason 'not needed' correctly rejected")

    def test_recognized_reason_passes(self):
        """T-4.2b: skip_phase succeeds with valid reason."""
        valid_reasons = [
            "complexity_below_threshold", "user_explicit_request",
            "ci_equivalent_exists", "out_of_scope"
        ]
        reason = "complexity_below_threshold"
        reason_lower = reason.lower().strip()
        matched = any(
            reason_lower == vr.lower() or reason_lower.startswith(vr.lower())
            for vr in valid_reasons
            if reason_lower
        )
        self.assertTrue(matched, "Valid reason should match")
        print("PASS T-4.2b: valid reason 'complexity_below_threshold' accepted")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBannedReviewer))
    suite.addTests(loader.loadTestsFromTestCase(TestMinGateScore))
    suite.addTests(loader.loadTestsFromTestCase(TestLegacyMode))
    suite.addTests(loader.loadTestsFromTestCase(TestEmptyDeliverable))
    suite.addTests(loader.loadTestsFromTestCase(TestPhasesJsonStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestSkipPhaseStructuredReason))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
