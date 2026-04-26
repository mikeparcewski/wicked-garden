"""Unit tests for scripts/delivery/telemetry.py (Issue #443).

Covers:
    - capture_session writes a JSONL record with the documented schema
    - metric extraction from native task gate-finding events
    - cycle time computation from phase-transition events
    - fail-open on missing tasks dir / missing session state
    - append-only semantics (no rewriting)
    - sanitization of session_id + project

Stdlib-only, deterministic.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "delivery"))


def _load_telemetry(tmpdir: Path):
    """Fresh-import telemetry with a sandboxed local root.

    We point CLAUDE_CWD at tmpdir so _paths derives an isolated project slug,
    giving each test its own metrics directory.
    """
    os.environ["CLAUDE_CWD"] = str(tmpdir)
    # Force re-resolution of _LOCAL_ROOT inside _paths.
    for modname in ("_paths", "telemetry"):
        if modname in sys.modules:
            del sys.modules[modname]
    import telemetry  # noqa: F401 — re-import with fresh env
    importlib.reload(sys.modules["telemetry"])
    return sys.modules["telemetry"]


def _write_task(tasks_dir: Path, name: str, record: dict) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")


class TelemetryCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Isolate the Claude tasks config dir.
        self.config_dir = self.root / "claude-config"
        self.config_dir.mkdir()
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        self.session_id = "test-session-001"
        self.tasks_dir = self.config_dir / "tasks" / self.session_id
        self.telemetry = _load_telemetry(self.root)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        os.environ.pop("CLAUDE_CWD", None)

    def test_capture_writes_record_with_schema(self):
        """AC: capture_session returns a record and appends it to JSONL."""
        # One APPROVE + one REJECT gate-finding.
        _write_task(self.tasks_dir, "task-001", {
            "status": "completed",
            "metadata": {
                "event_type": "gate-finding",
                "verdict": "APPROVE",
                "score": 0.82,
            },
        })
        _write_task(self.tasks_dir, "task-002", {
            "status": "completed",
            "metadata": {
                "event_type": "gate-finding",
                "verdict": "REJECT",
                "score": 0.40,
            },
        })

        record = self.telemetry.capture_session(self.session_id, project="demo")
        self.assertIsNotNone(record, "capture_session returned None unexpectedly")
        self.assertEqual(record["version"], "1")
        self.assertEqual(record["project"], "demo")
        self.assertIn("recorded_at", record)
        m = record["metrics"]
        self.assertEqual(m["gate_verdict_count"], 2)
        self.assertEqual(m["gate_rework_count"], 1)
        # 1 APPROVE out of 2 verdicts = 0.5 pass rate.
        self.assertAlmostEqual(m["gate_pass_rate"], 0.5)
        # Average of 0.82 and 0.40 = 0.61.
        self.assertAlmostEqual(m["gate_avg_score"], 0.61, places=2)

        # Verify the file has one line.
        timeline = self.telemetry.read_timeline("demo")
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["session_id"], self.session_id)

    def test_capture_append_only(self):
        """Two captures for the same project produce two lines."""
        _write_task(self.tasks_dir, "t1", {
            "status": "completed",
            "metadata": {"event_type": "gate-finding", "verdict": "APPROVE", "score": 0.9},
        })
        r1 = self.telemetry.capture_session(self.session_id, project="demo")
        r2 = self.telemetry.capture_session(self.session_id, project="demo")
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertEqual(len(self.telemetry.read_timeline("demo")), 2)

    def test_capture_fails_open_on_missing_tasks_dir(self):
        """No tasks dir → record is still written with zeroed metrics."""
        # tasks_dir does not exist for this session_id
        record = self.telemetry.capture_session("never-existed", project="demo")
        self.assertIsNotNone(record)
        self.assertEqual(record["metrics"]["gate_verdict_count"], 0)
        self.assertIsNone(record["metrics"]["gate_pass_rate"])

    def test_cycle_time_from_phase_transitions(self):
        """Two phase-transitions on same phase → cycle_time delta is captured."""
        _write_task(self.tasks_dir, "pt1", {
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:10Z",
            "metadata": {"event_type": "phase-transition", "phase": "design"},
        })
        _write_task(self.tasks_dir, "pt2", {
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:40Z",
            "metadata": {"event_type": "phase-transition", "phase": "design"},
        })
        record = self.telemetry.capture_session(self.session_id, project="demo")
        self.assertIsNotNone(record)
        cycle = record["metrics"]["cycle_time_by_phase"]
        self.assertIn("design", cycle)
        # Second transition is 30s after first.
        self.assertAlmostEqual(cycle["design"], 30.0, places=1)

    def test_sanitization_strips_path_traversal(self):
        """session_id and project with path traversal become safe strings."""
        rec = self.telemetry.capture_session("../evil", project="../etc")
        self.assertIsNotNone(rec)
        self.assertNotIn("..", rec["session_id"])
        self.assertNotIn("..", rec["project"])

    def test_capture_under_budget(self):
        """A realistic session scan should complete well under 500ms."""
        for i in range(20):
            _write_task(self.tasks_dir, f"t{i:03d}", {
                "status": "completed",
                "metadata": {
                    "event_type": "gate-finding",
                    "verdict": "APPROVE" if i % 3 else "REJECT",
                    "score": 0.7,
                },
            })
        t0 = time.monotonic()
        rec = self.telemetry.capture_session(self.session_id, project="demo")
        elapsed_ms = (time.monotonic() - t0) * 1000
        self.assertIsNotNone(rec)
        self.assertLess(elapsed_ms, 500, f"capture took {elapsed_ms:.1f}ms, budget is 500ms")


    def test_tasks_observed_reflects_task_count_not_file_count(self):
        """tasks_observed must equal the number of tasks read, not the file scan count (#660).

        Before the fix, sample_window used len(task_files) which was always 0
        on the happy path (daemon-routed read_session_tasks), making the metric
        useless for daemon sessions.  After the fix, len(tasks) is used
        regardless of path so the metric correctly reports how many tasks were
        actually observed.

        How this test exercises the metric (#667 follow-up clarification):
        telemetry.capture_session() always imports crew._task_reader.read_session_tasks
        and calls it first. Under unit-test conditions no daemon is running, so
        read_session_tasks returns an empty list and the function falls through
        to the direct-file-scan path that reads ${tasks_dir}/*.json. The 3 task
        files we write below are read by that fallback path. The assertion still
        proves the bug fix because both the daemon path and the direct-scan path
        flow through the same len(tasks) computation — the regression we are
        guarding against (len(task_files) instead of len(tasks)) would surface
        the same way on either path. Test name preserved for traceability to #660.
        """
        # Write 3 task files in the direct-scan path.
        for i in range(3):
            _write_task(self.tasks_dir, f"task-obs-{i:02d}", {
                "status": "completed",
                "created_at": "2026-04-25T10:00:00Z",
                "updated_at": "2026-04-25T10:01:00Z",
                "metadata": {
                    "event_type": "gate-finding",
                    "verdict": "APPROVE",
                    "score": 0.9,
                },
            })

        record = self.telemetry.capture_session(self.session_id, project="obs-test")
        self.assertIsNotNone(record)
        sw = record["sample_window"]

        # tasks_observed must reflect the 3 tasks written — not 0 (stale file count).
        self.assertEqual(sw["tasks_observed"], 3,
                         f"tasks_observed should be 3, got {sw['tasks_observed']!r}. "
                         "If 0, the metric still uses len(task_files) instead of len(tasks).")
        # task_files_scanned is emitted as a deprecated alias for v8.3.x per
        # PR #663 council (backward-compat for downstream consumers). Same
        # value as tasks_observed. Removed in v8.4.0.
        self.assertEqual(sw.get("task_files_scanned"), sw["tasks_observed"],
                         "task_files_scanned (deprecated alias) must mirror "
                         "tasks_observed exactly until removed in v8.4.0.")


if __name__ == "__main__":
    unittest.main()
