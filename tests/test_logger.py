#!/usr/bin/env python3
"""
Unit tests for scripts/_logger.py

Covers:
- AC-01: Schema and existence
- AC-02: Level filtering
- AC-03: TMPDIR fallback
- AC-11: WICKED_LOG_LEVEL env var precedence
- Security: path traversal in session ID
- Edge cases: non-serializable detail, never-raises contract
"""

import importlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup — matching existing test suite pattern
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS))


def _fresh_logger():
    """Import or re-import _logger with a clean module state."""
    if "_logger" in sys.modules:
        del sys.modules["_logger"]
    import _logger
    return _logger


# ---------------------------------------------------------------------------
# AC-01: Schema and existence
# ---------------------------------------------------------------------------


class TestLoggerSchemaAndExistence(unittest.TestCase):
    """AC-01: _logger.py exists, imports cleanly, and writes valid JSONL."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "TMPDIR": self.tmpdir.name,
                "CLAUDE_SESSION_ID": "test-session-001",
                "WICKED_LOG_LEVEL": "normal",
            },
            clear=False,
        )
        self.env_patch.start()
        self.logger = _fresh_logger()

    def tearDown(self):
        self.env_patch.stop()
        self.tmpdir.cleanup()

    def _log_path(self):
        return Path(self.tmpdir.name) / "wicked-ops-test-session-001.jsonl"

    def _call_and_read(self, **kwargs):
        defaults = dict(domain="bootstrap", level="normal", event="onboarding.status", ok=True)
        defaults.update(kwargs)
        self.logger.log(**defaults)
        lp = self._log_path()
        self.assertTrue(lp.exists(), "Log file was not created")
        return lp.read_text(encoding="utf-8").strip().splitlines()

    # S01-A: import succeeds with stdlib-only env
    def test_import_no_external_deps(self):
        """Import _logger cleanly — module is present in sys.modules and no ImportError raised."""
        logger = _fresh_logger()
        # Verify the module is accessible and has the expected public API
        self.assertIn("_logger", sys.modules)
        self.assertTrue(callable(logger.log), "_logger.log should be callable")
        # Verify only stdlib modules were imported (spot-check for absence of known third-party libs)
        third_party_markers = {"pydantic", "requests", "aiohttp", "numpy", "pandas"}
        loaded = set(sys.modules.keys())
        overlap = third_party_markers & loaded
        self.assertEqual(overlap, set(), f"Third-party modules loaded by _logger: {overlap}")

    # S01-B: log() writes a file
    def test_log_writes_valid_jsonl(self):
        """log() creates the expected .jsonl file and writes a parseable line."""
        lines = self._call_and_read()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertIsInstance(entry, dict)

    # S01-C / S01-D: all 8 required keys present
    def test_schema_keys(self):
        """Parsed log entry contains all 8 required keys."""
        lines = self._call_and_read()
        entry = json.loads(lines[0])
        required = {"ts", "session", "domain", "level", "event", "ok", "ms", "detail"}
        self.assertEqual(required, required & entry.keys())

    # S01-E: ts is ISO-8601 UTC ending in Z
    def test_ts_is_iso8601_utc(self):
        """The ts field is ISO-8601 UTC format ending with 'Z'."""
        lines = self._call_and_read()
        entry = json.loads(lines[0])
        ts = entry["ts"]
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$"
        self.assertRegex(ts, pattern, f"ts '{ts}' is not ISO-8601 UTC")

    # S01-F: null fields are explicit null, not absent
    def test_null_fields_explicit(self):
        """ms and detail are explicitly null (not missing) when not provided."""
        lines = self._call_and_read()
        entry = json.loads(lines[0])
        self.assertIn("ms", entry)
        self.assertIn("detail", entry)
        self.assertIsNone(entry["ms"])
        self.assertIsNone(entry["detail"])

    # S01-G: ms rounded to 2 decimal places
    def test_ms_is_integer(self):
        """ms value is a float/int when provided and rounded to 2 decimal places."""
        lines = self._call_and_read(ms=12.3456789)
        entry = json.loads(lines[0])
        self.assertIsNotNone(entry["ms"])
        self.assertEqual(entry["ms"], 12.35)

    # S01-H: multiple writes append
    def test_multiple_writes_append(self):
        """Calling log() twice produces exactly 2 lines (append, not overwrite)."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "normal"}):
            self.logger.log("bootstrap", "normal", "ev.first", ok=True)
            self.logger.log("bootstrap", "normal", "ev.second", ok=True)
        lp = self._log_path()
        lines = lp.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)

    # S01-I: nested detail serializes cleanly
    def test_nested_detail_serializes(self):
        """detail with nested dict serializes without TypeError."""
        lines = self._call_and_read(detail={"key": {"nested": True}})
        entry = json.loads(lines[0])
        self.assertEqual(entry["detail"], {"key": {"nested": True}})


