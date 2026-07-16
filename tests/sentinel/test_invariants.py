"""Tests for the claim sentinel (scripts/sentinel/invariants.py + pre_push.py).

The sentinel's whole premise is state-diff over command-match, so these tests
exercise it against REAL temp git repos (init/commit/push to a bare remote) —
no mocking of git. The ledger is redirected to a temp HOME so tests never touch
the developer's real ~/.something-wicked.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "scripts", _REPO / "scripts" / "sentinel"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import invariants as inv  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def _make_repo(base: Path, name: str = "work") -> Path:
    repo = base / name
    repo.mkdir()
    _git(repo, "init", "-b", "main", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


class _TempHome(unittest.TestCase):
    """Redirect the ledger (under ~) into a temp HOME."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self._home = patch.dict(os.environ, {"HOME": str(self.base / "home")})
        self._home.start()
        (self.base / "home").mkdir()

    def tearDown(self):
        self._home.stop()
        self._tmp.cleanup()


class LedgerTests(_TempHome):
    def test_stamp_then_verdict_for_head(self):
        repo = _make_repo(self.base)
        self.assertIsNone(inv.verdict_for(repo))
        inv.stamp_verdict(repo, overall="PASS", satisfied=True, re_derived=True,
                          scope="t", phase="build")
        stamp = inv.verdict_for(repo)
        self.assertIsNotNone(stamp)
        self.assertEqual(stamp["overall"], "PASS")

    def test_verdict_covers_recent_ancestor(self):
        repo = _make_repo(self.base)
        inv.stamp_verdict(repo, overall="PASS", satisfied=True, re_derived=True)
        (repo / "f.txt").write_text("two\n")
        _git(repo, "commit", "-aqm", "c2")  # HEAD moved past the stamp
        self.assertIsNotNone(inv.verdict_for(repo), "ancestor stamp must cover HEAD")

    def test_unsatisfied_or_claim_only_stamps_do_not_count(self):
        repo = _make_repo(self.base)
        inv.stamp_verdict(repo, overall="FAIL", satisfied=False, re_derived=True)
        inv.stamp_verdict(repo, overall="PASS", satisfied=True, re_derived=False)
        self.assertIsNone(inv.verdict_for(repo),
                          "only satisfied+re-derived stamps are a verdict")


class ClaimGateTests(_TempHome):
    """Answer tier is claim-gated at Stop: it fires only when the turn's final
    message asserts done/passing/shipped AND HEAD has no verdict. The old
    ref-watch fired on git-ref state regardless of any claim (every Bash call
    during planning tripped it); push/publish protection now lives only in
    pre_push.py (block tier) + CI."""

    def test_is_done_claim_detects_verification_assertions(self):
        for msg in (
            "All tests pass — 12/12 green.",
            "Done. Shipped it and it's ready to merge.",
            "The build is clean and all checks pass.",
        ):
            self.assertTrue(inv.is_done_claim(msg), msg)

    def test_is_done_claim_ignores_planning_and_progress(self):
        for msg in (
            "Here's my plan: first I'll explore the codebase.",
            "Let me investigate why the brain isn't starting.",
            "I'll write the spec next so we can review it.",
            "",
            None,
        ):
            self.assertFalse(inv.is_done_claim(msg), repr(msg))

    def test_claim_tick_silent_without_a_claim(self):
        # Regression: an unproven HEAD must NOT fire during planning/progress.
        repo = _make_repo(self.base)
        store: dict = {}
        self.assertIsNone(inv.claim_tick(
            store.get, store.__setitem__,
            final_message="Here's the plan; nothing is done yet.", cwd=repo))

    def test_claim_tick_fires_on_unverified_done_claim(self):
        repo = _make_repo(self.base)
        store: dict = {}
        v = inv.claim_tick(store.get, store.__setitem__,
                           final_message="All tests pass, shipped it.", cwd=repo)
        self.assertIsNotNone(v)
        self.assertEqual(v["invariant"], "done-claim-verdict")
        trail = inv._ledger_path(repo).with_suffix(".events.jsonl")
        self.assertTrue(trail.exists())
        self.assertIn("claim_unverified", trail.read_text())

    def test_claim_tick_suppressed_by_verdict(self):
        repo = _make_repo(self.base)
        inv.stamp_verdict(repo, overall="PASS", satisfied=True, re_derived=True)
        store: dict = {}
        self.assertIsNone(inv.claim_tick(
            store.get, store.__setitem__,
            final_message="All tests pass.", cwd=repo))

    def test_claim_tick_debounces_per_sha(self):
        repo = _make_repo(self.base)
        store: dict = {}
        first = inv.claim_tick(store.get, store.__setitem__,
                               final_message="all green, done", cwd=repo)
        self.assertIsNotNone(first)
        second = inv.claim_tick(store.get, store.__setitem__,
                                final_message="all green, done", cwd=repo)
        self.assertIsNone(second, "same unproven HEAD must not re-fire in a session")


