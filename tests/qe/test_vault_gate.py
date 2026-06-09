"""Tests for vault_gate — the garden's produces-gate backed by wicked-vault.

The load-bearing test is ``test_gate_rejects_claimed_but_false``: it
proves the gate REJECTS a claim that ``evidence_tracker`` would have
passed (satisfied-when-claimed). That delta is the whole reason the gate
moved onto the vault.

Tests that need a real vault resolve it from ``WICKED_VAULT_BIN`` or a
sibling ``../wicked-vault`` checkout, and ``skipTest`` when neither node
nor the vault is available — so CI stays honest rather than green-by-skip
masquerading as green-by-pass.
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
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import vault_gate as vg  # noqa: E402
import evidence_tracker as et  # noqa: E402

_CONTRACT = {
    "required_evidence": [
        {
            "claim_id": "tests-pass",
            "kind": "test-run",
            "verifier": {"kind": "exit_code_eq", "params": {"code": 0}},
            "required": True,
        }
    ]
}


def _locate_vault() -> str | None:
    """Resolve a runnable vault .mjs path, or None to skip vault-backed tests."""
    if shutil.which("node") is None:
        return None
    env = os.environ.get("WICKED_VAULT_BIN")
    if env and Path(env).exists():
        return env
    sibling = _REPO_ROOT.parent / "wicked-vault" / "bin" / "wicked-vault.mjs"
    if sibling.exists():
        return str(sibling)
    return None


def _locate_loom() -> str | None:
    """Resolve a runnable loom .mjs path, or None.

    Post-contract, garden's gate re-derives through ``wicked-loom`` (which
    shells the vault), not the vault directly. So the end-to-end re-derivation
    integration test below needs BOTH a real vault AND a real loom; absent
    either it skips (keeping CI Python-only / hermetic — the same skip-when-the-
    integration-peer-is-absent posture this suite always had for the vault)."""
    if shutil.which("node") is None:
        return None
    env = os.environ.get("WICKED_LOOM_BIN")
    if env and Path(env).exists():
        return env
    if shutil.which("wicked-loom"):
        return shutil.which("wicked-loom")
    sibling = _REPO_ROOT.parent / "wicked-loom" / "bin" / "wicked-loom.mjs"
    if sibling.exists():
        return str(sibling)
    return None


def _vault(bin_path: str, work: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", bin_path, *args],
        cwd=str(work), capture_output=True, text=True, timeout=120,
    )


class ResolutionTests(unittest.TestCase):
    """The in-process concrete-install ladder is the ``allow_npx=False`` probe
    (``vault_available``) after the contract phase: ``WICKED_VAULT_BIN`` env →
    config → PATH → ``node_modules`` (no npx, no loom). The default
    ``allow_npx=True`` path is loom-authoritative and is covered in
    ``tests/crew/test_loom_resolve_contract.py``; here we pin the in-process
    ladder that survives the contract."""

    def setUp(self):
        self._saved = os.environ.get("WICKED_VAULT_BIN")
        os.environ.pop("WICKED_VAULT_BIN", None)

    def tearDown(self):
        os.environ.pop("WICKED_VAULT_BIN", None)
        if self._saved is not None:
            os.environ["WICKED_VAULT_BIN"] = self._saved

    def test_env_mjs_path_resolves_via_node(self):
        os.environ["WICKED_VAULT_BIN"] = "/some/where/wicked-vault.mjs"
        self.assertEqual(vg.resolve_vault(allow_npx=False),
                         ["node", "/some/where/wicked-vault.mjs"])

    def test_env_executable_resolves_directly(self):
        os.environ["WICKED_VAULT_BIN"] = "/usr/local/bin/wicked-vault"
        self.assertEqual(vg.resolve_vault(allow_npx=False),
                         ["/usr/local/bin/wicked-vault"])

    def test_empty_env_is_killswitch(self):
        # Set-but-empty disables resolution entirely (no silent reach).
        os.environ["WICKED_VAULT_BIN"] = ""
        self.assertIsNone(vg.resolve_vault(allow_npx=False))
        self.assertFalse(vg.vault_available())


class RequiredFailClosedTests(unittest.TestCase):
    """vault is required: no vault + default require → fail closed, never a
    self-asserted PASS."""

    def setUp(self):
        self._saved = os.environ.get("WICKED_VAULT_BIN")
        self._saved_loom = os.environ.get("WICKED_LOOM_CUTOVER")
        os.environ["WICKED_VAULT_BIN"] = ""  # kill-switch: force unresolvable
        # Loom off too: no loom path AND no vault -> unambiguous fail-closed.
        os.environ["WICKED_LOOM_CUTOVER"] = "off"

    def tearDown(self):
        os.environ.pop("WICKED_VAULT_BIN", None)
        if self._saved is not None:
            os.environ["WICKED_VAULT_BIN"] = self._saved
        os.environ.pop("WICKED_LOOM_CUTOVER", None)
        if self._saved_loom is not None:
            os.environ["WICKED_LOOM_CUTOVER"] = self._saved_loom

    def test_required_missing_vault_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            et.initialize_for_archetype(project, "build")
            # Even a fully-claimed tracker must NOT pass when the required
            # vault is absent — this is the anti-vacuous-PASS guarantee.
            et.claim_produces(project, "shipped-code", artifact_path="x", claimed_by="t")
            et.claim_produces(project, "test-report", artifact_path="y", claimed_by="t")
            out = vg.gate_satisfied(project, "demo", "build")
            self.assertFalse(out["satisfied"])
            self.assertEqual(out["gate"], "unavailable")
            self.assertFalse(out["re_derived"])

    def test_opt_out_restores_claim_only(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            et.initialize_for_archetype(project, "build")
            self.assertFalse(
                vg.gate_satisfied(project, "demo", "build", require=False)["satisfied"])
            et.claim_produces(project, "shipped-code", artifact_path="x", claimed_by="t")
            et.claim_produces(project, "test-report", artifact_path="y", claimed_by="t")
            out = vg.gate_satisfied(project, "demo", "build", require=False)
            self.assertTrue(out["satisfied"])
            self.assertEqual(out["gate"], "claim-only")
            self.assertFalse(out["re_derived"])


@unittest.skipIf(_locate_vault() is None or _locate_loom() is None,
                 "needs a runnable wicked-vault AND wicked-loom (set "
                 "WICKED_VAULT_BIN / WICKED_LOOM_BIN or sibling checkouts) — "
                 "post-contract the gate re-derives through loom, not the vault "
                 "directly")
class VaultBackedGateTests(unittest.TestCase):
    """The real point: a re-derived gate that rejects a self-asserted 'done'.

    Post-contract this is an end-to-end integration test: garden shells
    ``wicked-loom gate``, loom shells ``wicked-vault cross-check`` against the
    recorded evidence. It runs only when BOTH peers are concretely resolvable;
    otherwise it skips (hermetic CI)."""

    def setUp(self):
        self._bin = _locate_vault()
        self._loom_bin = _locate_loom()
        self._saved = os.environ.get("WICKED_VAULT_BIN")
        self._saved_loom = os.environ.get("WICKED_LOOM_BIN")
        self._saved_flag = os.environ.get("WICKED_LOOM_CUTOVER")
        os.environ["WICKED_VAULT_BIN"] = self._bin
        os.environ["WICKED_LOOM_BIN"] = self._loom_bin
        os.environ["WICKED_LOOM_CUTOVER"] = "on"  # force the loom path
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=str(self.work), check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"],
                       cwd=str(self.work),
                       env={**os.environ, "GIT_AUTHOR_NAME": "t",
                            "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t"}, check=True)
        _vault(self._bin, self.work, "init")
        contract = self.work / "contract.json"
        contract.write_text(json.dumps(_CONTRACT), encoding="utf-8")
        _vault(self._bin, self.work, "declare-contract",
               "--scope", "demo", "--phase", "build", "--spec", str(contract))

    def tearDown(self):
        os.environ.pop("WICKED_VAULT_BIN", None)
        if self._saved is not None:
            os.environ["WICKED_VAULT_BIN"] = self._saved
        os.environ.pop("WICKED_LOOM_BIN", None)
        if self._saved_loom is not None:
            os.environ["WICKED_LOOM_BIN"] = self._saved_loom
        os.environ.pop("WICKED_LOOM_CUTOVER", None)
        if self._saved_flag is not None:
            os.environ["WICKED_LOOM_CUTOVER"] = self._saved_flag
        self._tmp.cleanup()

    def _record(self, source: str):
        _vault(self._bin, self.work, "record", "--scope", "demo", "--phase", "build",
               "--claim", "tests-pass", "--kind", "test-run", "--source", source,
               "--criteria", "tests pass (exit 0)", "--verifier", "exit_code_eq:0",
               "--run")

    def test_gate_fails_closed_with_no_evidence(self):
        # Contract declared, but nothing recorded → fail-closed (G5).
        out = vg.gate_satisfied(self.work, "demo", "build")
        self.assertTrue(out["re_derived"])
        self.assertFalse(out["satisfied"])

    def test_gate_rejects_claimed_but_false(self):
        # The falsifier: claim 'tests-pass' but the command exits 1.
        # evidence_tracker would have passed this; the vault must REJECT.
        self._record("false")
        out = vg.gate_satisfied(self.work, "demo", "build")
        self.assertTrue(out["re_derived"])
        self.assertFalse(out["satisfied"])
        self.assertEqual(out["overall"], "REJECT")

    def test_gate_passes_genuinely_passing(self):
        self._record("true")
        out = vg.gate_satisfied(self.work, "demo", "build")
        self.assertTrue(out["re_derived"])
        self.assertTrue(out["satisfied"])
        self.assertEqual(out["overall"], "PASS")

    def test_cross_check_returns_structured_verdict(self):
        self._record("true")
        cc = vg.cross_check("demo", "build", project_dir=self.work)
        self.assertTrue(cc["available"])
        self.assertEqual(cc["overall"], "PASS")
        self.assertEqual(len(cc["claims"]), 1)


class CliInvocationTests(unittest.TestCase):
    """The gate must work when run as a CLI, not only imported as a module.

    Regression (loom cutover, #891): this scripts/qe/ module imports its
    sibling ``_loom`` from scripts/. Invoked as a CLI (``python3
    scripts/qe/vault_gate.py …``, incl. via _python.sh) only scripts/qe is on
    sys.path, so the import failed, ``_loom`` became None, and EVERY gate
    silently failed closed ("unavailable") even with loom + vault installed.
    Module-level tests run with scripts/ already on sys.path (conftest), so
    they cannot catch this — only a subprocess invocation can. The fix inserts
    scripts/ onto sys.path before importing _loom; this test pins it.
    """

    def test_cli_resolve_imports_loom_shim(self):
        repo = Path(__file__).resolve().parents[2]
        script = repo / "scripts" / "qe" / "vault_gate.py"
        # Strip PYTHONPATH so the subprocess sees the same sys.path the real
        # CLI/_python.sh invocation does (only the script's own dir, scripts/qe).
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        proc = subprocess.run(
            [sys.executable, str(script), "resolve"],
            capture_output=True, text=True, cwd=str(repo), env=env, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(
            out.get("loom_shim_loaded"),
            "vault_gate CLI failed to import the _loom shim — the gate would "
            "fail closed regardless of whether loom/vault are installed",
        )


if __name__ == "__main__":
    unittest.main()