# ---------------------------------------------------------------------------
# AC-02: Level filtering
# ---------------------------------------------------------------------------


class TestLevelFiltering(unittest.TestCase):
    """AC-02: Events filtered according to effective log level."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "TMPDIR": self.tmpdir.name,
                "CLAUDE_SESSION_ID": "test-session-002",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.tmpdir.cleanup()

    def _log_path(self):
        return Path(self.tmpdir.name) / "wicked-ops-test-session-002.jsonl"

    def _line_count(self):
        lp = self._log_path()
        if not lp.exists():
            return 0
        text = lp.read_text(encoding="utf-8").strip()
        return len(text.splitlines()) if text else 0

    def _call(self, event_level):
        logger = _fresh_logger()
        logger.log("test", event_level, "test.event", ok=True)

    # S02-A: normal filters verbose
    def test_normal_blocks_verbose(self):
        """WICKED_LOG_LEVEL=normal: verbose events are not written."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "normal"}):
            self._call("verbose")
        self.assertEqual(self._line_count(), 0)

    # S02-B: normal blocks debug
    def test_normal_blocks_debug(self):
        """WICKED_LOG_LEVEL=normal: debug events are not written."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "normal"}):
            self._call("debug")
        self.assertEqual(self._line_count(), 0)

    # S02-C: verbose passes verbose
    def test_verbose_passes_verbose(self):
        """WICKED_LOG_LEVEL=verbose: verbose events ARE written."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "verbose"}):
            self._call("verbose")
        self.assertEqual(self._line_count(), 1)

    # S02-D: verbose blocks debug
    def test_verbose_blocks_debug(self):
        """WICKED_LOG_LEVEL=verbose: debug events are not written."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "verbose"}):
            self._call("debug")
        self.assertEqual(self._line_count(), 0)

    # S02-E: debug passes all
    def test_debug_passes_all(self):
        """WICKED_LOG_LEVEL=debug: all levels are written."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "debug"}):
            logger = _fresh_logger()
            logger.log("test", "normal", "ev.normal", ok=True)
            logger.log("test", "verbose", "ev.verbose", ok=True)
            logger.log("test", "debug", "ev.debug", ok=True)
        self.assertEqual(self._line_count(), 3)

    # S02-F: debug allows normal (explicit)
    def test_debug_passes_normal(self):
        """WICKED_LOG_LEVEL=debug: normal events are also written."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "debug"}):
            self._call("normal")
        self.assertEqual(self._line_count(), 1)

    # S02-G: invalid level treated as debug (most permissive)
    def test_invalid_level_treated_as_debug(self):
        """Unknown event level is treated as debug (rank 2) — still written when level=debug."""
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "debug"}):
            self._call("bogus")
        # bogus level gets rank 2 (debug), effective debug rank is 2, so 2 <= 2: written
        self.assertEqual(self._line_count(), 1)


# ---------------------------------------------------------------------------
# AC-03: TMPDIR fallback
# ---------------------------------------------------------------------------


class TestTmpDirFallback(unittest.TestCase):
    """AC-03: Log file written to $TMPDIR with /tmp fallback when unset."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        # Track files we write to /tmp for cleanup
        self._tmp_files_to_clean = []

    def tearDown(self):
        self.tmpdir.cleanup()
        for p in self._tmp_files_to_clean:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass

    # S03-A + S03-B: TMPDIR unset falls back to /tmp
    def test_tmpdir_unset_falls_back_to_tmp(self):
        """When TMPDIR is unset, log file is written under tempfile.gettempdir()."""
        env = {
            "CLAUDE_SESSION_ID": "test-session-tmpfallback",
            "WICKED_LOG_LEVEL": "normal",
        }
        # Remove TMPDIR if present
        env_clean = {k: v for k, v in os.environ.items() if k != "TMPDIR"}
        env_clean.update(env)
        with patch.dict(os.environ, env_clean, clear=True):
            logger = _fresh_logger()
            logger.log("bootstrap", "normal", "onboarding.status", ok=True)
        # Use tempfile.gettempdir() which matches _logger.py behavior (not hardcoded /tmp)
        expected = Path(tempfile.gettempdir()) / "wicked-ops-test-session-tmpfallback.jsonl"
        self._tmp_files_to_clean.append(str(expected))
        self.assertTrue(expected.exists(), f"Expected log file at {expected}")

    # S03-C: custom TMPDIR is respected
    def test_custom_tmpdir_respected(self):
        """When TMPDIR is set to a custom path, log file is written there (not /tmp)."""
        env = {
            "TMPDIR": self.tmpdir.name,
            "CLAUDE_SESSION_ID": "test-session-customtmp",
            "WICKED_LOG_LEVEL": "normal",
        }
        with patch.dict(os.environ, env, clear=False):
            logger = _fresh_logger()
            logger.log("bootstrap", "normal", "onboarding.status", ok=True)
        expected = Path(self.tmpdir.name) / "wicked-ops-test-session-customtmp.jsonl"
        self.assertTrue(expected.exists(), f"Expected log file at {expected}")
        # Ensure NOT written to /tmp
        not_expected = Path("/tmp") / "wicked-ops-test-session-customtmp.jsonl"
        self._tmp_files_to_clean.append(str(not_expected))
        self.assertFalse(not_expected.exists(), "File should not be in /tmp when TMPDIR is set")

    # S03-D: TMPDIR set to non-existent path does not raise
    def test_nonexistent_tmpdir_does_not_raise(self):
        """When TMPDIR points to a non-existent path, log() returns without raising."""
        env = {
            "TMPDIR": "/nonexistent/path/for/wicked/test",
            "CLAUDE_SESSION_ID": "test-session-badtmp",
            "WICKED_LOG_LEVEL": "normal",
        }
        with patch.dict(os.environ, env, clear=False):
            logger = _fresh_logger()
            try:
                logger.log("bootstrap", "normal", "onboarding.status", ok=True)
            except Exception as exc:
                self.fail(f"log() raised an exception with bad TMPDIR: {exc}")