class EvidenceFreshnessTests(_TempHome):
    def test_not_applicable_without_testing_layer(self):
        repo = _make_repo(self.base)
        self.assertIsNone(inv.check_evidence_freshness(repo))

    def test_stale_when_source_newer_than_evidence(self):
        repo = _make_repo(self.base)
        ev = repo / ".wicked-testing" / "evidence"
        ev.mkdir(parents=True)
        rec = ev / "run.json"
        rec.write_text("{}")
        old = time.time() - 3600
        os.utime(rec, (old, old))
        (repo / "f.txt").write_text("modified after evidence\n")  # uncommitted
        violation = inv.check_evidence_freshness(repo)
        self.assertIsNotNone(violation)
        self.assertEqual(violation["invariant"], "evidence-freshness")

    def test_fresh_evidence_is_silent(self):
        repo = _make_repo(self.base)
        (repo / "f.txt").write_text("modified\n")
        ev = repo / ".wicked-testing" / "evidence"
        ev.mkdir(parents=True)
        (ev / "run.json").write_text("{}")  # written after the source change
        self.assertIsNone(inv.check_evidence_freshness(repo))


class PrePushTests(_TempHome):
    def _run_prepush(self, repo: Path, stdin: str):
        env = dict(os.environ)
        return subprocess.run(
            [sys.executable, str(_REPO / "scripts" / "sentinel" / "pre_push.py")],
            input=stdin, capture_output=True, text=True, timeout=15,
            cwd=str(repo), env=env,
        )

    def test_blocks_unverified_main_push(self):
        repo = _make_repo(self.base)
        sha = _git(repo, "rev-parse", "HEAD")
        proc = self._run_prepush(
            repo, f"refs/heads/main {sha} refs/heads/main {_z()}\n")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("done-claim-verdict", proc.stderr)

    def test_passes_verified_main_push(self):
        repo = _make_repo(self.base)
        inv.stamp_verdict(repo, overall="PASS", satisfied=True, re_derived=True)
        sha = _git(repo, "rev-parse", "HEAD")
        proc = self._run_prepush(
            repo, f"refs/heads/main {sha} refs/heads/main {_z()}\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_feature_branch_push_never_gated(self):
        repo = _make_repo(self.base)
        sha = _git(repo, "rev-parse", "HEAD")
        proc = self._run_prepush(
            repo, f"refs/heads/feat/x {sha} refs/heads/feat/x {_z()}\n")
        self.assertEqual(proc.returncode, 0)


def _z() -> str:
    return "0" * 40


class GateStampIntegrationTests(_TempHome):
    def test_gate_satisfied_stamps_ledger_on_rederived_pass(self):
        """vault_gate.gate_satisfied is the front door — a re-derived PASS must
        leave a sentinel stamp without the gate knowing sentinel internals."""
        repo = _make_repo(self.base)
        qe = _REPO / "scripts" / "qe"
        if str(qe) not in sys.path:
            sys.path.insert(0, str(qe))
        import vault_gate  # noqa: WPS433
        fake_cc = {"available": True, "overall": "PASS", "claims": [],
                   "contract_version": 1, "detail": None, "error": None}
        with patch.object(vault_gate, "resolve_vault", return_value=["vault"]), \
             patch.object(vault_gate, "cross_check", return_value=fake_cc):
            result = vault_gate.gate_satisfied(repo, "scope", "build")
        self.assertTrue(result["satisfied"])
        self.assertIsNotNone(inv.verdict_for(repo),
                             "gate_satisfied must stamp the sentinel ledger")


class SessionEndTests(_TempHome):
    def test_capture_check_silent_without_brain_layer(self):
        repo = _make_repo(self.base)
        self.assertIsNone(inv.check_session_capture(repo, time.time() - 100, 50))

    def test_capture_check_fires_for_active_uncaptured_session(self):
        repo = _make_repo(self.base)
        proj = Path(os.environ["HOME"]) / ".wicked-brain" / "projects" / "p1"
        (proj / "_meta").mkdir(parents=True)
        (proj / "memory").mkdir()
        (proj / "_meta" / "config.json").write_text(
            json.dumps({"source_path": str(repo)}))
        v = inv.check_session_capture(repo, time.time() - 100, 50)
        self.assertIsNotNone(v)
        self.assertEqual(v["invariant"], "session-capture")
        # writing a memory silences it
        (proj / "memory" / "m.md").write_text("learned")
        self.assertIsNone(inv.check_session_capture(repo, time.time() - 100, 50))


if __name__ == "__main__":
    unittest.main()
