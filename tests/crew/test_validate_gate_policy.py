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


# ---------------------------------------------------------------------------
# COND-TG-4 — approve_phase() must call _validate_gate_policy_full_rigor()
# ---------------------------------------------------------------------------


class TestApprovePhaseInvokesFullRigorValidator(unittest.TestCase):
    """COND-TG-4 — approve_phase surfaces a malformed full-rigor gate-policy.

    The validator's docstring claims it is called from both ``execute()`` and
    ``approve_phase()`` entry points. A bug previously dropped the call from
    ``approve_phase()``; this regression test asserts the validator runs (and
    raises on a malformed policy) when the project is at full rigor.
    """

    def setUp(self):
        phase_manager._GATE_POLICY_FULL_VALIDATED = False
        phase_manager._GATE_POLICY_CACHE = None

    def tearDown(self):
        phase_manager._GATE_POLICY_FULL_VALIDATED = False
        phase_manager._GATE_POLICY_CACHE = None

    def _make_full_rigor_state(self, name: str = "full-rigor-approve"):
        return phase_manager.ProjectState(
            name=name,
            current_phase="build",
            created_at="2026-04-18T00:00:00Z",
            phase_plan=["clarify", "design", "build", "review"],
            phases={
                "clarify": phase_manager.PhaseState(status="approved"),
                "design": phase_manager.PhaseState(status="approved"),
                "build": phase_manager.PhaseState(
                    status="in_progress",
                    started_at="2026-04-18T01:00:00Z",
                ),
                "review": phase_manager.PhaseState(status="pending"),
            },
            extras={"rigor_tier": "full"},
        )

    def test_approve_phase_raises_config_error_on_malformed_policy(self):
        """approve_phase at full rigor raises ConfigError when policy is malformed."""
        bad_policy = {
            "gates": {
                "code-quality": {
                    "full": {"reviewers": [], "mode": "parallel",
                             "fallback": "senior-engineer"},
                },
            },
        }
        state = self._make_full_rigor_state()
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            (project_dir / "phases" / "build").mkdir(parents=True, exist_ok=True)
            with patch.object(phase_manager, "_load_gate_policy",
                              return_value=bad_policy), \
                 patch.object(phase_manager, "get_project_dir",
                              return_value=project_dir), \
                 patch.object(phase_manager, "save_project_state"):
                with self.assertRaises(phase_manager.ConfigError):
                    phase_manager.approve_phase(state, "build")

    def test_approve_phase_skips_validator_at_standard_rigor(self):
        """approve_phase at non-full rigor does NOT run the full-rigor validator.

        Empty reviewers are legitimate at minimal/standard rigor (advisory
        gates); the validator MUST only fire at full rigor so low-rigor
        projects aren't blocked by a policy gap that doesn't apply to them.
        """
        bad_policy = {
            "gates": {
                "code-quality": {
                    "full": {"reviewers": [], "mode": "parallel",
                             "fallback": "senior-engineer"},
                },
            },
        }
        state = self._make_full_rigor_state("standard-rigor-approve")
        state.extras["rigor_tier"] = "standard"
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            (project_dir / "phases" / "build").mkdir(parents=True, exist_ok=True)
            with patch.object(phase_manager, "_load_gate_policy",
                              return_value=bad_policy), \
                 patch.object(phase_manager, "get_project_dir",
                              return_value=project_dir), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "_check_addendum_freshness",
                              return_value=None), \
                 patch.object(phase_manager, "_check_phase_deliverables",
                              return_value=[]), \
                 patch.object(phase_manager, "load_phases_config", return_value={
                     "build": {"gate_required": False, "depends_on": []},
                 }), \
                 patch.object(phase_manager, "_load_session_dispatches",
                              return_value=[]), \
                 patch.object(phase_manager, "_run_checkpoint_reanalysis",
                              return_value=([], [])), \
                 patch.object(phase_manager, "get_phase_order", return_value=[
                     "clarify", "design", "build", "review"]), \
                 patch.object(phase_manager, "_run_build_phase_guard",
                              return_value=[]), \
                 patch.object(phase_manager, "_sm"):
                # Must NOT raise ConfigError — validator is gated on full rigor.
                try:
                    phase_manager.approve_phase(state, "build")
                except phase_manager.ConfigError as exc:
                    self.fail(
                        f"Validator fired at non-full rigor (regression): {exc}"
                    )
                except ValueError:
                    # Downstream checks may raise for unrelated reasons — we
                    # only care that ConfigError from the validator does not.
                    pass


if __name__ == "__main__":
    unittest.main()
