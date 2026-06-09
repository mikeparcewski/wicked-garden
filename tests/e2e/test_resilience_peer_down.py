"""E2E Tier C — resilience / chaos. Down each peer and assert the plugin
degrades correctly: the GATE fails CLOSED (never a vacuous PASS), and the
HOOKS fail OPEN (never block the session). The two invariants must not be
confused — a closed gate protects correctness; an open hook protects the user.

These are the claims behind "five required peers, resilient to a transient
runtime outage": an outage degrades, it does not crash.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_GATE_CLI = _REPO / "scripts" / "qe" / "vault_gate.py"
_INVOKE = _REPO / "hooks" / "scripts" / "invoke.py"
_ENV = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(_REPO)}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import configured_home, has_python_traceback  # noqa: E402


def _clean_env(**overrides) -> dict:
    env = {k: v for k, v in _ENV.items() if k != "PYTHONPATH"}
    env.update(overrides)
    return env


class GateFailsClosedTests(unittest.TestCase):
    """The gate must NEVER report satisfied when its backend is gone."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _gate(self, env) -> dict:
        proc = subprocess.run(
            [sys.executable, str(_GATE_CLI), "gate", str(self.proj),
             "--scope", "demo", "--phase", "build"],
            cwd=str(_REPO), env=env, capture_output=True, text=True, timeout=60)
        self.assertTrue(proc.stdout.strip(), proc.stderr)
        # exit code must be non-zero (gate not satisfied)
        self.assertNotEqual(proc.returncode, 0, "fail-closed must exit non-zero")
        return json.loads(proc.stdout)

    def test_loom_cutover_off_fails_closed(self):
        out = self._gate(_clean_env(WICKED_LOOM_CUTOVER="off"))
        self.assertFalse(out["satisfied"])
        self.assertEqual(out["gate"], "unavailable")

    def test_vault_killswitch_fails_closed(self):
        # Empty WICKED_VAULT_BIN is the documented vault kill-switch.
        out = self._gate(_clean_env(WICKED_VAULT_BIN="", WICKED_LOOM_CUTOVER="auto"))
        self.assertFalse(out["satisfied"])
        self.assertEqual(out["gate"], "unavailable")

    def test_loom_pointed_at_missing_binary_fails_closed(self):
        out = self._gate(_clean_env(WICKED_LOOM_BIN="/nonexistent/loom",
                                    WICKED_LOOM_CUTOVER="on"))
        self.assertFalse(out["satisfied"])
        # never a vacuous PASS — satisfied is false regardless of the label
        self.assertNotEqual(out.get("overall"), "PASS")


class HooksFailOpenTests(unittest.TestCase):
    """Hooks must never block the session when a peer is down."""

    def _bootstrap(self, env) -> subprocess.CompletedProcess:
        payload = json.dumps({"hook_event_name": "SessionStart",
                              "cwd": str(_REPO), "session_id": "e2e-chaos"})
        return subprocess.run([sys.executable, str(_INVOKE), "bootstrap"],
                              input=payload, capture_output=True, text=True,
                              env=env, cwd=str(_REPO), timeout=30)

    def test_bootstrap_fails_open_with_brain_down(self):
        # Brain unreachable: point the brain port somewhere dead. Bootstrap must
        # still return 0 with valid JSON (it only warns, never blocks).
        env = _clean_env(WICKED_BRAIN_PORT="59999")
        proc = self._bootstrap(env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout)

    def test_bootstrap_fails_open_with_all_backends_killswitched(self):
        env = _clean_env(WICKED_LOOM_CUTOVER="off", WICKED_VAULT_BIN="",
                         WICKED_BRAIN_PORT="59999")
        proc = self._bootstrap(env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout)

    def test_prompt_submit_fails_open_with_backends_down(self):
        # Configured HOME so the hook proceeds PAST the setup gate and actually
        # exercises the backend-down path (in a fresh/unconfigured env the setup
        # gate blocks first — correct, but it wouldn't test resilience). All
        # evidence backends are killswitched + brain unreachable: the hook must
        # still produce a controlled exit and never crash.
        home = configured_home()
        try:
            env = _clean_env(WICKED_LOOM_CUTOVER="off", WICKED_VAULT_BIN="",
                             WICKED_BRAIN_PORT="59999", HOME=home.name)
            payload = json.dumps({"hook_event_name": "UserPromptSubmit",
                                  "prompt": "implement a feature",
                                  "cwd": str(_REPO), "session_id": "e2e-chaos"})
            proc = subprocess.run([sys.executable, str(_INVOKE), "prompt_submit"],
                                  input=payload, capture_output=True, text=True,
                                  env=env, cwd=str(_REPO), timeout=30)
            self.assertFalse(has_python_traceback(proc.stderr),
                             f"hook crashed under peer-down: {proc.stderr}")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for line in proc.stdout.splitlines():
                if line.strip():
                    json.loads(line)
        finally:
            home.cleanup()


if __name__ == "__main__":
    unittest.main()
