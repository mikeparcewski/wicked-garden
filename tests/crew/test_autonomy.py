#!/usr/bin/env python3
"""tests/crew/test_autonomy.py — Test suite for scripts/crew/autonomy.py.

Issue #593 (v8-PR-6).

Covers:
  - Policy JSON loads and validates against schema.
  - ``get_mode()`` reads env var and CLI arg with correct precedence.
  - ``apply_policy()`` for each (mode × gate_type) combination returns
    the documented decision.
  - ``full`` mode + all-ACs-satisfied → auto-proceed.
  - ``full`` mode + partial ACs → falls back to HITL judge behaviour.
  - Deprecation shims: correct new-mode mapping.

Stdlib-only.  No sleep-based sync (T2).  Single-assertion focus (T4).
Descriptive names (T5).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup — mirrors conftest.py but self-contained for robustness
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = str(_REPO / "scripts")
_SCRIPTS_CREW = str(_REPO / "scripts" / "crew")
_PLUGIN_ROOT = str(_REPO)

for _p in [_SCRIPTS, _SCRIPTS_CREW]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import autonomy as _aut  # noqa: E402
from autonomy import (  # noqa: E402
    AutonomyMode,
    GateDecision,
    GatePolicy,
    apply_policy,
    emit_deprecation_warning,
    get_mode,
    load_policy,
    map_deprecated_surface,
    GATE_CLARIFY,
    GATE_COUNCIL,
    GATE_CHALLENGE,
    GATE_DESTRUCTIVE,
    DEPRECATION_MAP,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POLICY_PATH = _REPO / ".claude-plugin" / "autonomy-policy.json"
_SCHEMA_PATH = _REPO / ".claude-plugin" / "autonomy-policy.schema.json"


def _load_real_policy() -> dict[AutonomyMode, GatePolicy]:
    """Load policy from the real JSON file in .claude-plugin/."""
    return load_policy(policy_path=_POLICY_PATH)


# ---------------------------------------------------------------------------
# Stream 1: Policy JSON validation
# ---------------------------------------------------------------------------


class TestPolicyJson(unittest.TestCase):
    """autonomy-policy.json loads and has the required shape."""

    def test_policy_file_exists(self):
        """Policy JSON file exists at expected path."""
        self.assertTrue(_POLICY_PATH.exists(), f"Missing: {_POLICY_PATH}")

    def test_schema_file_exists(self):
        """Schema JSON file exists at expected path."""
        self.assertTrue(_SCHEMA_PATH.exists(), f"Missing: {_SCHEMA_PATH}")

    def test_policy_has_three_modes(self):
        """Policy JSON defines all three modes: ask, balanced, full."""
        policy = _load_real_policy()
        self.assertIn(AutonomyMode.ASK, policy)
        self.assertIn(AutonomyMode.BALANCED, policy)
        self.assertIn(AutonomyMode.FULL, policy)

    def test_ask_clarify_halt_is_always_pause(self):
        """ask mode: clarify_halt == always_pause."""
        policy = _load_real_policy()
        self.assertEqual(policy[AutonomyMode.ASK].clarify_halt, "always_pause")

    def test_balanced_clarify_halt_is_hitl_judge(self):
        """balanced mode: clarify_halt == hitl_judge."""
        policy = _load_real_policy()
        self.assertEqual(policy[AutonomyMode.BALANCED].clarify_halt, "hitl_judge")

    def test_full_clarify_halt_is_auto_unless_judge_pauses(self):
        """full mode: clarify_halt == auto_unless_judge_pauses."""
        policy = _load_real_policy()
        self.assertEqual(
            policy[AutonomyMode.FULL].clarify_halt, "auto_unless_judge_pauses"
        )

    def test_destructive_ops_always_confirm_all_modes(self):
        """All modes: destructive_ops == confirm (never auto-approve)."""
        policy = _load_real_policy()
        for mode, gp in policy.items():
            with self.subTest(mode=mode):
                self.assertEqual(gp.destructive_ops, "confirm")

    def test_load_policy_raises_on_missing_file(self):
        """load_policy raises FileNotFoundError when file does not exist."""
        with self.assertRaises(FileNotFoundError):
            load_policy(policy_path=Path("/nonexistent/autonomy-policy.json"))

    def test_load_policy_raises_on_malformed_json(self):
        """load_policy raises ValueError when JSON has wrong structure."""
        bad_json = json.dumps({"modes": "not-a-dict"})
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(bad_json)
            bad_path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                load_policy(policy_path=bad_path)
        finally:
            bad_path.unlink(missing_ok=True)

    def test_load_policy_raises_on_missing_required_mode(self):
        """load_policy raises ValueError when a required mode is absent."""
        partial_json = json.dumps(
            {"modes": {"ask": {
                "clarify_halt": "always_pause",
                "council_verdict": "show_and_pause",
                "challenge_phase": "require_approval",
                "destructive_ops": "confirm",
            }}}
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(partial_json)
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                load_policy(policy_path=path)
            self.assertIn("missing required modes", str(ctx.exception))
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Stream 2: get_mode() precedence
# ---------------------------------------------------------------------------


class TestGetMode(unittest.TestCase):
    """get_mode() resolves mode from CLI > env > project > default."""

    def test_cli_arg_overrides_env(self):
        """CLI arg takes precedence over WG_AUTONOMY env var."""
        mode = get_mode(cli_arg="balanced", env={"WG_AUTONOMY": "full"})
        self.assertEqual(mode, AutonomyMode.BALANCED)

    def test_env_var_overrides_project_extras(self):
        """WG_AUTONOMY env var overrides project extras."""
        mode = get_mode(
            project_extras={"autonomy_mode": "full"},
            env={"WG_AUTONOMY": "balanced"},
        )
        self.assertEqual(mode, AutonomyMode.BALANCED)

    def test_project_extras_overrides_default(self):
        """Project extras override the ask default."""
        mode = get_mode(
            project_extras={"autonomy_mode": "full"},
            env={},
        )
        self.assertEqual(mode, AutonomyMode.FULL)

    def test_default_is_ask_when_nothing_set(self):
        """Default mode is ask when no CLI arg, no env, no project extras."""
        mode = get_mode(cli_arg=None, project_extras=None, env={})
        self.assertEqual(mode, AutonomyMode.ASK)

    def test_unknown_cli_arg_falls_to_env(self):
        """Unknown CLI arg value is skipped; env is used instead."""
        mode = get_mode(cli_arg="turbo", env={"WG_AUTONOMY": "balanced"})
        self.assertEqual(mode, AutonomyMode.BALANCED)

    def test_unknown_env_falls_to_default(self):
        """Unknown env value falls through to default (ask)."""
        mode = get_mode(env={"WG_AUTONOMY": "yolo-legacy"})
        self.assertEqual(mode, AutonomyMode.ASK)

    def test_all_valid_values_parse(self):
        """All three valid mode strings are accepted."""
        for val in ("ask", "balanced", "full"):
            with self.subTest(val=val):
                self.assertEqual(get_mode(cli_arg=val), AutonomyMode(val))


# ---------------------------------------------------------------------------
# Stream 2: apply_policy() gate decisions
# ---------------------------------------------------------------------------


class TestApplyPolicyAsk(unittest.TestCase):
    """ask mode always pauses for every gate type (except destructive)."""

    def setUp(self):
        self._policy = _load_real_policy()

    def test_ask_clarify_returns_no_proceed(self):
        """ask + clarify: proceed=False."""
        d = apply_policy(AutonomyMode.ASK, GATE_CLARIFY, {}, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_ask_council_returns_no_proceed(self):
        """ask + council: proceed=False."""
        d = apply_policy(AutonomyMode.ASK, GATE_COUNCIL, {}, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_ask_challenge_returns_no_proceed(self):
        """ask + challenge: proceed=False."""
        d = apply_policy(AutonomyMode.ASK, GATE_CHALLENGE, {}, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_ask_destructive_returns_no_proceed(self):
        """ask + destructive: proceed=False."""
        d = apply_policy(AutonomyMode.ASK, GATE_DESTRUCTIVE, {}, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_ask_decision_mode_is_ask(self):
        """ask decisions carry mode=ask."""
        d = apply_policy(AutonomyMode.ASK, GATE_CLARIFY, {}, policy=self._policy)
        self.assertEqual(d.mode, AutonomyMode.ASK)


class TestApplyPolicyBalanced(unittest.TestCase):
    """balanced mode delegates to HITL judge."""

    def setUp(self):
        self._policy = _load_real_policy()

    def test_balanced_clarify_clean_signals_proceeds(self):
        """balanced + clarify + clean signals → judge auto-proceeds."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.9,
            "open_questions": 0,
        }
        d = apply_policy(AutonomyMode.BALANCED, GATE_CLARIFY, ctx, policy=self._policy)
        # With yolo=True + clean signals, hitl_judge should auto-proceed
        self.assertTrue(d.proceed)

    def test_balanced_clarify_low_confidence_pauses(self):
        """balanced + clarify + low confidence → judge pauses."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.5,
            "open_questions": 0,
        }
        d = apply_policy(AutonomyMode.BALANCED, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_balanced_clarify_open_questions_pauses(self):
        """balanced + clarify + open questions → judge pauses."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.9,
            "open_questions": 1,
        }
        d = apply_policy(AutonomyMode.BALANCED, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_balanced_clarify_high_complexity_pauses(self):
        """balanced + clarify + complexity >= 5 → judge pauses."""
        ctx = {
            "complexity": 5,
            "facilitator_confidence": 0.9,
            "open_questions": 0,
        }
        d = apply_policy(AutonomyMode.BALANCED, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_balanced_council_unanimous_high_confidence_proceeds(self):
        """balanced + council + unanimous high-confidence votes → proceeds."""
        votes = [
            {"model": "a", "verdict": "APPROVE", "confidence": 0.9},
            {"model": "b", "verdict": "APPROVE", "confidence": 0.85},
            {"model": "c", "verdict": "APPROVE", "confidence": 0.8},
        ]
        d = apply_policy(
            AutonomyMode.BALANCED,
            GATE_COUNCIL,
            {"votes": votes},
            policy=self._policy,
        )
        self.assertTrue(d.proceed)

    def test_balanced_council_split_pauses(self):
        """balanced + council + split verdicts → pauses."""
        votes = [
            {"model": "a", "verdict": "APPROVE", "confidence": 0.9},
            {"model": "b", "verdict": "REJECT", "confidence": 0.85},
            {"model": "c", "verdict": "APPROVE", "confidence": 0.8},
        ]
        d = apply_policy(
            AutonomyMode.BALANCED,
            GATE_COUNCIL,
            {"votes": votes},
            policy=self._policy,
        )
        self.assertFalse(d.proceed)

    def test_balanced_destructive_always_pauses(self):
        """balanced + destructive: proceed=False regardless of signals."""
        d = apply_policy(
            AutonomyMode.BALANCED, GATE_DESTRUCTIVE, {}, policy=self._policy
        )
        self.assertFalse(d.proceed)


class TestApplyPolicyFull(unittest.TestCase):
    """full mode auto-proceeds when signals are clean."""

    def setUp(self):
        self._policy = _load_real_policy()

    def test_full_clarify_clean_no_ac_module_proceeds(self):
        """full + clarify + clean signals + no AC module → HITL judge auto-proceeds."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.9,
            "open_questions": 0,
        }
        d = apply_policy(AutonomyMode.FULL, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertTrue(d.proceed)

    def test_full_clarify_precomputed_ac_satisfied_proceeds(self):
        """full + clarify + ac_satisfied=True → auto-proceed."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.9,
            "open_questions": 0,
            "ac_satisfied": True,
        }
        d = apply_policy(AutonomyMode.FULL, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertTrue(d.proceed)

    def test_full_clarify_precomputed_ac_not_satisfied_falls_back(self):
        """full + clarify + ac_satisfied=False → falls back to HITL judge."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.9,
            "open_questions": 0,
            "ac_satisfied": False,
        }
        d = apply_policy(AutonomyMode.FULL, GATE_CLARIFY, ctx, policy=self._policy)
        # Clean signals → HITL judge proceeds even without ACs satisfied
        self.assertTrue(d.proceed)
        # But reason should mention fallback
        self.assertIn("ACs not all satisfied", d.reason)

    def test_full_clarify_precomputed_ac_not_satisfied_low_confidence_pauses(self):
        """full + clarify + ac_satisfied=False + low confidence → pauses."""
        ctx = {
            "complexity": 2,
            "facilitator_confidence": 0.5,
            "open_questions": 0,
            "ac_satisfied": False,
        }
        d = apply_policy(AutonomyMode.FULL, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertFalse(d.proceed)

    def test_full_council_unanimous_proceeds(self):
        """full + council + unanimous → auto-proceed."""
        votes = [
            {"model": "a", "verdict": "APPROVE", "confidence": 0.9},
            {"model": "b", "verdict": "APPROVE", "confidence": 0.85},
            {"model": "c", "verdict": "APPROVE", "confidence": 0.8},
        ]
        d = apply_policy(
            AutonomyMode.FULL,
            GATE_COUNCIL,
            {"votes": votes},
            policy=self._policy,
        )
        self.assertTrue(d.proceed)

    def test_full_council_split_pauses(self):
        """full + council + split (not unanimous) → pauses."""
        votes = [
            {"model": "a", "verdict": "APPROVE", "confidence": 0.9},
            {"model": "b", "verdict": "REJECT", "confidence": 0.85},
            {"model": "c", "verdict": "APPROVE", "confidence": 0.8},
        ]
        d = apply_policy(
            AutonomyMode.FULL,
            GATE_COUNCIL,
            {"votes": votes},
            policy=self._policy,
        )
        self.assertFalse(d.proceed)

    def test_full_challenge_proceeds(self):
        """full + challenge: auto-proceed."""
        d = apply_policy(
            AutonomyMode.FULL, GATE_CHALLENGE, {"complexity": 4}, policy=self._policy
        )
        self.assertTrue(d.proceed)

    def test_full_destructive_always_pauses(self):
        """full + destructive: proceed=False (never auto-approved)."""
        d = apply_policy(
            AutonomyMode.FULL, GATE_DESTRUCTIVE, {}, policy=self._policy
        )
        self.assertFalse(d.proceed)

    def test_full_clarify_ac_from_file_all_satisfied(self):
        """full + clarify + ac-evidence.json all satisfied → auto-proceed."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            clarify_dir = project_dir / "phases" / "clarify"
            clarify_dir.mkdir(parents=True)
            (clarify_dir / "ac-evidence.json").write_text(
                json.dumps([
                    {"id": "AC-1", "statement": "login works",
                     "satisfied": True, "satisfied_by": ["test_login.py"]},
                    {"id": "AC-2", "statement": "logout works",
                     "satisfied": True, "satisfied_by": ["test_logout.py"]},
                ]),
                encoding="utf-8",
            )
            ctx = {
                "complexity": 2,
                "facilitator_confidence": 0.9,
                "open_questions": 0,
                "project_dir": str(project_dir),
            }
            d = apply_policy(AutonomyMode.FULL, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertTrue(d.proceed)
        self.assertIn("ACs satisfied", d.reason)

    def test_full_clarify_ac_from_file_partial_satisfied_low_conf_pauses(self):
        """full + clarify + partial ACs + low confidence → pauses."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            clarify_dir = project_dir / "phases" / "clarify"
            clarify_dir.mkdir(parents=True)
            (clarify_dir / "ac-evidence.json").write_text(
                json.dumps([
                    {"id": "AC-1", "statement": "login works",
                     "satisfied": True, "satisfied_by": ["test_login.py"]},
                    {"id": "AC-2", "statement": "logout works",
                     "satisfied": False, "satisfied_by": []},
                ]),
                encoding="utf-8",
            )
            ctx = {
                "complexity": 2,
                "facilitator_confidence": 0.5,  # low confidence
                "open_questions": 0,
                "project_dir": str(project_dir),
            }
            d = apply_policy(AutonomyMode.FULL, GATE_CLARIFY, ctx, policy=self._policy)
        self.assertFalse(d.proceed)


class TestApplyPolicyGateDecisionShape(unittest.TestCase):
    """GateDecision has the correct shape and is serialisable."""

    def setUp(self):
        self._policy = _load_real_policy()

    def test_gate_decision_has_required_fields(self):
        """GateDecision has proceed, reason, mode, gate_type, signals."""
        d = apply_policy(AutonomyMode.ASK, GATE_CLARIFY, {}, policy=self._policy)
        self.assertIsInstance(d.proceed, bool)
        self.assertIsInstance(d.reason, str)
        self.assertIsInstance(d.mode, AutonomyMode)
        self.assertIsInstance(d.gate_type, str)
        self.assertIsInstance(d.signals, dict)

    def test_gate_decision_to_dict_is_json_serialisable(self):
        """GateDecision.to_dict() serialises to JSON without error."""
        d = apply_policy(AutonomyMode.BALANCED, GATE_COUNCIL, {"votes": []},
                         policy=self._policy)
        serialised = json.dumps(d.to_dict())
        self.assertIsInstance(serialised, str)

    def test_unknown_gate_type_returns_no_proceed(self):
        """apply_policy with unknown gate_type returns proceed=False."""
        d = apply_policy(AutonomyMode.FULL, "exotic-gate", {}, policy=self._policy)
        self.assertFalse(d.proceed)


# ---------------------------------------------------------------------------
# Stream 2: map_deprecated_surface
# ---------------------------------------------------------------------------


class TestMapDeprecatedSurface(unittest.TestCase):
    """map_deprecated_surface() maps old names to new modes."""

    def test_auto_approve_maps_to_full(self):
        """crew:auto-approve → full."""
        self.assertEqual(map_deprecated_surface("crew:auto-approve"), AutonomyMode.FULL)

    def test_yolo_maps_to_full(self):
        """--yolo → full."""
        self.assertEqual(map_deprecated_surface("--yolo"), AutonomyMode.FULL)

    def test_just_finish_maps_to_full(self):
        """--just-finish → full."""
        self.assertEqual(map_deprecated_surface("--just-finish"), AutonomyMode.FULL)

    def test_engagement_level_just_finish_maps_to_full(self):
        """engagementLevel:just-finish → full."""
        self.assertEqual(
            map_deprecated_surface("engagementLevel:just-finish"),
            AutonomyMode.FULL,
        )

    def test_engagement_level_snake_case_maps_to_full(self):
        """engagement_level:just-finish → full."""
        self.assertEqual(
            map_deprecated_surface("engagement_level:just-finish"),
            AutonomyMode.FULL,
        )

    def test_unknown_old_surface_maps_to_full(self):
        """Unknown old surfaces default to full (all old surfaces were 'more autonomous')."""
        self.assertEqual(
            map_deprecated_surface("some-unknown-flag"),
            AutonomyMode.FULL,
        )

    def test_deprecation_map_covers_all_expected_surfaces(self):
        """DEPRECATION_MAP has entries for all five documented surfaces."""
        expected_keys = {
            "crew:auto-approve",
            "--yolo",
            "--just-finish",
            "engagementLevel:just-finish",
            "engagement_level:just-finish",
        }
        missing = expected_keys - set(DEPRECATION_MAP.keys())
        self.assertFalse(
            missing,
            f"DEPRECATION_MAP is missing entries for: {missing}",
        )


# ---------------------------------------------------------------------------
# Deprecation warning
# ---------------------------------------------------------------------------


class TestEmitDeprecationWarning(unittest.TestCase):
    """emit_deprecation_warning() emits once per session."""

    def setUp(self):
        # Clear the warned flag from os.environ before each test
        import os
        os.environ.pop(_aut.ENV_WARNED, None)

    def tearDown(self):
        import os
        os.environ.pop(_aut.ENV_WARNED, None)

    def test_emits_warning_on_first_call(self):
        """Warning is emitted on the first call."""
        import io
        with patch("sys.stderr", io.StringIO()) as fake_err:
            result = emit_deprecation_warning("--yolo")
        self.assertTrue(result)
        self.assertIn("DEPRECATION", fake_err.getvalue())

    def test_suppresses_warning_on_second_call(self):
        """Warning is suppressed on the second call (once per session)."""
        import io
        import os
        # Simulate already-warned state
        os.environ[_aut.ENV_WARNED] = "1"
        with patch("sys.stderr", io.StringIO()) as fake_err:
            result = emit_deprecation_warning("--yolo")
        self.assertFalse(result)
        self.assertEqual(fake_err.getvalue(), "")

    def test_warning_message_contains_old_surface_name(self):
        """Warning message mentions the deprecated surface name."""
        import io
        with patch("sys.stderr", io.StringIO()) as fake_err:
            emit_deprecation_warning("crew:auto-approve")
        self.assertIn("crew:auto-approve", fake_err.getvalue())

    def test_warning_message_contains_new_flag(self):
        """Warning message mentions the replacement flag."""
        import io
        with patch("sys.stderr", io.StringIO()) as fake_err:
            emit_deprecation_warning("--yolo", new_flag="--autonomy=full")
        self.assertIn("--autonomy=full", fake_err.getvalue())


# ---------------------------------------------------------------------------
# GatePolicy dataclass
# ---------------------------------------------------------------------------


class TestGatePolicy(unittest.TestCase):
    """GatePolicy dataclass is frozen and converts to dict."""

    def test_gate_policy_is_frozen(self):
        """GatePolicy is immutable (frozen dataclass)."""
        gp = GatePolicy(
            clarify_halt="always_pause",
            council_verdict="show_and_pause",
            challenge_phase="require_approval",
            destructive_ops="confirm",
        )
        with self.assertRaises(Exception):
            gp.clarify_halt = "hitl_judge"  # type: ignore[misc]

    def test_gate_policy_to_dict(self):
        """GatePolicy.to_dict() returns expected keys."""
        gp = GatePolicy(
            clarify_halt="always_pause",
            council_verdict="show_and_pause",
            challenge_phase="require_approval",
            destructive_ops="confirm",
        )
        d = gp.to_dict()
        self.assertIn("clarify_halt", d)
        self.assertIn("council_verdict", d)
        self.assertIn("challenge_phase", d)
        self.assertIn("destructive_ops", d)


# ---------------------------------------------------------------------------
# Issue #620: narrowed exception handling in _check_ac_gate
# ---------------------------------------------------------------------------


class TestCheckAcGateExceptionHandling(unittest.TestCase):
    """Issue #620: silent fallback to None must distinguish expected vs unexpected.

    - FileNotFoundError + ACParseError are EXPECTED ("no ACs available yet")
      and should log at debug, NOT warning.
    - Any other exception is UNEXPECTED (suggests a regression in load_acs or
      environmental failure) and MUST log at WARNING so operators surface it.
    """

    def test_expected_acparseerror_returns_none_no_warning(self):
        """ACParseError raised by load_acs → None, no WARNING-level log."""
        # Import from BOTH possible names so the exception identity matches the
        # one ``_check_ac_gate`` will see — autonomy resolves load_acs lazily,
        # and pytest may resolve the symbol via either ``crew.acceptance_criteria``
        # (package path) or ``acceptance_criteria`` (direct path) depending on
        # sys.path ordering.
        try:
            from crew.acceptance_criteria import ACParseError as _PkgErr
        except ImportError:
            _PkgErr = None
        from acceptance_criteria import ACParseError as _DirectErr

        # Raise the package-import variant if available, since the lazy import
        # in ``_check_ac_gate`` prefers ``from crew.acceptance_criteria``.
        ACParseError = _PkgErr or _DirectErr

        ctx = {"project_dir": "/tmp/_issue_620_does_not_exist"}

        def _raise_parse_error(_project_dir):
            raise ACParseError("simulated parse failure")

        with patch.object(_aut, "logger") as mock_logger, \
             patch("acceptance_criteria.load_acs", side_effect=_raise_parse_error), \
             patch("crew.acceptance_criteria.load_acs", side_effect=_raise_parse_error):
            result = _aut._check_ac_gate(ctx)

        self.assertIsNone(
            result,
            "ACParseError must produce None (silent fallback), not crash.",
        )
        mock_logger.warning.assert_not_called()
        # debug() should have been called with the error
        self.assertTrue(
            mock_logger.debug.called,
            "Expected debug-level log for ACParseError (operators should not see "
            "WARNING noise during the migration window).",
        )

    def test_expected_filenotfounderror_returns_none_no_warning(self):
        """FileNotFoundError raised by load_acs → None, no WARNING-level log."""
        ctx = {"project_dir": "/tmp/_issue_620_does_not_exist"}

        def _raise_fnf(_project_dir):
            raise FileNotFoundError("simulated missing file")

        with patch.object(_aut, "logger") as mock_logger, \
             patch("acceptance_criteria.load_acs", side_effect=_raise_fnf), \
             patch("crew.acceptance_criteria.load_acs", side_effect=_raise_fnf):
            result = _aut._check_ac_gate(ctx)

        self.assertIsNone(result)
        mock_logger.warning.assert_not_called()

    def test_unexpected_exception_returns_none_with_warning(self):
        """Unexpected exception (e.g. RuntimeError) → None + WARNING log (#620)."""
        ctx = {"project_dir": "/tmp/_issue_620_does_not_exist"}

        def _raise_runtime(_project_dir):
            raise RuntimeError("simulated upstream regression")

        with patch.object(_aut, "logger") as mock_logger, \
             patch("acceptance_criteria.load_acs", side_effect=_raise_runtime), \
             patch("crew.acceptance_criteria.load_acs", side_effect=_raise_runtime):
            result = _aut._check_ac_gate(ctx)

        self.assertIsNone(
            result,
            "Unexpected exception must still return None — never crash a gate.",
        )
        self.assertTrue(
            mock_logger.warning.called,
            "Unexpected exception MUST emit a WARNING so operators see the silent "
            "full→balanced mode downgrade (Issue #620 contract).",
        )
        # The warning should mention the fallback so operators can act
        warning_args = mock_logger.warning.call_args
        self.assertIn("balanced mode", str(warning_args))


if __name__ == "__main__":
    unittest.main()
