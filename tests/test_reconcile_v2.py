#!/usr/bin/env python3
"""Tests for scripts/crew/reconcile_v2.py (Issue #746 Site 3, PR-AB).

Per ADR docs/v9/adr-reconcile-v2.md, reconcile_v2 is the post-cutover
projection-vs-event drift detector.  These tests verify:

  1. API contract: reconcile_all() returns empty list when DB unavailable.
  2. reconcile_project() shape matches staging plan §5 schema keys.
  3. Drift detection: projection-stale (pending event, file absent).
  4. Drift detection: event-without-projection (applied/error event, file absent).
  5. Drift detection: projection-without-event (file present, no event row).
  6. No drift when events + projections are consistent (clean state).
  7. _phase_from_chain_id helpers (unit-level).
  8. read-only contract: reconcile_v2 never writes to disk.
  9. CLI smoke test: --all --json output is well-formed JSON.

Stdlib + pytest only; provisions a real SQLite DB for event_log
fixture rows (avoid mocking sqlite3 — driver-level bugs matter).

Constraints (T1-T6):
  - No sleep-based sync
  - Per-test tempdir isolation
  - Single-assertion focus where practical
  - Descriptive names
  - Provenance: Issue #746 Site 3, ADR adr-reconcile-v2.md
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import reconcile_v2  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _init_event_log_schema(db_path: Path) -> None:
    """Create the minimal event_log table matching daemon/db.py schema."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS event_log (
            event_id            INTEGER PRIMARY KEY,
            event_type          TEXT NOT NULL,
            chain_id            TEXT,
            payload_json        TEXT NOT NULL DEFAULT '{}',
            projection_status   TEXT NOT NULL DEFAULT 'applied',
            error_message       TEXT,
            ingested_at         INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_event_row(
    db_path: Path,
    *,
    event_id: int,
    event_type: str,
    chain_id: str,
    projection_status: str = "applied",
    error_message: Optional[str] = None,
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO event_log
           (event_id, event_type, chain_id, payload_json, projection_status,
            error_message, ingested_at)
           VALUES (?, ?, ?, '{}', ?, ?, ?)""",
        (event_id, event_type, chain_id, projection_status, error_message,
         int(time.time())),
    )
    conn.commit()
    conn.close()


def _make_project_dir(workspace: Path, slug: str) -> Path:
    """Create a project directory under workspace/wicked-crew/projects/{slug}."""
    project_dir = workspace / "wicked-crew" / "projects" / slug
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _make_phase_dir(project_dir: Path, phase: str) -> Path:
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


def _write_file(path: Path, content: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Base fixture class
# ---------------------------------------------------------------------------

class _ReconcileV2Fixture(unittest.TestCase):
    """Per-test tempdir with patched _projects_root + WG_LOCAL_ROOT."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wg-rv2-test-")
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)

        self.projects_root = self.workspace / "wicked-crew" / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)

        # Patch _projects_root so reconcile_v2 reads from tempdir.
        self._patch = patch.object(
            reconcile_v2, "_projects_root",
            return_value=self.projects_root,
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

        # Create the DB in the tempdir.
        self.db_path = self.workspace / "projections.db"
        _init_event_log_schema(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        """Open a shared read-write connection for test seeding."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


# ---------------------------------------------------------------------------
# 1. API contract
# ---------------------------------------------------------------------------

class TestApiContract(_ReconcileV2Fixture):

    def test_reconcile_all_returns_empty_list_when_db_missing(self) -> None:
        """reconcile_all returns [] — never raises — when DB path is missing."""
        result = reconcile_v2.reconcile_all(
            daemon_db_path="/no/such/projections.db"
        )
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_reconcile_all_returns_empty_list_when_db_has_no_event_log_table(self) -> None:
        """An empty DB (no tables) must be treated as unavailable."""
        empty_db = self.workspace / "empty.db"
        # Write an empty SQLite file.
        sqlite3.connect(str(empty_db)).close()
        result = reconcile_v2.reconcile_all(daemon_db_path=str(empty_db))
        self.assertEqual(result, [])

    def test_reconcile_project_result_has_required_schema_keys(self) -> None:
        """Per staging plan §5 schema — all required keys must be present."""
        _make_project_dir(self.workspace, "myproj")
        result = reconcile_v2.reconcile_project(
            "myproj",
            _daemon_conn=self._conn(),
        )
        required = {
            "project_slug", "events_for_project",
            "projections_materialized", "drift", "summary", "errors",
        }
        self.assertEqual(required, required & set(result.keys()))

    def test_reconcile_project_summary_has_all_count_keys(self) -> None:
        _make_project_dir(self.workspace, "summaryproj")
        result = reconcile_v2.reconcile_project("summaryproj", _daemon_conn=self._conn())
        summary_keys = {
            "total_drift_count",
            "projection_stale_count",
            "event_without_projection_count",
            "projection_without_event_count",
        }
        self.assertEqual(summary_keys, summary_keys & set(result["summary"].keys()))


# ---------------------------------------------------------------------------
# 2. Drift detection — projection-stale
# ---------------------------------------------------------------------------

class TestProjectionStaleDrift(_ReconcileV2Fixture):

    def test_pending_event_with_no_on_disk_file_is_projection_stale(self) -> None:
        """An event with projection_status=pending and absent on-disk file → drift."""
        _make_project_dir(self.workspace, "stale-proj")
        # Gate-decided event pending; NO gate-result.json on disk.
        _insert_event_row(
            self.db_path,
            event_id=1,
            event_type="wicked.gate.decided",
            chain_id="stale-proj.build.gate",
            projection_status="pending",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("stale-proj", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(reconcile_v2.DRIFT_PROJECTION_STALE, drift_types)

    def test_pending_event_with_file_present_is_not_projection_stale(self) -> None:
        """When the file exists, a pending event is not projection-stale."""
        project_dir = _make_project_dir(self.workspace, "not-stale")
        phase_dir = _make_phase_dir(project_dir, "build")
        _write_file(phase_dir / "gate-result.json", '{"verdict": "APPROVE"}')

        _insert_event_row(
            self.db_path,
            event_id=2,
            event_type="wicked.gate.decided",
            chain_id="not-stale.build.gate",
            projection_status="pending",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("not-stale", _daemon_conn=conn)
        conn.close()

        stale = [d for d in result["drift"]
                 if d["type"] == reconcile_v2.DRIFT_PROJECTION_STALE]
        self.assertEqual(stale, [])


# ---------------------------------------------------------------------------
# 3. Drift detection — event-without-projection
# ---------------------------------------------------------------------------

class TestEventWithoutProjectionDrift(_ReconcileV2Fixture):

    def test_applied_event_with_no_file_is_event_without_projection(self) -> None:
        """Applied event but no on-disk projection → event-without-projection drift."""
        _make_project_dir(self.workspace, "ewp-proj")
        _insert_event_row(
            self.db_path,
            event_id=10,
            event_type="wicked.gate.decided",
            chain_id="ewp-proj.design.gate",
            projection_status="applied",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("ewp-proj", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION, drift_types)

    def test_error_event_with_no_file_is_event_without_projection(self) -> None:
        """Error-status event with absent file → event-without-projection."""
        _make_project_dir(self.workspace, "ewp-err")
        _insert_event_row(
            self.db_path,
            event_id=11,
            event_type="wicked.consensus.report_created",
            chain_id="ewp-err.review.consensus.aabbccdd",
            projection_status="error",
            error_message="handler raised",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("ewp-err", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION, drift_types)

    def test_applied_event_with_file_present_is_not_event_without_projection(self) -> None:
        project_dir = _make_project_dir(self.workspace, "ewp-ok")
        phase_dir = _make_phase_dir(project_dir, "design")
        _write_file(phase_dir / "gate-result.json")

        _insert_event_row(
            self.db_path,
            event_id=12,
            event_type="wicked.gate.decided",
            chain_id="ewp-ok.design.gate",
            projection_status="applied",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("ewp-ok", _daemon_conn=conn)
        conn.close()

        ewp = [d for d in result["drift"]
               if d["type"] == reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION]
        self.assertEqual(ewp, [])


# ---------------------------------------------------------------------------
# 4. Drift detection — projection-without-event
# ---------------------------------------------------------------------------

class TestProjectionWithoutEventDrift(_ReconcileV2Fixture):

    def test_on_disk_file_with_no_event_is_projection_without_event(self) -> None:
        """A gate-result.json on disk but no event_log row → projection-without-event."""
        project_dir = _make_project_dir(self.workspace, "pwe-proj")
        phase_dir = _make_phase_dir(project_dir, "build")
        _write_file(phase_dir / "gate-result.json")
        # No event rows in DB.
        conn = self._conn()
        result = reconcile_v2.reconcile_project("pwe-proj", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT, drift_types)

    def test_on_disk_file_with_matching_event_is_not_projection_without_event(self) -> None:
        project_dir = _make_project_dir(self.workspace, "pwe-ok")
        phase_dir = _make_phase_dir(project_dir, "build")
        _write_file(phase_dir / "gate-result.json")

        _insert_event_row(
            self.db_path,
            event_id=20,
            event_type="wicked.gate.decided",
            chain_id="pwe-ok.build.gate",
            projection_status="applied",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("pwe-ok", _daemon_conn=conn)
        conn.close()

        pwe = [d for d in result["drift"]
               if d["type"] == reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT]
        self.assertEqual(pwe, [])


# ---------------------------------------------------------------------------
# 5. Clean state — no drift
# ---------------------------------------------------------------------------

class TestNoDriftWhenClean(_ReconcileV2Fixture):

    def test_no_drift_when_all_events_have_projections_and_vice_versa(self) -> None:
        """Zero drift when every event has a file and every file has an event."""
        project_dir = _make_project_dir(self.workspace, "clean-proj")
        phase_dir = _make_phase_dir(project_dir, "build")
        _write_file(phase_dir / "gate-result.json")

        _insert_event_row(
            self.db_path,
            event_id=30,
            event_type="wicked.gate.decided",
            chain_id="clean-proj.build.gate",
            projection_status="applied",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("clean-proj", _daemon_conn=conn)
        conn.close()

        self.assertEqual(result["drift"], [],
                         f"Expected no drift, got: {result['drift']}")
        self.assertEqual(result["summary"]["total_drift_count"], 0)


# ---------------------------------------------------------------------------
# 6. Read-only contract
# ---------------------------------------------------------------------------

class TestReadOnlyContract(_ReconcileV2Fixture):

    def test_reconcile_project_does_not_write_any_files(self) -> None:
        """reconcile_project must never write to either store."""
        project_dir = _make_project_dir(self.workspace, "readonly-proj")

        before_mtimes = {
            str(p): p.stat().st_mtime
            for p in project_dir.rglob("*")
            if p.is_file()
        }

        conn = self._conn()
        reconcile_v2.reconcile_project("readonly-proj", _daemon_conn=conn)
        conn.close()

        after_mtimes = {
            str(p): p.stat().st_mtime
            for p in project_dir.rglob("*")
            if p.is_file()
        }
        self.assertEqual(
            before_mtimes,
            after_mtimes,
            "reconcile_v2.reconcile_project mutated a file — read-only violation",
        )


# ---------------------------------------------------------------------------
# 7. _phase_from_chain_id helper
# ---------------------------------------------------------------------------

class TestPhaseFromChainId(unittest.TestCase):

    def test_standard_chain_id_returns_phase(self) -> None:
        self.assertEqual(
            reconcile_v2._phase_from_chain_id("myproj.build.gate"),
            "build",
        )

    def test_root_chain_id_returns_none(self) -> None:
        self.assertIsNone(reconcile_v2._phase_from_chain_id("myproj.root"))

    def test_project_only_returns_none(self) -> None:
        self.assertIsNone(reconcile_v2._phase_from_chain_id("myproj"))

    def test_none_input_returns_none(self) -> None:
        self.assertIsNone(reconcile_v2._phase_from_chain_id(None))

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(reconcile_v2._phase_from_chain_id(""))

    def test_consensus_chain_id_returns_phase(self) -> None:
        # e.g. "myproj.design.consensus.abc123"
        self.assertEqual(
            reconcile_v2._phase_from_chain_id("myproj.design.consensus.abc123"),
            "design",
        )


# ---------------------------------------------------------------------------
# 8. CLI smoke test
# ---------------------------------------------------------------------------

class TestCliSmokeTest(unittest.TestCase):

    def test_all_json_with_no_db_outputs_valid_json(self) -> None:
        """reconcile_v2 --all --json must always produce valid JSON even when DB absent."""
        buf = io.StringIO()
        with redirect_stdout(buf), \
             patch.dict(os.environ, {"WG_DAEMON_DB": "/no/such/projections.db"}):
            rc = reconcile_v2.main(["--all", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIsInstance(payload, list)

    def test_all_text_with_no_db_outputs_string(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf), \
             patch.dict(os.environ, {"WG_DAEMON_DB": "/no/such/projections.db"}):
            rc = reconcile_v2.main(["--all"])
        self.assertEqual(rc, 0)
        self.assertIsInstance(buf.getvalue(), str)
        self.assertGreater(len(buf.getvalue()), 0)


# ---------------------------------------------------------------------------
# 9. Drift type constant values
# ---------------------------------------------------------------------------

class TestDriftTypeConstants(unittest.TestCase):

    def test_projection_stale_value(self) -> None:
        self.assertEqual(reconcile_v2.DRIFT_PROJECTION_STALE, "projection-stale")

    def test_event_without_projection_value(self) -> None:
        self.assertEqual(
            reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION, "event-without-projection"
        )

    def test_projection_without_event_value(self) -> None:
        self.assertEqual(
            reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT, "projection-without-event"
        )


if __name__ == "__main__":
    unittest.main()
