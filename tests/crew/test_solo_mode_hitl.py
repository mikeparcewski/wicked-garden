"""Tests for solo-mode HITL dispatch (Issue #651).

Covers:
  - dispatch_human_inline APPROVE → score 1.0
  - dispatch_human_inline CONDITIONAL → conditions-manifest.json written
  - dispatch_human_inline REJECT → blocks advancement
  - Ambiguous response → re-prompt → second response parsed
  - Headless fallback → stub with mode_fallback_reason
  - gate_result_schema.validate_gate_result accepts mode=human-inline
  - gate_result_schema.validate_gate_result accepts gate-result without mode field
  - content_sanitizer passes reviewer=human-inline
  - dispatch_log: orphan check passes when dispatch-log entry exists for human-inline
  - full rigor + solo_mode flag → rejects with SoloModeUnavailableError
  - global config default_hitl_mode=inline activates solo mode
  - resolve_solo_mode precedence (flag > extras > global config > default)

Deterministic (no wall-clock, no random, no sleep). Stdlib-only.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import solo_mode as sm
from solo_mode import (
    dispatch_human_inline,
    is_solo_mode,
    load_global_config,
    reject_full_rigor_solo,
    resolve_solo_mode,
    SoloModeUnavailableError,
    REVIEWER_NAME,
    DISPATCH_MODE,
)
from gate_result_schema import validate_gate_result, GateResultSchemaError
from content_sanitizer import sanitize_strict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(name="test-solo", rigor_tier=None, solo_mode=False) -> MagicMock:
    """Return a minimal ProjectState-like mock."""
    state = MagicMock()
    state.name = name
    state.extras = {}
    if rigor_tier:
        state.extras["rigor_tier"] = rigor_tier
    if solo_mode:
        state.extras["solo_mode"] = True
    return state


def _minimal_gate_policy() -> dict:
    return {
        "mode": "human-inline",
        "reviewers": ["gate-adjudicator"],
        "min_score": 0.7,
        "evidence_required": ["code-review-complete"],
    }


def _valid_gate_result(**overrides) -> dict:
    base = {
        "verdict": "APPROVE",
        "reviewer": "security-engineer",
        "recorded_at": "2026-04-25T10:00:00+00:00",
        "reason": "All conditions met.",
        "score": 0.9,
        "min_score": 0.7,
        "conditions": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# dispatch_human_inline — happy path: APPROVE → score 1.0
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineApprove(unittest.TestCase):
    """dispatch_human_inline with APPROVE response produces score=1.0."""

    def test_approve_verdict_score_is_1(self):
        state = _make_state()
        policy = _minimal_gate_policy()
        responses = iter(["APPROVE"])
        printed = []

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=Path(tmpdir)), \
                 patch("dispatch_log.append"):
                result = dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": next(responses),
                    _print_fn=printed.append,
                )

        self.assertEqual(result["verdict"], "APPROVE")
        self.assertAlmostEqual(result["score"], 1.0)
        self.assertEqual(result["reviewer"], REVIEWER_NAME)
        self.assertEqual(result["dispatch_mode"], DISPATCH_MODE)

    def test_approve_case_insensitive(self):
        """'approve' (lowercase) is accepted."""
        state = _make_state()
        policy = _minimal_gate_policy()
        responses = iter(["approve"])

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
                _input_fn=lambda _="": next(responses),
                _print_fn=lambda _: None,
            )

        self.assertEqual(result["verdict"], "APPROVE")


# ---------------------------------------------------------------------------
# dispatch_human_inline — CONDITIONAL → conditions-manifest written
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineConditional(unittest.TestCase):
    """CONDITIONAL response writes conditions-manifest.json."""

    def test_conditional_conditions_manifest_written(self):
        state = _make_state()
        policy = _minimal_gate_policy()
        conditions_text = "All tests must pass before merge"
        responses = iter([f"CONDITIONAL: {conditions_text}"])

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=proj_dir), \
                 patch("dispatch_log.append"):
                result = dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": next(responses),
                    _print_fn=lambda _: None,
                )

            self.assertEqual(result["verdict"], "CONDITIONAL")
            self.assertAlmostEqual(result["score"], 0.7)

            manifest_path = proj_dir / "phases" / "build" / "conditions-manifest.json"
            self.assertTrue(manifest_path.exists(), "conditions-manifest.json must be written")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(len(manifest["conditions"]), 1)
            self.assertEqual(manifest["conditions"][0]["id"], "C-inline-1")
            self.assertIn(conditions_text, manifest["conditions"][0]["description"])
            self.assertEqual(manifest["conditions"][0]["status"], "pending")

    def test_conditional_manifest_path_in_result(self):
        """Result dict includes conditions_manifest_path."""
        state = _make_state()
        policy = _minimal_gate_policy()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=Path(tmpdir)), \
                 patch("dispatch_log.append"):
                result = dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": "CONDITIONAL: needs review",
                    _print_fn=lambda _: None,
                )

        self.assertIn("conditions_manifest_path", result)

    def test_conditional_score_is_0_7(self):
        state = _make_state()
        policy = _minimal_gate_policy()

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "review", "evidence-quality", policy,
                _input_fn=lambda _="": "CONDITIONAL: fix linting",
                _print_fn=lambda _: None,
            )

        self.assertAlmostEqual(result["score"], 0.7)


# ---------------------------------------------------------------------------
# dispatch_human_inline — REJECT → blocks advancement
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineReject(unittest.TestCase):
    """REJECT response → score=0.0, verdict REJECT."""

    def test_reject_verdict_and_score(self):
        state = _make_state()
        policy = _minimal_gate_policy()
        responses = iter(["REJECT: tests are failing"])

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
                _input_fn=lambda _="": next(responses),
                _print_fn=lambda _: None,
            )

        self.assertEqual(result["verdict"], "REJECT")
        self.assertAlmostEqual(result["score"], 0.0)
        self.assertIn("REJECT", result["reason"])

    def test_reject_no_conditions_manifest(self):
        """REJECT does not write a conditions-manifest.json."""
        state = _make_state()
        policy = _minimal_gate_policy()

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=proj_dir), \
                 patch("dispatch_log.append"):
                dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": "REJECT: not ready",
                    _print_fn=lambda _: None,
                )

            manifest_path = proj_dir / "phases" / "build" / "conditions-manifest.json"
            self.assertFalse(
                manifest_path.exists(),
                "conditions-manifest.json must NOT be written on REJECT",
            )


# ---------------------------------------------------------------------------
# dispatch_human_inline — Ambiguous → re-prompt → second response parsed
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineReprompt(unittest.TestCase):
    """Ambiguous first response triggers re-prompt; second response is parsed."""

    def test_ambiguous_then_approve(self):
        """First response is ambiguous; second APPROVE is accepted."""
        state = _make_state()
        policy = _minimal_gate_policy()
        call_count = {"n": 0}
        responses = ["maybe?", "APPROVE"]

        def _input(_=""):
            val = responses[call_count["n"]]
            call_count["n"] += 1
            return val

        printed = []
        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "review", "evidence-quality", policy,
                _input_fn=_input,
                _print_fn=printed.append,
            )

        self.assertEqual(result["verdict"], "APPROVE")
        # Re-prompt message must have been printed
        reprompt_msgs = [m for m in printed if "Please respond" in m]
        self.assertEqual(len(reprompt_msgs), 1, "Expected exactly one re-prompt message")

    def test_ambiguous_twice_defaults_to_conditional(self):
        """Two ambiguous responses default to CONDITIONAL (not a hard failure)."""
        state = _make_state()
        policy = _minimal_gate_policy()

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "review", "evidence-quality", policy,
                _input_fn=lambda _="": "uhh",
                _print_fn=lambda _: None,
            )

        self.assertEqual(result["verdict"], "CONDITIONAL")


# ---------------------------------------------------------------------------
# dispatch_human_inline — headless fallback
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineHeadless(unittest.TestCase):
    """When session is non-interactive, returns stub with mode_fallback_reason."""

    def test_headless_fallback_stub_returned(self):
        state = _make_state()
        policy = _minimal_gate_policy()

        with patch("solo_mode._is_interactive", return_value=False):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
            )

        self.assertIn("mode_fallback_reason", result)
        self.assertEqual(result["mode_fallback_reason"], "no-interactive-session")
        self.assertEqual(result["dispatch_mode"], DISPATCH_MODE)

    def test_headless_env_var_triggers_fallback(self):
        """WG_HEADLESS=true is treated as non-interactive."""
        state = _make_state()
        policy = _minimal_gate_policy()

        with patch.dict(os.environ, {"WG_HEADLESS": "true"}):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
            )

        self.assertIn("mode_fallback_reason", result)


# ---------------------------------------------------------------------------
# gate_result_schema — mode=human-inline accepted
# ---------------------------------------------------------------------------

class TestGateResultSchemaHumanInlineMode(unittest.TestCase):
    """validate_gate_result accepts mode=human-inline."""

    def test_mode_human_inline_accepted(self):
        data = _valid_gate_result(mode="human-inline")
        validate_gate_result(data)  # must not raise

    def test_mode_council_accepted(self):
        data = _valid_gate_result(mode="council")
        validate_gate_result(data)  # must not raise

    def test_mode_sequential_accepted(self):
        data = _valid_gate_result(mode="sequential")
        validate_gate_result(data)  # must not raise

    def test_invalid_mode_rejected(self):
        data = _valid_gate_result(mode="bogus-mode-xyz")
        with self.assertRaises(GateResultSchemaError):
            validate_gate_result(data)

    def test_absent_mode_accepted_backward_compat(self):
        """Gate-result without a mode field must still validate (backward-compat)."""
        data = _valid_gate_result()  # no mode key
        self.assertNotIn("mode", data)
        validate_gate_result(data)  # must not raise

    def test_mode_none_accepted_backward_compat(self):
        """mode=None is treated as absent (backward-compat)."""
        data = _valid_gate_result(mode=None)
        validate_gate_result(data)  # must not raise


# ---------------------------------------------------------------------------
# content_sanitizer — reviewer=human-inline passes strict allowlist
# ---------------------------------------------------------------------------

class TestContentSanitizerHumanInlineReviewer(unittest.TestCase):
    """reviewer: 'human-inline' passes the strict codepoint allow-list."""

    def test_human_inline_reviewer_passes_strict(self):
        result = sanitize_strict(REVIEWER_NAME, field="reviewer")
        self.assertEqual(result, REVIEWER_NAME)

    def test_mode_human_inline_passes_strict(self):
        result = sanitize_strict(DISPATCH_MODE, field="mode")
        self.assertEqual(result, DISPATCH_MODE)


# ---------------------------------------------------------------------------
# dispatch_log — orphan check passes when pre-registered entry exists
# ---------------------------------------------------------------------------

class TestDispatchLogHumanInlineOrphan(unittest.TestCase):
    """check_orphan passes when a human-inline dispatch-log entry exists."""

    def test_orphan_check_passes_with_prior_dispatch_entry(self):
        """When dispatch_log.append is called before gate-result write,
        check_orphan finds the matching (reviewer, phase, gate, dispatched_at)
        entry, HMAC-verifies it, and returns without raising.

        The env override WG_GATE_RESULT_DISPATCH_CHECK=off was removed in
        #662 blocker-3.  The test now exercises the real orphan-check path.
        The HMAC used by append and check_orphan is the same process-local
        secret (auto-generated once per process), so the verify succeeds.
        """
        from dispatch_log import append, check_orphan, set_hmac_secret

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            phase = "build"
            gate = "code-quality"
            reviewer = REVIEWER_NAME
            dispatched_at = "2026-04-25T10:00:00+00:00"

            # Pin a known secret so append and check_orphan share it
            # deterministically within this test (avoids SessionState I/O).
            test_secret = "test-hmac-secret-662-blocker3"
            set_hmac_secret(test_secret)
            try:
                # Write a dispatch-log entry (as _dispatch_human_inline does)
                append(
                    proj_dir, phase,
                    reviewer=reviewer,
                    gate=gate,
                    dispatch_id=f"{phase}:{gate}:{reviewer}:{dispatched_at}",
                    dispatcher_agent="wicked-garden:crew:phase-manager:human-inline",
                    dispatched_at=dispatched_at,
                )

                # check_orphan for a gate-result with recorded_at >= dispatched_at
                parsed = {
                    "reviewer": reviewer,
                    "gate": gate,
                    "recorded_at": "2026-04-25T10:01:00+00:00",
                }

                # Must match the pre-registered entry and HMAC-verify successfully
                try:
                    check_orphan(parsed, proj_dir, phase)
                except Exception as exc:
                    self.fail(f"check_orphan raised unexpectedly: {exc}")
            finally:
                set_hmac_secret(None)  # restore neutral state for other tests


# ---------------------------------------------------------------------------
# full rigor + solo_mode → SoloModeUnavailableError
# ---------------------------------------------------------------------------

class TestSoloModeFullRigorBlocked(unittest.TestCase):
    """solo_mode at full rigor raises SoloModeUnavailableError."""

    def test_full_rigor_raises(self):
        state = _make_state(rigor_tier="full")
        with self.assertRaises(SoloModeUnavailableError) as ctx:
            reject_full_rigor_solo(state)
        self.assertIn("full rigor", str(ctx.exception))

    def test_standard_rigor_does_not_raise(self):
        state = _make_state(rigor_tier="standard")
        reject_full_rigor_solo(state)  # must not raise

    def test_minimal_rigor_does_not_raise(self):
        state = _make_state(rigor_tier="minimal")
        reject_full_rigor_solo(state)  # must not raise


# ---------------------------------------------------------------------------
# global config default_hitl_mode=inline
# ---------------------------------------------------------------------------

class TestGlobalConfigDefaultHitlMode(unittest.TestCase):
    """default_hitl_mode: inline in global config activates solo mode."""

    def test_global_config_inline_activates_solo_mode(self):
        state = _make_state()  # no extras
        cfg = {"default_hitl_mode": "inline"}

        with patch("solo_mode.load_global_config", return_value=cfg):
            result = resolve_solo_mode(state, flag=None)

        self.assertTrue(result)

    def test_global_config_other_value_does_not_activate(self):
        state = _make_state()
        cfg = {"default_hitl_mode": "council"}

        with patch("solo_mode.load_global_config", return_value=cfg):
            result = resolve_solo_mode(state, flag=None)

        self.assertFalse(result)

    def test_global_config_absent_does_not_activate(self):
        state = _make_state()
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag=None)
        self.assertFalse(result)

    def test_load_global_config_returns_empty_on_missing_file(self):
        with patch("solo_mode._GLOBAL_CONFIG_PATH",
                   Path("/tmp/wg-nonexistent-crew-defaults.json")):
            cfg = load_global_config()
        self.assertEqual(cfg, {})

    def test_load_global_config_returns_empty_on_malformed_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{not valid json}")
            tmp_path = Path(f.name)
        try:
            with patch("solo_mode._GLOBAL_CONFIG_PATH", tmp_path):
                cfg = load_global_config()
            self.assertEqual(cfg, {})
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# resolve_solo_mode precedence
# ---------------------------------------------------------------------------

class TestResolveSoloModePrecedence(unittest.TestCase):
    """resolve_solo_mode honours the flag > extras > config > default order."""

    def test_flag_wins_over_everything(self):
        """Explicit --hitl=inline wins even when extras and config disagree."""
        state = _make_state()  # no extras
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag="inline")
        self.assertTrue(result)

    def test_extras_wins_over_config(self):
        """solo_mode=True in state.extras wins over absent global config."""
        state = _make_state(solo_mode=True)
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag=None)
        self.assertTrue(result)

    def test_default_is_false(self):
        state = _make_state()
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag=None)
        self.assertFalse(result)

    def test_flag_none_and_no_extras_and_no_config_is_false(self):
        state = _make_state()
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag=None)
        self.assertFalse(result)

    def test_solo_mode_flag_inline_activates(self):
        """--hitl=inline (canonical flag) activates solo mode."""
        state = _make_state()
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag="inline")
        self.assertTrue(result)

    def test_hitl_flag_council_does_not_activate(self):
        """--hitl=council does not activate inline HITL."""
        state = _make_state()
        with patch("solo_mode.load_global_config", return_value={}):
            result = resolve_solo_mode(state, flag="council")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# is_solo_mode helper
# ---------------------------------------------------------------------------

class TestIsSoloMode(unittest.TestCase):
    def test_true_when_extras_set(self):
        state = _make_state(solo_mode=True)
        self.assertTrue(is_solo_mode(state))

    def test_false_when_extras_not_set(self):
        state = _make_state()
        self.assertFalse(is_solo_mode(state))

    def test_false_when_state_is_none(self):
        self.assertFalse(is_solo_mode(None))


# ---------------------------------------------------------------------------
# dispatch_human_inline — gate-result.json written with correct shape
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineArtifacts(unittest.TestCase):
    """gate-result.json and inline-review-context.md are written."""

    def test_gate_result_written(self):
        state = _make_state()
        policy = _minimal_gate_policy()

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=proj_dir), \
                 patch("dispatch_log.append"):
                dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": "APPROVE",
                    _print_fn=lambda _: None,
                )

            gr_path = proj_dir / "phases" / "build" / "gate-result.json"
            self.assertTrue(gr_path.exists(), "gate-result.json must be written")
            gr = json.loads(gr_path.read_text())
            self.assertEqual(gr["verdict"], "APPROVE")
            self.assertEqual(gr["reviewer"], REVIEWER_NAME)
            self.assertIn("mode", gr)
            self.assertEqual(gr["mode"], DISPATCH_MODE)

    def test_inline_review_context_written(self):
        state = _make_state()
        policy = _minimal_gate_policy()

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=proj_dir), \
                 patch("dispatch_log.append"):
                dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": "APPROVE",
                    _print_fn=lambda _: None,
                )

            ctx_path = proj_dir / "phases" / "build" / "inline-review-context.md"
            self.assertTrue(ctx_path.exists(), "inline-review-context.md must be written")
            content = ctx_path.read_text()
            self.assertIn("Inline Gate Review", content)
            self.assertIn("APPROVE", content)


# ---------------------------------------------------------------------------
# Blocker 1 (#662): rigor upgraded to full mid-flight → council fallback
# ---------------------------------------------------------------------------

class TestDispatchHumanInlineRigorUpgradeFallback(unittest.TestCase):
    """#662 blocker-1: _dispatch_human_inline falls back to council when
    the project's rigor_tier has been upgraded to 'full' at dispatch time,
    regardless of what the gate-policy entry says.
    """

    def test_full_rigor_at_dispatch_falls_back_to_council(self):
        """Project starts standard+solo_mode, rigor upgrades to full before
        the next gate dispatch — _dispatch_human_inline must route to council
        and annotate the result with mode_fallback_reason=rigor-upgraded-to-full.
        """
        # Import the private dispatcher directly so we can inject a fake council
        import phase_manager as pm

        # State as it looks AFTER the re-evaluate checkpoint upgrades rigor
        state = _make_state(rigor_tier="full", solo_mode=True)
        policy = _minimal_gate_policy()

        # A mock council dispatcher that records what it was called with and
        # returns a minimal council-shaped result.
        council_calls = []

        def _fake_council(s, phase, gate_name, reviewers, *, dispatcher, shared_context_path):
            council_calls.append({
                "phase": phase,
                "gate_name": gate_name,
                "reviewers": reviewers,
            })
            return {
                "verdict": "APPROVE",
                "result": "APPROVE",
                "score": 1.0,
                "min_score": 0.7,
                "reviewer": "gate-adjudicator",
                "reason": "council fallback",
                "conditions": [],
                "phase": phase,
                "gate_name": gate_name,
                "per_reviewer_verdicts": [],
                "reviewers_dispatched": reviewers,
                "dispatch_mode": "council",
                "mode": "council",
                "external_review": False,
                "recorded_at": "2026-04-25T10:00:00Z",
            }

        with patch.object(pm, "_dispatch_council", side_effect=_fake_council):
            result = pm._dispatch_human_inline(
                state, "build", "code-quality", policy,
                dispatcher=None,
            )

        # Council must have been called once
        self.assertEqual(len(council_calls), 1, "council must be dispatched exactly once")
        self.assertEqual(council_calls[0]["gate_name"], "code-quality")

        # Result must carry the fallback annotations
        self.assertEqual(
            result.get("mode_fallback_reason"), "rigor-upgraded-to-full",
            "mode_fallback_reason must be 'rigor-upgraded-to-full'",
        )
        self.assertEqual(
            result.get("original_mode"), "human-inline",
            "original_mode must be 'human-inline'",
        )

    def test_standard_rigor_does_not_trigger_council_fallback(self):
        """Standard rigor does NOT bypass human-inline; the interactive path runs."""
        import phase_manager as pm

        state = _make_state(rigor_tier="standard", solo_mode=True)
        policy = _minimal_gate_policy()
        council_calls = []

        def _unexpected_council(*args, **kwargs):
            council_calls.append(True)
            return {}

        with patch.object(pm, "_dispatch_council", side_effect=_unexpected_council), \
             patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            pm._dispatch_human_inline(
                state, "build", "code-quality", policy,
                _input_fn=lambda _="": "APPROVE",
                _print_fn=lambda _: None,
            )

        self.assertEqual(
            council_calls, [],
            "council must NOT be dispatched at standard rigor",
        )

    def test_no_state_does_not_trigger_council_fallback(self):
        """state=None defaults to 'standard' (no full-rigor bypass)."""
        import phase_manager as pm

        policy = _minimal_gate_policy()
        council_calls = []

        def _unexpected_council(*args, **kwargs):
            council_calls.append(True)
            return {}

        with patch.object(pm, "_dispatch_council", side_effect=_unexpected_council), \
             patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            pm._dispatch_human_inline(
                None, "build", "code-quality", policy,
                _input_fn=lambda _="": "APPROVE",
                _print_fn=lambda _: None,
            )

        self.assertEqual(
            council_calls, [],
            "council must NOT be dispatched when state is None (defaults to standard)",
        )


# ---------------------------------------------------------------------------
# Blocker 2 (#662): bare CONDITIONAL re-prompts instead of silently accepting
# ---------------------------------------------------------------------------

class TestBareConditionalReprompts(unittest.TestCase):
    """#662 blocker-2: bare 'CONDITIONAL' (no colon, no text) is unrecognised
    input and triggers a re-prompt rather than silently writing a vacuous
    conditions-manifest.
    """

    def test_bare_conditional_no_colon_triggers_reprompt(self):
        """CONDITIONAL with no colon is unrecognised — re-prompt fires."""
        state = _make_state()
        policy = _minimal_gate_policy()
        printed = []
        # First call: bare CONDITIONAL (must re-prompt); second call: APPROVE
        responses = iter(["CONDITIONAL", "APPROVE"])

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
                _input_fn=lambda _="": next(responses),
                _print_fn=printed.append,
            )

        # Final verdict is APPROVE (second response), not CONDITIONAL
        self.assertEqual(result["verdict"], "APPROVE")
        # A re-prompt message must have been emitted
        reprompt_msgs = [m for m in printed if "Please respond" in m]
        self.assertEqual(len(reprompt_msgs), 1, "Expected exactly one re-prompt message")

    def test_bare_conditional_with_colon_but_no_text_triggers_reprompt(self):
        """'CONDITIONAL:' (colon present, nothing after) is also unrecognised."""
        state = _make_state()
        policy = _minimal_gate_policy()
        printed = []
        responses = iter(["CONDITIONAL:", "APPROVE"])

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
                _input_fn=lambda _="": next(responses),
                _print_fn=printed.append,
            )

        self.assertEqual(result["verdict"], "APPROVE")
        reprompt_msgs = [m for m in printed if "Please respond" in m]
        self.assertEqual(len(reprompt_msgs), 1, "Expected exactly one re-prompt message")

    def test_bare_conditional_twice_defaults_to_conditional_with_text(self):
        """After max reprompts, the fallback default is CONDITIONAL and the
        conditions-manifest description is NOT the vacuous placeholder
        '(no conditions text provided)' — the fallback sets a non-empty
        conditions_text before calling _write_conditions_manifest.
        """
        state = _make_state()
        policy = _minimal_gate_policy()

        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = Path(tmpdir)
            with patch("solo_mode._is_interactive", return_value=True), \
                 patch("phase_manager.get_project_dir", return_value=proj_dir), \
                 patch("dispatch_log.append"):
                result = dispatch_human_inline(
                    state, "build", "code-quality", policy,
                    _input_fn=lambda _="": "CONDITIONAL",  # always bare
                    _print_fn=lambda _: None,
                )

            # Final verdict must still be CONDITIONAL (soft failure, not error)
            self.assertEqual(result["verdict"], "CONDITIONAL")

            # The conditions-manifest must have been written with a real description
            manifest_path = proj_dir / "phases" / "build" / "conditions-manifest.json"
            self.assertTrue(manifest_path.exists(), "conditions-manifest must be written")
            manifest = json.loads(manifest_path.read_text())
            description = manifest["conditions"][0]["description"]
            self.assertNotEqual(description, "", "manifest description must not be empty")
            self.assertNotIn(
                "(no conditions text provided)", description,
                "vacuous placeholder must never appear in the manifest",
            )

    def test_conditional_with_text_still_accepted(self):
        """'CONDITIONAL: some text' continues to parse successfully."""
        state = _make_state()
        policy = _minimal_gate_policy()

        with patch("solo_mode._is_interactive", return_value=True), \
             patch("phase_manager.get_project_dir", return_value=Path(tempfile.mkdtemp())), \
             patch("dispatch_log.append"):
            result = dispatch_human_inline(
                state, "build", "code-quality", policy,
                _input_fn=lambda _="": "CONDITIONAL: fix linting before merge",
                _print_fn=lambda _: None,
            )

        self.assertEqual(result["verdict"], "CONDITIONAL")
        self.assertAlmostEqual(result["score"], 0.7)


if __name__ == "__main__":
    unittest.main()
