"""tests/daemon/test_test_dispatch.py — Test suite for daemon/test_dispatch.py.

Issue #595 (v8 PR-7).

Coverage:
  - Detection: phases with test-strategy/test/qe activities → plan includes correct skills
  - Dispatch: mock wicked-testing invocation, verify evidence row written
  - Graceful degradation: wicked-testing unavailable → WARNING + skipped_unavailable
  - Autonomy integration: ask/balanced/full mode dispatch behaviors
  - Idempotency: re-dispatching same (project, phase, skill) within window → no-op
  - DB schema: test_dispatches table created by init_schema
  - HTTP endpoints: POST /test-dispatch, GET /test-dispatches
  - plan shape: to_dict() serialisation

T1: deterministic — no wall-clock, no network calls in unit tests
T2: no sleep-based sync
T3: isolated — each test gets a fresh in-memory DB
T4: single assertion focus per test case
T5: descriptive names
T6: provenance #595 v8-PR-7
"""

from __future__ import annotations

import json
import sys
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sys.path: ensure daemon package + scripts/ are importable
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from daemon.db import connect, init_schema  # noqa: E402
import daemon.test_dispatch as td  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mem_conn():
    """Open in-memory SQLite connection with schema initialised."""
    conn = connect(":memory:")
    init_schema(conn)
    return conn


def _phase_row(name: str, specialists=None, activities=None) -> dict:
    """Build a minimal phase dict for detection tests."""
    return {
        "phase": name,
        "name": name,
        "specialists": specialists or [],
        "activities": activities or [],
    }


# ===========================================================================
# Stream 1 — Phase detection
# ===========================================================================

class TestDetectTestPhases:
    def test_test_strategy_phase_detected(self):
        phases = [_phase_row("test-strategy")]
        result = td.detect_test_phases(phases)
        assert "test-strategy" in result

    def test_test_phase_detected(self):
        phases = [_phase_row("test")]
        result = td.detect_test_phases(phases)
        assert "test" in result

    def test_build_phase_not_detected(self):
        phases = [_phase_row("build")]
        result = td.detect_test_phases(phases)
        assert "build" not in result

    def test_clarify_phase_not_detected(self):
        phases = [_phase_row("clarify")]
        result = td.detect_test_phases(phases)
        assert "clarify" not in result

    def test_qe_specialist_triggers_detection(self):
        phases = [_phase_row("custom-phase", specialists=["qe"])]
        result = td.detect_test_phases(phases)
        assert "custom-phase" in result

    def test_non_qe_specialist_not_detected(self):
        phases = [_phase_row("build", specialists=["engineering"])]
        result = td.detect_test_phases(phases)
        assert "build" not in result

    def test_activities_containing_test_triggers_detection(self):
        phases = [_phase_row("validate", activities=["run test scenarios"])]
        result = td.detect_test_phases(phases)
        assert "validate" in result

    def test_empty_phases_list_returns_empty(self):
        assert td.detect_test_phases([]) == []

    def test_phase_with_no_name_skipped(self):
        phases = [{"phase": "", "specialists": ["qe"]}]
        # Empty name is skipped even with a QE specialist
        result = td.detect_test_phases(phases)
        assert result == []

    def test_multiple_test_phases_all_detected(self):
        phases = [_phase_row("test-strategy"), _phase_row("test"), _phase_row("build")]
        result = td.detect_test_phases(phases)
        assert set(result) == {"test-strategy", "test"}


