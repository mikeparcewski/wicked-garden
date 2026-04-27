#!/usr/bin/env python3
"""Unit tests for scripts/crew/reconcile.py.

Coverage focuses on:
  - Empty / healthy / mixed-drift projects
  - Each drift type in isolation
  - reconcile_all aggregation across multiple projects
  - JSON output is parseable
  - Text output contains the drift counts
  - READ-ONLY contract: no file mtimes change during reconcile

All tests are deterministic, stdlib-only, and use cross-platform tempdirs.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Iterable, List
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import reconcile  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_plan_task(
    *,
    task_id: str,
    title: str,
    phase: str,
    chain_id: str,
    blocked_by: List[str] | None = None,
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "phase": phase,
        "blockedBy": blocked_by or [],
        "metadata": {
            "chain_id": chain_id,
            "event_type": "task",
            "source_agent": "facilitator",
            "phase": phase,
            "rigor_tier": "standard",
        },
    }


def _make_native_task(
    *,
    task_id: str,
    subject: str,
    status: str,
    chain_id: str,
    phase: str,
    event_type: str = "task",
) -> dict:
    return {
        "id": task_id,
        "subject": subject,
        "status": status,
        "metadata": {
            "chain_id": chain_id,
            "event_type": event_type,
            "source_agent": "implementer",
            "phase": phase,
            "rigor_tier": "standard",
        },
    }


def _build_plan(slug: str, tasks: List[dict]) -> dict:
    return {
        "project_slug": slug,
        "summary": "fixture",
        "rigor_tier": "standard",
        "complexity": 2,
        "factors": {},
        "specialists": [],
        "phases": ["build"],
        "tasks": tasks,
    }


def _snapshot_mtimes(root: Path) -> dict[str, float]:
    """Capture every file mtime under ``root`` as {relpath: mtime}."""
    out: dict[str, float] = {}
    if not root.exists():
        return out
    for path in root.rglob("*"):
        if path.is_file():
            out[str(path.relative_to(root))] = path.stat().st_mtime_ns
    return out


# ---------------------------------------------------------------------------
# Test scaffolding — patches projects root + CLAUDE_CONFIG_DIR for every test
# ---------------------------------------------------------------------------

class _ReconcileFixture(unittest.TestCase):
    """Base class that patches the two filesystem roots reconcile reads from."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

        self.projects_root = self.tmp_root / "wicked-crew" / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)

        self.config_dir = self.tmp_root / "claude-config"
        self.tasks_root = self.config_dir / "tasks"
        self.tasks_root.mkdir(parents=True, exist_ok=True)

        # Patch: route _projects_root + _claude_config_dir to the fixture.
        self._patches = [
            mock.patch.object(reconcile, "_projects_root", return_value=self.projects_root),
            mock.patch.object(reconcile, "_claude_config_dir", return_value=self.config_dir),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    # --- Convenience fixture builders -------------------------------------

    def _add_project(self, slug: str) -> Path:
        proj_dir = self.projects_root / slug
        proj_dir.mkdir(parents=True, exist_ok=True)
        return proj_dir

    def _write_plan(self, slug: str, plan: dict) -> Path:
        proj_dir = self._add_project(slug)
        path = proj_dir / "process-plan.json"
        _write_json(path, plan)
        return path

    def _write_gate_result(self, slug: str, phase: str, verdict: str) -> Path:
        path = self.projects_root / slug / "phases" / phase / "gate-result.json"
        _write_json(path, {"verdict": verdict, "min_score": 0.7, "score": 0.85})
        return path

    def _write_native_task(self, session: str, task: dict) -> Path:
        path = self.tasks_root / session / f"{task['id']}.json"
        _write_json(path, task)
        return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class EmptyProjectTests(_ReconcileFixture):
    def test_project_with_no_chain_emits_no_error(self) -> None:
        # Project dir exists but no process-plan.json and no native tasks.
        self._add_project("empty-proj")
        result = reconcile.reconcile_project("empty-proj")
        self.assertEqual(result["project_slug"], "empty-proj")
        self.assertEqual(result["garden_chain_tasks"], 0)
        self.assertEqual(result["native_tasks"], 0)
        self.assertEqual(result["drift"], [])
        # The missing process-plan.json must surface as an error string,
        # not an exception.
        self.assertTrue(any("process-plan.json" in err for err in result["errors"]))

    def test_completely_unknown_project_returns_empty_drift(self) -> None:
        # Nothing under the projects root at all.
        result = reconcile.reconcile_project("does-not-exist")
        self.assertEqual(result["garden_chain_tasks"], 0)
        self.assertEqual(result["native_tasks"], 0)
        self.assertEqual(result["drift"], [])


class HealthyProjectTests(_ReconcileFixture):
    def test_healthy_project_has_zero_drift(self) -> None:
        slug = "healthy"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Implement feature",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        self._write_native_task("session-1", _make_native_task(
            task_id="native-1",
            subject="Implement feature",
            status="completed",
            chain_id=f"{slug}.build",
            phase="build",
        ))
        result = reconcile.reconcile_project(slug)
        self.assertEqual(result["garden_chain_tasks"], 1)
        self.assertEqual(result["native_tasks"], 1)
        self.assertEqual(result["drift"], [])
        self.assertEqual(result["summary"]["total_drift_count"], 0)


