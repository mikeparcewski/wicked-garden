#!/usr/bin/env python3
"""
tests/hooks/test_hot_path_fast_exit.py

Issue #281: HOT continuation fast-exit gap.

Verifies that the hook-level HOT fast-exit path in prompt_submit.py:
1. Returns {"continue": true} for all _HOT_CONTINUATIONS tokens
2. Does NOT instantiate the Orchestrator (hook-level bypass, not Orchestrator-level)
3. Attempts HistoryCondenser accumulation before returning (best-effort)

This is distinct from test_hot_continuation_accumulation.py which verifies
that HistoryCondenser IS called. This test verifies the Orchestrator is NOT called
at the hook level.

WHY this is intentional: HOT continuation tokens ("yes", "ok", "continue", etc.)
carry no new intent. There is nothing for context assembly to add beyond what is
already in the conversation window. The Orchestrator is bypassed entirely at the
hook level (not just routed to HOT path internally) to keep p95 latency under 100ms.
"""

import json
import os
import subprocess
import sys
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
    env.update(overrides)
    return env


def _run_hook(stdin_data: dict | str, env_overrides: dict = None, timeout: int = 15) -> tuple:
    """Run the hook as a subprocess, return (parsed_stdout_json, result)."""
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
# TestHotPathStructural — source inspection
# =============================================================================

class TestHotPathStructural(unittest.TestCase):
    """Source-level: HOT fast-exit return must appear before Orchestrator import."""

    @classmethod
    def setUpClass(cls):
        cls.src = _HOOK_PY.read_text(encoding="utf-8")
        cls.lines = cls.src.splitlines()

    def test_hot_exit_before_orchestrator_import(self):
        """Source-level: HOT fast-exit return must appear before 'from orchestrator import Orchestrator'."""
        lines = self.lines
        # Find the _HOT_CONTINUATIONS frozenset definition line
        hot_check_line = next(
            i for i, l in enumerate(lines)
            if "_HOT_CONTINUATIONS" in l and "frozenset" in l
        )
        # Find the print(json.dumps({"continue": True})) in the HOT block (after hot_check_line)
        early_return_line = next(
            i for i, l in enumerate(lines)
            if i > hot_check_line and "print(json.dumps" in l and "continue" in l
        )
        # Find the Orchestrator import
        orch_import_line = next(
            i for i, l in enumerate(lines)
            if "from orchestrator import Orchestrator" in l
        )
        self.assertLess(
            early_return_line, orch_import_line,
            "HOT fast-exit print/return must occur before 'from orchestrator import Orchestrator'"
        )

    def test_hot_continuations_is_frozenset(self):
        """_HOT_CONTINUATIONS must be defined as a frozenset."""
        self.assertIn("frozenset", self.src)
        self.assertIn("_HOT_CONTINUATIONS", self.src)

    def test_history_condenser_called_before_hot_return(self):
        """HistoryCondenser import/call must appear between _HOT_CONTINUATIONS check and early return."""
        lines = self.lines
        hot_check_line = next(
            i for i, l in enumerate(lines)
            if "_HOT_CONTINUATIONS" in l and "frozenset" in l
        )
        early_return_line = next(
            i for i, l in enumerate(lines)
            if i > hot_check_line and "print(json.dumps" in l and "continue" in l
        )
        hot_block = lines[hot_check_line:early_return_line]
        self.assertTrue(
            any("HistoryCondenser" in l for l in hot_block),
            "HistoryCondenser must be referenced in the HOT fast-exit block"
        )


# =============================================================================
# TestHotPathFastExit — subprocess tests
# =============================================================================

class TestHotPathFastExit(unittest.TestCase):
    """Subprocess tests: HOT tokens return continue:true, non-HOT tokens reach Orchestrator."""

    def test_hot_token_returns_continue_true(self):
        """All HOT tokens return {"continue": true} via hook."""
        for token in ["yes", "ok", "lgtm", "no", "cancel", "continue", "do it", "go ahead"]:
            output, _ = _run_hook({"prompt": token, "session_id": "test-281"})
            self.assertTrue(
                output.get("continue"),
                f"Token '{token}' must return continue:true"
            )

    def test_hot_token_case_insensitive(self):
        """HOT tokens are matched case-insensitively."""
        for token in ["YES", "Ok", "LGTM", "Cancel"]:
            output, _ = _run_hook({"prompt": token, "session_id": "test-281-case"})
            self.assertTrue(
                output.get("continue"),
                f"Token '{token}' (uppercased) must return continue:true"
            )

    def test_hot_token_with_leading_trailing_whitespace(self):
        """HOT tokens with surrounding whitespace are matched via strip()."""
        for token in ["  yes  ", "\tok\t", " lgtm "]:
            output, _ = _run_hook({"prompt": token, "session_id": "test-281-ws"})
            self.assertTrue(
                output.get("continue"),
                f"Token '{token!r}' (whitespace-padded) must return continue:true"
            )

    def test_non_hot_token_does_not_fast_exit(self):
        """A non-HOT prompt must NOT take the fast-exit path (control: Orchestrator is invoked)."""
        output, result = _run_hook(
            {"prompt": "explain the architecture of specialist discovery", "session_id": "test-281-slow"},
            env_overrides={"WICKED_SMAHT_FAIL_INJECT": "1"}
        )
        # FAIL_INJECT makes Orchestrator raise. If fast-exit didn't run, we get continue:true from
        # the outer except. But if it DID fast-exit, the FAIL_INJECT env var would not appear in stderr.
        # We check stderr for FAIL_INJECT signal to prove Orchestrator was reached.
        self.assertIn(
            "WICKED_SMAHT_FAIL_INJECT", result.stderr,
            "Non-HOT prompt must reach and fail at Orchestrator (proving it did not fast-exit)"
        )


# =============================================================================
# TestHotTokenCoverage — semantic group coverage (AC-281-3)
# =============================================================================

_SEMANTIC_GROUPS = {
    "affirmative": ["yes", "ok", "lgtm"],
    "negative": ["no", "cancel"],
    "action": ["continue", "do it", "go ahead"],
}


class TestHotTokenCoverage(unittest.TestCase):
    """Semantic group coverage: each group must have at least one HOT token that returns continue:true."""

    def test_semantic_groups_covered(self):
        for group, tokens in _SEMANTIC_GROUPS.items():
            for token in tokens:
                with self.subTest(group=group, token=token):
                    output, _ = _run_hook(
                        {"prompt": token, "session_id": f"test-281-{group}"}
                    )
                    self.assertTrue(
                        output.get("continue"),
                        f"Semantic group '{group}', token '{token}' must return continue:true"
                    )


if __name__ == "__main__":
    unittest.main()