# ---------------------------------------------------------------------------
# AC-11: WICKED_LOG_LEVEL env var precedence
# ---------------------------------------------------------------------------


class TestLevelPrecedence(unittest.TestCase):
    """AC-11: Level resolution — env var > session state > default 'normal'."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "TMPDIR": self.tmpdir.name,
                "CLAUDE_SESSION_ID": "test-session-prec",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.tmpdir.cleanup()

    def _log_path(self):
        return Path(self.tmpdir.name) / "wicked-ops-test-session-prec.jsonl"

    def _session_state_path(self):
        return Path(self.tmpdir.name) / "wicked-garden-session-test-session-prec.json"

    def _write_session_state(self, log_level):
        self._session_state_path().write_text(
            json.dumps({"log_level": log_level}), encoding="utf-8"
        )

    def _line_count(self):
        lp = self._log_path()
        if not lp.exists():
            return 0
        text = lp.read_text(encoding="utf-8").strip()
        return len(text.splitlines()) if text else 0

    # S11-A: env var beats session state
    def test_env_var_overrides_session(self):
        """WICKED_LOG_LEVEL=debug wins over session log_level=normal — debug event written."""
        self._write_session_state("normal")
        with patch.dict(os.environ, {"WICKED_LOG_LEVEL": "debug"}):
            logger = _fresh_logger()
            logger.log("test", "debug", "test.debug", ok=True)
        self.assertEqual(self._line_count(), 1, "debug event should be written when env=debug overrides session=normal")

    # S11-B: session state used when no env var
    def test_session_state_used_when_no_env(self):
        """Without WICKED_LOG_LEVEL, session log_level=verbose allows verbose events."""
        self._write_session_state("verbose")
        env = {k: v for k, v in os.environ.items() if k != "WICKED_LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True):
            logger = _fresh_logger()
            logger.log("test", "verbose", "test.verbose", ok=True)
        self.assertEqual(self._line_count(), 1, "verbose event should be written when session=verbose")

    # S11-C: default normal when both absent — verbose not written
    def test_default_normal_when_both_absent(self):
        """Without WICKED_LOG_LEVEL and without log_level in session, verbose is NOT written."""
        # No session state file written
        env = {k: v for k, v in os.environ.items() if k != "WICKED_LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True):
            logger = _fresh_logger()
            logger.log("test", "verbose", "test.verbose", ok=True)
        self.assertEqual(self._line_count(), 0, "verbose event should be filtered when default=normal")

    # S11-D: missing session file still works with default
    def test_missing_session_file_uses_default(self):
        """When session file doesn't exist, logger uses default 'normal' level gracefully."""
        # Session state file deliberately not created
        env = {k: v for k, v in os.environ.items() if k != "WICKED_LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True):
            logger = _fresh_logger()
            try:
                logger.log("test", "normal", "test.normal", ok=True)
            except Exception as exc:
                self.fail(f"log() raised with missing session file: {exc}")
        # normal event should still be written at default normal level
        self.assertEqual(self._line_count(), 1)

    # S11-E: malformed session JSON falls back to default
    def test_malformed_session_json_falls_back(self):
        """Malformed session state JSON is silently ignored; default normal level is used."""
        self._session_state_path().write_text("invalid json{", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "WICKED_LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True):
            logger = _fresh_logger()
            logger.log("test", "verbose", "test.verbose", ok=True)
        self.assertEqual(self._line_count(), 0, "verbose should be blocked when malformed session defaults to normal")


# ---------------------------------------------------------------------------
# Security: path traversal in CLAUDE_SESSION_ID
# ---------------------------------------------------------------------------


class TestSessionIdSanitization(unittest.TestCase):
    """Security: path-traversal characters in CLAUDE_SESSION_ID are sanitized."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "TMPDIR": self.tmpdir.name,
                "WICKED_LOG_LEVEL": "normal",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.tmpdir.cleanup()

    def test_session_id_path_traversal_sanitized(self):
        """Session ID with path-traversal chars produces a safe filename under TMPDIR."""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "../../etc/passwd"}):
            logger = _fresh_logger()
            logger.log("bootstrap", "normal", "test.event", ok=True)

        # No file should appear outside tmpdir
        traversal_target = Path("/etc/passwd")
        # The file should NOT have been written outside tmpdir
        # Verify any .jsonl file written is inside tmpdir
        written = list(Path(self.tmpdir.name).glob("wicked-ops-*.jsonl"))
        self.assertTrue(len(written) > 0, "No log file was written — session was silently dropped")
        for f in written:
            self.assertTrue(
                str(f).startswith(self.tmpdir.name),
                f"Log file '{f}' escaped TMPDIR '{self.tmpdir.name}'"
            )
            # The filename should not contain bare slashes in the session portion
            filename = f.name  # e.g. wicked-ops-___..._etc_passwd.jsonl
            session_part = filename[len("wicked-ops-"):-len(".jsonl")]
            self.assertNotIn("/", session_part, f"Slash present in session part: '{session_part}'")
            self.assertNotIn("..", session_part, f"'..' present in session part: '{session_part}'")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases(unittest.TestCase):
    """Edge cases: non-serializable detail, never-raises contract."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "TMPDIR": self.tmpdir.name,
                "CLAUDE_SESSION_ID": "test-session-edge",
                "WICKED_LOG_LEVEL": "debug",
            },
            clear=False,
        )
        self.env_patch.start()
        self.logger = _fresh_logger()

    def tearDown(self):
        self.env_patch.stop()
        self.tmpdir.cleanup()

    # S01-K: non-serializable detail should not crash
    def test_non_serializable_detail(self):
        """log() with non-JSON-serializable detail does not raise."""
        try:
            self.logger.log(
                "bootstrap", "normal", "test.event", ok=True,
                detail={"obj": object()}
            )
        except Exception as exc:
            self.fail(f"log() raised with non-serializable detail: {exc}")

    def test_non_serializable_detail_writes_fallback(self):
        """Non-serializable detail is replaced by a string fallback, not silently dropped."""
        self.logger.log(
            "bootstrap", "normal", "test.event", ok=True,
            detail={"obj": object()}
        )
        lp = Path(self.tmpdir.name) / "wicked-ops-test-session-edge.jsonl"
        self.assertTrue(lp.exists())
        entry = json.loads(lp.read_text(encoding="utf-8").strip())
        # detail should be present (either original or _raw fallback)
        self.assertIn("detail", entry)
        self.assertIsNotNone(entry["detail"])

    # S01-K extended: various bad inputs should never raise
    def test_log_never_raises_none_domain(self):
        try:
            self.logger.log(None, "normal", "test.event", ok=True)
        except Exception as exc:
            self.fail(f"log() raised with None domain: {exc}")

    def test_log_never_raises_empty_event(self):
        try:
            self.logger.log("bootstrap", "normal", "", ok=True)
        except Exception as exc:
            self.fail(f"log() raised with empty event: {exc}")

    def test_log_never_raises_bad_ms(self):
        try:
            self.logger.log("bootstrap", "normal", "test.event", ok=True, ms="not-a-number")
        except Exception as exc:
            self.fail(f"log() raised with non-numeric ms: {exc}")

    def test_log_never_raises_ok_none(self):
        try:
            self.logger.log("bootstrap", "normal", "test.event", ok=None)
        except Exception as exc:
            self.fail(f"log() raised with ok=None: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