class MissingNativeTests(_ReconcileFixture):
    def test_plan_task_without_native_counterpart(self) -> None:
        slug = "missing-native"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t5",
                title="Refactor module",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        # No native task written.
        result = reconcile.reconcile_project(slug)
        self.assertEqual(result["summary"]["missing_native_count"], 1)
        entry = result["drift"][0]
        self.assertEqual(entry["type"], reconcile.DRIFT_MISSING_NATIVE)
        self.assertEqual(entry["plan_task_id"], "t5")
        self.assertEqual(entry["expected_chain_id"], f"{slug}.build")

    def test_chain_present_but_title_mismatch_flags_missing(self) -> None:
        slug = "title-mismatch"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="A very specific feature title",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        self._write_native_task("session-1", _make_native_task(
            task_id="native-x",
            subject="Something completely different",
            status="completed",
            chain_id=f"{slug}.build",
            phase="build",
        ))
        result = reconcile.reconcile_project(slug)
        # Native tasks count is 1 (chain matches the project), but drift is
        # surfaced because the title heuristic doesn't see a match.
        self.assertEqual(result["native_tasks"], 1)
        self.assertEqual(result["summary"]["missing_native_count"], 1)


class StaleStatusTests(_ReconcileFixture):
    def test_native_pending_when_phase_approved(self) -> None:
        slug = "stale-pending"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Build the thing",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "build", "APPROVE")
        self._write_native_task("session-1", _make_native_task(
            task_id="native-1",
            subject="Build the thing",
            status="in_progress",
            chain_id=f"{slug}.build",
            phase="build",
        ))
        result = reconcile.reconcile_project(slug)
        stale = [d for d in result["drift"] if d["type"] == reconcile.DRIFT_STALE_STATUS]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["native_status"], "in_progress")
        self.assertEqual(stale[0]["phase"], "build")
        self.assertEqual(stale[0]["phase_verdict"], "APPROVE")

    def test_conditional_verdict_also_implies_completion(self) -> None:
        slug = "conditional"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Build the thing",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "build", "CONDITIONAL")
        self._write_native_task("session-1", _make_native_task(
            task_id="native-1",
            subject="Build the thing",
            status="pending",
            chain_id=f"{slug}.build",
            phase="build",
        ))
        result = reconcile.reconcile_project(slug)
        self.assertEqual(result["summary"]["stale_status_count"], 1)

    def test_completed_when_phase_rejected_is_drift(self) -> None:
        slug = "rejected-but-done"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Build the thing",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "build", "REJECT")
        self._write_native_task("session-1", _make_native_task(
            task_id="native-1",
            subject="Build the thing",
            status="completed",
            chain_id=f"{slug}.build",
            phase="build",
        ))
        result = reconcile.reconcile_project(slug)
        self.assertEqual(result["summary"]["stale_status_count"], 1)


class OrphanNativeTests(_ReconcileFixture):
    def test_orphan_only_surfaced_via_reconcile_all(self) -> None:
        # A native task references a project that does not exist on disk.
        self._write_native_task("session-1", _make_native_task(
            task_id="orphan-1",
            subject="Old work",
            status="completed",
            chain_id="deleted-project.build",
            phase="build",
        ))
        # And a real project exists (with no native tasks).
        slug = "real-project"
        self._write_plan(slug, _build_plan(slug, []))

        results = reconcile.reconcile_all()
        # Find the result for the real project — orphan drift attaches there
        # (the only place it can attach in --all mode).
        flat = [d for r in results for d in r["drift"]]
        orphans = [d for d in flat if d["type"] == reconcile.DRIFT_ORPHAN_NATIVE]
        self.assertEqual(len(orphans), 1)
        self.assertEqual(orphans[0]["orphan_project_slug"], "deleted-project")

    def test_single_project_mode_skips_orphan_detection(self) -> None:
        # Without the registry, single-project mode cannot tell "orphan"
        # from "task belonging to a different known project". Make sure we
        # don't false-positive in that mode.
        self._write_native_task("session-1", _make_native_task(
            task_id="other-1",
            subject="Other project work",
            status="completed",
            chain_id="some-other-project.build",
            phase="build",
        ))
        slug = "primary"
        self._write_plan(slug, _build_plan(slug, []))
        result = reconcile.reconcile_project(slug)
        orphans = [d for d in result["drift"] if d["type"] == reconcile.DRIFT_ORPHAN_NATIVE]
        self.assertEqual(orphans, [])