class TestBuildDispatchPlan:
    def test_test_strategy_yields_wt_plan_skill(self):
        phases = [_phase_row("test-strategy")]
        plan = td.build_dispatch_plan("proj-1", phases)
        skill_names = [s.skill for s in plan.skills]
        assert "wicked-testing:plan" in skill_names

    def test_test_phase_yields_authoring_and_execution(self):
        phases = [_phase_row("test")]
        plan = td.build_dispatch_plan("proj-1", phases)
        skill_names = [s.skill for s in plan.skills]
        assert "wicked-testing:authoring" in skill_names
        assert "wicked-testing:execution" in skill_names

    def test_no_test_phases_yields_empty_plan(self):
        phases = [_phase_row("build"), _phase_row("clarify")]
        plan = td.build_dispatch_plan("proj-1", phases)
        assert plan.skills == []
        assert plan.test_phases_detected == []

    def test_plan_carries_project_id(self):
        phases = [_phase_row("test-strategy")]
        plan = td.build_dispatch_plan("my-project", phases)
        assert plan.project_id == "my-project"

    def test_plan_to_dict_is_json_serialisable(self):
        phases = [_phase_row("test-strategy")]
        plan = td.build_dispatch_plan("proj-1", phases)
        d = plan.to_dict()
        # Should not raise
        json.dumps(d)

    def test_catalog_enrichment_adds_specialist_info(self):
        catalog = {
            "phases": {
                "custom-test": {"specialists": ["qe"], "activities": []}
            }
        }
        phases = [{"phase": "custom-test"}]
        plan = td.build_dispatch_plan("proj-1", phases, phase_catalog=catalog)
        # qe specialist → should be detected
        assert "custom-test" in plan.test_phases_detected


# ===========================================================================
# Stream 2 — Dispatch mechanism
# ===========================================================================

class TestDispatchForPhase:
    def test_dispatch_ok_writes_row(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=0, stdout="evidence: /tmp/ev.json\n", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )

        assert record.verdict == td._VERDICT_OK
        conn.close()

    def test_dispatch_ok_writes_evidence_path(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=0, stdout="evidence: /tmp/test-ev.json\n", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )

        assert record.evidence_path == "/tmp/test-ev.json"
        conn.close()

    def test_dispatch_persists_row_to_db(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=0, stdout="ok\n", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            record = td.dispatch_for_phase(
                conn, "proj-1", "test", "wicked-testing:authoring",
                autonomy_mode_str="full",
            )

        rows = td.list_test_dispatches(conn, project_id="proj-1")
        assert len(rows) == 1
        assert rows[0]["dispatch_id"] == record.dispatch_id
        conn.close()

    def test_dispatch_subprocess_error_writes_error_verdict(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=1, stdout="", stderr="npm ERR!")
        with patch("subprocess.run", return_value=fake_result):
            record = td.dispatch_for_phase(
                conn, "proj-1", "test", "wicked-testing:execution",
                autonomy_mode_str="full",
            )

        assert record.verdict == td._VERDICT_ERROR
        conn.close()

    def test_dispatch_records_latency(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            record = td.dispatch_for_phase(
                conn, "proj-1", "test", "wicked-testing:review",
                autonomy_mode_str="full",
            )

        assert record.latency_ms >= 0
        conn.close()


# ===========================================================================
# Stream 3 — Graceful degradation
# ===========================================================================

class TestGracefulDegradation:
    def test_unavailable_writes_skipped_unavailable(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        record = td.dispatch_for_phase(
            conn, "proj-1", "test-strategy", "wicked-testing:plan",
            autonomy_mode_str="full",
        )

        assert record.verdict == td._VERDICT_SKIPPED_UNAVAILABLE
        conn.close()

    def test_unavailable_emits_warning(self, monkeypatch, caplog):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        import logging
        with caplog.at_level(logging.WARNING, logger="daemon.test_dispatch"):
            td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )

        assert any("skipped_unavailable" in r.message or "not available" in r.message
                   for r in caplog.records)
        conn.close()

    def test_unavailable_phase_proceeds_with_gap_flag(self, monkeypatch):
        """Phase gate sees flagged evidence gap when wicked-testing is missing."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        record = td.dispatch_for_phase(
            conn, "proj-1", "test-strategy", "wicked-testing:plan",
            autonomy_mode_str="full",
        )

        # Evidence gap indicated in notes
        assert "evidence gap" in record.notes.lower() or "not installed" in record.notes.lower()
        # Row is persisted — gate can query it
        rows = td.list_test_dispatches(conn, project_id="proj-1")
        assert len(rows) == 1
        assert rows[0]["verdict"] == td._VERDICT_SKIPPED_UNAVAILABLE
        conn.close()

    def test_run_dispatches_degrades_gracefully_when_unavailable(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        phases = [_phase_row("test-strategy"), _phase_row("test")]
        records = td.run_test_dispatches(
            conn, "proj-1", phases, autonomy_mode_str="full"
        )

        # All records should be skipped_unavailable, not errors
        assert all(r.verdict == td._VERDICT_SKIPPED_UNAVAILABLE for r in records)
        conn.close()


# ===========================================================================
# Stream 5 — Autonomy-mode integration
# ===========================================================================

class TestAutonomyIntegration:
    def test_ask_mode_defers_dispatch(self, monkeypatch):
        """ask mode: logs intent, does NOT invoke subprocess."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)

        # ask mode must NOT call subprocess
        with patch("subprocess.run") as mock_run:
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="ask",
            )
        mock_run.assert_not_called()
        assert record.verdict == td._VERDICT_DEFERRED_ASK
        conn.close()

    def test_ask_mode_notes_explain_deferral(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)

        record = td.dispatch_for_phase(
            conn, "proj-1", "test-strategy", "wicked-testing:plan",
            autonomy_mode_str="ask",
        )

        assert "ask mode" in record.notes.lower() or "confirmation" in record.notes.lower()
        conn.close()

    def test_full_mode_auto_dispatches(self, monkeypatch):
        """full mode: invokes subprocess without pause."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )
        mock_run.assert_called_once()
        assert record.verdict == td._VERDICT_OK
        conn.close()

    def test_balanced_mode_auto_dispatches_for_test_dispatch(self, monkeypatch):
        """balanced mode: test dispatch is not blocked (conservative auto)."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        # WG_HITL_TEST_DISPATCH defaults to 'auto' → balanced proceeds
        monkeypatch.delenv("WG_HITL_TEST_DISPATCH", raising=False)

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="balanced",
            )
        mock_run.assert_called_once()
        assert record.verdict == td._VERDICT_OK
        conn.close()

    def test_balanced_mode_env_override_pause(self, monkeypatch):
        """WG_HITL_TEST_DISPATCH=pause forces deferral even in balanced mode."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setenv("WG_HITL_TEST_DISPATCH", "pause")

        with patch("subprocess.run") as mock_run:
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="balanced",
            )
        mock_run.assert_not_called()
        assert record.verdict == td._VERDICT_DEFERRED_ASK
        conn.close()

    def test_balanced_mode_env_override_off_dispatches(self, monkeypatch):
        """WG_HITL_TEST_DISPATCH=off means no pause in balanced mode."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setenv("WG_HITL_TEST_DISPATCH", "off")

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            record = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="balanced",
            )
        mock_run.assert_called_once()
        assert record.verdict == td._VERDICT_OK
        conn.close()


