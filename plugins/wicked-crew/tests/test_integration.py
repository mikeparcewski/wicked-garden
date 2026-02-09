#!/usr/bin/env python3
"""
Integration tests for wicked-crew v3.

Tests the end-to-end workflow from signal detection to phase management.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from smart_decisioning import (
    detect_signals,
    assess_complexity,
    is_ambiguous,
    analyze_input,
    SignalAnalysis,
)
from phase_manager import (
    Phase,
    PhaseStatus,
    PhaseState,
    ProjectState,
    get_project_dir,
    is_safe_project_name,
    start_phase,
    complete_phase,
    approve_phase,
    can_transition,
    save_project_state,
    load_project_state,
)
from specialist_discovery import (
    discover_specialists,
    clear_cache,
    Specialist,
    Persona,
    Enhancement,
)


class TestSignalDetection(unittest.TestCase):
    """Test signal detection from user input."""

    def test_security_signals(self):
        """Test detection of security-related signals."""
        text = "I need to implement JWT authentication with OAuth2"
        signals = detect_signals(text)
        self.assertIn("security", signals)

    def test_performance_signals(self):
        """Test detection of performance-related signals."""
        text = "We need to optimize the database queries for better latency"
        signals = detect_signals(text)
        self.assertIn("performance", signals)

    def test_ambiguity_signals(self):
        """Test detection of ambiguous input."""
        text = "Should we use PostgreSQL or MongoDB? What are the tradeoffs?"
        self.assertTrue(is_ambiguous(text))

    def test_multiple_signals(self):
        """Test detection of multiple signals."""
        text = "Build a secure API with caching for performance and user login with JWT tokens"
        signals = detect_signals(text)
        self.assertIn("security", signals)  # jwt, login are security keywords
        self.assertIn("performance", signals)  # cache is performance keyword

    def test_no_signals(self):
        """Test when no signals are detected."""
        text = "Hello world"
        signals = detect_signals(text)
        self.assertEqual(len(signals), 0)


class TestComplexityAssessment(unittest.TestCase):
    """Test complexity scoring."""

    def test_simple_input(self):
        """Test simple input scores low complexity."""
        text = "Add a button"
        complexity = assess_complexity(text)
        self.assertLessEqual(complexity, 2)

    def test_complex_input(self):
        """Test complex input scores high complexity."""
        text = """
        We need to migrate the existing authentication system to use OAuth2.
        This involves updating the frontend React components in src/auth/,
        the backend API in src/api/auth.ts, and integrating with our
        existing user database. The team needs to coordinate with the
        security team and the customer success team. What's the best approach?
        """
        complexity = assess_complexity(text)
        self.assertGreaterEqual(complexity, 4)

    def test_complexity_bounds(self):
        """Test complexity is bounded 0-7."""
        text = "x" * 10000
        complexity = assess_complexity(text)
        self.assertLessEqual(complexity, 7)
        self.assertGreaterEqual(complexity, 0)


class TestProjectNameValidation(unittest.TestCase):
    """Test project name validation for path traversal prevention."""

    def test_valid_names(self):
        """Test valid project names."""
        valid_names = [
            "my-project",
            "project_123",
            "MyProject",
            "test",
            "a",
        ]
        for name in valid_names:
            self.assertTrue(is_safe_project_name(name), f"{name} should be valid")

    def test_invalid_names(self):
        """Test invalid project names (path traversal attempts)."""
        invalid_names = [
            "../malicious",
            "../../etc/passwd",
            "project/subdir",
            "project\\subdir",
            "",
            "a" * 100,  # Too long
            "project name with spaces",
            "project.with.dots",
        ]
        for name in invalid_names:
            self.assertFalse(is_safe_project_name(name), f"{name} should be invalid")


class TestPhaseStateMachine(unittest.TestCase):
    """Test phase state machine transitions."""

    def setUp(self):
        """Set up test project state."""
        self.project = ProjectState(
            name="test-project",
            current_phase="clarify",
            created_at="2026-01-24T00:00:00Z",
            phases={}
        )

    def test_start_phase(self):
        """Test starting a phase."""
        updated = start_phase(self.project, Phase.CLARIFY)
        self.assertEqual(updated.current_phase, "clarify")
        self.assertEqual(updated.phases["clarify"].status, "in_progress")
        self.assertIsNotNone(updated.phases["clarify"].started_at)

    def test_complete_phase(self):
        """Test completing a phase."""
        self.project = start_phase(self.project, Phase.CLARIFY)
        updated = complete_phase(self.project, Phase.CLARIFY)
        self.assertEqual(updated.phases["clarify"].status, "complete")
        self.assertIsNotNone(updated.phases["clarify"].completed_at)

    def test_approve_phase(self):
        """Test approving a phase and advancing."""
        self.project = start_phase(self.project, Phase.CLARIFY)
        self.project = complete_phase(self.project, Phase.CLARIFY)
        updated, next_phase = approve_phase(self.project, Phase.CLARIFY)

        self.assertEqual(updated.phases["clarify"].status, "approved")
        self.assertIsNotNone(updated.phases["clarify"].approved_at)
        self.assertEqual(next_phase, Phase.DESIGN)

    def test_cannot_skip_phases(self):
        """Test that phases cannot be skipped without approval."""
        can, reasons = can_transition(self.project, Phase.BUILD)
        self.assertFalse(can)
        self.assertTrue(len(reasons) > 0)

    def test_can_advance_after_approval(self):
        """Test advancing after proper approval."""
        self.project = start_phase(self.project, Phase.CLARIFY)
        self.project = complete_phase(self.project, Phase.CLARIFY)
        self.project, _ = approve_phase(self.project, Phase.CLARIFY)

        can, reasons = can_transition(self.project, Phase.DESIGN)
        self.assertTrue(can)
        self.assertEqual(len(reasons), 0)


class TestAnalysisToSpecialistIntegration(unittest.TestCase):
    """Test end-to-end from analysis to specialist selection."""

    def test_security_input_recommends_devsecops(self):
        """Test security input recommends devsecops specialist."""
        text = "Implement JWT authentication with token refresh"
        analysis = analyze_input(text)

        self.assertIn("security", analysis.signals)
        # wicked-platform should be recommended for security signals
        self.assertTrue(
            any("devsecops" in s for s in analysis.recommended_specialists),
            f"Expected devsecops in {analysis.recommended_specialists}"
        )

    def test_ambiguous_input_recommends_jam(self):
        """Test ambiguous input recommends wicked-jam."""
        text = "Should we use REST or GraphQL? What are the tradeoffs?"
        analysis = analyze_input(text)

        self.assertTrue(analysis.is_ambiguous)
        self.assertTrue(
            any("jam" in s for s in analysis.recommended_specialists),
            f"Expected jam in {analysis.recommended_specialists}"
        )

    def test_high_complexity_includes_qe(self):
        """Test high complexity always includes QE."""
        text = """
        Migrate the payment system to use Stripe. This requires updating
        the database schema, API endpoints, frontend components, and
        integrating with multiple external services. The security team
        and compliance team need to review the changes.
        """
        analysis = analyze_input(text)

        self.assertGreaterEqual(analysis.complexity_score, 3)
        self.assertTrue(
            any("qe" in s for s in analysis.recommended_specialists),
            f"Expected qe in {analysis.recommended_specialists}"
        )


class TestSpecialistDiscoveryCache(unittest.TestCase):
    """Test specialist discovery caching."""

    def setUp(self):
        """Clear cache before each test."""
        clear_cache()

    def test_cache_returns_same_results(self):
        """Test that cached results are returned on second call."""
        # First call
        specialists1 = discover_specialists(use_cache=True)

        # Second call should use cache
        specialists2 = discover_specialists(use_cache=True)

        self.assertEqual(set(specialists1.keys()), set(specialists2.keys()))

    def test_cache_bypass(self):
        """Test that cache can be bypassed."""
        # First call with cache
        specialists1 = discover_specialists(use_cache=True)

        # Second call bypassing cache
        specialists2 = discover_specialists(use_cache=False)

        # Results should still be equal (just not from cache)
        self.assertEqual(set(specialists1.keys()), set(specialists2.keys()))


class TestProjectStatePersistence(unittest.TestCase):
    """Test project state save/load."""

    def setUp(self):
        """Create temp directory for test projects."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get("HOME")
        # We won't actually override HOME since get_project_dir uses Path.home()

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_state_roundtrip(self):
        """Test saving and loading project state."""
        project = ProjectState(
            name="test-roundtrip",
            current_phase="design",
            created_at="2026-01-24T00:00:00Z",
            signals_detected=["security", "performance"],
            complexity_score=5,
            specialists_recommended=["wicked-qe", "wicked-product"],
            phases={
                "clarify": PhaseState(
                    status="approved",
                    started_at="2026-01-24T00:00:00Z",
                    completed_at="2026-01-24T01:00:00Z",
                    approved_at="2026-01-24T01:30:00Z"
                )
            }
        )

        # Save
        try:
            save_project_state(project)

            # Load
            loaded = load_project_state("test-roundtrip")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.name, project.name)
            self.assertEqual(loaded.current_phase, project.current_phase)
            self.assertEqual(loaded.signals_detected, project.signals_detected)
            self.assertEqual(loaded.complexity_score, project.complexity_score)
            self.assertEqual(loaded.phases["clarify"].status, "approved")
        except ValueError as e:
            # If test project already exists or name validation fails
            self.skipTest(f"Project state test skipped: {e}")


if __name__ == "__main__":
    # Set log level to WARNING for tests to reduce noise
    import logging
    logging.getLogger().setLevel(logging.WARNING)

    unittest.main(verbosity=2)
