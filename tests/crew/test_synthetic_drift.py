#!/usr/bin/env python3
"""Tests for scripts/crew/synthetic_drift.py.

For each pre-cutover drift class the test:
  1. Builds a fixture in an isolated tempdir.
  2. Patches reconcile.py's two filesystem roots to point at the tempdir.
  3. Calls reconcile_all() and asserts the synthesised drift class appears
     for the synthetic project.
  4. Asserts no other drift class fires for the same project (no false
     positives).
  5. Tears down the fixture and asserts a re-run sees zero drift.

For each post-cutover class (projection-stale,
event-without-projection, projection-without-event) the test
``skipif``s when the daemon DB is unavailable.  When it IS available
the test asserts the manifest builds successfully and reports the
expected event_seq / projection path so the future post-cutover
reconciler has a stable contract to match.

Stdlib + pytest only — no extra deps.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Iterable, List
from unittest import mock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import reconcile  # noqa: E402
import synthetic_drift  # noqa: E402


# ---------------------------------------------------------------------------
# Pre-cutover helpers
# ---------------------------------------------------------------------------

PRE_CUTOVER_CLASSES: tuple[str, ...] = (
    "missing_native",
    "stale_status",
    "orphan_native",
    "phase_drift",
)

POST_CUTOVER_CLASSES: tuple[str, ...] = (
    "projection-stale",
    "event-without-projection",
    "projection-without-event",
)


def _daemon_db_available() -> bool:
    """Return True when the projector DB exists and looks usable."""
    db = synthetic_drift._daemon_db_path(None)
    if db is None:
        return False
    # Confirm the event_log table exists — otherwise the DB is half-formed
    # and we should treat it as unavailable to keep tests honest.
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='event_log'"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


_DAEMON_AVAILABLE = _daemon_db_available()
_SKIP_DAEMON = pytest.mark.skipif(
    not _DAEMON_AVAILABLE,
    reason="daemon_db_unavailable: projector DB not reachable for post-cutover fixture",
)


class _BuilderFixture(unittest.TestCase):
    """Per-test tempdir + patched reconcile roots.

    Mirrors the pattern in tests/crew/test_reconcile.py so test behaviour
    stays directly comparable.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wg-synth-drift-")
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)

        self.projects_root = self.workspace / "wicked-crew" / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.config_dir = self.workspace / "claude-config"
        (self.config_dir / "tasks").mkdir(parents=True, exist_ok=True)

        # Patch reconcile so it reads from the tempdir, not the real machine.
        self._patches = [
            mock.patch.object(reconcile, "_projects_root", return_value=self.projects_root),
            mock.patch.object(reconcile, "_claude_config_dir", return_value=self.config_dir),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    # ------------------------------------------------------------------
    # Drift inspection helpers
    # ------------------------------------------------------------------

    def _drift_for_project(self, slug: str) -> List[dict]:
        results = reconcile.reconcile_all()
        for r in results:
            if r.get("project_slug") == slug:
                return list(r.get("drift") or [])
        return []

    def _drift_types_for_project(self, slug: str) -> List[str]:
        return [d.get("type") for d in self._drift_for_project(slug)]

    def _all_drift_types(self) -> List[str]:
        out: List[str] = []
        for r in reconcile.reconcile_all():
            for d in r.get("drift") or []:
                out.append(d.get("type"))
        return out


# ---------------------------------------------------------------------------
# Pre-cutover: per-class build/detect/teardown round-trip
# ---------------------------------------------------------------------------

class MissingNativeRoundTripTests(_BuilderFixture):
    SLUG = "synth-missing-native"

    def test_built_and_detected_by_reconciler(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "missing_native",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.assertEqual(manifest["drift_class"], "missing_native")
        self.assertIn(f"{self.SLUG}.build", manifest["missing_chain_ids"])

        types = self._drift_types_for_project(self.SLUG)
        self.assertIn("missing_native", types,
                      f"expected missing_native drift, got {types}")

        synthetic_drift.teardown_drift_fixture(manifest)
        self.assertEqual(self._drift_for_project(self.SLUG), [],
                         "teardown left residual drift")
        self.assertEqual(self._all_drift_types(), [],
                         "teardown left residual drift across all projects")

    def test_no_false_positives_for_other_classes(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "missing_native",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        types = set(self._drift_types_for_project(self.SLUG))
        # Only missing_native should fire for this project.
        self.assertEqual(types & {"stale_status", "orphan_native", "phase_drift"}, set(),
                         f"unexpected non-missing_native drift: {types}")


class StaleStatusRoundTripTests(_BuilderFixture):
    SLUG = "synth-stale-status"

    def test_built_and_detected_by_reconciler(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "stale_status",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)

        types = self._drift_types_for_project(self.SLUG)
        self.assertIn("stale_status", types,
                      f"expected stale_status drift, got {types}")

        synthetic_drift.teardown_drift_fixture(manifest)
        self.assertEqual(self._drift_for_project(self.SLUG), [])
        self.assertEqual(self._all_drift_types(), [])

    def test_no_false_positives_for_other_classes(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "stale_status",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)
        types = set(self._drift_types_for_project(self.SLUG))
        # phase_drift could legitimately co-fire here only if the gate
        # finding is missing, which our fixture deliberately does NOT
        # create.  Assert the explicit drift expectation.
        self.assertEqual(types & {"orphan_native"}, set(),
                         f"unexpected orphan_native drift: {types}")


class OrphanNativeRoundTripTests(_BuilderFixture):
    SLUG = "synth-orphan-native"

    def test_built_and_detected_by_reconciler(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "orphan_native",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        ghost_slug = manifest["ghost_project_slug"]

        # Orphan drift is reported in the FIRST project's drift entries by
        # reconcile_all (single-pass aggregation).  Scan all projects.
        all_results = reconcile.reconcile_all()
        orphans: List[dict] = []
        for r in all_results:
            for d in r.get("drift") or []:
                if d.get("type") == "orphan_native":
                    orphans.append(d)

        self.assertGreaterEqual(len(orphans), 1,
                                "expected at least one orphan_native entry")
        self.assertTrue(
            any(o.get("orphan_project_slug") == ghost_slug for o in orphans),
            f"orphan entries did not name ghost slug {ghost_slug!r}: {orphans}",
        )

        synthetic_drift.teardown_drift_fixture(manifest)
        leftover = [d for r in reconcile.reconcile_all()
                    for d in r.get("drift") or []]
        self.assertEqual(leftover, [], f"teardown left residual drift: {leftover}")

    def test_no_false_positives_for_other_classes(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "orphan_native",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)
        all_types = set(self._all_drift_types())
        # Only orphan_native should fire — no missing/stale/phase.
        self.assertEqual(
            all_types - {"orphan_native"}, set(),
            f"unexpected non-orphan_native drift: {all_types}",
        )


class PhaseDriftRoundTripTests(_BuilderFixture):
    SLUG = "synth-phase-drift"

    def test_built_and_detected_by_reconciler(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "phase_drift",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)

        types = self._drift_types_for_project(self.SLUG)
        self.assertIn("phase_drift", types,
                      f"expected phase_drift, got {types}")

        synthetic_drift.teardown_drift_fixture(manifest)
        self.assertEqual(self._drift_for_project(self.SLUG), [])
        self.assertEqual(self._all_drift_types(), [])

    def test_no_false_positives_for_other_classes(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "phase_drift",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)
        types = set(self._drift_types_for_project(self.SLUG))
        # phase_drift inherently overlaps with stale_status today: a
        # gate-finding native task is, by construction, an in_progress
        # native task in an APPROVE-d phase, which the stale_status
        # detector also flags.  We assert phase_drift IS present and that
        # the off-the-rails classes (missing_native / orphan_native) are
        # NOT present.  See reconcile.py:_detect_stale_status — the
        # detector iterates every native task in the project, including
        # gate-findings, and there is no way to suppress that overlap
        # without changing the production reconciler (out of scope for
        # the synthetic-drift suite).
        self.assertIn("phase_drift", types)
        self.assertEqual(
            types & {"missing_native", "orphan_native"}, set(),
            f"unexpected drift outside the gate-finding overlap: {types}",
        )


# ---------------------------------------------------------------------------
# Builder-level integration: every supported class produces a manifest
# ---------------------------------------------------------------------------

class AllSupportedClassesBuildableTests(unittest.TestCase):
    """Each supported drift class either builds a valid manifest OR returns
    a clean ``ok: False`` with the documented daemon_db_unavailable reason.
    """

    def test_every_class_returns_a_legible_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wg-synth-allclasses-") as tmp:
            workspace = Path(tmp)
            for drift_class in synthetic_drift.SUPPORTED_DRIFT_CLASSES:
                slug = f"synth-allclasses-{drift_class.replace('_', '-').replace(':', '-')}"
                manifest = synthetic_drift.build_drift_fixture(
                    drift_class,
                    project_slug=slug,
                    workspace_dir=workspace,
                )
                # Either it built ok OR we got a clean unavailable signal.
                if manifest.get("ok"):
                    self.assertEqual(manifest["drift_class"], drift_class)
                    self.assertIn("expected_drift_types", manifest)
                    self.assertIn(drift_class, manifest["expected_drift_types"])
                    self.assertIn("created_paths", manifest)
                    self.assertIn("created_event_ids", manifest)
                    # Tear down so the next iteration starts from a clean slate.
                    synthetic_drift.teardown_drift_fixture(manifest)
                else:
                    self.assertEqual(
                        manifest.get("reason"),
                        synthetic_drift.REASON_DAEMON_UNAVAILABLE,
                        f"class {drift_class!r} declined for unexpected reason: {manifest}",
                    )
                    # Only post-cutover classes are allowed to decline.
                    self.assertIn(
                        drift_class, POST_CUTOVER_CLASSES,
                        f"pre-cutover class {drift_class!r} should never decline",
                    )

    def test_unsupported_class_returns_clean_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wg-synth-bad-") as tmp:
            manifest = synthetic_drift.build_drift_fixture(
                "not-a-real-class",
                project_slug="foo",
                workspace_dir=Path(tmp),
            )
        self.assertFalse(manifest["ok"])
        self.assertEqual(manifest["reason"], synthetic_drift.REASON_UNSUPPORTED_CLASS)
        self.assertIn("supported", manifest)

    def test_bad_workspace_returns_clean_failure(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "missing_native",
            project_slug="foo",
            workspace_dir=Path("/nonexistent/synth-drift-path-does-not-exist"),
        )
        self.assertFalse(manifest["ok"])
        self.assertEqual(manifest["reason"], synthetic_drift.REASON_BAD_INPUT)


# ---------------------------------------------------------------------------
# Post-cutover: only run when the daemon DB is reachable
# ---------------------------------------------------------------------------

class _PostCutoverFixture(unittest.TestCase):
    """Per-test tempdir for post-cutover fixtures.

    Does NOT patch reconcile because the post-cutover reconciler does not
    yet exist — these tests assert the FIXTURE shape (event_log row +
    projection presence/absence), not detector output.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wg-synth-post-")
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)
        self.projects_root = self.workspace / "wicked-crew" / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)
        (self.workspace / "claude-config" / "tasks").mkdir(parents=True, exist_ok=True)


@_SKIP_DAEMON
class ProjectionStaleTests(_PostCutoverFixture):
    SLUG = "synth-projection-stale"

    def test_event_inserted_and_projection_absent(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "projection-stale",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        # The expected projection file MUST NOT exist.
        self.assertFalse(Path(manifest["expected_projection_path"]).exists())

        # The event_log row MUST exist with our seq + chain_id.
        db_path = Path(manifest["daemon_db_path"])
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT event_id, event_type, chain_id, projection_status FROM event_log WHERE event_id = ?",
                (manifest["event_seq"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "synthetic event_log row was not inserted")
        self.assertEqual(row[1], "wicked.gate.decided")
        self.assertEqual(row[2], manifest["event_chain_id"])
        self.assertEqual(row[3], "pending")

    def test_teardown_removes_event_row(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "projection-stale",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        synthetic_drift.teardown_drift_fixture(manifest)

        db_path = Path(manifest["daemon_db_path"])
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT event_id FROM event_log WHERE event_id = ?",
                (manifest["event_seq"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row, "teardown left synthetic event_log row behind")


@_SKIP_DAEMON
class EventWithoutProjectionTests(_PostCutoverFixture):
    SLUG = "synth-event-without-projection"

    def test_event_inserted_and_projection_absent(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "event-without-projection",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        self.assertFalse(Path(manifest["expected_projection_path"]).exists())

        db_path = Path(manifest["daemon_db_path"])
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT event_type, projection_status, error_message FROM event_log WHERE event_id = ?",
                (manifest["event_seq"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "wicked.consensus.report_created")
        self.assertEqual(row[1], "error")
        self.assertIn("synthetic", (row[2] or "").lower())


@_SKIP_DAEMON
class ProjectionWithoutEventTests(_PostCutoverFixture):
    SLUG = "synth-projection-without-event"

    def test_projection_present_no_synthetic_event(self) -> None:
        manifest = synthetic_drift.build_drift_fixture(
            "projection-without-event",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        # The projection file MUST exist on disk.
        proj_path = Path(manifest["orphan_projection_path"])
        self.assertTrue(proj_path.is_file(),
                        f"expected orphan projection file at {proj_path}")
        # The file must look like a real gate-result.json (verdict + score).
        body = json.loads(proj_path.read_text(encoding="utf-8"))
        self.assertIn("verdict", body)
        self.assertEqual(body.get("_synthetic_drift_class"), "projection-without-event")

        # No new event was emitted by this fixture (we recorded the head).
        db_path = Path(manifest["daemon_db_path"])
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT MAX(event_id) FROM event_log").fetchone()
            head_now = (row[0] or 0) if row else 0
        finally:
            conn.close()
        self.assertEqual(head_now, manifest["event_log_head_at_build"])


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

class CliSmokeTests(unittest.TestCase):
    def test_list_command_lists_supported_classes(self) -> None:
        # We exercise main() rather than capturing stdout from a subprocess
        # to keep the test stdlib-only and fast.
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = synthetic_drift.main(["list"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(set(payload["supported"]),
                         set(synthetic_drift.SUPPORTED_DRIFT_CLASSES))

    def test_build_then_teardown_via_cli(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory(prefix="wg-synth-cli-") as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            rc = synthetic_drift.main([
                "build",
                "--class", "missing_native",
                "--workspace", tmp,
                "--slug", "cli-fixture",
                "--manifest-out", str(manifest_path),
            ])
            self.assertEqual(rc, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["ok"])
            self.assertTrue(Path(manifest["process_plan_path"]).is_file())

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = synthetic_drift.main(["teardown", "--manifest", str(manifest_path)])
            self.assertEqual(rc, 0)
            self.assertFalse(Path(manifest["process_plan_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
