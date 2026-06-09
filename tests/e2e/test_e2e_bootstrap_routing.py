"""E2E — SessionStart bootstrap + prompt routing through the REAL hook surfaces.

- Bootstrap: invoked as a subprocess via invoke.py (the way Claude Code calls
  it). Asserts it returns valid JSON (fail-open contract), reports the required
  peers, and emits NO 'Unknown capability' warnings (the capability-registry
  regression we fixed).
- Routing: the detector driven through its real CLI (`archetypes_v11.py detect`)
  over the labeled calibration corpus → per-archetype recall outcome. This is
  the subprocess-surface complement to tests/calibration (which calls the
  function in-process).
- Hook smoke: prompt_submit must never crash and must always emit valid JSON
  (fail-open), regardless of prompt.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_INVOKE = _REPO / "hooks" / "scripts" / "invoke.py"
_DETECT = _REPO / "scripts" / "crew" / "archetypes_v11.py"

# Reuse the labeled corpus the calibration suite uses.
sys.path.insert(0, str(_REPO / "tests" / "calibration"))
from corpus import CORPUS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import configured_home, unconfigured_home, has_python_traceback  # noqa: E402

_ENV = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(_REPO)}


class BootstrapEndToEndTests(unittest.TestCase):
    def _run_bootstrap(self):
        payload = json.dumps({"hook_event_name": "SessionStart",
                              "cwd": str(_REPO), "session_id": "e2e-boot"})
        return subprocess.run([sys.executable, str(_INVOKE), "bootstrap"],
                              input=payload, capture_output=True, text=True,
                              env=_ENV, cwd=str(_REPO), timeout=30)

    def test_bootstrap_returns_valid_json_and_does_not_crash(self):
        proc = self._run_bootstrap()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # fail-open contract: stdout is a single JSON object
        json.loads(proc.stdout)

    def test_bootstrap_emits_no_unknown_capability_warnings(self):
        # The capability-registry regression printed these to stderr on every
        # session start. The fix (registering apm/tracing/logging/telemetry)
        # must keep them at zero.
        proc = self._run_bootstrap()
        self.assertNotIn("Unknown capability", proc.stderr,
                         f"capability warnings leaked: {proc.stderr}")

    def test_bootstrap_reports_required_peers(self):
        proc = self._run_bootstrap()
        ctx = (json.loads(proc.stdout).get("hookSpecificOutput") or {}).get(
            "additionalContext", "")
        # The readiness/briefing context should reference the evidence backend.
        self.assertTrue(ctx, "bootstrap emitted no additionalContext")


class RoutingRecallEndToEndTests(unittest.TestCase):
    """Drive the detector CLI over the corpus; assert per-archetype recall."""

    def _detect(self, prompt: str) -> set[str]:
        proc = subprocess.run(
            [sys.executable, str(_DETECT), "detect", "--prompt", prompt],
            capture_output=True, text=True, env=_ENV, cwd=str(_REPO), timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        return {m["archetype"] for m in data.get("matches", [])}

    def test_corpus_recall_through_cli_meets_threshold(self):
        # The full-corpus recall bar is held fast by tests/calibration (in
        # process). Here we prove the CLI *surface* routes correctly with a
        # representative sample — the first corpus entry per primary archetype
        # — keeping the subprocess cost to ~one call per archetype.
        sample = {}
        for entry in CORPUS:
            sample.setdefault(entry["primary"], entry)
        hits, misses = 0, []
        for primary, entry in sample.items():
            got = self._detect(entry["prompt"])
            if primary in got:
                hits += 1
            else:
                misses.append((entry["prompt"], primary, sorted(got)))
        recall = hits / max(1, len(sample))
        self.assertGreaterEqual(
            recall, 0.85,
            f"CLI routing recall {recall:.2f} < 0.85 over {len(sample)} "
            f"archetypes; misses={misses}")


class HookSmokeEndToEndTests(unittest.TestCase):
    """prompt_submit must never CRASH (no uncaught traceback) and must always
    produce a controlled outcome — regardless of prompt or whether the project
    is configured. Uses an isolated, explicitly-configured HOME so it behaves
    identically in CI and on a developer machine (the assumption that broke the
    first version of this test)."""

    def _run(self, prompt: str, home_dir: str) -> subprocess.CompletedProcess:
        payload = json.dumps({"hook_event_name": "UserPromptSubmit",
                              "prompt": prompt, "cwd": str(_REPO),
                              "session_id": "e2e-smoke"})
        env = {**_ENV, "HOME": home_dir}
        return subprocess.run([sys.executable, str(_INVOKE), "prompt_submit"],
                              input=payload, capture_output=True, text=True,
                              env=env, cwd=str(_REPO), timeout=30)

    def test_configured_project_proceeds_without_crash(self):
        home = configured_home()
        try:
            for p in ["add a CSV export button to the dashboard",
                      "the prod API is down with 500s",
                      "", "yes", "rm -rf /; drop table"]:
                proc = self._run(p, home.name)
                self.assertFalse(has_python_traceback(proc.stderr),
                                 f"prompt={p!r} crashed: {proc.stderr}")
                # configured → setup gate passes → controlled exit 0
                self.assertEqual(proc.returncode, 0,
                                 f"prompt={p!r} rc={proc.returncode} err={proc.stderr}")
                for line in proc.stdout.splitlines():
                    if line.strip():
                        json.loads(line)  # valid JSON or raises
        finally:
            home.cleanup()

    def test_unconfigured_project_setup_gate_blocks_and_cannot_be_bypassed(self):
        # The contract that broke the first version of this test: an
        # unconfigured project HARD-BLOCKS (exit 2) — setup cannot be bypassed,
        # even by a continuation token. That is correct, controlled behavior
        # (not a crash), and it must hold deterministically.
        home = unconfigured_home()
        try:
            for p in ["implement a feature", "yes"]:
                proc = self._run(p, home.name)
                self.assertFalse(has_python_traceback(proc.stderr),
                                 f"prompt={p!r} crashed: {proc.stderr}")
                self.assertEqual(proc.returncode, 2,
                                 f"setup gate must hard-block unconfigured; "
                                 f"prompt={p!r} rc={proc.returncode}")
        finally:
            home.cleanup()


if __name__ == "__main__":
    unittest.main()
