#!/usr/bin/env python3
"""
Standalone tests for bootstrap._check_search_staleness() — W-17, W-18, W-19.

Run with:
    python3 scripts/search/test_watcher_integration.py

These tests import _check_search_staleness directly from bootstrap.py and
monkey-patch subprocess.run / sqlite3 to avoid any real I/O.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap import — replicate how the hook is loaded
# ---------------------------------------------------------------------------

BOOTSTRAP_PATH = Path(__file__).resolve().parents[2] / "hooks" / "scripts" / "bootstrap.py"

spec = importlib.util.spec_from_file_location("bootstrap", BOOTSTRAP_PATH)
bootstrap = importlib.util.module_from_spec(spec)
# Prevent main() from executing during import
with patch("sys.stdin"):
    spec.loader.exec_module(bootstrap)

_check_search_staleness = bootstrap._check_search_staleness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeCompletedProcess:
    """Minimal subprocess.CompletedProcess stand-in."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_db(tmp_dir: Path) -> Path:
    """Create a minimal unified_search.db with a 'symbols' table and one row."""
    db_path = tmp_dir / "unified_search.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE symbols (file TEXT, name TEXT)")
    conn.execute("INSERT INTO symbols VALUES (?, ?)", (str(tmp_dir / "src" / "foo.py"), "foo"))
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# W-17: No DB present → function returns None immediately
# ---------------------------------------------------------------------------

class TestNoDatabase(unittest.TestCase):
    """W-17 — bootstrap works when no search DB exists."""

    def test_returns_none_when_db_absent(self):
        with patch.object(Path, "exists", return_value=False):
            result = _check_search_staleness()
        self.assertIsNone(result)

    def test_does_not_call_subprocess_when_db_absent(self):
        with patch.object(Path, "exists", return_value=False), \
             patch("subprocess.run") as mock_run:
            _check_search_staleness()
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# W-18: DB present, index is up to date → function returns None
# ---------------------------------------------------------------------------

class TestIndexUpToDate(unittest.TestCase):
    """W-18 — Bootstrap skips staleness note when watcher reports not stale."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        wicked_dir = self.tmp_path / ".something-wicked" / "wicked-search"
        wicked_dir.mkdir(parents=True)
        self.db_path = _make_db(wicked_dir)
        # Patch home so db_path resolves to our temp dir
        self.home_patcher = patch.object(Path, "home", return_value=self.tmp_path)
        self.home_patcher.start()

    def tearDown(self):
        self.home_patcher.stop()
        self.tmp.cleanup()

    def test_returns_none_when_not_stale(self):
        watcher_response = json.dumps({"stale": False, "changed_count": 0})
        mock_result = _FakeCompletedProcess(returncode=0, stdout=watcher_response)

        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()

        self.assertIsNone(result)

    def test_returns_none_when_watcher_empty_output(self):
        mock_result = _FakeCompletedProcess(returncode=0, stdout="")

        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()

        self.assertIsNone(result)

    def test_returns_none_when_watcher_nonzero_exit(self):
        mock_result = _FakeCompletedProcess(returncode=1, stdout="", stderr="error")

        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# W-18b: DB present, watcher reports stale → function returns briefing note
# ---------------------------------------------------------------------------

class TestIndexStale(unittest.TestCase):
    """W-18 — Bootstrap includes note when watcher reports stale index."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        wicked_dir = self.tmp_path / ".something-wicked" / "wicked-search"
        wicked_dir.mkdir(parents=True)
        self.db_path = _make_db(wicked_dir)
        self.home_patcher = patch.object(Path, "home", return_value=self.tmp_path)
        self.home_patcher.start()

    def tearDown(self):
        self.home_patcher.stop()
        self.tmp.cleanup()

    def test_reindex_ok_true_returns_auto_updated_note(self):
        watcher_response = json.dumps({
            "stale": True,
            "changed_count": 5,
            "reindex_ok": True,
        })
        mock_result = _FakeCompletedProcess(returncode=0, stdout=watcher_response)

        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()

        self.assertIsNotNone(result)
        self.assertIn("auto-updated", result)
        self.assertIn("5", result)

    def test_reindex_ok_false_returns_stale_warning(self):
        watcher_response = json.dumps({
            "stale": True,
            "changed_count": 3,
            "reindex_ok": False,
        })
        mock_result = _FakeCompletedProcess(returncode=0, stdout=watcher_response)

        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()

        self.assertIsNotNone(result)
        self.assertIn("stale", result.lower())
        self.assertIn("3", result)
        self.assertIn("failed", result.lower())

    def test_stale_without_reindex_flag_returns_generic_note(self):
        """reindex_ok absent in response — should still warn about staleness."""
        watcher_response = json.dumps({
            "stale": True,
            "changed_count": 7,
            # reindex_ok deliberately absent
        })
        mock_result = _FakeCompletedProcess(returncode=0, stdout=watcher_response)

        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()

        self.assertIsNotNone(result)
        self.assertIn("stale", result.lower())
        self.assertIn("7", result)


