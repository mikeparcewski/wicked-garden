"""Functional test for the A3 retarget (ADR 0005): the wicked-patch flow runs
END-TO-END against a wicked-estate store — not just the adapter in isolation.

    estate store -> estate_db.py (translate) -> patch.py plan / rename / apply

Runs the real CLIs as subprocesses on a copy of the fixture repo. The store is
built by the real `wicked-estate index` when the binary is on PATH, otherwise
from the authentic checked-in dump (fixtures/estate_store.sql) — so CI executes
the full flow either way. `patch.py apply` runs the real safety gate (git-clean
+ graph freshness) inside a throwaway git repo.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_PATCH_DIR = Path(__file__).resolve().parents[1]
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_PY = sys.executable


def _run(args, cwd, input_text=None):
    return subprocess.run(
        [_PY, *args], cwd=str(cwd), input=input_text,
        capture_output=True, text=True, timeout=120,
    )


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.email=a3@test", "-c", "user.name=a3", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=60,
    )


@unittest.skipUnless(shutil.which("git"), "the apply flow's safety gate needs git")
class EstatePatchFlowTests(unittest.TestCase):
    """One repo per test: index -> translate -> plan/rename/apply -> assert files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        shutil.copytree(_FIXTURES / "estate_repo", self.repo)
        store = self.repo / ".codegraph" / "estate.db"
        store.parent.mkdir(parents=True)
        if shutil.which("wicked-estate"):
            subprocess.run(
                ["wicked-estate", "index", str(self.repo), "--db", str(store)],
                check=True, capture_output=True, text=True, timeout=120,
            )
        else:
            conn = sqlite3.connect(str(store))
            conn.executescript((_FIXTURES / "estate_store.sql").read_text(encoding="utf-8"))
            conn.commit()
            conn.close()
        # translate via the adapter CLI, exercising default store discovery
        result = _run([str(_PATCH_DIR / "estate_db.py")], cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.counts = json.loads(result.stdout)
        self.db = self.repo / ".wicked" / "patch-symbols.db"
        self.assertTrue(self.db.exists())
        for line in _git(self.repo, "init", "-q"), _git(self.repo, "add", "-A"), \
                _git(self.repo, "commit", "-qm", "fixture"):
            self.assertEqual(line.returncode, 0, line.stderr)

    def tearDown(self):
        self._tmp.cleanup()

    def _patch(self, *args, input_text=None):
        return _run([str(_PATCH_DIR / "patch.py"), "--db", str(self.db), *args],
                    cwd=self.repo, input_text=input_text)

    def test_translation_carried_the_graph(self):
        self.assertGreaterEqual(self.counts["symbols"], 12)
        self.assertGreaterEqual(self.counts["symbol_calls"], 4)
        self.assertGreaterEqual(self.counts["symbol_imports"], 1)

    def test_plan_propagates_across_files_via_estate_call_edges(self):
        """`plan` on add() must reach both callers: multiply (same file) and
        total (src/app.py) — those edges exist ONLY in the estate graph."""
        result = self._patch("plan", "src/calc.py::add", "--change", "rename_field")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("src/calc.py", result.stdout)
        self.assertIn("total", result.stdout)
        self.assertIn("multiply", result.stdout)
        self.assertIn("in 2 files", result.stdout)

    def test_rename_apply_end_to_end(self):
        """The A3 functional gate: rename Order.status across languages and APPLY it."""
        result = self._patch("rename", "src/app.py::Order",
                             "--old", "status", "--new", "provider_status",
                             "--output", "patches.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        patches = json.loads((self.repo / "patches.json").read_text())
        touched = {p["file"] for p in patches["patches"]}
        self.assertEqual(touched, {"src/app.py", "src/util.ts"},
                         "rename must reach the Python class AND the TS interface")

        # commit the generated artifacts so the git-clean safety check passes
        self.assertEqual(_git(self.repo, "add", "-A").returncode, 0)
        self.assertEqual(_git(self.repo, "commit", "-qm", "artifacts").returncode, 0)

        result = self._patch("apply", "patches.json", input_text="y\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Applied 2 files successfully", result.stdout)

        app = (self.repo / "src" / "app.py").read_text()
        util = (self.repo / "src" / "util.ts").read_text()
        self.assertIn("self.provider_status = status", app)
        self.assertNotIn("self.status", app)
        self.assertIn("provider_status: string;", util)
        self.assertIn("o.provider_status", util)
        self.assertNotIn("o.status", util)


if __name__ == "__main__":
    unittest.main()
