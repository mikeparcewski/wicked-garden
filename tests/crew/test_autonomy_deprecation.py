#!/usr/bin/env python3
"""tests/crew/test_autonomy_deprecation.py — Deprecation shim mapping tests.

Issue #593 (v8-PR-6).

Covers:
  - Each old surface (auto-approve, just-finish, yolo, engagementLevel) maps
    to the correct new AutonomyMode.
  - Deprecation warning emitted exactly once per session.
  - Shim routing: old mode → autonomy layer produces expected GateDecision shape.

Stdlib-only.  No sleep-based sync.  Single-assertion focus.  Descriptive names.
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = str(_REPO / "scripts")
_SCRIPTS_CREW = str(_REPO / "scripts" / "crew")

for _p in [_SCRIPTS, _SCRIPTS_CREW]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import autonomy as _aut  # noqa: E402
from autonomy import (  # noqa: E402
    AutonomyMode,
    DEPRECATION_MAP,
    apply_policy,
    emit_deprecation_warning,
    load_policy,
    map_deprecated_surface,
    get_mode,
    GATE_CLARIFY,
    GATE_COUNCIL,
    GATE_CHALLENGE,
    GATE_DESTRUCTIVE,
)

_POLICY_PATH = _REPO / ".claude-plugin" / "autonomy-policy.json"


def _policy():
    return load_policy(policy_path=_POLICY_PATH)


# ---------------------------------------------------------------------------
# Mapping tests: each old surface → correct AutonomyMode
# ---------------------------------------------------------------------------


class TestDeprecationMappings(unittest.TestCase):
    """Each old surface maps to the documented new mode."""

    # crew:auto-approve → full
    def test_auto_approve_command_maps_to_full(self):
        """crew:auto-approve → AutonomyMode.FULL."""
        self.assertEqual(map_deprecated_surface("crew:auto-approve"), AutonomyMode.FULL)

    # --yolo → full
    def test_yolo_flag_maps_to_full(self):
        """--yolo → AutonomyMode.FULL."""
        self.assertEqual(map_deprecated_surface("--yolo"), AutonomyMode.FULL)

    # --just-finish → full
    def test_just_finish_flag_maps_to_full(self):
        """--just-finish → AutonomyMode.FULL."""
        self.assertEqual(map_deprecated_surface("--just-finish"), AutonomyMode.FULL)

    # engagementLevel:just-finish → full
    def test_engagement_level_camel_maps_to_full(self):
        """engagementLevel:just-finish → AutonomyMode.FULL."""
        self.assertEqual(
            map_deprecated_surface("engagementLevel:just-finish"), AutonomyMode.FULL
        )

    # engagement_level:just-finish → full (snake_case variant)
    def test_engagement_level_snake_maps_to_full(self):
        """engagement_level:just-finish → AutonomyMode.FULL."""
        self.assertEqual(
            map_deprecated_surface("engagement_level:just-finish"), AutonomyMode.FULL
        )


# ---------------------------------------------------------------------------
# One-shot warning tests
# ---------------------------------------------------------------------------


class TestDeprecationWarningOnce(unittest.TestCase):
    """Deprecation warning fires exactly once per session per process."""

    def setUp(self):
        os.environ.pop(_aut.ENV_WARNED, None)

    def tearDown(self):
        os.environ.pop(_aut.ENV_WARNED, None)

    def test_first_call_emits_warning_returns_true(self):
        """First call returns True and writes to stderr."""
        with patch("sys.stderr", io.StringIO()) as buf:
            result = emit_deprecation_warning("crew:auto-approve")
        self.assertTrue(result)
        self.assertGreater(len(buf.getvalue()), 0)

    def test_second_call_suppressed_returns_false(self):
        """Second call is suppressed (returns False, no stderr output)."""
        os.environ[_aut.ENV_WARNED] = "1"
        with patch("sys.stderr", io.StringIO()) as buf:
            result = emit_deprecation_warning("crew:auto-approve")
        self.assertFalse(result)
        self.assertEqual(buf.getvalue(), "")

    def test_warning_emitted_once_across_sequential_calls(self):
        """Warning fires on call-1 and is suppressed on call-2."""
        call_results = []
        with patch("sys.stderr", io.StringIO()):
            call_results.append(emit_deprecation_warning("--yolo"))
            call_results.append(emit_deprecation_warning("--just-finish"))
        self.assertEqual(call_results, [True, False])

    def test_auto_approve_warning_mentions_surface(self):
        """Warning for crew:auto-approve mentions 'crew:auto-approve'."""
        with patch("sys.stderr", io.StringIO()) as buf:
            emit_deprecation_warning("crew:auto-approve")
        self.assertIn("crew:auto-approve", buf.getvalue())

    def test_yolo_warning_mentions_autonomy_full(self):
        """Warning for --yolo mentions '--autonomy=full'."""
        with patch("sys.stderr", io.StringIO()) as buf:
            emit_deprecation_warning("--yolo", new_flag="--autonomy=full")
        self.assertIn("--autonomy=full", buf.getvalue())


# ---------------------------------------------------------------------------
# Shim routing: old surface → autonomy layer produces valid GateDecision
# ---------------------------------------------------------------------------


class TestShimRoutingProducesValidDecision(unittest.TestCase):
    """Calling apply_policy after mapping an old surface produces a valid decision."""

    def setUp(self):
        self._policy = _policy()

    def _shim(self, surface: str, gate_type: str, context: dict) -> _aut.GateDecision:
        """Simulate what a deprecation shim does: map surface, apply policy."""
        mode = map_deprecated_surface(surface)
        return apply_policy(mode, gate_type, context, policy=self._policy)

    def test_auto_approve_shim_clarify_clean_proceeds(self):
        """auto-approve shim → full mode → clarify clean → proceeds."""
        ctx = {"complexity": 2, "facilitator_confidence": 0.9, "open_questions": 0}
        d = self._shim("crew:auto-approve", GATE_CLARIFY, ctx)
        self.assertTrue(d.proceed)

    def test_yolo_shim_council_unanimous_proceeds(self):
        """--yolo shim → full mode → council unanimous → proceeds."""
        votes = [
            {"model": "a", "verdict": "APPROVE", "confidence": 0.9},
            {"model": "b", "verdict": "APPROVE", "confidence": 0.85},
            {"model": "c", "verdict": "APPROVE", "confidence": 0.8},
        ]
        d = self._shim("--yolo", GATE_COUNCIL, {"votes": votes})
        self.assertTrue(d.proceed)

    def test_just_finish_shim_destructive_always_pauses(self):
        """--just-finish shim → full mode → destructive always pauses."""
        d = self._shim("--just-finish", GATE_DESTRUCTIVE, {})
        self.assertFalse(d.proceed)

    def test_engagement_level_shim_challenge_proceeds(self):
        """engagementLevel:just-finish shim → full mode → challenge proceeds."""
        d = self._shim("engagementLevel:just-finish", GATE_CHALLENGE, {"complexity": 4})
        self.assertTrue(d.proceed)

    def test_shim_decision_is_json_serialisable(self):
        """Shim GateDecision serialises to JSON without error."""
        d = self._shim("--yolo", GATE_CLARIFY,
                        {"complexity": 1, "facilitator_confidence": 0.95,
                         "open_questions": 0})
        serialised = json.dumps(d.to_dict())
        self.assertIsInstance(serialised, str)

    def test_shim_decision_mode_is_full(self):
        """GateDecision.mode is full when routed from any old surface."""
        d = self._shim("--yolo", GATE_CLARIFY, {})
        self.assertEqual(d.mode, AutonomyMode.FULL)

    def test_all_documented_surfaces_produce_valid_decision(self):
        """All five documented deprecated surfaces produce a GateDecision."""
        surfaces = list(DEPRECATION_MAP.keys())
        for surface in surfaces:
            with self.subTest(surface=surface):
                d = self._shim(surface, GATE_CLARIFY, {})
                self.assertIsInstance(d, _aut.GateDecision)


# ---------------------------------------------------------------------------
# get_mode integration: WG_AUTONOMY env var
# ---------------------------------------------------------------------------


class TestGetModeEnvIntegration(unittest.TestCase):
    """WG_AUTONOMY env var controls mode without a CLI arg."""

    def test_wg_autonomy_full_yields_full(self):
        """WG_AUTONOMY=full → AutonomyMode.FULL."""
        mode = get_mode(env={"WG_AUTONOMY": "full"})
        self.assertEqual(mode, AutonomyMode.FULL)

    def test_wg_autonomy_balanced_yields_balanced(self):
        """WG_AUTONOMY=balanced → AutonomyMode.BALANCED."""
        mode = get_mode(env={"WG_AUTONOMY": "balanced"})
        self.assertEqual(mode, AutonomyMode.BALANCED)

    def test_wg_autonomy_ask_yields_ask(self):
        """WG_AUTONOMY=ask → AutonomyMode.ASK."""
        mode = get_mode(env={"WG_AUTONOMY": "ask"})
        self.assertEqual(mode, AutonomyMode.ASK)

    def test_wg_autonomy_unset_yields_ask(self):
        """WG_AUTONOMY unset → AutonomyMode.ASK (conservative default)."""
        mode = get_mode(env={})
        self.assertEqual(mode, AutonomyMode.ASK)

    def test_wg_autonomy_invalid_falls_back_to_ask(self):
        """WG_AUTONOMY=yolo-mode (legacy name) → AutonomyMode.ASK (safe fallback)."""
        mode = get_mode(env={"WG_AUTONOMY": "yolo-mode"})
        self.assertEqual(mode, AutonomyMode.ASK)


if __name__ == "__main__":
    unittest.main()
