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

import ast
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

# Site 3 (Issue #746 PR-AB): import reconcile_v2 now that the module exists.
# This import activates Tier B of the two-tier meta-test in
# TestPostCutoverContract (the detector-assertion contract that was deferred
# until Site 3 landed per ADR docs/v9/adr-reconcile-v2.md and Issue #750).
try:
    import reconcile_v2  # noqa: E402
    _RECONCILE_V2_AVAILABLE = True
except ImportError:
    reconcile_v2 = None  # type: ignore[assignment]
    _RECONCILE_V2_AVAILABLE = False


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

    @pytest.mark.skipif(
        not _RECONCILE_V2_AVAILABLE,
        reason="reconcile_v2 not importable — Tier B detector skip",
    )
    def test_reconcile_v2_detects_projection_stale(self) -> None:
        """Tier B: reconcile_v2 must classify this fixture as projection-stale drift.

        Activates once scripts/crew/reconcile_v2.py lands (Site 3 PR-AB).
        Per ADR docs/v9/adr-reconcile-v2.md and Issue #750.
        """
        manifest = synthetic_drift.build_drift_fixture(
            "projection-stale",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        db_path = manifest["daemon_db_path"]
        results = reconcile_v2.reconcile_all(daemon_db_path=db_path)
        all_drift_types = [
            d["type"]
            for r in results
            for d in r.get("drift", [])
        ]
        self.assertIn(
            reconcile_v2.DRIFT_PROJECTION_STALE,
            all_drift_types,
            f"reconcile_v2 did not detect projection-stale drift. "
            f"All drift types found: {all_drift_types}",
        )


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

    @pytest.mark.skipif(
        not _RECONCILE_V2_AVAILABLE,
        reason="reconcile_v2 not importable — Tier B detector skip",
    )
    def test_reconcile_v2_detects_event_without_projection(self) -> None:
        """Tier B: reconcile_v2 must classify this fixture as event-without-projection.

        Activates once scripts/crew/reconcile_v2.py lands (Site 3 PR-AB).
        Per ADR docs/v9/adr-reconcile-v2.md and Issue #750.
        """
        manifest = synthetic_drift.build_drift_fixture(
            "event-without-projection",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        db_path = manifest["daemon_db_path"]
        results = reconcile_v2.reconcile_all(daemon_db_path=db_path)
        all_drift_types = [
            d["type"]
            for r in results
            for d in r.get("drift", [])
        ]
        self.assertIn(
            reconcile_v2.DRIFT_EVENT_WITHOUT_PROJECTION,
            all_drift_types,
            f"reconcile_v2 did not detect event-without-projection drift. "
            f"All drift types found: {all_drift_types}",
        )


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

    @pytest.mark.skipif(
        not _RECONCILE_V2_AVAILABLE,
        reason="reconcile_v2 not importable — Tier B detector skip",
    )
    def test_reconcile_v2_detects_projection_without_event(self) -> None:
        """Tier B: reconcile_v2 must classify this fixture as projection-without-event.

        Activates once scripts/crew/reconcile_v2.py lands (Site 3 PR-AB).
        Per ADR docs/v9/adr-reconcile-v2.md and Issue #750.
        """
        manifest = synthetic_drift.build_drift_fixture(
            "projection-without-event",
            project_slug=self.SLUG,
            workspace_dir=self.workspace,
        )
        self.assertTrue(manifest["ok"], manifest)
        self.addCleanup(synthetic_drift.teardown_drift_fixture, manifest)

        db_path = manifest["daemon_db_path"]
        # reconcile_v2 needs the project dir to exist under its _projects_root.
        # For this fixture the orphan file lives inside the workspace; we need
        # to tell reconcile_v2 where the projects root is.
        orphan_path = Path(manifest["orphan_projection_path"])
        # orphan_path layout: {workspace}/wicked-crew/projects/{slug}/phases/{phase}/gate-result.json
        projects_root = orphan_path.parents[3]

        with mock.patch.object(reconcile_v2, "_projects_root", return_value=projects_root):
            results = reconcile_v2.reconcile_all(daemon_db_path=db_path)

        all_drift_types = [
            d["type"]
            for r in results
            for d in r.get("drift", [])
        ]
        self.assertIn(
            reconcile_v2.DRIFT_PROJECTION_WITHOUT_EVENT,
            all_drift_types,
            f"reconcile_v2 did not detect projection-without-event drift. "
            f"All drift types found: {all_drift_types}",
        )


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


# ---------------------------------------------------------------------------
# Post-cutover contract meta-test (Issue #750, ADR adr-reconcile-v2.md)
# ---------------------------------------------------------------------------

class TestPostCutoverContract(unittest.TestCase):
    """Meta-test: every post-cutover synthetic-drift test class MUST be
    exercised by a test method that imports/references ``reconcile_v2``
    (the post-cutover reconciler shipped by Site 3 of #746).

    Today, before Site 3 lands ``scripts/crew/reconcile_v2.py``, this
    test passes trivially: NO test in this file references
    ``reconcile_v2`` yet, and NO post-cutover test asserts against a
    reconciler — they all assert fixture state only (the documented
    council deferral on #750).

    The moment ``reconcile_v2`` lands AND the post-cutover test classes
    grow real detector assertions, this meta-test starts enforcing the
    contract: any test method inside a class that targets a
    post-cutover drift class MUST reference ``reconcile_v2`` somewhere
    in its body. This blocks the "fixture-shape only assertion"
    pattern from sneaking back in.

    No escape hatch (no ``# fixture-only-OK`` comment marker). If a
    test is genuinely fixture-only it does not belong in
    ``test_synthetic_drift.py`` — move it to a unit test for the
    fixture builder.

    Adapts to real ``synthetic_drift`` structure:
      - canonical post-cutover set is ``synthetic_drift._DAEMON_DB_BEARING``
        (a frozenset of drift class names)
      - test classes for those drift classes follow the convention of
        embedding the kebab-case slug as PascalCase in the class name
        (e.g. ``projection-stale`` -> ``ProjectionStale*``)

    See ``docs/v9/adr-reconcile-v2.md`` for the contract this enforces.
    """

    # When Site 3 ships reconcile_v2, the meta-test transitions from
    # "trivially passes" to "actively enforces". The transition is
    # automatic — no flag flip needed.
    _RECONCILE_V2_MODULE = "reconcile_v2"

    def _post_cutover_drift_classes(self) -> set[str]:
        """Return the canonical set of post-cutover drift classes, or
        an empty set if the underlying registry is missing.

        Skips gracefully if ``synthetic_drift`` is restructured so
        ``_DAEMON_DB_BEARING`` no longer exists — the meta-test should
        never fail because the registry layout changed.
        """
        registry = getattr(synthetic_drift, "_DAEMON_DB_BEARING", None)
        if registry is None:
            return set()
        try:
            return {str(c) for c in registry}
        except TypeError:
            return set()

    @staticmethod
    def _slug_to_pascal(slug: str) -> str:
        """``projection-stale`` -> ``ProjectionStale``. Stable for matching
        against PascalCase class names in the test file."""
        parts = slug.replace("_", "-").split("-")
        return "".join(p[:1].upper() + p[1:].lower() for p in parts if p)

    @staticmethod
    def _identifiers_in_node(node: ast.AST) -> set[str]:
        """Collect every identifier and module reference under ``node``.

        Captures Name, Attribute, ImportFrom (module + aliases), and
        Import (module names). This is conservative on purpose — we
        want any reference to ``reconcile_v2`` to count, not just
        explicit imports, because a test could receive the module via
        a fixture.
        """
        idents: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                idents.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                idents.add(sub.attr)
            elif isinstance(sub, ast.ImportFrom):
                if sub.module:
                    idents.add(sub.module)
                for alias in sub.names:
                    idents.add(alias.name)
                    if alias.asname:
                        idents.add(alias.asname)
            elif isinstance(sub, ast.Import):
                for alias in sub.names:
                    idents.add(alias.name)
                    if alias.asname:
                        idents.add(alias.asname)
        return idents

    def test_every_post_cutover_class_has_a_reconciler_test(self) -> None:
        # Local import keeps top-of-file imports unchanged for readers
        # tracing the v1 test suite.
        import ast as _ast  # noqa: F401  -- kept explicit for the docstring contract

        post_cutover_classes = self._post_cutover_drift_classes()
        if not post_cutover_classes:
            # Registry layout changed or post-cutover set was emptied.
            # Skip rather than failing — the contract is "test EVERY
            # post-cutover class", not "fail when the set is empty".
            self.skipTest(
                "synthetic_drift._DAEMON_DB_BEARING is missing or empty; "
                "meta-test has nothing to enforce"
            )

        # Module-existence gate. If ``scripts/crew/reconcile_v2.py``
        # does not exist on disk, Site 3 has not landed yet — the
        # contract passes trivially. This is the documented deferral
        # path from #750 + adr-reconcile-v2.md. We check for the FILE
        # rather than try to import (importing would mutate sys.modules
        # and could interact with the existing ``import reconcile``
        # statement at the top of this file).
        reconcile_v2_path = (
            _REPO_ROOT / "scripts" / "crew" / f"{self._RECONCILE_V2_MODULE}.py"
        )
        # Two-tier check, both ALWAYS run:
        #
        #   Tier A (#757 — coverage gap): every post-cutover slug in
        #   _DAEMON_DB_BEARING MUST have at least one matching test
        #   class. This runs whether or not Site 3 has landed —
        #   the test-class-existence requirement is independent of
        #   the reconcile_v2 module itself.
        #
        #   Tier B (#750 — detector-assertion contract): every matched
        #   class MUST have at least one test method that references
        #   reconcile_v2. This is gated on Site 3 having landed —
        #   if reconcile_v2.py does not exist on disk, the detector
        #   check is skipped (the documented deferral from #750 +
        #   adr-reconcile-v2.md). #757 fix: this gate is now narrow,
        #   it does NOT skip Tier A's coverage check.
        site_3_landed = reconcile_v2_path.is_file()
        test_file = Path(__file__).resolve()
        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        violations: list[str] = []

        for drift_class in sorted(post_cutover_classes):
            pascal = self._slug_to_pascal(drift_class)
            matching_classes: list[ast.ClassDef] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and pascal in node.name:
                    matching_classes.append(node)

            # Tier A — always runs.
            if not matching_classes:
                # #757: silent skip defeats half the contract. A
                # post-cutover drift class in _DAEMON_DB_BEARING with NO
                # matching test class is a real coverage gap — name it.
                violations.append(
                    f"  {drift_class}: no test class found matching "
                    f"PascalCase {pascal!r} (expected e.g. {pascal}Tests). "
                    f"Add a test class for this _DAEMON_DB_BEARING slug "
                    f"or remove it from the registry."
                )
                continue

            # Tier B — gated on Site 3 landing.
            if not site_3_landed:
                continue

            has_v2_assertion = False
            for cls in matching_classes:
                for item in cls.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not item.name.startswith("test_"):
                        continue
                    idents = self._identifiers_in_node(item)
                    if self._RECONCILE_V2_MODULE in idents:
                        has_v2_assertion = True
                        break
                if has_v2_assertion:
                    break

            if not has_v2_assertion:
                violations.append(
                    f"  {drift_class}: classes "
                    f"{[c.name for c in matching_classes]} have no test "
                    f"method that references {self._RECONCILE_V2_MODULE!r}; "
                    f"add a detector assertion (see ADR adr-reconcile-v2.md)"
                )

        self.assertEqual(
            violations, [],
            "Post-cutover synthetic-drift tests MUST assert against "
            "reconcile_v2's detector output, not just fixture state. "
            "Per ADR docs/v9/adr-reconcile-v2.md and Issue #750.\n"
            "Violations:\n" + "\n".join(violations)
        )


if __name__ == "__main__":
    unittest.main()
