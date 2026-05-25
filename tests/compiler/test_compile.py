"""Tests for the wicked-garden compiler emit stage (scripts/compiler/compile.py).

Two layers:
  - EmitterOutputTests — pure, fast, no vault. The emitter writes the 4
    harness files, the contract pins the detected command, the emitted
    gate bakes in the command, and (critically) the emitted gate imports
    NOTHING from wicked-garden — it must run with the garden absent.
  - EmittedGateIntegrationTests — the falsification. Emit onto a passing
    repo and a failing repo, run the emitted gate.py AS A SUBPROCESS with
    a clean PYTHONPATH (no garden on the path), and assert PASS / exit 0
    vs REJECT / exit 1. Skipped when node or the vault CLI is unavailable.
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
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "compiler"))
import compile as wgc  # noqa: E402


def _git_init(d: Path) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=str(d), check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"],
                   cwd=str(d), env=env, check=True)


def _node_pkg(d: Path, test_script: str, lint: str | None = None,
              build: str | None = None) -> None:
    scripts = {"test": test_script}
    if lint is not None:
        scripts["lint"] = lint
    if build is not None:
        scripts["build"] = build
    (d / "package.json").write_text(json.dumps({
        "name": d.name, "version": "1.0.0", "scripts": scripts,
    }))


def _locate_vault() -> str | None:
    if shutil.which("node") is None:
        return None
    env = os.environ.get("WICKED_VAULT_BIN")
    if env and Path(env).exists():
        return env
    sibling = _REPO_ROOT.parent / "wicked-vault" / "bin" / "wicked-vault.mjs"
    return str(sibling) if sibling.exists() else None


class EmitterOutputTests(unittest.TestCase):
    def test_emits_four_files_and_pins_detected_command(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _node_pkg(repo, "exit 0")
            m = wgc.compile_repo(str(repo))
            self.assertEqual(sorted(m["emitted"]),
                             ["README.md", "bindings.json", "contract.json", "gate.py"])
            contract = json.loads((repo / ".wicked" / "contract.json").read_text())
            req = contract["required_evidence"][0]
            self.assertEqual(req["claim_id"], "tests-pass")
            self.assertEqual(req["source_pin"], "npm test")
            self.assertEqual(req["verifier"], {"kind": "exit_code_eq", "params": {"code": 0}})

    def test_emitted_gate_is_self_contained_no_garden_imports(self):
        import ast
        _STDLIB = {"json", "os", "shutil", "subprocess", "sys", "tempfile", "pathlib"}
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _node_pkg(repo, "exit 0")
            wgc.compile_repo(str(repo))
            gate_src = (repo / ".wicked" / "gate.py").read_text()
            tree = ast.parse(gate_src)
            # The whole point: the emitted harness cannot reach back into the
            # garden. Every import must be stdlib — no vault_gate, no scripts.qe.
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        self.assertIn(n.name.split(".")[0], _STDLIB,
                                      f"non-stdlib import leaked: {n.name}")
                elif isinstance(node, ast.ImportFrom):
                    root = (node.module or "").split(".")[0]
                    self.assertIn(root, _STDLIB | {"__future__"},
                                  f"non-stdlib import leaked: {node.module}")
            # And it must not reach back out via sys.path manipulation.
            self.assertNotIn("sys.path", gate_src)
            self.assertIn("'command': 'npm test'", gate_src)

    def test_unknown_ecosystem_flags_needs_review(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)  # no package.json / go.mod / pyproject → unknown
            m = wgc.compile_repo(str(repo))
            self.assertTrue(m["needs_review"])

    def test_go_repo_pins_test_lint_build(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "go.mod").write_text("module example.com/x\n\ngo 1.21\n")
            m = wgc.compile_repo(str(repo))
            # go gives all three for free (go test/vet/build are standard).
            self.assertEqual(m["claims"], {
                "tests-pass": "go test ./...",
                "lint-clean": "go vet ./...",
                "build-clean": "go build ./...",
            })
            self.assertFalse(m["needs_review"])
            contract = json.loads((repo / ".wicked" / "contract.json").read_text())
            self.assertEqual(len(contract["required_evidence"]), 3)

    def test_python_pytest_is_scoped_to_tests_dir(self):
        # Regression (found dogfooding the garden): bare `python3 -m pytest`
        # collects stray test-like files across the repo and can exit 2 on a
        # broken import. Scope it to the tests dir, matching how CI runs it.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
            (repo / "tests").mkdir()
            m = wgc.compile_repo(str(repo))
            self.assertEqual(m["claims"]["tests-pass"], "python3 -m pytest tests")

    def test_node_lint_build_only_when_declared(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _node_pkg(repo, "exit 0")  # test only, no lint/build scripts
            m = wgc.compile_repo(str(repo))
            # tests-pass present; lint/build omitted (pinning a missing linter
            # would make the gate fail forever).
            self.assertEqual(list(m["claims"]), ["tests-pass"])

    def test_node_multi_claim_when_all_declared(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _node_pkg(repo, "exit 0", lint="exit 0", build="exit 0")
            m = wgc.compile_repo(str(repo))
            self.assertEqual(m["claims"], {
                "tests-pass": "npm test",
                "lint-clean": "npm run lint",
                "build-clean": "npm run build",
            })
            gate_src = (repo / ".wicked" / "gate.py").read_text()
            self.assertIn("lint-clean", gate_src)
            self.assertIn("build-clean", gate_src)


class TriggerInstallTests(unittest.TestCase):
    """The compiler installs the trigger; it never clobbers foreign content."""

    def _repo(self, git: bool = True) -> Path:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        repo = Path(tmp)
        if git:
            _git_init(repo)
        wgc.compile_repo(str(repo))
        return repo

    def test_hook_created_executable_and_calls_gate(self):
        repo = self._repo()
        res = wgc.install_triggers(str(repo), ["hook"])[0]
        self.assertEqual(res["status"], "created")
        hook = repo / ".git" / "hooks" / "pre-push"
        self.assertTrue(hook.exists())
        self.assertTrue(os.access(hook, os.X_OK), "hook must be executable")
        self.assertIn(".wicked/gate.py", hook.read_text())

    def test_hook_reemit_is_idempotent(self):
        repo = self._repo()
        wgc.install_triggers(str(repo), ["hook"])
        res2 = wgc.install_triggers(str(repo), ["hook"])[0]
        self.assertEqual(res2["status"], "updated")
        body = (repo / ".git" / "hooks" / "pre-push").read_text()
        self.assertEqual(body.count(wgc._HOOK_START), 1, "managed block must not duplicate")

    def test_hook_preserves_foreign_hook(self):
        repo = self._repo()
        hook = repo / ".git" / "hooks" / "pre-push"
        hook.write_text("#!/bin/sh\necho my-existing-hook\n")
        res = wgc.install_triggers(str(repo), ["hook"])[0]
        self.assertEqual(res["status"], "appended")
        body = hook.read_text()
        self.assertIn("my-existing-hook", body)   # foreign content preserved
        self.assertIn(".wicked/gate.py", body)     # ours added

    def test_hook_skipped_without_git(self):
        repo = self._repo(git=False)
        res = wgc.install_triggers(str(repo), ["hook"])[0]
        self.assertEqual(res["status"], "skipped")

    def test_ci_workflow_uses_detected_ecosystem_setup(self):
        repo = self._repo()
        wgc.install_triggers(str(repo), ["ci"], ecosystem="go")
        wf = (repo / ".github" / "workflows" / "wicked-gate.yml").read_text()
        self.assertIn("actions/setup-go@", wf)
        self.assertIn("python3 .wicked/gate.py", wf)

    def test_ci_refuses_to_overwrite_foreign_workflow(self):
        repo = self._repo()
        wf = repo / ".github" / "workflows" / "wicked-gate.yml"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("name: someone-elses-workflow\n")
        res = wgc.install_triggers(str(repo), ["ci"], ecosystem="go")[0]
        self.assertEqual(res["status"], "skipped")
        self.assertIn("someone-elses-workflow", wf.read_text())  # untouched


@unittest.skipIf(_locate_vault() is None,
                 "no runnable wicked-vault (set WICKED_VAULT_BIN or sibling checkout)")
class EmittedGateIntegrationTests(unittest.TestCase):
    """Run the EMITTED gate.py with the garden off its path — PASS vs REJECT."""

    def setUp(self):
        self._bin = _locate_vault()

    def _emit_and_gate(self, test_script: str, lint: str | None = None,
                       build: str | None = None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        repo = Path(tmp)
        _git_init(repo)
        _node_pkg(repo, test_script, lint=lint, build=build)
        wgc.compile_repo(str(repo))
        # Subprocess with a CLEAN environment path: the emitted gate must NOT
        # rely on anything from wicked-garden. We hand it only the vault bin.
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "WICKED_VAULT_BIN": self._bin,
            # Deliberately NO PYTHONPATH — garden is unreachable.
        }
        proc = subprocess.run(
            [sys.executable, str(repo / ".wicked" / "gate.py")],
            cwd=str(repo), capture_output=True, text=True, timeout=180, env=env,
        )
        out = json.loads(proc.stdout) if proc.stdout.strip() else {}
        return proc.returncode, out

    def test_passing_repo_gate_passes(self):
        rc, out = self._emit_and_gate("exit 0")
        self.assertEqual(out.get("overall"), "PASS")
        self.assertEqual(rc, 0)

    def test_failing_repo_gate_rejects(self):
        # The falsification: a build whose tests do NOT pass cannot gate green,
        # even with the garden entirely absent. Re-derived, not self-asserted.
        rc, out = self._emit_and_gate("exit 1")
        self.assertEqual(out.get("overall"), "REJECT")
        self.assertEqual(rc, 1)

    def test_lint_failure_rejects_even_when_tests_pass(self):
        # The multi-claim money case: tests pass but lint fails -> the gate
        # must REJECT. A tests-only gate would have passed this build.
        rc, out = self._emit_and_gate("exit 0", lint="exit 1", build="exit 0")
        self.assertEqual(out.get("overall"), "REJECT")
        self.assertEqual(rc, 1)
        claims = {c["claim_id"]: c.get("result") for c in (out.get("claims") or [])}
        self.assertEqual(claims.get("tests-pass"), "PASS")
        self.assertEqual(claims.get("lint-clean"), "FAIL")

    def test_all_clean_passes(self):
        rc, out = self._emit_and_gate("exit 0", lint="exit 0", build="exit 0")
        self.assertEqual(out.get("overall"), "PASS")
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
