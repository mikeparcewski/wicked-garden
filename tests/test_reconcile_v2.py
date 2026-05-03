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
        """An event with projection_status=pending and absent on-disk file → drift.

        Site 4 prep (#778) flipped wicked.gate.decided/blocked to True in the
        production registry, so no handler-gate patching is required to
        exercise the drift detection logic for gate-result.json events.
        Handler-gate behaviour is still tested in
        TestHandlerGateInDetectorFunctions.
        """
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
        """When the file exists, a pending event is not projection-stale.

        Site 4 prep (#778) flipped the gate.* registry entries True natively;
        no handler-gate patching is needed.
        """
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
        """Applied event but no on-disk projection → event-without-projection drift.

        Site 4 prep (#778) flipped the gate.* registry entries True natively.
        """
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

        Site 4 prep (#778) flipped wicked.gate.decided/blocked to True in the
        production registry, so no handler-gate patching is required.
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
        """gate_pending event but no reviewer-report.md → event-without-projection drift.

        Note (#769 fold): the handler-presence gate now filters per event type.
        This test patches gate_pending as True (handler present) so the detector
        runs and reports the missing projection.  Without patching, gate_pending
        handler is False and the detector correctly skips it — that
        negative case is covered in TestHandlerGateInDetectorFunctions.

        PR #781 flipped the gate_completed/pending registry entries True
        natively, so no patching is required to exercise this path.
        """
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

class TestConditionsManifestPostSite5(_ReconcileV2Fixture):
    """Site 5 cutover (#746): conditions-manifest.json IS now a tracked
    projection.  An on-disk manifest with no producing event in event_log
    must fire ``projection-without-event`` drift (the TODO from the
    original ``TestConditionsManifestExcludedPreSite5`` class is now done).
    """

    def test_conditions_manifest_without_event_reports_drift(self) -> None:
        """Post-Site-5: conditions-manifest.json on disk with NO producing
        event in event_log → projection-without-event drift fires.

        The expected producers post-Site-5 are:
        - ``wicked.gate.decided`` with verdict CONDITIONAL + non-empty
          conditions list (initial creation), OR
        - ``wicked.condition.marked_cleared`` (subsequent verification flips).

        With neither in event_log, the file is an orphan.
        """
        project_dir = _make_project_dir(self.workspace, "cond-orphan-proj")
        phase_dir = _make_phase_dir(project_dir, "design")
        _write_file(
            phase_dir / "conditions-manifest.json",
            '{"conditions": []}',
        )
        # No event rows inserted — orphan file scenario.
        conn = self._conn()
        result = reconcile_v2.reconcile_project("cond-orphan-proj", _daemon_conn=conn)
        conn.close()

        pwe = [
            d for d in result["drift"]
            if d["type"] == reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT
        ]
        self.assertTrue(
            any(
                d["projection"] == "phases/design/conditions-manifest.json"
                for d in pwe
            ),
            "conditions-manifest.json with no producing event must fire "
            f"projection-without-event drift. Got: {pwe}",
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
    """Finding #1 BLOCKER: with all flags explicitly OFF, _active_projection_names()
    returns an empty frozenset so no projection-without-event drift fires.

    After the flag-fold (PR #777), unset / empty env vars for shipped sites
    (DISPATCH_LOG, CONSENSUS_REPORT, CONSENSUS_EVIDENCE, REVIEWER_REPORT) now
    default ON.  Tests use explicit ``"off"`` to exercise the opt-out path."""

    def test_all_flags_off_returns_empty_set(self) -> None:
        """With all WG_BUS_AS_TRUTH_* flags explicitly ``"off"``, active names is empty."""
        env_clear = {
            "WG_BUS_AS_TRUTH_DISPATCH_LOG":        "off",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT":    "off",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE":  "off",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT":     "off",
            "WG_BUS_AS_TRUTH_GATE_RESULT":         "off",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "off",
        }
        with patch.dict(os.environ, env_clear):
            result = reconcile_v2._active_projection_names()
        self.assertEqual(result, frozenset(),
                         f"Expected empty frozenset with all flags off, got {result!r}")

    def test_site3_flag_on_returns_reviewer_report_only(self) -> None:
        """With only REVIEWER_REPORT flag ON, active names is {'reviewer-report.md'}.

        Note (#769 fold): the handler-presence gate uses per-event-type keys.
        This test patches _PROJECTION_HANDLERS_AVAILABLE to mark both
        gate_completed and gate_pending as True (simulating Site 3 handler
        present) so the flag-gate behaviour is testable in isolation.  The
        handler-gate behaviour is covered separately in TestHandlerPresenceGate.
        """
        env = {
            "WG_BUS_AS_TRUTH_DISPATCH_LOG":        "off",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT":    "off",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE":  "off",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT":     "on",
            "WG_BUS_AS_TRUTH_GATE_RESULT":         "off",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST": "off",
        }
        # PR #781 flipped the Site 3 registry entries True natively;
        # no handler-presence patching required.
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
        # No event rows — simulating pre-Site-1 state with flag explicitly OFF.
        # Uses "off" (not empty string) after the flag-fold (PR #777) which made
        # unset → default-ON for shipped sites like DISPATCH_LOG.
        env = {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "off"}
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
        """Site 3 flag ON + reviewer-report.md but no matching event → drift fires.

        PR #781 flipped the Site 3 registry entries True natively, so the
        handler-presence gate no longer vetoes the file.  The
        handler-absent → file-excluded behaviour stays covered in
        TestHandlerPresenceGate.test_active_projection_names_excludes_files_with_no_handler.
        """
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
    the projector cursor is unavailable, and projector_health must be
    'unreachable' (schema-conformant enum value — 'unknown' is not in the
    documented v2 schema of {ok, lagging, unreachable})."""

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

    def test_projector_health_is_unreachable_when_db_reachable_but_cursor_absent(self) -> None:
        """projector_health must be 'unreachable' when cursor is absent.

        Schema enum is {ok, lagging, unreachable}; 'unknown' is not valid.
        Cursor-absent collapses with DB-unavailable — consumer cannot act on
        the cursor either way.
        """
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
            "unreachable",
            f"projector_health should be 'unreachable' when cursor absent "
            f"(schema enum: {{ok, lagging, unreachable}}), "
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
        """projection-stale entry must contain projection_last_applied_seq + lag_events.

        Site 4 prep (#778) flipped the gate.* registry entries True natively.
        """
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
        # Baseline: all flags OFF via explicit "off" so shipped tokens don't
        # bleed through the default-ON map (PR #777 flag-fold).
        baseline = {k: "off" for k in [
            "WG_BUS_AS_TRUTH_DISPATCH_LOG",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT",
            "WG_BUS_AS_TRUTH_GATE_RESULT",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST",
        ]}
        with patch.dict(os.environ, baseline, clear=False):
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
        """With both Site 2 flags explicitly ``"off"``, scan set excludes both files."""
        result = self._projection_names_with_env({
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT": "off",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE": "off",
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


# ---------------------------------------------------------------------------
# Issue #769 — handler-presence gate on _active_projection_names()
# (registry is now per-EVENT-TYPE, not per-filename — fold fix Finding #2)
# ---------------------------------------------------------------------------

class TestHandlerPresenceGate(unittest.TestCase):
    """Tests for the #769 handler-presence gate added to _active_projection_names().

    A file must be included in the active scan set iff BOTH:
      (a) its WG_BUS_AS_TRUTH_<TOKEN> flag is "on"   (flag gate)
      (b) _handler_available_for_file(name) is True  (handler gate)

    _handler_available_for_file resolves per-event-type keys from
    _PROJECTION_HANDLERS_AVAILABLE.  The registry is now keyed by
    EVENT TYPE, not filename (fold fix Finding #2 — per-file boolean
    cannot model multi-event-type files like reviewer-report.md).
    """

    def _active_with_registry(
        self,
        env: dict,
        registry: dict,
    ) -> frozenset:
        """Invoke _active_projection_names() with controlled env and registry.

        Baseline: all flags set to ``"off"`` so shipped tokens don't bleed
        through the default-ON map (PR #777 flag-fold).  Each test's ``env``
        dict then overrides specific flags to ``"on"`` or ``"off"`` as needed.
        """
        baseline = {k: "off" for k in [
            "WG_BUS_AS_TRUTH_DISPATCH_LOG",
            "WG_BUS_AS_TRUTH_CONSENSUS_REPORT",
            "WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE",
            "WG_BUS_AS_TRUTH_REVIEWER_REPORT",
            "WG_BUS_AS_TRUTH_GATE_RESULT",
            "WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST",
        ]}
        with patch.dict(os.environ, baseline, clear=False):
            with patch.dict(os.environ, env):
                with patch.object(
                    reconcile_v2,
                    "_PROJECTION_HANDLERS_AVAILABLE",
                    registry,
                ):
                    return reconcile_v2._active_projection_names()

    def _make_event_type_registry(self, overrides: dict) -> dict:
        """Build a per-event-type registry starting from defaults, applying overrides."""
        base = dict(reconcile_v2._PROJECTION_HANDLERS_AVAILABLE)
        base.update(overrides)
        return base

    def test_active_projection_names_excludes_files_with_no_handler(self) -> None:
        """Flag ON but handler False for all event types → file excluded from scan set.

        Scenario: WG_BUS_AS_TRUTH_REVIEWER_REPORT=on but reviewer-report.md
        handler has not yet landed in daemon/projector.py (pending #768).
        The drift detector must NOT scan for reviewer-report.md because the
        projector can never materialise it — scanning would produce false
        event-without-projection drift.

        Registry is per-event-type: both gate_completed and gate_pending must
        be False for reviewer-report.md to be excluded.
        """
        registry = self._make_event_type_registry({
            "wicked.consensus.gate_completed": False,   # handler absent — pending #768
            "wicked.consensus.gate_pending":   False,   # handler absent — pending #768
        })
        result = self._active_with_registry(
            {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"},
            registry,
        )
        self.assertNotIn(
            "reviewer-report.md",
            result,
            "reviewer-report.md must be excluded when all its event handlers are absent, "
            "even if flag is ON",
        )

    def test_active_projection_names_includes_files_with_handler_and_flag(self) -> None:
        """Both flag ON and all event-type handlers True → file included in scan set.

        Scenario: dispatch-log.jsonl with flag on and handler available.
        dispatch-log.jsonl maps to a single event type (log_entry_appended).
        """
        registry = self._make_event_type_registry({
            "wicked.dispatch.log_entry_appended": True,    # handler present
        })
        result = self._active_with_registry(
            {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
            registry,
        )
        self.assertIn(
            "dispatch-log.jsonl",
            result,
            "dispatch-log.jsonl must be included when both flag is ON and handler is True",
        )

    def test_active_projection_names_excludes_when_handler_present_but_flag_off(self) -> None:
        """Handler True but flag explicitly OFF → file excluded from scan set.

        The flag gate (pre-existing) must still apply even when the handler
        is available: both conditions are required.

        Uses explicit ``"off"`` after the flag-fold (PR #777) which made unset /
        empty string → default-ON for shipped sites like DISPATCH_LOG.
        """
        registry = self._make_event_type_registry({
            "wicked.dispatch.log_entry_appended": True,    # handler present
        })
        result = self._active_with_registry(
            {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "off"},   # explicit opt-out
            registry,
        )
        self.assertNotIn(
            "dispatch-log.jsonl",
            result,
            "dispatch-log.jsonl must be excluded when flag is OFF, even if handler is True",
        )

    def test_active_projection_names_excludes_when_flag_on_but_handler_missing(self) -> None:
        """Flag ON but handler False → file excluded (the core #769 invariant).

        This is the canonical test for the new behaviour: a flag enabled for
        a site whose handler has not yet landed must NOT expand the scan set.
        Registry uses event-type keys (fold fix Finding #2).
        """
        registry = self._make_event_type_registry({
            "wicked.dispatch.log_entry_appended":  True,   # handler present
            "wicked.consensus.report_created":     True,   # handler present
            "wicked.consensus.evidence_recorded":  True,   # handler present
            "wicked.consensus.gate_completed":     False,  # handler absent
            "wicked.consensus.gate_pending":       False,  # handler absent
            "wicked.gate.decided":                 False,  # handler absent
            "wicked.gate.blocked":                 False,  # handler absent
        })
        # Enable flags for both an absent-handler file and present-handler files.
        result = self._active_with_registry(
            {
                "WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on",    # flag on, handlers False
                "WG_BUS_AS_TRUTH_GATE_RESULT":     "on",    # flag on, handlers False
                "WG_BUS_AS_TRUTH_DISPATCH_LOG":    "on",    # flag on, handler True
            },
            registry,
        )
        # Handler-absent files must be excluded despite flag-on.
        self.assertNotIn(
            "reviewer-report.md",
            result,
            "reviewer-report.md must be excluded: flag ON but all event handlers absent",
        )
        self.assertNotIn(
            "gate-result.json",
            result,
            "gate-result.json must be excluded: flag ON but all event handlers absent",
        )
        # Handler-present file must still be included.
        self.assertIn(
            "dispatch-log.jsonl",
            result,
            "dispatch-log.jsonl must be included: flag ON and handler present",
        )


# ---------------------------------------------------------------------------
# Issue #769 fold — Finding #3: end-to-end regression tests for detector
# functions consulting handler registry per-event
# ---------------------------------------------------------------------------

class TestHandlerGateInDetectorFunctions(_ReconcileV2Fixture):
    """Finding #3 regression: reconcile_project() end-to-end with handler absent.

    The handler-presence gate must be applied inside the detector functions
    (_detect_projection_stale and _detect_event_without_projection), not just
    in _active_projection_names().  Without this, an event type with handler
    absent but flag enabled would still produce false drift.

    Negative test (handler absent → NO drift):
      - Project dir exists, no reviewer-report.md.
      - gate_completed event in event_log with status=applied.
      - WG_BUS_AS_TRUTH_REVIEWER_REPORT=on.
      - Handler marked ABSENT (gate_completed=False).
      - Expected: no event-without-projection drift.

    Positive test (handler present → drift IS reported):
      - Same setup but handler marked PRESENT (gate_completed=True).
      - Expected: event-without-projection drift IS reported because the
        projector should have materialised the file but didn't.
    """

    def test_detector_no_drift_when_handler_absent_even_with_flag_on(self) -> None:
        """Handler absent → event-without-projection NOT reported even with flag on.

        Scenario mirrors the false-positive class described in PR #774 Finding #1:
        WG_BUS_AS_TRUTH_REVIEWER_REPORT=on AND gate_completed event in DB AND
        no reviewer-report.md on disk AND handler absent → should produce ZERO drift.
        """
        _make_project_dir(self.workspace, "handler-absent-proj")
        _insert_event_row(
            self.db_path,
            event_id=400,
            event_type="wicked.consensus.gate_completed",
            chain_id="handler-absent-proj.review.consensus.aabbccdd",
            projection_status="applied",
        )
        conn = self._conn()
        # Registry with gate_completed handler explicitly absent.
        registry = dict(reconcile_v2._PROJECTION_HANDLERS_AVAILABLE)
        registry["wicked.consensus.gate_completed"] = False
        registry["wicked.consensus.gate_pending"] = False
        env = {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}
        with patch.dict(os.environ, env):
            with patch.object(reconcile_v2, "_PROJECTION_HANDLERS_AVAILABLE", registry):
                result = reconcile_v2.reconcile_project("handler-absent-proj", _daemon_conn=conn)
        conn.close()

        ewp = [d for d in result["drift"]
               if d["type"] == reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION]
        self.assertEqual(
            ewp,
            [],
            "event-without-projection must NOT be reported when handler is absent; "
            f"got: {ewp}",
        )

    def test_detector_reports_drift_when_handler_present_and_file_absent(self) -> None:
        """Handler present → event-without-projection IS reported when file missing.

        Scenario: WG_BUS_AS_TRUTH_REVIEWER_REPORT=on AND gate_completed event in DB
        AND no reviewer-report.md AND handler PRESENT → drift must be reported because
        the projector should have materialised the file.
        """
        _make_project_dir(self.workspace, "handler-present-proj")
        _insert_event_row(
            self.db_path,
            event_id=401,
            event_type="wicked.consensus.gate_completed",
            chain_id="handler-present-proj.review.consensus.aabbccdd",
            projection_status="applied",
        )
        conn = self._conn()
        # PR #781 flipped both handler-presence entries True natively.
        env = {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}
        with patch.dict(os.environ, env):
            result = reconcile_v2.reconcile_project("handler-present-proj", _daemon_conn=conn)
        conn.close()

        drift_types = [d["type"] for d in result["drift"]]
        self.assertIn(
            reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION,
            drift_types,
            "event-without-projection MUST be reported when handler is present "
            "but projection file is absent",
        )

    def test_detector_no_stale_drift_when_handler_absent(self) -> None:
        """Handler absent → projection-stale NOT reported even with pending event.

        Scenario: gate_completed event with status=pending AND handler absent →
        no projection-stale drift (the projector could never have processed it).
        """
        _make_project_dir(self.workspace, "stale-handler-absent-proj")
        _insert_event_row(
            self.db_path,
            event_id=402,
            event_type="wicked.consensus.gate_completed",
            chain_id="stale-handler-absent-proj.review.consensus.aabbccdd",
            projection_status="pending",
        )
        conn = self._conn()
        registry = dict(reconcile_v2._PROJECTION_HANDLERS_AVAILABLE)
        registry["wicked.consensus.gate_completed"] = False
        registry["wicked.consensus.gate_pending"] = False
        env = {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}
        with patch.dict(os.environ, env):
            with patch.object(reconcile_v2, "_PROJECTION_HANDLERS_AVAILABLE", registry):
                result = reconcile_v2.reconcile_project(
                    "stale-handler-absent-proj", _daemon_conn=conn
                )
        conn.close()

        stale = [d for d in result["drift"]
                 if d["type"] == reconcile_v2.DRIFT_PROJECTION_STALE]
        self.assertEqual(
            stale,
            [],
            "projection-stale must NOT be reported when handler is absent; "
            f"got: {stale}",
        )


# ---------------------------------------------------------------------------
# TestReconcileV2FlagPredicate — proves reconcile_v2 sees the PR #777 flag-fold
# ---------------------------------------------------------------------------

class TestReconcileV2FlagPredicate(unittest.TestCase):
    """Verify reconcile_v2._flag_on() delegates to _bus_as_truth_enabled().

    Finding #2 fix (PR #777): prior _flag_on() did its own
    ``os.environ.get(...) == "on"`` check, bypassing the canonical predicate
    in ``scripts/_bus.py``.  These tests prove the delegation is live.
    """

    def test_dispatch_log_default_on_when_unset(self) -> None:
        """With no env var, DISPATCH_LOG (shipped) is ON via default map."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)
            self.assertTrue(reconcile_v2._flag_on("DISPATCH_LOG"))

    def test_dispatch_log_off_when_explicit_off(self) -> None:
        """Explicit ``"off"`` opts out for a shipped site."""
        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "off"}):
            self.assertFalse(reconcile_v2._flag_on("DISPATCH_LOG"))

    def test_unknown_token_default_off_when_unset(self) -> None:
        """Tokens NOT in ``_BUS_AS_TRUTH_DEFAULT_ON`` default OFF when unset.

        After Site 5 (this PR), all five planned cutover tokens
        (DISPATCH_LOG, CONSENSUS_REPORT, CONSENSUS_EVIDENCE,
        REVIEWER_REPORT, GATE_RESULT, CONDITIONS_MANIFEST) are in the
        default-ON set — there are no unshipped tokens left.  This test
        guards the safety property: any FUTURE token (e.g. a hypothetical
        Site 6 placeholder, or a token used in tests) defaults OFF when
        unset, so an env-var typo never silently flips bus-as-truth on
        for something we didn't intend to ship.
        """
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WG_BUS_AS_TRUTH_NEVER_SHIPPED_TOKEN", None)
            self.assertFalse(reconcile_v2._flag_on("NEVER_SHIPPED_TOKEN"))

    def test_active_projection_names_includes_dispatch_log_by_default(self) -> None:
        """Without any env var, DISPATCH_LOG is default-ON → dispatch-log.jsonl
        is in _active_projection_names() (handler also present).

        Proves reconcile_v2 sees the default-ON flip from _bus_as_truth_enabled().
        This is the core Finding #2 regression test.
        """
        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var so we get pure default-map behavior.
            os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)
            result = reconcile_v2._active_projection_names()
        self.assertIn(
            "dispatch-log.jsonl",
            result,
            "dispatch-log.jsonl must be in active_projection_names() when "
            "DISPATCH_LOG is in _BUS_AS_TRUTH_DEFAULT_ON and no env override. "
            "If this fails, reconcile_v2._flag_on() is not delegating to "
            "_bus_as_truth_enabled() (Finding #2 regression).",
        )


if __name__ == "__main__":
    unittest.main()
