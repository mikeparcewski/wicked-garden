"""Integration tests for B-1: dispatch-log wiring into phase_manager
``_dispatch_*`` helpers (AC-7 of #471).

Contract:
  - Every ``_dispatch_fast_evaluator`` / ``_dispatch_sequential`` /
    ``_dispatch_parallel_and_merge`` / ``_dispatch_council`` invocation
    MUST append a dispatch-log record BEFORE invoking the reviewer.
  - ``_load_gate_result`` orphan-check passes when a matching entry exists.
  - When no matching entry exists (orphan), the soft-window emits a
    warn-once deprecation and accepts (before strict-after).

Deterministic. Stdlib-only.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import dispatch_log  # noqa: E402
import phase_manager as pm  # noqa: E402
from phase_manager import ProjectState  # noqa: E402


def _mk_state(tmp_base: Path, name: str = "test-proj") -> ProjectState:
    """Build a ProjectState whose ``get_project_dir`` resolves under tmp_base.

    The phase-manager's ``get_project_dir`` derives the directory from the
    shared DomainStore local-path root. Patching ``get_local_path`` via
    the shared test-helper approach is out of scope for this test — we
    instead monkeypatch ``get_project_dir`` directly for a clean
    tmp-project fixture.
    """
    state = ProjectState(
        name=name,
        current_phase="build",
        created_at="2026-04-19T00:00:00Z",
    )
    state.phase_plan = ["clarify", "design", "build", "review"]
    return state


def _project_dir_of(tmp_base: Path, name: str) -> Path:
    project_dir = tmp_base / name
    (project_dir / "phases" / "build").mkdir(parents=True, exist_ok=True)
    return project_dir


def _setup_daemon_pipeline(tmp_base: Path, project_dir: Path):
    """Setup an in-memory daemon DB + bus emit replacement (PR #800).

    Site 1's source-side disk write was deleted in PR #800 — these
    integration tests need a real projector roundtrip to observe
    dispatch-log entries.  Returns the bus-emit replacement; caller
    uses ``patch("_bus.emit_event", side_effect=_emit)`` and remembers
    to ``os.environ.pop("WG_DAEMON_DB", None)`` in finally.
    """
    sys.path.insert(0, str(_REPO_ROOT / "daemon"))
    import db as daemon_db  # noqa: PLC0415
    import sqlite3 as _sqlite3  # noqa: PLC0415
    from projector import _dispatch_log_appended  # noqa: PLC0415

    db_path = tmp_base / "projections.db"
    conn = _sqlite3.connect(str(db_path))
    daemon_db.init_schema(conn)
    project_id = project_dir.name
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(project_dir), "active", "build",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()
    conn.close()
    os.environ["WG_DAEMON_DB"] = str(db_path)
    os.environ["WG_BUS_AS_TRUTH_DISPATCH_LOG"] = "on"

    counter = {"event_id": 0}

    def _emit(event_type, payload, chain_id=None, metadata=None):
        if event_type != "wicked.dispatch.log_entry_appended":
            return  # only the dispatch-log handler is wired in this fixture
        counter["event_id"] += 1
        eid = counter["event_id"]
        c = _sqlite3.connect(str(db_path))
        c.row_factory = _sqlite3.Row  # daemon.db.get_project requires Row factory
        try:
            event = {
                "event_id": eid,
                "event_type": event_type,
                "chain_id": chain_id,
                "created_at": 1_700_000_000 + eid,
                "payload": payload,
            }
            # Production ordering (mirrors ``daemon/consumer.py::process_batch``,
            # PR #800 fix-up): projector runs FIRST, event_log row is
            # appended AFTER.  Same change as
            # ``tests/crew/test_dispatch_log.py::_simulate_bus_pipeline``.
            _dispatch_log_appended(c, event)
            c.commit()
            c.execute(
                "INSERT INTO event_log (event_id, event_type, chain_id, "
                "payload_json, projection_status, ingested_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (eid, event_type, chain_id or "",
                 json.dumps(payload), "applied", 1_700_000_000 + eid),
            )
            c.commit()
        finally:
            c.close()

    return _emit


def _teardown_daemon_pipeline() -> None:
    os.environ.pop("WG_DAEMON_DB", None)
    os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)


class DispatchLogWiringFastEvaluator(unittest.TestCase):
    """B-1: ``_dispatch_fast_evaluator`` MUST append a dispatch-log entry
    BEFORE invoking the reviewer dispatcher."""

    def test_fast_evaluator_appends_dispatch_log_before_reviewer_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_base = Path(tmp)
            state = _mk_state(tmp_base)
            project_dir = _project_dir_of(tmp_base, state.name)
            emit = _setup_daemon_pipeline(tmp_base, project_dir)
            try:
                with patch.object(pm, "get_project_dir", return_value=project_dir), \
                     patch("_bus.emit_event", side_effect=emit):
                    calls = []

                    def spy_dispatcher(subagent_type, prompt, ctx):
                        # Assert a matching dispatch-log entry exists BEFORE
                        # the reviewer is invoked.
                        entries = dispatch_log.read_entries(project_dir, "build")
                        calls.append({"subagent": subagent_type,
                                      "log_len_at_call": len(entries)})
                        return {"verdict": "APPROVE", "score": 0.9,
                                "reason": "ok", "conditions": []}

                    pm._dispatch_fast_evaluator(
                        state, "build", "code-quality",
                        dispatcher=spy_dispatcher,
                    )

                # Log entry MUST have been appended BEFORE the spy was invoked.
                self.assertEqual(len(calls), 1)
                self.assertGreaterEqual(
                    calls[0]["log_len_at_call"], 1,
                    "dispatch-log must be appended BEFORE reviewer dispatch",
                )

                with patch("_bus.emit_event", side_effect=emit):
                    entries = dispatch_log.read_entries(project_dir, "build")
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["reviewer"], "gate-evaluator")
                self.assertEqual(entries[0]["phase"], "build")
                self.assertEqual(entries[0]["gate"], "code-quality")
                self.assertEqual(
                    entries[0]["dispatcher_agent"],
                    "wicked-garden:crew:phase-manager",
                )
                self.assertEqual(
                    entries[0]["expected_result_path"], "gate-result.json",
                )
            finally:
                _teardown_daemon_pipeline()


class DispatchLogWiringSequential(unittest.TestCase):
    def test_sequential_appends_one_entry_per_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_base = Path(tmp)
            state = _mk_state(tmp_base)
            project_dir = _project_dir_of(tmp_base, state.name)
            emit = _setup_daemon_pipeline(tmp_base, project_dir)
            try:
                with patch.object(pm, "get_project_dir", return_value=project_dir), \
                     patch("_bus.emit_event", side_effect=emit):
                    def mock_dispatcher(subagent_type, prompt, ctx):
                        return {"verdict": "APPROVE", "score": 0.85,
                                "reason": "ok", "conditions": []}

                    pm._dispatch_sequential(
                        state, "build", "code-quality",
                        ["security-engineer", "senior-engineer"],
                        dispatcher=mock_dispatcher,
                    )
                    entries = dispatch_log.read_entries(project_dir, "build")
                self.assertEqual(len(entries), 2)
                self.assertEqual(
                    {e["reviewer"] for e in entries},
                    {"security-engineer", "senior-engineer"},
                )
            finally:
                _teardown_daemon_pipeline()


class DispatchLogWiringParallel(unittest.TestCase):
    def test_parallel_appends_one_entry_per_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_base = Path(tmp)
            state = _mk_state(tmp_base)
            project_dir = _project_dir_of(tmp_base, state.name)
            emit = _setup_daemon_pipeline(tmp_base, project_dir)
            try:
                with patch.object(pm, "get_project_dir", return_value=project_dir), \
                     patch("_bus.emit_event", side_effect=emit):
                    def mock_dispatcher(subagent_type, prompt, ctx):
                        return {"verdict": "APPROVE", "score": 0.85,
                                "reason": "ok", "conditions": []}

                    pm._dispatch_parallel_and_merge(
                        state, "build", "code-quality",
                        ["security-engineer", "senior-engineer"],
                        dispatcher=mock_dispatcher,
                    )
                    entries = dispatch_log.read_entries(project_dir, "build")
                reviewers = {e["reviewer"] for e in entries}
                self.assertIn("security-engineer", reviewers)
                self.assertIn("senior-engineer", reviewers)
            finally:
                _teardown_daemon_pipeline()


class DispatchLogWiringCouncil(unittest.TestCase):
    def test_council_appends_council_tagged_entry_per_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_base = Path(tmp)
            state = _mk_state(tmp_base)
            project_dir = _project_dir_of(tmp_base, state.name)
            emit = _setup_daemon_pipeline(tmp_base, project_dir)
            try:
                with patch.object(pm, "get_project_dir", return_value=project_dir), \
                     patch("_bus.emit_event", side_effect=emit):
                    def mock_dispatcher(subagent_type, prompt, ctx):
                        return {"verdict": "APPROVE", "score": 0.85,
                                "reason": "ok", "conditions": []}

                    pm._dispatch_council(
                        state, "build", "code-quality",
                        ["security-engineer", "senior-engineer"],
                        dispatcher=mock_dispatcher,
                    )
                    entries = dispatch_log.read_entries(project_dir, "build")
                # Council records its own entries; parallel-and-merge
                # underneath records additional entries.  We only assert
                # the council-tagged entries exist.
                council_entries = [
                    e for e in entries
                    if e.get("dispatcher_agent") ==
                    "wicked-garden:crew:phase-manager:council"
                ]
                self.assertEqual(len(council_entries), 2)
                self.assertEqual(
                    {e["reviewer"] for e in council_entries},
                    {"security-engineer", "senior-engineer"},
                )
            finally:
                _teardown_daemon_pipeline()


class DispatchLogOrphanCheckIntegration(unittest.TestCase):
    """B-1: after dispatch + gate-result write, ``_load_gate_result``
    orphan-check must find the matching entry and pass.
    """

    def test_dispatch_then_load_passes_orphan_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_base = Path(tmp)
            state = _mk_state(tmp_base)
            project_dir = _project_dir_of(tmp_base, state.name)

            with patch.object(pm, "get_project_dir", return_value=project_dir):
                def mock_dispatcher(subagent_type, prompt, ctx):
                    return {"verdict": "APPROVE", "score": 0.9,
                            "reason": "ok", "conditions": []}

                pm._dispatch_sequential(
                    state, "build", "code-quality",
                    ["security-engineer"],
                    dispatcher=mock_dispatcher,
                )

            # Reviewer writes gate-result.json with the dispatched identity.
            gate_result = {
                "verdict": "APPROVE",
                "result": "APPROVE",
                "reviewer": "security-engineer",
                "recorded_at": "2099-01-01T00:00:00+00:00",
                "phase": "build",
                "gate": "code-quality",
                "score": 0.9,
                "min_score": 0.7,
            }
            (project_dir / "phases" / "build" / "gate-result.json").write_text(
                json.dumps(gate_result)
            )

            # _load_gate_result must not raise — the dispatch-log has the
            # matching reviewer+phase+gate row recorded-at <= recorded_at.
            parsed = pm._load_gate_result(project_dir, "build")
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["reviewer"], "security-engineer")


class DispatchLogOrphanSoftWindowAllows(unittest.TestCase):
    """B-1 negative case: a gate-result with no matching dispatch entry
    triggers the soft-window warn+allow path (pre-cutover). The
    ``_load_gate_result`` caller receives the parsed result + an
    ``unauthorized_dispatch_accepted_legacy`` audit entry.
    """

    def test_orphan_in_soft_window_is_allowed_with_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_base = Path(tmp)
            project_dir = _project_dir_of(tmp_base, "test-proj")

            # NO dispatch-log entry — orphan condition.
            gate_result = {
                "verdict": "APPROVE",
                "result": "APPROVE",
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-20T00:00:00+00:00",
                "phase": "build",
                "gate": "code-quality",
                "score": 0.9,
                "min_score": 0.7,
            }
            (project_dir / "phases" / "build" / "gate-result.json").write_text(
                json.dumps(gate_result)
            )

            # Force strict-after to the future so the soft window applies.
            with patch.dict(os.environ,
                            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"}):
                # Reset session markers so warn-once fires deterministically.
                dispatch_log._DEPRECATION_EMITTED.clear()
                parsed = pm._load_gate_result(project_dir, "build")

            # Soft window: accepted with audit, NOT rejected.
            self.assertIsNotNone(parsed)
            audit_path = (
                project_dir / "phases" / "build" / "gate-ingest-audit.jsonl"
            )
            self.assertTrue(audit_path.exists())
            text = audit_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertTrue(
                any('"unauthorized_dispatch_accepted_legacy"' in line
                    for line in text),
                "audit log must record the soft-window acceptance",
            )


if __name__ == "__main__":
    unittest.main()
