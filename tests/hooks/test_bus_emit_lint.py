"""Unit tests for the bus-emit lint helper in hooks/scripts/pre_tool.py (#734 Part B).

Covers:
    * mode resolution: warn / strict / off / invalid → default warn
    * window resolution: env var honored, invalid → default 60
    * target classification: only the 4 high-priority gap suffixes match
    * recent-emit query: hits + misses + DB missing
    * end-to-end _check_bus_emit_lint: allow / warn / deny paths

Stdlib + unittest only. Provisions a real SQLite DB matching daemon/db.py
event_log schema for the recent-emit query — mocking sqlite3 hides
driver-level bugs that hit production.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# pre_tool.py lives at hooks/scripts/, not under scripts/. Add directly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
_SCRIPTS = _REPO_ROOT / "scripts"
for p in (_HOOKS_SCRIPTS, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pre_tool  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _init_event_log_only(db_path: Path) -> None:
    """Create just the event_log table — that's all the lint reads."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE event_log (
            event_id            INTEGER PRIMARY KEY,
            event_type          TEXT NOT NULL,
            chain_id            TEXT,
            payload_json        TEXT NOT NULL,
            projection_status   TEXT NOT NULL,
            error_message       TEXT,
            ingested_at         INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _seed_event(db_path: Path, *, event_id: int, event_type: str,
                chain_id: str, ingested_at: int) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO event_log
           (event_id, event_type, chain_id, payload_json,
            projection_status, ingested_at)
           VALUES (?, ?, ?, '{}', 'applied', ?)""",
        (event_id, event_type, chain_id, ingested_at),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Mode + window resolution
# ---------------------------------------------------------------------------

class TestModeAndWindow(unittest.TestCase):
    def test_mode_default_is_warn(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WG_BUS_EMIT_LINT", None)
            self.assertEqual(pre_tool._bus_emit_lint_mode(), "warn")

    def test_mode_strict_honored(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "strict"}):
            self.assertEqual(pre_tool._bus_emit_lint_mode(), "strict")

    def test_mode_off_honored(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "off"}):
            self.assertEqual(pre_tool._bus_emit_lint_mode(), "off")

    def test_mode_case_and_whitespace_tolerant(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "  STRICT  "}):
            self.assertEqual(pre_tool._bus_emit_lint_mode(), "strict")

    def test_mode_invalid_falls_back_to_warn(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "loose"}):
            self.assertEqual(pre_tool._bus_emit_lint_mode(), "warn")

    def test_window_default_60(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WG_BUS_EMIT_LINT_WINDOW_SEC", None)
            self.assertEqual(pre_tool._bus_emit_lint_window_sec(), 60)

    def test_window_env_honored(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT_WINDOW_SEC": "120"}):
            self.assertEqual(pre_tool._bus_emit_lint_window_sec(), 120)

    def test_window_invalid_falls_back_to_60(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT_WINDOW_SEC": "not-an-int"}):
            self.assertEqual(pre_tool._bus_emit_lint_window_sec(), 60)

    def test_window_zero_clamped_to_one(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT_WINDOW_SEC": "0"}):
            self.assertEqual(pre_tool._bus_emit_lint_window_sec(), 1)


# ---------------------------------------------------------------------------
# Target classification
# ---------------------------------------------------------------------------

class TestTargetClassification(unittest.TestCase):
    def test_gate_result_matches(self):
        self.assertTrue(pre_tool._is_bus_emit_lint_target(
            "/proj/foo/phases/build/gate-result.json"))

    def test_dispatch_log_matches(self):
        self.assertTrue(pre_tool._is_bus_emit_lint_target(
            "/proj/foo/phases/build/dispatch-log.jsonl"))

    def test_conditions_manifest_matches(self):
        self.assertTrue(pre_tool._is_bus_emit_lint_target(
            "/proj/foo/phases/build/conditions-manifest.json"))

    def test_reviewer_report_matches(self):
        self.assertTrue(pre_tool._is_bus_emit_lint_target(
            "/proj/foo/phases/build/reviewer-report.md"))

    def test_unrelated_path_does_not_match(self):
        self.assertFalse(pre_tool._is_bus_emit_lint_target("/proj/foo/src/main.py"))
        self.assertFalse(pre_tool._is_bus_emit_lint_target("/proj/foo/README.md"))
        self.assertFalse(pre_tool._is_bus_emit_lint_target(
            "/proj/foo/phases/build/status.md"))

    def test_scratch_file_outside_phases_dir_not_target(self):
        """Suffix-only matching would falsely flag /tmp/notes/gate-result.json.

        The path must actually live under a ``phases/`` parent for the
        lint to fire — that's the wicked-crew artifact convention.
        """
        self.assertFalse(pre_tool._is_bus_emit_lint_target(
            "/tmp/notes/gate-result.json"))
        self.assertFalse(pre_tool._is_bus_emit_lint_target(
            "/home/user/scratch/dispatch-log.jsonl"))

    def test_basename_match_is_platform_agnostic(self):
        """Path.name handles both POSIX and native-Windows separators.

        On Windows, file_path may be ``C:\\proj\\phases\\build\\gate-result.json``.
        The previous suffix-with-leading-slash check would never match.
        """
        # Construct a Windows-style path that pathlib will normalize.
        # On POSIX this becomes a single segment; on Windows, real path.
        # Either way ``.name`` is "gate-result.json" and "phases" appears
        # in parts when constructed from forward-slash form.
        win_like = "C:/proj/phases/build/gate-result.json"
        self.assertTrue(pre_tool._is_bus_emit_lint_target(win_like))


# ---------------------------------------------------------------------------
# Recent-emit query
# ---------------------------------------------------------------------------

class TestRecentEmitQuery(unittest.TestCase):
    def test_missing_db_returns_true_fail_open(self):
        """Fail-open contract: when we can't verify (no DB), assume emit happened.

        Mirrors ``_check_challenge_gate``'s "any unexpected error →
        return '' (fail-open)" convention. Users running without the
        daemon must not get false-positive lint warnings.
        """
        with patch.dict(os.environ, {"WG_DAEMON_DB": "/no/such/file.db"}):
            self.assertTrue(pre_tool._has_recent_bus_emit("anything", 60))

    def test_corrupt_db_returns_true_fail_open(self):
        """sqlite3.Error path also fail-opens to True."""
        with TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "corrupt.db"
            corrupt.write_bytes(b"this is not a sqlite database")
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(corrupt)}):
                self.assertTrue(pre_tool._has_recent_bus_emit("anything", 60))

    def test_recent_emit_within_window(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            _seed_event(db, event_id=1, event_type="wicked.gate.decided",
                        chain_id="proj-x.build", ingested_at=int(time.time()))
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(db)}):
                self.assertTrue(pre_tool._has_recent_bus_emit("proj-x", 60))

    def test_unrelated_event_type_does_not_count_as_pairing(self):
        """A wicked.project.created at session start MUST NOT pair an orphan
        gate-result.json write 30s later. Without an event_type filter the
        query would falsely return True; with the filter it stays False.
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            _seed_event(db, event_id=1, event_type="wicked.project.created",
                        chain_id="proj-x.root", ingested_at=int(time.time()))
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(db)}):
                self.assertFalse(
                    pre_tool._has_recent_bus_emit("proj-x", 60),
                    "wicked.project.created must NOT count as pairing for "
                    "gate/dispatch/conditions/reviewer-report writes",
                )

    def test_recent_gate_decided_pairs_correctly(self):
        """Sanity check the paired set — gate.decided is the most common pair."""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            for ev_type in ("wicked.gate.decided", "wicked.gate.blocked",
                            "wicked.rework.triggered"):
                _seed_event(db, event_id=hash(ev_type) & 0xFFFFFF,
                            event_type=ev_type,
                            chain_id="proj-x.build",
                            ingested_at=int(time.time()))
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(db)}):
                self.assertTrue(pre_tool._has_recent_bus_emit("proj-x", 60))

    def test_emit_outside_window_returns_false(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            # Emit was 1 hour ago.
            _seed_event(db, event_id=1, event_type="wicked.gate.decided",
                        chain_id="proj-x.build",
                        ingested_at=int(time.time()) - 3600)
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(db)}):
                self.assertFalse(pre_tool._has_recent_bus_emit("proj-x", 60))

    def test_emit_for_other_project_does_not_satisfy(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            _seed_event(db, event_id=1, event_type="wicked.gate.decided",
                        chain_id="other-proj.build", ingested_at=int(time.time()))
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(db)}):
                self.assertFalse(pre_tool._has_recent_bus_emit("proj-x", 60))

    def test_underscore_in_project_id_does_not_falsely_match(self):
        """Regression: same LIKE-escape gotcha as resume_projector.py.

        Without ESCAPE clause, ``proj_x.%`` would match ``projXx.build``
        because SQLite LIKE treats ``_`` as a single-char wildcard.
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            _seed_event(db, event_id=1, event_type="wicked.gate.decided",
                        chain_id="projXx.build", ingested_at=int(time.time()))
            with patch.dict(os.environ, {"WG_DAEMON_DB": str(db)}):
                self.assertFalse(pre_tool._has_recent_bus_emit("proj_x", 60))


# ---------------------------------------------------------------------------
# End-to-end _check_bus_emit_lint
# ---------------------------------------------------------------------------

class TestCheckBusEmitLint(unittest.TestCase):
    def test_off_mode_always_allows(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "off"}):
            action, msg = pre_tool._check_bus_emit_lint(
                "/proj/foo/phases/build/gate-result.json")
            self.assertEqual(action, "allow")
            self.assertEqual(msg, "")

    def test_non_target_path_allows(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "warn"}):
            action, msg = pre_tool._check_bus_emit_lint("/proj/foo/src/main.py")
            self.assertEqual(action, "allow")
            self.assertEqual(msg, "")

    def test_no_active_project_allows(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "strict"}), \
             patch.object(pre_tool, "_find_active_crew_project",
                          return_value=(None, None, None)):
            action, msg = pre_tool._check_bus_emit_lint(
                "/proj/foo/phases/build/gate-result.json")
            self.assertEqual(action, "allow")

    def test_warn_when_target_and_no_recent_emit(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)  # empty event_log
            with patch.dict(os.environ, {
                "WG_BUS_EMIT_LINT": "warn",
                "WG_DAEMON_DB": str(db),
            }), patch.object(pre_tool, "_find_active_crew_project",
                             return_value=({"id": "proj-x"}, "proj-x", "init-x")):
                action, msg = pre_tool._check_bus_emit_lint(
                    "/proj/foo/phases/build/gate-result.json")
                self.assertEqual(action, "warn")
                self.assertIn("bus-emit lint", msg)
                self.assertIn("proj-x", msg)
                self.assertIn("WG_BUS_EMIT_LINT=off", msg)

    def test_deny_when_target_strict_and_no_recent_emit(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            with patch.dict(os.environ, {
                "WG_BUS_EMIT_LINT": "strict",
                "WG_DAEMON_DB": str(db),
            }), patch.object(pre_tool, "_find_active_crew_project",
                             return_value=({"id": "proj-x"}, "proj-x", "init-x")):
                action, msg = pre_tool._check_bus_emit_lint(
                    "/proj/foo/phases/build/dispatch-log.jsonl")
                self.assertEqual(action, "deny")
                self.assertIn("bus-emit lint", msg)

    def test_allow_when_recent_emit_found(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_event_log_only(db)
            _seed_event(db, event_id=1, event_type="wicked.gate.decided",
                        chain_id="proj-x.build", ingested_at=int(time.time()))
            with patch.dict(os.environ, {
                "WG_BUS_EMIT_LINT": "strict",
                "WG_DAEMON_DB": str(db),
            }), patch.object(pre_tool, "_find_active_crew_project",
                             return_value=({"id": "proj-x"}, "proj-x", "init-x")):
                action, msg = pre_tool._check_bus_emit_lint(
                    "/proj/foo/phases/build/gate-result.json")
                self.assertEqual(action, "allow", f"got msg: {msg!r}")
                self.assertEqual(msg, "")

    def test_missing_db_fails_open_to_allow(self):
        """End-to-end: target + warn mode + missing DB → allow, no message.

        This is the fail-open contract surfaced through the public lint
        API. Users running without the daemon (common in dev) must not
        see false-positive lint warnings on every gate-result.json write.
        """
        with patch.dict(os.environ, {
            "WG_BUS_EMIT_LINT": "warn",
            "WG_DAEMON_DB": "/no/such/db/file.db",
        }), patch.object(pre_tool, "_find_active_crew_project",
                         return_value=({"id": "proj-x"}, "proj-x", "init-x")):
            action, msg = pre_tool._check_bus_emit_lint(
                "/proj/foo/phases/build/gate-result.json")
            self.assertEqual(action, "allow",
                             f"missing DB must fail-open, got {action}: {msg!r}")
            self.assertEqual(msg, "")

    def test_missing_db_fails_open_even_in_strict(self):
        """Strict mode + missing DB → still fails open. Daemon-not-running must not deny."""
        with patch.dict(os.environ, {
            "WG_BUS_EMIT_LINT": "strict",
            "WG_DAEMON_DB": "/no/such/db/file.db",
        }), patch.object(pre_tool, "_find_active_crew_project",
                         return_value=({"id": "proj-x"}, "proj-x", "init-x")):
            action, msg = pre_tool._check_bus_emit_lint(
                "/proj/foo/phases/build/gate-result.json")
            self.assertEqual(action, "allow",
                             f"strict mode must fail-open on missing DB, got {action}")
            self.assertEqual(msg, "")

    def test_unexpected_error_in_project_lookup_fails_open(self):
        with patch.dict(os.environ, {"WG_BUS_EMIT_LINT": "strict"}), \
             patch.object(pre_tool, "_find_active_crew_project",
                          side_effect=RuntimeError("DomainStore exploded")):
            action, msg = pre_tool._check_bus_emit_lint(
                "/proj/foo/phases/build/gate-result.json")
            self.assertEqual(action, "allow")
            self.assertEqual(msg, "")


if __name__ == "__main__":
    unittest.main()
