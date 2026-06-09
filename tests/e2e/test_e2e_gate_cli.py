"""E2E — the produces-gate exercised through its REAL production CLI surface.

This is the test that would have caught both loom-cutover regressions:
  1. the cwd regression (gate re-derived against the process cwd, not the
     project) — #891; and
  2. the `_loom` CLI-import regression (gate failed closed because scripts/
     wasn't on sys.path when invoked as a CLI).

Both were invisible to module-level tests (which run with scripts/ already on
sys.path via conftest). The only way to catch them is to invoke the gate the
way production does: ``python3 scripts/qe/vault_gate.py gate <dir> …`` as a
subprocess, from a DIFFERENT cwd than the project, with PYTHONPATH stripped.

Outcomes asserted (positive + negative pairing — the plugin's own doctrine):
  - genuinely-passing evidence   → satisfied:true,  re_derived:true,  PASS
  - claimed-but-false 'done'     → satisfied:false, re_derived:true,  REJECT
  - backend disabled (cutover)   → satisfied:false, re_derived:false, unavailable

Skips (does not fake-pass) when node / wicked-loom / wicked-vault are not
resolvable — the same hermetic posture the rest of the suite uses. CI installs
the peers (see .github/workflows/test.yml) so this RUNS rather than skips.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_CLI = _REPO_ROOT / "scripts" / "qe" / "vault_gate.py"
_CONTRACT = json.dumps({
    "required_evidence": [{
        "claim_id": "tests-pass", "kind": "test-run",
        "verifier": {"kind": "exit_code_eq", "params": {"code": 0}},
        "required": True,
    }]
})


def _locate(env_var: str, *sibling_parts: str) -> str | None:
    if shutil.which("node") is None:
        return None
    env = os.environ.get(env_var)
    if env and Path(env).exists():
        return env
    onpath = shutil.which(sibling_parts[-1].replace(".mjs", "")) if sibling_parts else None
    if onpath:
        return onpath
    sib = _REPO_ROOT.parent.joinpath(*sibling_parts)
    return str(sib) if sib.exists() else None


_VAULT = _locate("WICKED_VAULT_BIN", "wicked-vault", "bin", "wicked-vault.mjs")
_LOOM = _locate("WICKED_LOOM_BIN", "wicked-loom", "bin", "loom.mjs") or shutil.which("wicked-loom")


@unittest.skipIf(_VAULT is None or _LOOM is None,
                 "needs runnable wicked-vault + wicked-loom (sibling checkout, "
                 "PATH, or WICKED_*_BIN) — E2E gate is an integration test")
class GateCliEndToEndTests(unittest.TestCase):
    """Drive the gate the way the archetype playbooks tell agents to."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name)
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"],
                       cwd=self.proj, env=env, check=True)
        self._vault("init")
        (self.proj / "c.json").write_text(_CONTRACT, encoding="utf-8")
        self._vault("declare-contract", "--scope", "demo", "--phase", "build",
                    "--spec", str(self.proj / "c.json"))

    def tearDown(self):
        self._tmp.cleanup()

    def _vault(self, *args: str):
        subprocess.run(["node", _VAULT, *args], cwd=self.proj,
                       capture_output=True, text=True, timeout=60, check=False)

    def _record(self, source: str):
        self._vault("record", "--scope", "demo", "--phase", "build",
                    "--claim", "tests-pass", "--kind", "test-run", "--source", source,
                    "--criteria", "tests pass", "--verifier", "exit_code_eq:0", "--run")

    def _gate(self, *extra_env_pairs) -> dict:
        # The crux: invoke the gate CLI from the REPO ROOT (not the project),
        # with PYTHONPATH stripped, so we exercise the real sys.path the
        # production CLI sees. project_dir is passed as an arg.
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["WICKED_VAULT_BIN"] = _VAULT
        env["WICKED_LOOM_BIN"] = _LOOM
        for k, v in extra_env_pairs:
            env[k] = v
        proc = subprocess.run(
            [sys.executable, str(_GATE_CLI), "gate", str(self.proj),
             "--scope", "demo", "--phase", "build"],
            cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, timeout=120,
        )
        self.assertTrue(proc.stdout.strip(), f"no stdout; stderr={proc.stderr}")
        return json.loads(proc.stdout)

    def test_genuinely_passing_evidence_gates_PASS(self):
        self._record("true")
        out = self._gate(("WICKED_LOOM_CUTOVER", "on"))
        self.assertTrue(out["re_derived"], out)
        self.assertTrue(out["satisfied"], out)
        self.assertEqual(out["overall"], "PASS", out)

    def test_claimed_but_false_done_is_REJECTED(self):
        # The headline claim: 'done' cannot be self-asserted into truth.
        self._record("false")
        out = self._gate(("WICKED_LOOM_CUTOVER", "on"))
        self.assertTrue(out["re_derived"], out)
        self.assertFalse(out["satisfied"], out)
        self.assertEqual(out["overall"], "REJECT", out)

    def test_backend_disabled_fails_closed(self):
        # Kill-switch: gate is unavailable, never a vacuous PASS.
        self._record("true")
        out = self._gate(("WICKED_LOOM_CUTOVER", "off"))
        self.assertFalse(out["satisfied"], out)
        self.assertFalse(out["re_derived"], out)
        self.assertEqual(out["gate"], "unavailable", out)


@unittest.skipIf(shutil.which("node") is None, "node required for the CLI shim probe")
class GateCliShimLoadTests(unittest.TestCase):
    """`resolve` via the CLI must import the _loom shim regardless of cwd /
    PYTHONPATH. Without scripts/ on sys.path the import fails and every gate
    silently fails closed — the #891 CLI-import regression. This runs even
    when loom/vault are absent (it checks the import, not resolution)."""

    def test_cli_resolve_loads_loom_shim(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        proc = subprocess.run(
            [sys.executable, str(_GATE_CLI), "resolve"],
            cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(out.get("loom_shim_loaded"),
                        "CLI failed to import _loom — gate would fail closed "
                        "regardless of whether loom/vault are installed")


if __name__ == "__main__":
    unittest.main()
