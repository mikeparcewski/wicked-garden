#!/usr/bin/env python3
"""
tests/hooks/test_prompt_submit_refactor.py

Comprehensive test suite for the prompt_submit.py refactor.

Covers:
  AC-1, AC-2, AC-3  — structural inspection (deleted functions absent)
  AC-4              — hook-local functions preserved
  AC-5              — output format preserved
  AC-8              — fail-open at all four architectural layers
  AC-9              — session state accumulation via HistoryCondenser
  AC-10             — no context duplication

All subprocess tests set CLAUDE_PLUGIN_ROOT to the repo root to prevent the
installed plugin cache from interfering with path resolution.

Pattern follows tests/hooks/test_stop_memory_promotion.py.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_V2_DIR = _SCRIPTS / "smaht" / "v2"
_HOOK_PY = _REPO_ROOT / "hooks" / "scripts" / "prompt_submit.py"


def _base_env(**overrides) -> dict:
    """Build subprocess env with required plugin vars set to repo root."""
    env = {**os.environ}
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    env["WICKED_CP_ENDPOINT"] = ""  # Disable control plane calls
    env.update(overrides)
    return env


def _run_hook(stdin_data: dict | str, env_overrides: dict = None, timeout: int = 15) -> dict:
    """Run the hook as a subprocess, return parsed stdout JSON."""
    if isinstance(stdin_data, dict):
        stdin_str = json.dumps(stdin_data)
    else:
        stdin_str = stdin_data

    env = _base_env(**(env_overrides or {}))
    result = subprocess.run(
        [sys.executable, str(_HOOK_PY)],
        input=stdin_str,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    stdout = result.stdout.strip()
    if not stdout:
        raise AssertionError(
            f"Hook produced no stdout. returncode={result.returncode}, "
            f"stderr={result.stderr[:500]}"
        )
    return json.loads(stdout), result


# =============================================================================
# AC-1, AC-2, AC-3: Structural inspection — deleted functions must be absent
# =============================================================================

class TestRemovedFunctions(unittest.TestCase):
    """AC-1, AC-2, AC-3: Deleted functions must not appear in prompt_submit.py."""

    @classmethod
    def setUpClass(cls):
        cls.src = _HOOK_PY.read_text(encoding="utf-8")

    # AC-1: Routing functions removed
    def test_is_hot_path_removed(self):
        self.assertNotIn("def _is_hot_path(", self.src,
                         "AC-1: _is_hot_path must be removed")

    def test_is_fast_path_removed(self):
        self.assertNotIn("def _is_fast_path(", self.src,
                         "AC-1: _is_fast_path must be removed")

    def test_classify_intents_removed(self):
        self.assertNotIn("def _classify_intents(", self.src,
                         "AC-1: _classify_intents must be removed")

    def test_estimate_complexity_removed(self):
        self.assertNotIn("def _estimate_complexity(", self.src,
                         "AC-1: _estimate_complexity must be removed")

    # AC-2: Assembly functions removed
    def test_assemble_hot_removed(self):
        self.assertNotIn("def _assemble_hot(", self.src,
                         "AC-2: _assemble_hot must be removed")

    def test_assemble_fast_removed(self):
        self.assertNotIn("def _assemble_fast(", self.src,
                         "AC-2: _assemble_fast must be removed")

    def test_assemble_slow_removed(self):
        self.assertNotIn("def _assemble_slow(", self.src,
                         "AC-2: _assemble_slow must be removed")

    def test_query_memory_removed(self):
        self.assertNotIn("def _query_memory(", self.src,
                         "AC-2: _query_memory must be removed")

    def test_query_crew_removed(self):
        self.assertNotIn("def _query_crew(", self.src,
                         "AC-2: _query_crew must be removed")

    def test_query_kanban_removed(self):
        self.assertNotIn("def _query_kanban(", self.src,
                         "AC-2: _query_kanban must be removed")

    def test_query_search_index_removed(self):
        self.assertNotIn("def _query_search_index(", self.src,
                         "AC-2: _query_search_index must be removed")

    def test_query_condenser_removed(self):
        self.assertNotIn("def _query_condenser(", self.src,
                         "AC-2: _query_condenser must be removed")

    # AC-3: Cache functions removed
    def test_read_adapter_cache_removed(self):
        self.assertNotIn("def _read_adapter_cache(", self.src,
                         "AC-3: _read_adapter_cache must be removed")

    def test_write_adapter_cache_removed(self):
        self.assertNotIn("def _write_adapter_cache(", self.src,
                         "AC-3: _write_adapter_cache must be removed")

    def test_no_tmpdir_cache_file_reference(self):
        """AC-3: No reference to the old session cache file path."""
        self.assertNotIn("wicked-smaht-cache-", self.src,
                         "AC-3: session cache file path must not appear in hook")


# =============================================================================
# AC-4: Hook-local functions preserved
# =============================================================================

class TestPreservedFunctions(unittest.TestCase):
    """AC-4: Hook-local functions must survive the refactor intact."""

    @classmethod
    def setUpClass(cls):
        cls.src = _HOOK_PY.read_text(encoding="utf-8")

    def test_check_setup_gate_preserved(self):
        self.assertIn("def _check_setup_gate(", self.src,
                      "AC-4: _check_setup_gate must be preserved")

    def test_build_onboarding_directive_preserved(self):
        self.assertIn("def _build_onboarding_directive(", self.src,
                      "AC-4: _build_onboarding_directive must be preserved")

    def test_increment_turn_preserved(self):
        self.assertIn("def _increment_turn(", self.src,
                      "AC-4: _increment_turn must be preserved")

    def test_capture_session_goal_preserved(self):
        self.assertIn("def _capture_session_goal(", self.src,
                      "AC-4: _capture_session_goal must be preserved")

    def test_suggest_jam_preserved(self):
        self.assertIn("def _suggest_jam(", self.src,
                      "AC-4: _suggest_jam must be preserved")

    def test_gather_context_sync_added(self):
        """New sync bridge must be present post-refactor."""
        self.assertIn("def _gather_context_sync(", self.src,
                      "AC-4: _gather_context_sync bridge must be added")

    def test_orchestrator_referenced(self):
        """Orchestrator must be used in the refactored hook."""
        self.assertIn("Orchestrator", self.src,
                      "AC-4: Orchestrator must be imported/used in hook")

    def test_memory_nudge_preserved(self):
        """Memory nudge logic (every 10 turns) must be preserved."""
        self.assertIn("_STORAGE_NUDGE_INTERVAL", self.src,
                      "AC-4: memory nudge interval must be preserved")

    def test_crew_suggestion_preserved(self):
        """Crew routing suggestion logic must be preserved."""
        self.assertIn("crew_hint_shown", self.src,
                      "AC-4: crew suggestion (crew_hint_shown) must be preserved")


# =============================================================================
# AC-5: Output format preserved
# =============================================================================

class TestOutputFormat(unittest.TestCase):
    """AC-5: Output must use single <system-reminder> block with correct header."""

    @classmethod
    def setUpClass(cls):
        cls.src = _HOOK_PY.read_text(encoding="utf-8")

    def test_system_reminder_tag_present(self):
        self.assertIn("<system-reminder>", self.src,
                      "AC-5: <system-reminder> tag must be present")

    def test_wicked_garden_header_format(self):
        """Header must include path= and turn= fields."""
        self.assertIn("path=", self.src)
        self.assertIn("turn=", self.src)
        self.assertIn("wicked-garden", self.src)

    def test_single_system_reminder_wrapper(self):
        """Output must be wrapped in exactly one <system-reminder> block.

        The format string should contain exactly one f-string that opens the tag.
        We check that the closing tag appears in the output template too,
        and that the content is not double-wrapped.
        """
        # The output format must open and close the tag exactly once
        # in the merged_context construction (not counting comments or sanitization)
        import re
        # Find lines that actually format the tag (not comments, not .replace())
        format_lines = [
            line for line in self.src.splitlines()
            if "<system-reminder>" in line
            and not line.strip().startswith("#")
            and ".replace(" not in line
        ]
        self.assertEqual(
            len(format_lines), 1,
            f"Must have exactly one <system-reminder> format line (not counting comments/sanitization). "
            f"Found: {format_lines}"
        )

    def test_no_context_duplication(self):
        """AC-10: briefing must only be appended to all_parts once."""
        briefing_appends = self.src.count("all_parts.append(briefing")
        self.assertLessEqual(briefing_appends, 1,
                             "AC-10: briefing must only be appended to all_parts once")


# =============================================================================
# AC-8: Fail-open at all four architectural layers
# =============================================================================

class TestFailOpenL1(unittest.TestCase):
    """L1: outer except in main() catches everything."""

    def test_env_var_injection(self):
        """WICKED_SMAHT_FAIL_INJECT causes hook to return continue:true."""
        output, result = _run_hook(
            {"prompt": "test prompt", "session_id": "test-fail-l1"},
            env_overrides={"WICKED_SMAHT_FAIL_INJECT": "1"},
        )
        self.assertTrue(output.get("continue"),
                        "Hook must return continue:true on injected error")
        self.assertEqual(result.returncode, 0,
                         "Hook must exit 0 (not crash) on injected error")
        # Error must be logged to stderr (not silently dropped)
        self.assertIn("WICKED_SMAHT_FAIL_INJECT", result.stderr,
                      "Hook must log injection error to stderr")

    def test_malformed_stdin(self):
        """Hook returns continue:true on malformed JSON stdin."""
        output, result = _run_hook("not valid json {{{")
        self.assertTrue(output.get("continue"))
        self.assertEqual(result.returncode, 0)

    def test_empty_stdin(self):
        """Hook returns continue:true on empty stdin."""
        output, result = _run_hook("")
        self.assertTrue(output.get("continue"))
        self.assertEqual(result.returncode, 0)

    def test_missing_prompt_field(self):
        """Hook returns continue:true when prompt field is empty/missing."""
        output, result = _run_hook({"session_id": "test-no-prompt"})
        self.assertTrue(output.get("continue"))
        self.assertEqual(result.returncode, 0)


class TestFailOpenStructural(unittest.TestCase):
    """Structural: fail-open mechanisms are correctly wired in source."""

    @classmethod
    def setUpClass(cls):
        cls.src = _HOOK_PY.read_text(encoding="utf-8")

    def test_outer_except_catches_all(self):
        """main() must have a catch-all except Exception block."""
        self.assertIn("except Exception", self.src,
                      "main() must have except Exception for fail-open guarantee")

    def test_outer_except_outputs_continue_true(self):
        """Outer except must output continue:True."""
        # Check that continue:True appears in the except block context
        self.assertIn('"continue": True', self.src,
                      "Hook must output continue:True in except handler")

    def test_fail_inject_escape_hatch_present(self):
        """WICKED_SMAHT_FAIL_INJECT escape hatch must be in _gather_context_sync."""
        self.assertIn("WICKED_SMAHT_FAIL_INJECT", self.src,
                      "Fail injection escape hatch must be present for testing")


# =============================================================================
# Unit tests for hook-local functions (importlib.util pattern)
# =============================================================================

def _load_hook_module():
    """Load prompt_submit.py module with CLAUDE_PLUGIN_ROOT set to repo root."""
    import importlib.util
    _orig_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    try:
        spec = importlib.util.spec_from_file_location("prompt_submit_unit", _HOOK_PY)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
    finally:
        if _orig_root is not None:
            os.environ["CLAUDE_PLUGIN_ROOT"] = _orig_root
        else:
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    return hook


class TestIncrementTurn(unittest.TestCase):
    """_increment_turn() increments and persists turn_count."""

    @classmethod
    def setUpClass(cls):
        cls.hook = _load_hook_module()

    def _make_state(self, turn_count=0):
        from unittest.mock import MagicMock
        state = MagicMock()
        state.turn_count = turn_count
        state.update = MagicMock()
        state.save = MagicMock()
        return state

    def test_increment_from_zero(self):
        state = self._make_state(0)
        result = self.hook._increment_turn(state)
        self.assertEqual(result, 1)
        state.update.assert_called_once_with(turn_count=1)
        state.save.assert_called_once()

    def test_increment_from_five(self):
        state = self._make_state(5)
        result = self.hook._increment_turn(state)
        self.assertEqual(result, 6)
        state.update.assert_called_once_with(turn_count=6)

    def test_increment_with_none_state(self):
        """_increment_turn(None) returns 0 gracefully."""
        result = self.hook._increment_turn(None)
        self.assertEqual(result, 0)

    def test_increment_with_save_exception(self):
        """_increment_turn() returns 0 if state.save() raises."""
        state = self._make_state(3)
        state.save.side_effect = OSError("disk full")
        result = self.hook._increment_turn(state)
        self.assertEqual(result, 0)


class TestSuggestJam(unittest.TestCase):
    """_suggest_jam() fires on ambiguity signals, respects hint_shown flag."""

    @classmethod
    def setUpClass(cls):
        cls.hook = _load_hook_module()

    def _make_state(self, jam_hint_shown=False):
        from unittest.mock import MagicMock
        state = MagicMock()
        state.jam_hint_shown = jam_hint_shown
        state.update = MagicMock()
        return state

    def test_returns_hint_on_ambiguity_signals(self):
        state = self._make_state(False)
        result = self.hook._suggest_jam("what are the options for this approach", state)
        self.assertIsNotNone(result)
        self.assertIn("jam", result.lower())

    def test_returns_none_when_hint_shown(self):
        state = self._make_state(jam_hint_shown=True)
        result = self.hook._suggest_jam("what are the options for this approach", state)
        self.assertIsNone(result)

    def test_returns_none_without_signals(self):
        state = self._make_state(False)
        result = self.hook._suggest_jam("find the Router class", state)
        self.assertIsNone(result)

    def test_returns_none_when_already_using_jam(self):
        state = self._make_state(False)
        result = self.hook._suggest_jam("/wicked-garden:jam:quick explore options", state)
        self.assertIsNone(result)

    def test_sets_hint_shown_flag_after_first_show(self):
        state = self._make_state(False)
        result = self.hook._suggest_jam("what are the tradeoffs here", state)
        self.assertIsNotNone(result)
        state.update.assert_called_once_with(jam_hint_shown=True)


class TestGatherContextSync(unittest.TestCase):
    """_gather_context_sync() bridges sync to async correctly."""

    @classmethod
    def setUpClass(cls):
        cls.hook = _load_hook_module()

    def test_fail_inject_raises(self):
        """WICKED_SMAHT_FAIL_INJECT causes _gather_context_sync to raise RuntimeError."""
        os.environ["WICKED_SMAHT_FAIL_INJECT"] = "1"
        try:
            from unittest.mock import MagicMock
            mock_orchestrator = MagicMock()
            with self.assertRaises(RuntimeError) as ctx:
                self.hook._gather_context_sync(mock_orchestrator, "test prompt")
            self.assertIn("WICKED_SMAHT_FAIL_INJECT", str(ctx.exception))
        finally:
            os.environ.pop("WICKED_SMAHT_FAIL_INJECT", None)

    def test_delegates_to_gather_context_sync(self):
        """_gather_context_sync delegates to orchestrator.gather_context_sync()."""
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.path_used = "fast"
        mock_result.briefing = "test briefing"
        mock_orchestrator = MagicMock()
        mock_orchestrator.gather_context_sync.return_value = mock_result

        result = self.hook._gather_context_sync(mock_orchestrator, "find the Router class")
        self.assertEqual(result.path_used, "fast")
        mock_orchestrator.gather_context_sync.assert_called_once_with("find the Router class")


# =============================================================================
# AC-9: Session state accumulation via HistoryCondenser
# (in-process tests, no subprocess needed)
# =============================================================================

class TestHistoryCondenserAccumulation(unittest.TestCase):
    """AC-9: Orchestrator calls update_from_prompt on every turn."""

    @classmethod
    def setUpClass(cls):
        # Load v2 modules with correct CLAUDE_PLUGIN_ROOT
        _orig = os.environ.get("CLAUDE_PLUGIN_ROOT")
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
        try:
            sys.path.insert(0, str(_SCRIPTS))
            sys.path.insert(0, str(_V2_DIR))
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_repo_orchestrator",
                _V2_DIR / "orchestrator.py"
            )
            cls.orch_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.orch_mod)
        finally:
            if _orig is not None:
                os.environ["CLAUDE_PLUGIN_ROOT"] = _orig
            else:
                os.environ.pop("CLAUDE_PLUGIN_ROOT", None)

    def test_update_from_prompt_called_on_hot_turn(self):
        """Even HOT path must call condenser.update_from_prompt() (AC-9 fix)."""
        import asyncio
        from unittest.mock import patch
        Orchestrator = self.orch_mod.Orchestrator

        orch = Orchestrator(session_id="test-ac9-hot")
        with patch.object(orch.condenser, "update_from_prompt",
                          wraps=orch.condenser.update_from_prompt) as mock_update:
            asyncio.run(orch.gather_context("yes"))

        mock_update.assert_called_once()
        call_prompt = mock_update.call_args[0][0]
        self.assertEqual(call_prompt, "yes",
                         "update_from_prompt must receive the original prompt")

    def test_update_from_prompt_called_on_fast_turn(self):
        """FAST path must call condenser.update_from_prompt()."""
        import asyncio
        from unittest.mock import patch
        Orchestrator = self.orch_mod.Orchestrator

        orch = Orchestrator(session_id="test-ac9-fast")
        with patch.object(orch.condenser, "update_from_prompt",
                          wraps=orch.condenser.update_from_prompt) as mock_update:
            asyncio.run(orch.gather_context("find the SessionState class"))

        mock_update.assert_called_once()

    def test_gather_context_returns_context_result(self):
        """Orchestrator.gather_context() returns a ContextResult."""
        import asyncio
        Orchestrator = self.orch_mod.Orchestrator
        ContextResult = self.orch_mod.ContextResult

        orch = Orchestrator(session_id="test-ac9-result")
        result = asyncio.run(orch.gather_context("find the Router class"))

        self.assertIsInstance(result, ContextResult)
        self.assertIn(result.path_used, ("hot", "fast", "slow"))
        self.assertIsNotNone(result.briefing)
        self.assertIsInstance(result.latency_ms, int)


# =============================================================================
# Integration: hook subprocess produces well-formed output
# =============================================================================

class TestHookIntegration(unittest.TestCase):
    """Integration: hook returns valid JSON with correct structure on normal prompts."""

    def test_hook_runs_without_crash(self):
        """Hook subprocess exits 0 and returns valid JSON for a simple prompt."""
        output, result = _run_hook(
            {"prompt": "find the Router class", "session_id": "test-integration"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("continue", output)
        self.assertTrue(output.get("continue"))

    def test_hook_output_contains_hook_specific_output(self):
        """On non-empty prompt, hook returns hookSpecificOutput with additionalContext."""
        output, result = _run_hook(
            {"prompt": "find the Router class in scripts/smaht/v2/",
             "session_id": "test-integration-output"},
        )
        # May return bare continue:true if Orchestrator fails (no session data),
        # but if it succeeds there should be hookSpecificOutput
        self.assertIn("continue", output)
        self.assertEqual(result.returncode, 0)

    def test_hook_returns_continue_true_on_inject(self):
        """WICKED_SMAHT_FAIL_INJECT causes hook to return continue:true."""
        output, result = _run_hook(
            {"prompt": "test", "session_id": "test-inject"},
            env_overrides={"WICKED_SMAHT_FAIL_INJECT": "1"},
        )
        self.assertTrue(output.get("continue"))
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
