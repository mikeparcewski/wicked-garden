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
        """A gate-result.json on disk but no event_log row → projection-without-event.

        Note: gate-result.json is owned by Site 4.  The test sets
        WG_BUS_AS_TRUTH_GATE_RESULT=on so the file is included in the active
        projection set — otherwise Finding #1 correctly suppresses it.
        """
        project_dir = _make_project_dir(self.workspace, "pwe-proj")
        phase_dir = _make_phase_dir(project_dir, "build")
        _write_file(phase_dir / "gate-result.json")
        # No event rows in DB.
        conn = self._conn()
        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
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
        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_GATE_RESULT": "on"}):
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
        """reconcile_v2 --all --json must always produce valid JSON even when DB absent.

        Per staging plan §5 the output is now:
          {"header": {...}, "results": [...]}
        rather than a bare list (schema bump from v1 bare-list shape).
        """
        buf = io.StringIO()
        with redirect_stdout(buf), \
             patch.dict(os.environ, {"WG_DAEMON_DB": "/no/such/projections.db"}):
            rc = reconcile_v2.main(["--all", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIsInstance(payload, dict)
        self.assertIn("header", payload)
        self.assertIn("results", payload)
        self.assertIsInstance(payload["results"], list)

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


# ---------------------------------------------------------------------------
# Finding #1 — gate_pending maps to reviewer-report.md
# ---------------------------------------------------------------------------

class TestGatePendingMapsToReviewerReport(_ReconcileV2Fixture):
    """Regression: wicked.consensus.gate_pending must map to reviewer-report.md.

    Before the fix, only gate_completed was in _PROJECTION_MAP.  A pending
    event would be unmapped, and an existing reviewer-report.md would be
    flagged as projection-without-event.
    """

    def test_gate_pending_event_with_reviewer_report_is_not_drift(self) -> None:
        """gate_pending event + reviewer-report.md on disk → zero drift."""
        project_dir = _make_project_dir(self.workspace, "pending-rpt-proj")
        phase_dir = _make_phase_dir(project_dir, "review")
        _write_file(phase_dir / "reviewer-report.md", "# pending review\n")

        _insert_event_row(
            self.db_path,
            event_id=100,
            event_type="wicked.consensus.gate_pending",
            chain_id="pending-rpt-proj.review.consensus.aabbccdd",
            projection_status="applied",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("pending-rpt-proj", _daemon_conn=conn)
        conn.close()

        self.assertEqual(
            result["drift"],
            [],
            f"Expected no drift for gate_pending + reviewer-report.md, got: {result['drift']}",
        )

    def test_gate_pending_event_without_reviewer_report_is_event_without_projection(
        self,
    ) -> None:
        """gate_pending event but no reviewer-report.md → event-without-projection drift."""
        _make_project_dir(self.workspace, "pending-missing-proj")
        _insert_event_row(
            self.db_path,
            event_id=101,
            event_type="wicked.consensus.gate_pending",
            chain_id="pending-missing-proj.review.consensus.ccddee00",
            projection_status="applied",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("pending-missing-proj", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION, drift_types)


# ---------------------------------------------------------------------------
# Finding #2 — conditions-manifest.json excluded during pre-Site-5 coexistence
# ---------------------------------------------------------------------------

class TestConditionsManifestExcludedPreSite5(_ReconcileV2Fixture):
    """Regression: conditions-manifest.json must NOT trigger projection-without-event
    before Site 5 ships.  Every existing CONDITIONAL phase would fire false drift
    otherwise.

    TODO (Site 5): when WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST ships, re-add
    conditions-manifest.json to _collect_projection_files + _PROJECTION_MAP and
    flip this test to assert drift IS detected when the file has no event.
    """

    def test_conditions_manifest_without_event_does_not_report_drift(self) -> None:
        """Pre-Site-5 coexistence: conditions-manifest.json is not a tracked
        projection and must produce zero drift even when no event exists for it."""
        project_dir = _make_project_dir(self.workspace, "cond-manifest-proj")
        phase_dir = _make_phase_dir(project_dir, "design")
        _write_file(
            phase_dir / "conditions-manifest.json",
            '{"conditions": []}',
        )
        # No event rows inserted — simulating pre-Site-5 state.
        conn = self._conn()
        result = reconcile_v2.reconcile_project("cond-manifest-proj", _daemon_conn=conn)
        conn.close()

        pwe = [
            d for d in result["drift"]
            if d["type"] == reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT
        ]
        self.assertEqual(
            pwe,
            [],
            "conditions-manifest.json should not trigger projection-without-event "
            "before Site 5 cuts over.",
        )


# ---------------------------------------------------------------------------
# Finding #3 — --daemon-db honoured in single-project CLI mode
# ---------------------------------------------------------------------------

class TestDaemonDbHonouredInSingleProjectMode(unittest.TestCase):
    """Regression: --project X --daemon-db /path must use the override path,
    not silently fall back to the default DB."""

    def test_single_project_mode_uses_daemon_db_override(self) -> None:
        """reconcile_project receives daemon_db_path when --daemon-db is supplied."""
        captured: dict = {}

        def fake_reconcile_project(slug: str, **kwargs: Any) -> dict:
            captured["daemon_db_path"] = kwargs.get("daemon_db_path")
            return {
                "project_slug": slug,
                "events_for_project": 0,
                "projections_materialized": {},
                "drift": [],
                "summary": {
                    "total_drift_count": 0,
                    "projection_stale_count": 0,
                    "event_without_projection_count": 0,
                    "projection_without_event_count": 0,
                },
                "errors": [],
            }

        override_path = "/tmp/fake-override.db"
        buf = io.StringIO()
        with redirect_stdout(buf), \
             patch.object(reconcile_v2, "reconcile_project", side_effect=fake_reconcile_project):
            rc = reconcile_v2.main(["--project", "myproj", "--daemon-db", override_path])

        self.assertEqual(rc, 0)
        self.assertIn(
            "daemon_db_path",
            captured,
            "reconcile_project was not called with daemon_db_path kwarg",
        )
        self.assertEqual(
            str(captured["daemon_db_path"]),
            override_path,
            f"Expected daemon_db_path={override_path!r}, got {captured['daemon_db_path']!r}",
        )


# ---------------------------------------------------------------------------
# Finding #4 — explicit --daemon-db with wrong schema returns empty-list / no drift
# ---------------------------------------------------------------------------

class TestExplicitDaemonDbWithWrongSchema(_ReconcileV2Fixture):
    """Regression: passing an empty SQLite file (no event_log table) via
    --daemon-db must not produce fake drift — it must be treated as
    "DB unavailable" (empty-list / no projector)."""

    def test_empty_db_via_daemon_db_path_kwarg_returns_db_unavailable_error(
        self,
    ) -> None:
        """reconcile_project with an empty DB (no event_log table) must report
        the DB as unavailable, not fake drift."""
        empty_db = self.workspace / "no-schema.db"
        sqlite3.connect(str(empty_db)).close()  # empty file, no tables

        project_dir = _make_project_dir(self.workspace, "bad-db-proj")
        _make_phase_dir(project_dir, "build")

        result = reconcile_v2.reconcile_project(
            "bad-db-proj",
            daemon_db_path=str(empty_db),
        )

        # Must carry an error entry documenting the unavailability.
        self.assertTrue(
            len(result["errors"]) > 0,
            "Expected at least one error for missing event_log table, got none",
        )
        # Must NOT report projection-without-event based on a broken DB read.
        pwe = [
            d for d in result["drift"]
            if d["type"] == reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT
        ]
        self.assertEqual(
            pwe,
            [],
            "Empty/wrong-schema DB must not produce projection-without-event drift",
        )

    def test_reconcile_all_with_empty_db_returns_empty_list(self) -> None:
        """reconcile_all with a no-schema DB via daemon_db_path must return []."""
        empty_db = self.workspace / "no-schema-all.db"
        sqlite3.connect(str(empty_db)).close()

        result = reconcile_v2.reconcile_all(daemon_db_path=str(empty_db))
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Finding #5 — --json output includes header + results keys
# ---------------------------------------------------------------------------

class TestJsonOutputSchema(_ReconcileV2Fixture):
    """The --json output must match the staging plan §5 schema:
    {"header": {..., "event_log_head_seq": int, ...}, "results": [...]}."""

    def test_json_output_has_header_and_results_keys(self) -> None:
        """--all --json must produce top-level 'header' and 'results' keys."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = reconcile_v2.main(
                ["--all", "--json", "--daemon-db", str(self.db_path)]
            )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("header", payload, "Missing 'header' key in --json output")
        self.assertIn("results", payload, "Missing 'results' key in --json output")

    def test_json_header_contains_event_log_head_seq(self) -> None:
        """header.event_log_head_seq must be a non-negative integer."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            reconcile_v2.main(
                ["--all", "--json", "--daemon-db", str(self.db_path)]
            )
        payload = json.loads(buf.getvalue())
        head_seq = payload["header"]["event_log_head_seq"]
        self.assertIsInstance(head_seq, int)
        self.assertGreaterEqual(head_seq, 0)

    def test_single_project_json_output_has_header_and_results_keys(self) -> None:
        """--project X --json must also produce 'header' and 'results' keys."""
        _make_project_dir(self.workspace, "json-proj")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = reconcile_v2.main(
                ["--project", "json-proj", "--json", "--daemon-db", str(self.db_path)]
            )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("header", payload)
        self.assertIn("results", payload)
        self.assertIsInstance(payload["results"], list)
        self.assertEqual(len(payload["results"]), 1)

    def test_json_output_header_unreachable_when_no_db(self) -> None:
        """When DB is absent, header.projector_health must be 'unreachable'."""
        buf = io.StringIO()
        with redirect_stdout(buf), \
             patch.dict(os.environ, {"WG_DAEMON_DB": "/no/such/projections.db"}):
            reconcile_v2.main(["--all", "--json"])
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["header"]["projector_health"], "unreachable")


# ---------------------------------------------------------------------------
# Copilot Finding #1 — per-site flag awareness on _active_projection_names()
# ---------------------------------------------------------------------------

class TestActiveProjNamesAllFlagsOff(unittest.TestCase):
    """Finding #1 BLOCKER: with all flags OFF (default), _active_projection_names()
    returns an empty frozenset so no projection-without-event drift fires."""

    def test_all_flags_off_returns_empty_set(self) -> None:
        """With no WG_BUS_AS_TRUTH_* flags set, active projection names is empty."""
        env_clear = {k: "" for k in [
            "WG_BUS_AS_TRUTH_DISPATCH_LOG",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT",
            "WG_BUS_AS_TRUTH_GATE_RESULT",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST",
        ]}
        with patch.dict(os.environ, env_clear):
            result = reconcile_v2._active_projection_names()
        self.assertEqual(result, frozenset(),
                         f"Expected empty frozenset with all flags off, got {result!r}")

    def test_site3_flag_on_returns_reviewer_report_only(self) -> None:
        """With only REVIEWER_REPORT flag ON, active names is {'reviewer-report.md'}."""
        env = {
            "WG_BUS_AS_TRUTH_DISPATCH_LOG": "",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on",
            "WG_BUS_AS_TRUTH_GATE_RESULT": "",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "",
        }
        with patch.dict(os.environ, env):
            result = reconcile_v2._active_projection_names()
        self.assertEqual(result, frozenset({"reviewer-report.md"}))


class TestProjWithoutEventFlagGating(_ReconcileV2Fixture):
    """Finding #1: drift detection respects per-site flag state."""

    def test_dispatch_log_with_site1_flag_off_reports_no_drift(self) -> None:
        """Legacy dispatch-log.jsonl with Site 1 flag OFF must NOT fire drift."""
        project_dir = _make_project_dir(self.workspace, "legacy-dispatch")
        phase_dir = _make_phase_dir(project_dir, "build")
        _write_file(phase_dir / "dispatch-log.jsonl", '{"event": "test"}\n')
        # No event rows — simulating pre-Site-1 state with flag OFF.
        env = {"WG_BUS_AS_TRUTH_DISPATCH_LOG": ""}  # flag explicitly off
        conn = self._conn()
        with patch.dict(os.environ, env):
            result = reconcile_v2.reconcile_project("legacy-dispatch", _daemon_conn=conn)
        conn.close()

        pwe = [d for d in result["drift"]
               if d["type"] == reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT]
        self.assertEqual(
            pwe, [],
            "dispatch-log.jsonl should not fire projection-without-event when Site 1 flag is OFF",
        )

    def test_reviewer_report_with_site3_flag_on_and_matching_event_reports_no_drift(
        self,
    ) -> None:
        """Site 3 flag ON + reviewer-report.md + matching event → zero drift."""
        project_dir = _make_project_dir(self.workspace, "s3-flag-on-clean")
        phase_dir = _make_phase_dir(project_dir, "review")
        _write_file(phase_dir / "reviewer-report.md", "# approved\n")

        _insert_event_row(
            self.db_path,
            event_id=200,
            event_type="wicked.consensus.gate_completed",
            chain_id="s3-flag-on-clean.review.consensus.aabbccdd",
            projection_status="applied",
        )
        conn = self._conn()
        env = {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}
        with patch.dict(os.environ, env):
            result = reconcile_v2.reconcile_project("s3-flag-on-clean", _daemon_conn=conn)
        conn.close()

        self.assertEqual(result["drift"], [],
                         f"Expected no drift with Site 3 flag ON and matching event, got {result['drift']}")

    def test_reviewer_report_with_site3_flag_on_and_no_event_reports_drift(self) -> None:
        """Site 3 flag ON + reviewer-report.md but no matching event → drift fires."""
        project_dir = _make_project_dir(self.workspace, "s3-flag-on-orphan")
        phase_dir = _make_phase_dir(project_dir, "review")
        _write_file(phase_dir / "reviewer-report.md", "# orphan report\n")
        # No event rows.
        conn = self._conn()
        env = {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}
        with patch.dict(os.environ, env):
            result = reconcile_v2.reconcile_project("s3-flag-on-orphan", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(
            reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT,
            drift_types,
            "reviewer-report.md with no event and Site 3 flag ON must fire projection-without-event",
        )


# ---------------------------------------------------------------------------
# Copilot Finding #2 — reconcile_all() validates explicit --daemon-db schema
# ---------------------------------------------------------------------------

class TestReconcileAllValidatesExplicitDb(unittest.TestCase):
    """Finding #2 HIGH: reconcile_all() with --daemon-db pointing at a SQLite
    file that lacks event_log must return [] — parity with reconcile_project()."""

    def test_reconcile_all_with_empty_db_no_event_log_returns_empty_list(self) -> None:
        """reconcile_all with an empty SQLite (no tables) via daemon_db_path returns []."""
        with tempfile.TemporaryDirectory(prefix="wg-rv2-f2-") as tmp:
            empty_db = Path(tmp) / "empty.db"
            sqlite3.connect(str(empty_db)).close()  # create empty file, no tables

            result = reconcile_v2.reconcile_all(daemon_db_path=str(empty_db))
        self.assertEqual(result, [],
                         "reconcile_all with an empty/wrong-schema DB must return []")


# ---------------------------------------------------------------------------
# Copilot Finding #3 — header lag_events and projector_health with null cursor
# ---------------------------------------------------------------------------

class TestHeaderLagFieldsNullCursor(unittest.TestCase):
    """Finding #3 HIGH: lag_events must be None (not a misleading zero) when
    the projector cursor is unavailable, and projector_health must be 'unknown'."""

    def test_lag_events_is_null_when_db_reachable(self) -> None:
        """With DB reachable but cursor absent, lag_events must be null."""
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory(prefix="wg-rv2-f3-") as tmp:
            db_path = Path(tmp) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript(
                """
                CREATE TABLE event_log (
                    event_id INTEGER PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    chain_id TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    projection_status TEXT NOT NULL DEFAULT 'applied',
                    error_message TEXT,
                    ingested_at INTEGER NOT NULL
                );
                """
            )
            conn.commit()
            conn.close()

            buf = io.StringIO()
            with redirect_stdout(buf):
                reconcile_v2.main(["--all", "--json", "--daemon-db", str(db_path)])

        payload = json.loads(buf.getvalue())
        header = payload["header"]
        self.assertIsNone(
            header["lag_events"],
            f"lag_events should be null (cursor unavailable), got {header['lag_events']!r}",
        )

    def test_projector_health_is_unknown_when_db_reachable_but_cursor_absent(self) -> None:
        """projector_health must be 'unknown' when cursor is absent (not 'ok')."""
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory(prefix="wg-rv2-f3b-") as tmp:
            db_path = Path(tmp) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript(
                """
                CREATE TABLE event_log (
                    event_id INTEGER PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    chain_id TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    projection_status TEXT NOT NULL DEFAULT 'applied',
                    error_message TEXT,
                    ingested_at INTEGER NOT NULL
                );
                """
            )
            conn.commit()
            conn.close()

            buf = io.StringIO()
            with redirect_stdout(buf):
                reconcile_v2.main(["--all", "--json", "--daemon-db", str(db_path)])

        payload = json.loads(buf.getvalue())
        self.assertEqual(
            payload["header"]["projector_health"],
            "unknown",
            f"projector_health should be 'unknown' when cursor absent, "
            f"got {payload['header']['projector_health']!r}",
        )


# ---------------------------------------------------------------------------
# Copilot Finding #4 — projection-stale entries carry staging-plan schema fields
# ---------------------------------------------------------------------------

class TestProjectionStaleEntrySchema(_ReconcileV2Fixture):
    """Finding #4 MEDIUM: each projection-stale drift entry must carry
    projection_last_applied_seq and lag_events per the staging plan §5 schema.
    Both fields are null until the projector cursor is wired in."""

    def test_projection_stale_entry_has_cursor_fields(self) -> None:
        """projection-stale entry must contain projection_last_applied_seq + lag_events."""
        _make_project_dir(self.workspace, "stale-schema-proj")
        _insert_event_row(
            self.db_path,
            event_id=300,
            event_type="wicked.gate.decided",
            chain_id="stale-schema-proj.build.gate",
            projection_status="pending",
        )
        conn = self._conn()
        result = reconcile_v2.reconcile_project("stale-schema-proj", _daemon_conn=conn)
        conn.close()

        stale_entries = [d for d in result["drift"]
                         if d["type"] == reconcile_v2.DRIFT_PROJECTION_STALE]
        self.assertGreater(len(stale_entries), 0, "Expected at least one projection-stale entry")

        for entry in stale_entries:
            self.assertIn(
                "projection_last_applied_seq",
                entry,
                "projection-stale entry missing 'projection_last_applied_seq' key",
            )
            self.assertIn(
                "lag_events",
                entry,
                "projection-stale entry missing 'lag_events' key",
            )
            # Values must be null until projector cursor is wired in.
            self.assertIsNone(
                entry["projection_last_applied_seq"],
                f"projection_last_applied_seq should be null (cursor unavailable), "
                f"got {entry['projection_last_applied_seq']!r}",
            )
            self.assertIsNone(
                entry["lag_events"],
                f"lag_events should be null (cursor unavailable), "
                f"got {entry['lag_events']!r}",
            )


# ---------------------------------------------------------------------------
# Finding #1 (PR #764 final fold) — Site 2 dual-flag independence
# Verifies that CONSENSUS_REPORT and CONSENSUS_EVIDENCE are gated by
# independent flags via the new per-file Shape A mapping.
# ---------------------------------------------------------------------------

class TestSite2DualFlagIndependence(unittest.TestCase):
    """Finding #1 HIGH: Site 2 ships with two independent flags.

    WG_BUS_AS_TRUTH_CONSENSUS_REPORT controls consensus-report.json.
    WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE controls consensus-evidence.json.
    Neither implies the other.
    """

    def _projection_names_with_env(self, env: dict) -> frozenset:
        with patch.dict(os.environ, {k: "" for k in [
            "WG_BUS_AS_TRUTH_DISPATCH_LOG",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT",
            "WG_BUS_AS_TRUTH_GATE_RESULT",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST",
        ]}, clear=False):
            with patch.dict(os.environ, env):
                return reconcile_v2._active_projection_names()

    def test_consensus_report_flag_alone_includes_only_consensus_report(self) -> None:
        """With only CONSENSUS_REPORT=on, scan set includes consensus-report.json
        but NOT consensus-evidence.json."""
        result = self._projection_names_with_env(
            {"WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on"}
        )
        self.assertIn("consensus-report.json", result)
        self.assertNotIn(
            "consensus-evidence.json", result,
            "consensus-evidence.json must NOT be included when only "
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT is on",
        )

    def test_consensus_evidence_flag_alone_includes_only_consensus_evidence(self) -> None:
        """With only CONSENSUS_EVIDENCE=on, scan set includes consensus-evidence.json
        but NOT consensus-report.json."""
        result = self._projection_names_with_env(
            {"WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on"}
        )
        self.assertIn("consensus-evidence.json", result)
        self.assertNotIn(
            "consensus-report.json", result,
            "consensus-report.json must NOT be included when only "
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE is on",
        )

    def test_both_flags_on_includes_both_files(self) -> None:
        """With both Site 2 flags on, scan set includes both consensus files."""
        result = self._projection_names_with_env({
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "on",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "on",
        })
        self.assertIn("consensus-report.json", result)
        self.assertIn("consensus-evidence.json", result)

    def test_both_flags_off_excludes_both_files(self) -> None:
        """With both Site 2 flags off, scan set excludes both consensus files."""
        result = self._projection_names_with_env({
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "",
        })
        self.assertNotIn("consensus-report.json", result)
        self.assertNotIn("consensus-evidence.json", result)

    def test_projection_file_flags_has_consensus_evidence_key(self) -> None:
        """PROJECTION_FILE_FLAGS must map consensus-evidence.json to its own token."""
        self.assertIn(
            "consensus-evidence.json",
            reconcile_v2.PROJECTION_FILE_FLAGS,
            "PROJECTION_FILE_FLAGS must have a consensus-evidence.json key",
        )
        self.assertEqual(
            reconcile_v2.PROJECTION_FILE_FLAGS["consensus-evidence.json"],
            "CONSENSUS_EVIDENCE",
        )

    def test_projection_file_flags_has_consensus_report_key(self) -> None:
        """PROJECTION_FILE_FLAGS must map consensus-report.json to its own token."""
        self.assertIn(
            "consensus-report.json",
            reconcile_v2.PROJECTION_FILE_FLAGS,
        )
        self.assertEqual(
            reconcile_v2.PROJECTION_FILE_FLAGS["consensus-report.json"],
            "CONSENSUS_REPORT",
        )


if __name__ == "__main__":
    unittest.main()
