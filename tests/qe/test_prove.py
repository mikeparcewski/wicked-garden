"""Tests for prove.py — the one-line re-derivation verb.

Unit layer (no peers): verifier parsing + fail-closed when the backend is
disabled (deterministic). Integration layer (skip when node/loom/vault are
absent): real PASS / REJECT through the actual CLI, proving the verb re-derives
rather than asserts.
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

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "scripts", _REPO / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import prove as pv  # noqa: E402

_PROVE_CLI = _REPO / "scripts" / "qe" / "prove.py"
_VAULT = os.environ.get("WICKED_VAULT_BIN")
if not _VAULT:
    sib = _REPO.parent / "wicked-vault" / "bin" / "wicked-vault.mjs"
    _VAULT = str(sib) if sib.exists() else None
_LOOM = os.environ.get("WICKED_LOOM_BIN") or shutil.which("wicked-loom")
_PEERS = shutil.which("node") and _VAULT and _LOOM


class VerifierParsingTests(unittest.TestCase):
    def test_exit_code_eq_parses(self):
        self.assertEqual(pv._parse_verifier("exit_code_eq:0"),
                         {"kind": "exit_code_eq", "params": {"code": 0}})

    def test_defaults_to_zero(self):
        self.assertEqual(pv._parse_verifier("exit_code_eq"),
                         {"kind": "exit_code_eq", "params": {"code": 0}})

    def test_unknown_verifier_raises(self):
        with self.assertRaises(ValueError):
            pv._parse_verifier("magic:1")

    def test_output_verifiers_parse(self):
        self.assertEqual(pv._parse_verifier("regex_match:## Decision"),
                         {"kind": "regex_match", "params": {"pattern": "## Decision"}})
        self.assertEqual(pv._parse_verifier("not_contains:TODO"),
                         {"kind": "not_contains", "params": {"pattern": "TODO"}})
        self.assertEqual(pv._parse_verifier("jq_pred:.a>=2"),
                         {"kind": "jq_pred", "params": {"expr": ".a>=2"}})

    def test_content_verifier_requires_argument(self):
        with self.assertRaises(ValueError):
            pv._parse_verifier("regex_match")  # no pattern


class AttestationForwardingTests(unittest.TestCase):
    """--with-attestations must reach the gate (hard gates require an
    independent attestation). Mocked — no peers, deterministic."""

    def test_with_attestations_forwarded_to_gate(self):
        import unittest.mock as mock
        captured = {}

        def fake_gate(pd, scope, phase, with_attestations=False):
            captured["wa"] = with_attestations
            return {"satisfied": True, "re_derived": True, "overall": "PASS"}

        with mock.patch.object(pv.vault_gate, "resolve_vault", return_value=["echo"]), \
             mock.patch.object(pv, "_vault", lambda *a, **k: None), \
             mock.patch.object(pv.vault_gate, "gate_satisfied", fake_gate):
            pv.prove("c", "true", with_attestations=True)
        self.assertTrue(captured.get("wa"), "with_attestations not forwarded to gate")


class FailClosedTests(unittest.TestCase):
    """No peers needed: with the loom cutover disabled the backend is
    unresolvable, so prove must fail closed — never a vacuous pass."""

    def test_backend_disabled_fails_closed(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["WICKED_LOOM_CUTOVER"] = "off"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                [sys.executable, str(_PROVE_CLI), "tests-pass", "--by", "true",
                 "--project-dir", d],
                capture_output=True, text=True, env=env, cwd=str(_REPO), timeout=60)
            out = json.loads(proc.stdout)
            self.assertFalse(out["satisfied"])
            self.assertEqual(out["gate"], "unavailable")
            self.assertEqual(proc.returncode, 3, "fail-closed must use exit 3")


@unittest.skipIf(not _PEERS, "needs node + wicked-loom + wicked-vault")
class ProveEndToEndTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name)
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "i"],
                       cwd=self.proj, env=env, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _prove(self, command: str):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(WICKED_VAULT_BIN=_VAULT, WICKED_LOOM_BIN=_LOOM,
                   WICKED_LOOM_CUTOVER="on")
        proc = subprocess.run(
            [sys.executable, str(_PROVE_CLI), "tests-pass", "--by", command,
             "--project-dir", str(self.proj)],
            capture_output=True, text=True, env=env, cwd=str(_REPO), timeout=120)
        return proc, json.loads(proc.stdout)

    def test_true_command_proves_PASS(self):
        proc, out = self._prove("true")
        self.assertTrue(out["satisfied"])
        self.assertTrue(out["re_derived"])
        self.assertEqual(out["overall"], "PASS")
        self.assertEqual(proc.returncode, 0)

    def test_false_command_is_REJECTED(self):
        proc, out = self._prove("false")
        self.assertFalse(out["satisfied"])
        self.assertTrue(out["re_derived"])
        self.assertEqual(out["overall"], "REJECT")
        self.assertEqual(proc.returncode, 1)

    def test_with_attestations_rejects_until_independent_attestation(self):
        # The fix for the v12.7.0 false guarantee: --with-attestations must set
        # require_attestation on the contract so a hard gate CANNOT be satisfied
        # by the doer's own evidence — it stays REJECT (UNATTESTED) until an
        # independent evaluator attests. A mock test cannot catch this (it was
        # green while the gate vacuously passed); only the real round-trip can.
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(WICKED_VAULT_BIN=_VAULT, WICKED_LOOM_BIN=_LOOM,
                   WICKED_LOOM_CUTOVER="on")
        # doer-only run → REJECT / UNATTESTED
        proc = subprocess.run(
            [sys.executable, str(_PROVE_CLI), "tests-pass", "--by", "true",
             "--scope", "s", "--phase", "migrate", "--with-attestations",
             "--project-dir", str(self.proj)],
            capture_output=True, text=True, env=env, cwd=str(_REPO), timeout=120)
        out = json.loads(proc.stdout)
        self.assertFalse(out["satisfied"])
        self.assertEqual(out["overall"], "REJECT")
        self.assertEqual(out["claims"][0]["result"], "UNATTESTED")
        self.assertEqual(proc.returncode, 1)

        # independent evaluator attests PASS → gate flips to PASS
        listing = subprocess.run(["node", _VAULT, "list", "--scope", "s",
                                  "--phase", "migrate"], cwd=str(self.proj),
                                 capture_output=True, text=True, timeout=60)
        aid = json.loads(listing.stdout)[0]["id"]
        subprocess.run(["node", _VAULT, "attest", aid, "--opinion", "pass",
                        "--evaluator", "independent-reviewer", "--rationale", "ok"],
                       cwd=str(self.proj), capture_output=True, text=True, timeout=60)
        gate = subprocess.run(
            [sys.executable, str(_REPO / "scripts" / "qe" / "vault_gate.py"),
             "gate", str(self.proj), "--scope", "s", "--phase", "migrate",
             "--with-attestations"],
            capture_output=True, text=True, env=env, cwd=str(_REPO), timeout=120)
        self.assertTrue(json.loads(gate.stdout)["satisfied"])

    # --- OUTPUT validation (not just exit codes): the capability the gate
    #     needs to be useful for produced artifacts, final or interim. ---
    def _prove_out(self, claim, command, verifier, phase):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(WICKED_VAULT_BIN=_VAULT, WICKED_LOOM_BIN=_LOOM,
                   WICKED_LOOM_CUTOVER="on")
        proc = subprocess.run(
            [sys.executable, str(_PROVE_CLI), claim, "--by", command,
             "--verifier", verifier, "--kind", "doc", "--scope", "s",
             "--phase", phase, "--project-dir", str(self.proj)],
            capture_output=True, text=True, env=env, cwd=str(_REPO), timeout=120)
        return json.loads(proc.stdout)["overall"]

    def test_regex_match_validates_output_content(self):
        (self.proj / "adr.md").write_text("## Decision\nUse PG.\n", encoding="utf-8")
        self.assertEqual(self._prove_out("has-decision", "cat adr.md",
                                         "regex_match:## Decision", "p1"), "PASS")
        self.assertEqual(self._prove_out("has-rollback", "cat adr.md",
                                         "regex_match:## Rollback", "p2"), "REJECT")

    def test_not_contains_validates_absence(self):
        (self.proj / "f.txt").write_text("clean line\n", encoding="utf-8")
        self.assertEqual(self._prove_out("no-todo", "cat f.txt",
                                         "not_contains:TODO", "p3"), "PASS")
        (self.proj / "g.txt").write_text("x  # TODO\n", encoding="utf-8")
        self.assertEqual(self._prove_out("no-todo2", "cat g.txt",
                                         "not_contains:TODO", "p4"), "REJECT")

    def test_jq_pred_validates_structured_output(self):
        (self.proj / "d.json").write_text('{"options":3}\n', encoding="utf-8")
        # natural expr (prove targets the command's JSON stdout automatically)
        self.assertEqual(self._prove_out("enough", "cat d.json",
                                         "jq_pred:.options >= 2", "p5"), "PASS")
        self.assertEqual(self._prove_out("too-few", "cat d.json",
                                         "jq_pred:.options >= 9", "p6"), "REJECT")


if __name__ == "__main__":
    unittest.main()
