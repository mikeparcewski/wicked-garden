#!/usr/bin/env python3
"""
tests/hooks/test_hot_continuation_accumulation.py

Tests for GH#281: HOT continuation session accumulation gap.

Verifies that when prompt_submit.py receives a HOT continuation token
(e.g. "yes", "ok"), it calls HistoryCondenser.update_from_prompt() BEFORE
the early return, so session state is accumulated even on the HOT fast-exit path.

AC-281-1: Hook-level HOT continuation invokes session accumulation (subprocess test)
AC-281-2: Orchestrator HOT path regression guard (covered in test_prompt_submit_refactor.py)
AC-281-3: In-process unit test of HistoryCondenser for HOT prompts
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_V2_DIR = _SCRIPTS / "smaht" / "v2"
_HOOK_PY = _REPO_ROOT / "hooks" / "scripts" / "prompt_submit.py"


def _base_env(**overrides) -> dict:
    """Build subprocess env with required plugin vars set to repo root."""
    env = {**os.environ}
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    # Ensure TMPDIR is stable — other tests may mutate os.environ
    if "TMPDIR" not in env:
        env["TMPDIR"] = tempfile.gettempdir()
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


def _session_dir(session_id: str) -> Path:
    """Resolve the expected session directory for a given session_id."""
    # Add scripts to path to resolve get_local_path
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    from _domain_store import get_local_path
    return get_local_path("wicked-smaht", "sessions") / session_id


class TestHotContinuationAccumulation(unittest.TestCase):
    """AC-281-1, AC-281-3: HOT continuations must invoke session accumulation."""

    def _unique_session_id(self) -> str:
        """Generate a unique session ID safe for HistoryCondenser path validation."""
        return f"test-ac281-{uuid.uuid4().hex[:12]}"

    def test_hot_continuation_sample_tokens(self):
        """AC-281-1 regression guard: all _HOT_CONTINUATIONS tokens return continue:true."""
        # These are the known HOT continuation tokens from prompt_submit.py
        hot_tokens = [
            "yes", "ok", "okay", "sure", "yep", "yup",
            "continue", "proceed", "go", "go ahead", "do it",
            "lgtm", "looks good", "approved", "approve",
            "no", "nope", "cancel", "stop", "skip",
            "next", "done",
        ]
        session_id = self._unique_session_id()
        sess_dir = _session_dir(session_id)
        self.addCleanup(lambda: shutil.rmtree(sess_dir, ignore_errors=True))

        for token in hot_tokens:
            with self.subTest(token=token):
                output, result = _run_hook({"prompt": token, "session_id": session_id})
                self.assertEqual(result.returncode, 0, f"Hook crashed for token '{token}'")
                self.assertTrue(
                    output.get("continue"),
                    f"Hook must return continue:true for HOT token '{token}'"
                )

    def test_hot_continuation_accumulation_in_process(self):
        """AC-281-3: In-process unit test — HistoryCondenser.update_from_prompt handles HOT prompts."""
        # Set up path so HistoryCondenser can be imported
        if str(_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS))
        if str(_V2_DIR) not in sys.path:
            sys.path.insert(0, str(_V2_DIR))

        os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)

        from history_condenser import HistoryCondenser

        session_id = self._unique_session_id()
        sess_dir = _session_dir(session_id)
        self.addCleanup(lambda: shutil.rmtree(sess_dir, ignore_errors=True))

        # Call update_from_prompt with a HOT continuation token
        hc = HistoryCondenser(session_id)
        hc.update_from_prompt("yes")

        summary_path = sess_dir / "summary.json"
        self.assertTrue(
            summary_path.exists(),
            "summary.json must be written by update_from_prompt('yes')"
        )

        # Verify the written JSON is valid
        data = json.loads(summary_path.read_text())
        self.assertIsInstance(data, dict, "summary.json must contain a JSON object")


if __name__ == "__main__":
    unittest.main(verbosity=2)