# ---------------------------------------------------------------------------
# W-19: Watcher subprocess fails → always returns None (fail-open)
# ---------------------------------------------------------------------------

class TestWatcherSubprocessFails(unittest.TestCase):
    """W-19 — Bootstrap continues even when watcher subprocess raises or crashes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        wicked_dir = self.tmp_path / ".something-wicked" / "wicked-search"
        wicked_dir.mkdir(parents=True)
        self.db_path = _make_db(wicked_dir)
        self.home_patcher = patch.object(Path, "home", return_value=self.tmp_path)
        self.home_patcher.start()

    def tearDown(self):
        self.home_patcher.stop()
        self.tmp.cleanup()

    def test_returns_none_when_subprocess_raises_oserror(self):
        with patch("subprocess.run", side_effect=OSError("uv not found")):
            result = _check_search_staleness()
        self.assertIsNone(result)

    def test_returns_none_when_subprocess_raises_timeout(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="uv", timeout=10)):
            result = _check_search_staleness()
        self.assertIsNone(result)

    def test_returns_none_when_json_is_invalid(self):
        mock_result = _FakeCompletedProcess(returncode=0, stdout="not-json{{{")
        with patch("subprocess.run", return_value=mock_result):
            result = _check_search_staleness()
        self.assertIsNone(result)

    def test_returns_none_when_subprocess_raises_generic_exception(self):
        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            result = _check_search_staleness()
        self.assertIsNone(result)

    def test_returns_none_when_db_is_corrupt(self):
        """Even if the SQLite DB is corrupt, function must not crash the session."""
        # Write garbage bytes to the DB path so sqlite3 raises DatabaseError
        db_path = self.tmp_path / ".something-wicked" / "wicked-search" / "unified_search.db"
        db_path.write_bytes(b"not a sqlite database \xff\xfe")

        # subprocess.run is never reached because DB read fails, but even if it
        # somehow were, we mock it to return None.
        with patch("subprocess.run", side_effect=Exception("should not be called")):
            result = _check_search_staleness()
        # Fail-open: either None (DB parse failed → no dirs → cwd used → watcher not mocked)
        # or an exception swallowed — the important thing is no exception propagates.
        # The outer except catches everything, so result must be None.
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Watcher command construction test
# ---------------------------------------------------------------------------

class TestWatcherCommandConstruction(unittest.TestCase):
    """Verify that watcher.py is invoked with --dirs and --json flags."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        wicked_dir = self.tmp_path / ".something-wicked" / "wicked-search"
        wicked_dir.mkdir(parents=True)
        self.db_path = _make_db(wicked_dir)
        self.home_patcher = patch.object(Path, "home", return_value=self.tmp_path)
        self.home_patcher.start()

    def tearDown(self):
        self.home_patcher.stop()
        self.tmp.cleanup()

    def test_watcher_invoked_with_json_flag(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"stale": False}))

        with patch("subprocess.run", side_effect=fake_run):
            _check_search_staleness()

        self.assertIn("--json", captured.get("cmd", []))

    def test_watcher_invoked_with_reindex_flag(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"stale": False}))

        with patch("subprocess.run", side_effect=fake_run):
            _check_search_staleness()

        self.assertIn("--reindex", captured.get("cmd", []))

    def test_watcher_invoked_with_dirs_flag(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"stale": False}))

        with patch("subprocess.run", side_effect=fake_run):
            _check_search_staleness()

        self.assertIn("--dirs", captured.get("cmd", []))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