# ===========================================================================
# Stream 7 — Idempotency
# ===========================================================================

class TestIdempotency:
    def test_second_dispatch_within_window_is_no_op(self, monkeypatch):
        """Re-dispatching same (project, phase, skill) within window → no_op_duplicate."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            r1 = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )
        assert r1.verdict == td._VERDICT_OK

        # Second call — should be no-op
        with patch("subprocess.run") as mock_run:
            r2 = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )
        mock_run.assert_not_called()
        assert r2.verdict == "no_op_duplicate"
        conn.close()

    def test_different_skill_is_not_idempotent(self, monkeypatch):
        """Different skill on same phase is NOT a duplicate."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            td.dispatch_for_phase(
                conn, "proj-1", "test", "wicked-testing:authoring",
                autonomy_mode_str="full",
            )

        with patch("subprocess.run", return_value=fake_result) as mock_run:
            r2 = td.dispatch_for_phase(
                conn, "proj-1", "test", "wicked-testing:execution",
                autonomy_mode_str="full",
            )
        mock_run.assert_called_once()
        assert r2.verdict == td._VERDICT_OK
        conn.close()

    def test_outside_window_is_not_duplicate(self, monkeypatch):
        """After the idempotency window expires, dispatch fires again."""
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: True)
        monkeypatch.setattr(td, "_should_pause_test_dispatch", lambda *a: False)

        # Write a stale row directly — emitted_at far in the past
        old_record = td.DispatchRecord(
            dispatch_id="old-id",
            session_id="s1",
            project_id="proj-1",
            phase="test-strategy",
            skill="wicked-testing:plan",
            verdict=td._VERDICT_OK,
            evidence_path=None,
            latency_ms=100,
            emitted_at=int(time.time()) - td._IDEMPOTENCY_WINDOW_S - 60,
            notes="old dispatch",
        )
        td._persist_dispatch(conn, old_record)

        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            r = td.dispatch_for_phase(
                conn, "proj-1", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )
        mock_run.assert_called_once()
        assert r.verdict == td._VERDICT_OK
        conn.close()