class PhaseDriftTests(_ReconcileFixture):
    def test_approved_phase_with_no_gate_finding_task_is_drift(self) -> None:
        slug = "phase-drift-no-task"
        plan = _build_plan(slug, [])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "design", "APPROVE")
        # No native gate-finding task at all.
        result = reconcile.reconcile_project(slug)
        phase_drift = [d for d in result["drift"] if d["type"] == reconcile.DRIFT_PHASE_GATE]
        self.assertEqual(len(phase_drift), 1)
        self.assertEqual(phase_drift[0]["phase"], "design")
        self.assertEqual(phase_drift[0]["phase_verdict"], "APPROVE")

    def test_approved_phase_with_open_gate_finding_is_drift(self) -> None:
        slug = "phase-drift-open"
        plan = _build_plan(slug, [])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "design", "APPROVE")
        self._write_native_task("session-1", _make_native_task(
            task_id="gf-1",
            subject="Gate finding",
            status="pending",
            chain_id=f"{slug}.design.gf-1",
            phase="design",
            event_type="gate-finding",
        ))
        result = reconcile.reconcile_project(slug)
        phase_drift = [d for d in result["drift"] if d["type"] == reconcile.DRIFT_PHASE_GATE]
        self.assertEqual(len(phase_drift), 1)
        self.assertEqual(phase_drift[0]["native_task_id"], "gf-1")

    def test_completed_gate_finding_is_not_drift(self) -> None:
        slug = "phase-clean"
        plan = _build_plan(slug, [])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "design", "APPROVE")
        self._write_native_task("session-1", _make_native_task(
            task_id="gf-1",
            subject="Gate finding",
            status="completed",
            chain_id=f"{slug}.design.gf-1",
            phase="design",
            event_type="gate-finding",
        ))
        result = reconcile.reconcile_project(slug)
        phase_drift = [d for d in result["drift"] if d["type"] == reconcile.DRIFT_PHASE_GATE]
        self.assertEqual(phase_drift, [])


