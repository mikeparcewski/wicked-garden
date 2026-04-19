#!/usr/bin/env python3
"""tests/crew/test_validate_gate_policy.py — SC-4 startup validation.

Verifies that ``_validate_gate_policy_full_rigor()`` raises ConfigError when
any gate at full rigor has an empty reviewers list.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


class TestValidateGatePolicyFullRigor(unittest.TestCase):
    """SC-4 / AC-α9 — empty full-rigor reviewers MUST raise ConfigError."""

    def setUp(self):
        # Reset the module-level cache flag so each test runs the validator.
        phase_manager._GATE_POLICY_FULL_VALIDATED = False
        phase_manager._GATE_POLICY_CACHE = None

    def tearDown(self):
        phase_manager._GATE_POLICY_FULL_VALIDATED = False
        phase_manager._GATE_POLICY_CACHE = None

    def test_raises_on_empty_full_reviewers(self):
        """Synthesized gate-policy with empty full-rigor reviewers raises ConfigError."""
        bad_policy = {
            "gates": {
                "design-quality": {
                    "full": {"reviewers": [], "mode": "council", "fallback": "senior-engineer"},
                    "standard": {"reviewers": ["senior-engineer"], "mode": "sequential"},
                },
            },
        }
        with patch.object(phase_manager, "_load_gate_policy", return_value=bad_policy):
            with self.assertRaises(phase_manager.ConfigError):
                phase_manager._validate_gate_policy_full_rigor()

    def test_accepts_populated_full_reviewers(self):
        """Policy with non-empty full-rigor reviewers passes validation."""
        good_policy = {
            "gates": {
                "design-quality": {
                    "full": {"reviewers": ["senior-engineer", "security-engineer"], "mode": "parallel"},
                },
            },
        }
        with patch.object(phase_manager, "_load_gate_policy", return_value=good_policy):
            try:
                phase_manager._validate_gate_policy_full_rigor()
            except phase_manager.ConfigError as exc:
                self.fail(f"Validator raised unexpectedly: {exc}")

    def test_skips_gate_without_full_tier(self):
        """Gates that do not advertise a full tier are skipped (not misconfigured)."""
        mixed_policy = {
            "gates": {
                "requirements-quality": {
                    "standard": {"reviewers": ["requirements-quality-analyst"]},
                    # no 'full' tier
                },
            },
        }
        with patch.object(phase_manager, "_load_gate_policy", return_value=mixed_policy):
            try:
                phase_manager._validate_gate_policy_full_rigor()
            except phase_manager.ConfigError as exc:
                self.fail(f"Validator raised on policy without full tier: {exc}")


if __name__ == "__main__":
    unittest.main()