# ===========================================================================
# DB schema — test_dispatches table
# ===========================================================================

class TestDbSchema:
    def test_init_schema_creates_test_dispatches_table(self):
        conn = _mem_conn()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_dispatches'"
        ).fetchone()
        assert row is not None, "test_dispatches table must exist after init_schema"
        conn.close()

    def test_test_dispatches_has_required_columns(self):
        conn = _mem_conn()
        info = conn.execute("PRAGMA table_info(test_dispatches)").fetchall()
        col_names = {r[1] for r in info}
        required = {
            "dispatch_id", "session_id", "project_id", "phase", "skill",
            "verdict", "evidence_path", "latency_ms", "emitted_at", "notes",
        }
        assert required.issubset(col_names)
        conn.close()

    def test_list_test_dispatches_empty_returns_empty(self):
        conn = _mem_conn()
        rows = td.list_test_dispatches(conn, project_id="proj-x")
        assert rows == []
        conn.close()


# ===========================================================================
# HTTP endpoints — POST /test-dispatch, GET /test-dispatches
# ===========================================================================

class TestHttpEndpoints:
    def _make_handler(self, db_path=None):
        """Build a ProjectionRequestHandler subclass with an in-memory test DB path."""
        from daemon.server import ProjectionRequestHandler
        handler_class = type(
            "TestProjectionRequestHandler",
            (ProjectionRequestHandler,),
            {"db_path": db_path},
        )
        return handler_class

    def _fake_request(self, handler_class, method: str, path: str, body: bytes | None = None):
        """Simulate an HTTP request and return (status, response_body)."""
        # We patch the underlying socket/wfile to capture the response.
        output = BytesIO()

        handler = handler_class.__new__(handler_class)
        handler.path = path
        handler.headers = {}
        if body is not None:
            handler.headers["Content-Length"] = str(len(body))
            handler.rfile = BytesIO(body)
        else:
            handler.headers["Content-Length"] = "0"
            handler.rfile = BytesIO(b"")

        captured_status = []
        captured_body = []

        def _send_response(code):
            captured_status.append(code)

        def _send_header(name, value):
            pass

        def _end_headers():
            pass

        def _wfile_write(data):
            captured_body.append(data)

        handler.send_response = _send_response
        handler.send_header = _send_header
        handler.end_headers = _end_headers
        handler.wfile = MagicMock()
        handler.wfile.write.side_effect = _wfile_write

        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()

        status = captured_status[0] if captured_status else None
        body_bytes = b"".join(captured_body)
        return status, body_bytes

    def test_post_test_dispatch_returns_200(self, monkeypatch, tmp_path):
        import daemon.db as db_mod
        # Use a real temp DB so schema is created
        db_file = str(tmp_path / "test.db")
        conn_ctx = connect(db_file)
        init_schema(conn_ctx)
        conn_ctx.close()

        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        handler_class = self._make_handler(db_path=db_file)
        body = json.dumps({
            "project_id": "proj-1",
            "phase": "test-strategy",
        }).encode("utf-8")
        status, resp = self._fake_request(handler_class, "POST", "/test-dispatch", body)
        assert status == 200

    def test_post_test_dispatch_missing_project_id_returns_400(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        conn_ctx = connect(db_file)
        init_schema(conn_ctx)
        conn_ctx.close()

        handler_class = self._make_handler(db_path=db_file)
        body = json.dumps({"phase": "test-strategy"}).encode("utf-8")
        status, resp = self._fake_request(handler_class, "POST", "/test-dispatch", body)
        assert status == 400

    def test_post_test_dispatch_missing_phase_returns_400(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        conn_ctx = connect(db_file)
        init_schema(conn_ctx)
        conn_ctx.close()

        handler_class = self._make_handler(db_path=db_file)
        body = json.dumps({"project_id": "proj-1"}).encode("utf-8")
        status, resp = self._fake_request(handler_class, "POST", "/test-dispatch", body)
        assert status == 400

    def test_get_test_dispatches_returns_200(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        conn_ctx = connect(db_file)
        init_schema(conn_ctx)
        conn_ctx.close()

        handler_class = self._make_handler(db_path=db_file)
        status, resp = self._fake_request(
            handler_class, "GET", "/test-dispatches?project_id=proj-1"
        )
        assert status == 200

    def test_get_test_dispatches_empty_returns_empty_list(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        conn_ctx = connect(db_file)
        init_schema(conn_ctx)
        conn_ctx.close()

        handler_class = self._make_handler(db_path=db_file)
        status, resp = self._fake_request(
            handler_class, "GET", "/test-dispatches?project_id=no-such-project"
        )
        assert status == 200
        data = json.loads(resp)
        assert data == []

    def test_get_test_dispatches_invalid_limit_returns_400(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        conn_ctx = connect(db_file)
        init_schema(conn_ctx)
        conn_ctx.close()

        handler_class = self._make_handler(db_path=db_file)
        status, _ = self._fake_request(
            handler_class, "GET", "/test-dispatches?limit=notanumber"
        )
        assert status == 400


# ===========================================================================
# DispatchRecord.to_dict() serialisation
# ===========================================================================

class TestDispatchRecordSerialisation:
    def test_to_dict_is_json_serialisable(self):
        record = td.DispatchRecord(
            dispatch_id="d-1",
            session_id="s-1",
            project_id="p-1",
            phase="test-strategy",
            skill="wicked-testing:plan",
            verdict="ok",
            evidence_path="/tmp/ev.json",
            latency_ms=123,
            emitted_at=1_700_000_000,
            notes="all good",
        )
        d = record.to_dict()
        # Should not raise
        json.dumps(d)

    def test_to_dict_contains_all_fields(self):
        record = td.DispatchRecord(
            dispatch_id="d-2",
            session_id="s-2",
            project_id="p-2",
            phase="test",
            skill="wicked-testing:authoring",
            verdict="skipped_unavailable",
            evidence_path=None,
            latency_ms=0,
            emitted_at=1_700_000_001,
            notes="degraded",
        )
        d = record.to_dict()
        expected_keys = {
            "dispatch_id", "session_id", "project_id", "phase", "skill",
            "verdict", "evidence_path", "latency_ms", "emitted_at", "notes",
        }
        assert expected_keys == set(d.keys())


# ===========================================================================
# run_test_dispatches — integration
# ===========================================================================

class TestRunTestDispatches:
    def test_returns_one_record_per_skill(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        phases = [_phase_row("test-strategy"), _phase_row("test")]
        records = td.run_test_dispatches(
            conn, "proj-1", phases, autonomy_mode_str="full"
        )
        # test-strategy → 1 skill; test → 2 skills = 3 total
        assert len(records) == 3
        conn.close()

    def test_skill_filter_limits_dispatches(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        phases = [_phase_row("test")]
        records = td.run_test_dispatches(
            conn, "proj-1", phases,
            autonomy_mode_str="full",
            skill_filter=["wicked-testing:authoring"],
        )
        assert len(records) == 1
        assert records[0].skill == "wicked-testing:authoring"
        conn.close()

    def test_empty_phases_returns_no_records(self, monkeypatch):
        conn = _mem_conn()
        monkeypatch.setattr(td, "_is_wicked_testing_available", lambda: False)

        records = td.run_test_dispatches(conn, "proj-1", [], autonomy_mode_str="full")
        assert records == []
        conn.close()


# ===========================================================================
# Stream 3 — Availability probe: Node-present-but-wicked-testing-absent
# Council condition C1 (PR #621 re-review)
# ===========================================================================

class TestAvailabilityProbeNodeWithoutWickedTesting:
    """Verify graceful degradation when Node.js is installed but wicked-testing is not.

    Council-caught contract bug (PR #621 re-review): the shutil fallback
    previously probed ``npx`` (returns True on any Node install), causing
    dispatches to produce _VERDICT_ERROR instead of _VERDICT_SKIPPED_UNAVAILABLE.

    Provenance: issue #621 / PR-7 council condition C1.
    """

    def test_node_present_wicked_testing_absent_returns_false(self):
        """probe module absent + npx wicked-testing returns 127 + no binary → False."""
        # Simulate: _wicked_testing_probe not importable, npx present but wicked-testing absent,
        # and wicked-testing binary not in PATH.
        fake_result = MagicMock(returncode=127, stdout="", stderr="command not found")
        with (
            patch.dict("sys.modules", {"_wicked_testing_probe": None}),
            patch("subprocess.run", return_value=fake_result),
            patch("shutil.which", return_value=None),
        ):
            result = td._is_wicked_testing_available()

        assert result is False

    def test_node_present_probe_returns_false_explicitly(self):
        """If _wicked_testing_probe.probe() returns a non-ok status, return False immediately."""
        probe_mod = MagicMock()
        probe_mod.probe.return_value = {"status": "not_found"}
        with patch.dict("sys.modules", {"_wicked_testing_probe": probe_mod}):
            result = td._is_wicked_testing_available()

        assert result is False

    def test_timeout_on_npx_probe_returns_false(self):
        """If ``npx --no-install wicked-testing`` hangs past the timeout, return False."""
        import subprocess as _sp
        with (
            patch.dict("sys.modules", {"_wicked_testing_probe": None}),
            patch("subprocess.run", side_effect=_sp.TimeoutExpired(cmd=["npx"], timeout=2.0)),
            patch("shutil.which", return_value=None),
        ):
            result = td._is_wicked_testing_available()

        assert result is False

    def test_dispatch_records_skipped_not_error_when_unavailable(self):
        """End-to-end: wicked-testing absent → dispatch_for_phase writes skipped_unavailable."""
        conn = _mem_conn()
        fake_result = MagicMock(returncode=127, stdout="", stderr="command not found")
        with (
            patch.dict("sys.modules", {"_wicked_testing_probe": None}),
            patch("subprocess.run", return_value=fake_result),
            patch("shutil.which", return_value=None),
        ):
            record = td.dispatch_for_phase(
                conn, "proj-node-only", "test-strategy", "wicked-testing:plan",
                autonomy_mode_str="full",
            )

        assert record.verdict == td._VERDICT_SKIPPED_UNAVAILABLE, (
            f"Expected skipped_unavailable but got {record.verdict!r}. "
            "Node-present-but-wicked-testing-absent must degrade gracefully, not error."
        )
        conn.close()


# ===========================================================================
# Issue #623 — phases.json prose vs structured-detector regression guard
# ===========================================================================

# Words that suggest a phase engages testing when they appear in the prose
# `description`/`summary` fields. Used by the regression guard below.
_PROSE_TEST_KEYWORDS: frozenset[str] = frozenset({
    "test", "verify", "validation", "verification", "qe",
})


class TestPhasesJsonProseGuard:
    """Regression guard for issue #623.

    `detect_test_phases` matches by name keyword, qe specialist, or test-keyword
    activity — it does NOT scan free-text `description`/`summary` fields. If a
    future phases.json entry describes testing only in prose (no structured
    signal) it would silently skip dispatch. This test fails CI in that case so
    the author either adds a structured signal or extends the detector.
    """

    @staticmethod
    def _load_catalog() -> dict:
        """Load .claude-plugin/phases.json from repo root."""
        catalog_path = _REPO_ROOT / ".claude-plugin" / "phases.json"
        with catalog_path.open() as fh:
            return json.load(fh)

    def test_every_prose_test_phase_has_structured_signal(self):
        """For each phase in phases.json: if its description mentions testing,
        the structured detector must also match it.
        """
        catalog = self._load_catalog()
        phases = catalog["phases"]

        # Build phase rows the way detect_test_phases expects
        phase_rows = []
        for name, phase in phases.items():
            row = dict(phase)
            row["phase"] = name
            phase_rows.append(row)

        detected = set(td.detect_test_phases(phase_rows))

        prose_only_misses: list[str] = []
        for name, phase in phases.items():
            prose = (
                (phase.get("description") or "") + " " + (phase.get("summary") or "")
            ).lower()
            mentions_test = any(kw in prose for kw in _PROSE_TEST_KEYWORDS)
            if mentions_test and name not in detected:
                prose_only_misses.append(name)

        assert prose_only_misses == [], (
            "Issue #623: the following phases in .claude-plugin/phases.json "
            "describe testing in prose but lack a structured signal "
            "(name keyword in {test-strategy,test,qe} / specialists contains 'qe' "
            f"/ test-keyword activity), so detect_test_phases skips them: "
            f"{prose_only_misses}. Either add a structured signal to the phase "
            "(preferred — keeps the detector cheap) or extend "
            "daemon/test_dispatch.detect_test_phases to scan description/summary."
        )