class MixedDriftTests(_ReconcileFixture):
    def test_project_with_all_three_local_drift_types(self) -> None:
        slug = "messy"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Build it",
                phase="build",
                chain_id=f"{slug}.build",
            ),
            _make_plan_task(
                task_id="t2",
                title="Document it",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        # gate-result.json says APPROVE
        self._write_gate_result(slug, "build", "APPROVE")
        # Native task t1 exists but is still in_progress -> stale_status
        self._write_native_task("session-1", _make_native_task(
            task_id="native-1",
            subject="Build it",
            status="in_progress",
            chain_id=f"{slug}.build",
            phase="build",
        ))
        # Native task t2 missing -> missing_native
        # No gate-finding task -> phase_drift

        result = reconcile.reconcile_project(slug)
        types = sorted({d["type"] for d in result["drift"]})
        self.assertIn(reconcile.DRIFT_MISSING_NATIVE, types)
        self.assertIn(reconcile.DRIFT_STALE_STATUS, types)
        self.assertIn(reconcile.DRIFT_PHASE_GATE, types)
        self.assertEqual(result["summary"]["total_drift_count"], len(result["drift"]))


class ReconcileAllTests(_ReconcileFixture):
    def test_reconcile_all_walks_multiple_projects(self) -> None:
        # Three projects, two with simple state, one empty.
        for slug in ["alpha", "beta", "gamma"]:
            self._write_plan(slug, _build_plan(slug, []))

        results = reconcile.reconcile_all()
        slugs = sorted(r["project_slug"] for r in results)
        self.assertEqual(slugs, ["alpha", "beta", "gamma"])

    def test_reconcile_all_returns_empty_when_no_projects(self) -> None:
        # Don't call _add_project — projects root exists but is empty.
        results = reconcile.reconcile_all()
        self.assertEqual(results, [])


class CLIOutputTests(_ReconcileFixture):
    def test_json_output_is_parseable_for_single_project(self) -> None:
        slug = "json-test"
        self._write_plan(slug, _build_plan(slug, []))

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = reconcile.main(["--project", slug, "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["project_slug"], slug)
        self.assertIn("summary", parsed)

    def test_json_output_is_parseable_for_all(self) -> None:
        for slug in ["one", "two"]:
            self._write_plan(slug, _build_plan(slug, []))

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = reconcile.main(["--all", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)

    def test_text_output_contains_drift_counts_and_header(self) -> None:
        slug = "text-test"
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Missing task",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = reconcile.main(["--project", slug])
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("Reconcile report", output)
        self.assertIn("Drift summary", output)
        self.assertIn("missing_native:", output)
        self.assertIn("stale_status:", output)
        self.assertIn("orphan_native:", output)
        self.assertIn("phase_drift:", output)


class ReadOnlyContractTests(_ReconcileFixture):
    """Snapshot mtimes around every reconcile call — they must NOT change."""

    def _build_busy_state(self, slug: str) -> None:
        plan = _build_plan(slug, [
            _make_plan_task(
                task_id="t1",
                title="Build it",
                phase="build",
                chain_id=f"{slug}.build",
            ),
        ])
        self._write_plan(slug, plan)
        self._write_gate_result(slug, "build", "APPROVE")
        self._write_native_task("session-1", _make_native_task(
            task_id="native-1",
            subject="Build it",
            status="in_progress",
            chain_id=f"{slug}.build",
            phase="build",
        ))

    def test_reconcile_project_does_not_mutate_any_file(self) -> None:
        slug = "ro-project"
        self._build_busy_state(slug)
        before = _snapshot_mtimes(self.tmp_root)
        reconcile.reconcile_project(slug)
        after = _snapshot_mtimes(self.tmp_root)
        self.assertEqual(before, after, "reconcile_project mutated a file")

    def test_reconcile_all_does_not_mutate_any_file(self) -> None:
        for slug in ["ro1", "ro2"]:
            self._build_busy_state(slug)
        before = _snapshot_mtimes(self.tmp_root)
        reconcile.reconcile_all()
        after = _snapshot_mtimes(self.tmp_root)
        self.assertEqual(before, after, "reconcile_all mutated a file")

    def test_cli_json_run_does_not_mutate_any_file(self) -> None:
        slug = "ro-cli"
        self._build_busy_state(slug)
        before = _snapshot_mtimes(self.tmp_root)
        buf = io.StringIO()
        with redirect_stdout(buf):
            reconcile.main(["--project", slug, "--json"])
        after = _snapshot_mtimes(self.tmp_root)
        self.assertEqual(before, after, "CLI run mutated a file")


class FailOpenTests(_ReconcileFixture):
    def test_invalid_json_in_process_plan_surfaces_as_error(self) -> None:
        slug = "broken-plan"
        proj_dir = self._add_project(slug)
        (proj_dir / "process-plan.json").write_text("{ not valid json", encoding="utf-8")
        result = reconcile.reconcile_project(slug)
        self.assertTrue(any("invalid JSON" in err for err in result["errors"]))
        # Should still return a complete result dict — no exception.
        self.assertEqual(result["project_slug"], slug)

    def test_unreachable_native_root_does_not_crash(self) -> None:
        # Patch _claude_config_dir to a path that does not exist.
        nonexistent = self.tmp_root / "no-such-dir"
        with mock.patch.object(reconcile, "_claude_config_dir", return_value=nonexistent):
            slug = "unreachable"
            self._write_plan(slug, _build_plan(slug, []))
            result = reconcile.reconcile_project(slug)
        self.assertTrue(any("native tasks" in err for err in result["errors"]))
        self.assertEqual(result["native_tasks"], 0)


class HelperTests(unittest.TestCase):
    def test_project_slug_extraction(self) -> None:
        self.assertEqual(reconcile._project_slug_from_chain_id("foo.root"), "foo")
        self.assertEqual(reconcile._project_slug_from_chain_id("foo.build.gate"), "foo")
        self.assertEqual(reconcile._project_slug_from_chain_id("only-slug"), "only-slug")
        self.assertIsNone(reconcile._project_slug_from_chain_id(""))
        self.assertIsNone(reconcile._project_slug_from_chain_id(None))  # type: ignore[arg-type]

    def test_phase_status_implies_completion(self) -> None:
        self.assertTrue(reconcile._phase_status_implies_completion({"verdict": "APPROVE"}))
        self.assertTrue(reconcile._phase_status_implies_completion({"verdict": "CONDITIONAL"}))
        self.assertFalse(reconcile._phase_status_implies_completion({"verdict": "REJECT"}))
        self.assertIsNone(reconcile._phase_status_implies_completion({"verdict": "MAYBE"}))
        self.assertIsNone(reconcile._phase_status_implies_completion({}))


if __name__ == "__main__":
    unittest.main()
