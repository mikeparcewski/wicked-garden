"""Tests for scripts/statusline.py — the work-mode status line renderer.

The status line runs on every Claude Code render, so the contract is: always
return a line, never crash, never block. These tests cover the pure render(),
session-state file resolution, and an end-to-end subprocess run (including the
fail-soft path on garbage input).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = str(_REPO_ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)

import statusline as sl  # noqa: E402


class RenderTests(unittest.TestCase):
    def test_full_state_shows_archetype_intent_phase(self):
        line = sl.render({
            "archetypes_v11": [{"name": "build", "score": 0.9},
                               {"name": "migrate", "score": 0.7}],
            "intent": "feature",
            "last_approved_phase": "implement",
        })
        self.assertIn("build·migrate", line)
        self.assertIn("intent: feature", line)
        self.assertIn("phase: implement", line)
        self.assertTrue(line.startswith("🌱 wg"))

    def test_empty_state_is_idle_not_crash(self):
        line = sl.render({})
        self.assertEqual(line, "🌱 wg │ idle")

    def test_low_score_archetypes_dropped(self):
        line = sl.render({"archetypes_v11": [
            {"name": "build", "score": 0.9},
            {"name": "triage", "score": 0.1},  # below _MIN_SCORE → dropped
        ]})
        self.assertIn("build", line)
        self.assertNotIn("triage", line)

    def test_archetype_without_score_is_kept(self):
        # Be permissive: a detected shape with no score still shows.
        line = sl.render({"archetypes_v11": [{"name": "explore"}]})
        self.assertIn("explore", line)

    def test_gate_verdict_surfaced_when_present(self):
        self.assertIn("⚖ PASS", sl.render({"last_gate_verdict": "PASS"}))
        self.assertIn("⚖ REJECT", sl.render({"last_gate_verdict": "reject"}))

    def test_render_never_omits_prefix(self):
        for state in ({}, {"intent": "rigor"}, {"archetypes_v11": "garbage"}):
            self.assertTrue(sl.render(state).startswith("🌱 wg"))


class StateLoadingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self._tmp, ignore_errors=True))
        self._saved_tmpdir = os.environ.get("TMPDIR")
        self._saved_sid = os.environ.get("CLAUDE_SESSION_ID")
        os.environ["TMPDIR"] = self._tmp

    def tearDown(self):
        for k, v in (("TMPDIR", self._saved_tmpdir), ("CLAUDE_SESSION_ID", self._saved_sid)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _write_state(self, sid: str, data: dict):
        Path(self._tmp, f"wicked-garden-session-{sid}.json").write_text(json.dumps(data))

    def test_loads_via_stdin_session_id(self):
        self._write_state("abc123", {"intent": "feature"})
        state = sl._load_state(json.dumps({"session_id": "abc123"}))
        self.assertEqual(state.get("intent"), "feature")

    def test_loads_via_env_when_stdin_absent(self):
        self._write_state("envsid", {"intent": "rigor"})
        os.environ["CLAUDE_SESSION_ID"] = "envsid"
        self.assertEqual(sl._load_state("")["intent"], "rigor")

    def test_missing_file_returns_empty(self):
        self.assertEqual(sl._load_state(json.dumps({"session_id": "nope"})), {})

    def test_corrupt_file_returns_empty_not_crash(self):
        Path(self._tmp, "wicked-garden-session-bad.json").write_text("{not json")
        self.assertEqual(sl._load_state(json.dumps({"session_id": "bad"})), {})

    def test_session_id_sanitized(self):
        # path-traversal / odd chars stripped to match _session.py
        self.assertEqual(sl._safe_session_id("../../etc/passwd"), "etcpasswd")
        self.assertIsNone(sl._safe_session_id("///"))


class SubprocessSmokeTests(unittest.TestCase):
    """The real contract: invoked like Claude Code does, it never errors."""

    def _run(self, stdin: str, env_extra=None):
        env = {"PATH": os.environ.get("PATH", ""), "TMPDIR": tempfile.gettempdir()}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(_REPO_ROOT / "scripts" / "statusline.py")],
            input=stdin, capture_output=True, text=True, env=env, timeout=15)

    def test_garbage_stdin_still_emits_a_line_exit_0(self):
        r = self._run("this is not json {{{")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("🌱 wg"))
        self.assertEqual(r.stderr, "")  # no traceback into the bar

    def test_empty_stdin_emits_idle(self):
        r = self._run("")
        self.assertEqual(r.returncode, 0)
        self.assertIn("🌱 wg", r.stdout)


if __name__ == "__main__":
    unittest.main()
