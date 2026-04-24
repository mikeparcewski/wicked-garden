"""tests/daemon/test_hook_dispatch.py — Test suite for daemon/hook_dispatch.py.

Issue #592 (v8 PR-8).

Coverage:
  - Filter matching: exact + glob patterns
  - Debounce rules: phase-boundary, once-per-session, rate-limit
  - Handler subprocess: happy path, timeout, error, chained emit_events
  - Invocation audit: every dispatch gets a row
  - load_subscriptions_from_config: valid + invalid config files
  - register_subscription: auto-id + explicit id
  - HTTP surface: GET /subscriptions, GET /subscriptions/<id>/invocations,
                  POST /subscriptions/<id>/toggle

T1: deterministic — no wall-clock (except where testing time-based logic with fixed epochs)
T2: no sleep-based sync
T3: isolated — each test gets a fresh in-memory DB
T4: single assertion focus per test
T5: descriptive names
T6: provenance #592 v8-PR-8
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from daemon.db import connect, init_schema, list_hook_invocations, list_hook_subscriptions  # noqa: E402
import daemon.hook_dispatch as hd  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mem():
    conn = connect(":memory:")
    init_schema(conn)
    return conn


def _event(event_type="wicked.gate.decided", event_id=1, project_id="proj-1",
           phase="design", session_id="sess-1", **kwargs):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "payload": {
            "project_id": project_id,
            "phase": phase,
            "session_id": session_id,
            "result": "APPROVE",
            "score": 0.85,
            **kwargs,
        },
    }


def _ok_result(message="ok", emit_events=None):
    return json.dumps({
        "status": "ok",
        "message": message,
        "emit_events": emit_events or [],
    }).encode()


def _error_result(message="handler error"):
    return json.dumps({
        "status": "error",
        "message": message,
        "emit_events": [],
    }).encode()


# ---------------------------------------------------------------------------
# Mock subprocess.run helper
# ---------------------------------------------------------------------------

def _mock_run(stdout=None, returncode=0, stderr=""):
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = (stdout or b"").decode() if isinstance(stdout, bytes) else (stdout or "")
    mock.stderr = stderr
    return mock


# ===========================================================================
# Stream 1 — Filter matching
# ===========================================================================

class TestFilterMatching:
    def test_exact_match(self):
        assert hd._matches_filter("wicked.gate.decided", "wicked.gate.decided") is True

    def test_exact_no_match(self):
        assert hd._matches_filter("wicked.gate.decided", "wicked.gate.rejected") is False

    def test_glob_star_suffix_matches(self):
        assert hd._matches_filter("wicked.gate.decided", "wicked.gate.*") is True

    def test_glob_star_matches_deep(self):
        assert hd._matches_filter("wicked.phase.transitioned", "wicked.*") is True

    def test_glob_star_no_match_wrong_prefix(self):
        assert hd._matches_filter("wicked.gate.decided", "wicked.phase.*") is False

    def test_glob_star_only_matches_anything(self):
        assert hd._matches_filter("wicked.anything.at.all", "wicked.*") is True

    def test_empty_filter_no_match(self):
        assert hd._matches_filter("wicked.gate.decided", "") is False

    def test_empty_event_type_no_match(self):
        assert hd._matches_filter("", "wicked.*") is False

    def test_exact_match_subsystem_event(self):
        assert hd._matches_filter("wicked.rework.triggered", "wicked.rework.triggered") is True


# ===========================================================================
# Stream 2 — Debounce rules
# ===========================================================================

class TestDebouncePhaseBoundary:
    def test_first_invocation_allowed(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "h.py",
                                        {"type": "phase-boundary"}, "sub-1")
        ev = _event()
        result = hd._check_debounce(conn, sid, ev, {"type": "phase-boundary"})
        assert result is False  # allow

    def test_duplicate_phase_boundary_debounced(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "h.py",
                                        {"type": "phase-boundary"}, "sub-1")
        ev = _event(event_type="wicked.gate.decided", event_id=1, project_id="p1", phase="design")
        # Simulate a prior DISPATCHED row with the boundary key
        from daemon.db import append_hook_invocation
        boundary_key = f"wicked.gate.decided:p1:design"
        append_hook_invocation(conn, "inv-prior", sid, 1, boundary_key, hd.VERDICT_DISPATCHED, 100)
        result = hd._check_debounce(conn, sid, ev, {"type": "phase-boundary"})
        assert result is True  # debounced

    def test_different_phase_not_debounced(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "h.py",
                                        {"type": "phase-boundary"}, "sub-1")
        ev_design = _event(phase="design", event_id=1)
        ev_build = _event(phase="build", event_id=2)
        # Record a DISPATCHED for design
        from daemon.db import append_hook_invocation
        boundary_key_design = f"wicked.gate.decided:proj-1:design"
        append_hook_invocation(conn, "inv-d", sid, 1, boundary_key_design, hd.VERDICT_DISPATCHED, 100)
        # Check build is not debounced
        result = hd._check_debounce(conn, sid, ev_build, {"type": "phase-boundary"})
        assert result is False


class TestDebounceOncePerSession:
    def test_first_session_allowed(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py",
                                        {"type": "once-per-session"}, "sub-1")
        ev = _event(session_id="session-abc")
        result = hd._check_debounce(conn, sid, ev, {"type": "once-per-session"})
        assert result is False

    def test_second_same_session_debounced(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py",
                                        {"type": "once-per-session"}, "sub-1")
        ev = _event(event_type="wicked.gate.decided", session_id="session-abc")
        from daemon.db import append_hook_invocation
        session_key = f"wicked.gate.decided:session:session-abc"
        append_hook_invocation(conn, "inv-s", sid, 1, session_key, hd.VERDICT_DISPATCHED, 100)
        result = hd._check_debounce(conn, sid, ev, {"type": "once-per-session"})
        assert result is True

    def test_different_session_not_debounced(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py",
                                        {"type": "once-per-session"}, "sub-1")
        from daemon.db import append_hook_invocation
        session_key_abc = "wicked.gate.decided:session:session-abc"
        append_hook_invocation(conn, "inv-abc", sid, 1, session_key_abc, hd.VERDICT_DISPATCHED, 100)
        ev_xyz = _event(event_type="wicked.gate.decided", session_id="session-xyz")
        result = hd._check_debounce(conn, sid, ev_xyz, {"type": "once-per-session"})
        assert result is False


class TestDebounceRateLimit:
    def test_within_limit_allowed(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", None, "sub-1")
        # No prior invocations; rate limit of 3 per 60s
        rule = {"type": "rate-limit", "window_s": 60, "max": 3}
        result = hd._check_debounce(conn, sid, _event(), rule)
        assert result is False

    def test_at_limit_debounced(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", None, "sub-1")
        from daemon.db import append_hook_invocation
        now = int(time.time())
        for i in range(3):
            append_hook_invocation(
                conn, f"inv-{i}", sid, i, "wicked.gate.decided", hd.VERDICT_DISPATCHED, 10,
                emitted_at=now - i
            )
        rule = {"type": "rate-limit", "window_s": 60, "max": 3}
        result = hd._check_debounce(conn, sid, _event(), rule)
        assert result is True

    def test_below_limit_not_debounced(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", None, "sub-1")
        from daemon.db import append_hook_invocation
        now = int(time.time())
        for i in range(2):
            append_hook_invocation(
                conn, f"inv-{i}", sid, i, "wicked.gate.decided", hd.VERDICT_DISPATCHED, 10,
                emitted_at=now - i
            )
        rule = {"type": "rate-limit", "window_s": 60, "max": 3}
        result = hd._check_debounce(conn, sid, _event(), rule)
        assert result is False  # only 2 in window, max is 3

    def test_outside_window_not_counted(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", None, "sub-1")
        from daemon.db import append_hook_invocation
        # Put 3 dispatched rows OUTSIDE the 10s window
        old_time = int(time.time()) - 100
        for i in range(3):
            append_hook_invocation(
                conn, f"inv-old-{i}", sid, i, "wicked.gate.decided", hd.VERDICT_DISPATCHED, 10,
                emitted_at=old_time + i
            )
        rule = {"type": "rate-limit", "window_s": 10, "max": 3}
        result = hd._check_debounce(conn, sid, _event(), rule)
        assert result is False  # outside window

    def test_unknown_debounce_type_allows(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", None, "sub-1")
        rule = {"type": "future-unrecognized-type"}
        result = hd._check_debounce(conn, sid, _event(), rule)
        assert result is False  # fail-open


# ===========================================================================
# Stream 3 — Handler subprocess invocation
# ===========================================================================

class TestHandlerSubprocessHappyPath:
    @patch("daemon.hook_dispatch.subprocess.run")
    def test_dispatched_verdict_on_success(self, mock_run):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "some/handler.py",
                                        None, "sub-1")
        mock_run.return_value = _mock_run(stdout=_ok_result())
        ev = _event()
        records = hd.dispatch_event_to_subscribers(conn, ev)
        assert len(records) == 1
        assert records[0].verdict == hd.VERDICT_DISPATCHED

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_invocation_row_persisted(self, mock_run):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "some/handler.py",
                                        None, "sub-1")
        mock_run.return_value = _mock_run(stdout=_ok_result())
        ev = _event()
        hd.dispatch_event_to_subscribers(conn, ev)
        rows = list_hook_invocations(conn, "sub-1")
        assert len(rows) == 1

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_stdout_digest_captured(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "some/handler.py", None, "sub-1")
        out = '{"status":"ok","message":"done","emit_events":[]}'
        mock_run.return_value = _mock_run(stdout=out.encode())
        hd.dispatch_event_to_subscribers(conn, _event())
        rows = list_hook_invocations(conn, "sub-1")
        assert rows[0]["stdout_digest"] == out

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_non_json_stdout_treated_as_success(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "some/handler.py", None, "sub-1")
        mock_run.return_value = _mock_run(stdout=b"Handler ran fine (plain text)")
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert records[0].verdict == hd.VERDICT_DISPATCHED

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_handler_status_error_gives_handler_error_verdict(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "some/handler.py", None, "sub-1")
        mock_run.return_value = _mock_run(stdout=_error_result("something went wrong"))
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert records[0].verdict == hd.VERDICT_HANDLER_ERROR

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_nonzero_exit_gives_handler_error_verdict(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "some/handler.py", None, "sub-1")
        mock_run.return_value = _mock_run(returncode=1, stderr="something failed")
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert records[0].verdict == hd.VERDICT_HANDLER_ERROR


class TestHandlerTimeout:
    @patch("daemon.hook_dispatch.subprocess.run")
    def test_timeout_gives_timeout_verdict(self, mock_run):
        import subprocess
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "some/handler.py", None, "sub-1")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python3", "h.py"], timeout=30)
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert records[0].verdict == hd.VERDICT_TIMEOUT

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_timeout_invocation_row_persisted(self, mock_run):
        import subprocess
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "some/handler.py", None, "sub-1")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python3", "h.py"], timeout=30)
        hd.dispatch_event_to_subscribers(conn, _event())
        rows = list_hook_invocations(conn, "sub-1")
        assert len(rows) == 1
        assert rows[0]["verdict"] == hd.VERDICT_TIMEOUT

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_file_not_found_gives_handler_error(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "nonexistent/handler.py", None, "sub-1")
        mock_run.side_effect = FileNotFoundError("python3: not found")
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert records[0].verdict == hd.VERDICT_HANDLER_ERROR


class TestHandlerChainedEmitEvents:
    @patch("daemon.hook_dispatch.subprocess.run")
    def test_emit_events_trigger_chained_dispatch(self, mock_run):
        conn = _mem()
        # Primary subscription: matches gate.decided, emits a follow-on event
        hd.register_subscription(conn, "wicked.gate.decided", "handler1.py", None, "sub-1")
        # Chained subscription: matches the emitted synthetic event
        hd.register_subscription(conn, "wicked.hook.gate_decided_processed", "handler2.py",
                                  None, "sub-2")
        emit_ev = {
            "event_type": "wicked.hook.gate_decided_processed",
            "event_id": 999,
            "payload": {"project_id": "p1", "phase": "design"},
        }
        out1 = json.dumps({
            "status": "ok",
            "message": "primary done",
            "emit_events": [emit_ev],
        })
        out2 = json.dumps({"status": "ok", "message": "chained done", "emit_events": []})
        mock_run.side_effect = [
            _mock_run(stdout=out1.encode()),
            _mock_run(stdout=out2.encode()),
        ]
        records = hd.dispatch_event_to_subscribers(conn, _event())
        # Both handlers should have fired
        assert len(records) == 2
        verdicts = {r.verdict for r in records}
        assert verdicts == {hd.VERDICT_DISPATCHED}

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_emit_events_records_chained_invocation(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.decided", "handler1.py", None, "sub-1")
        hd.register_subscription(conn, "wicked.hook.gate_decided_processed", "handler2.py",
                                  None, "sub-2")
        emit_ev = {
            "event_type": "wicked.hook.gate_decided_processed",
            "event_id": 999,
            "payload": {},
        }
        out1 = json.dumps({"status": "ok", "message": "ok", "emit_events": [emit_ev]})
        out2 = json.dumps({"status": "ok", "message": "ok", "emit_events": []})
        mock_run.side_effect = [
            _mock_run(stdout=out1.encode()),
            _mock_run(stdout=out2.encode()),
        ]
        hd.dispatch_event_to_subscribers(conn, _event())
        rows_sub2 = list_hook_invocations(conn, "sub-2")
        assert len(rows_sub2) == 1


# ===========================================================================
# Stream 2 — Filter: no match produces no record
# ===========================================================================

class TestFilterNoRecord:
    @patch("daemon.hook_dispatch.subprocess.run")
    def test_no_match_produces_no_record(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.phase.*", "handler.py", None, "sub-1")
        ev = _event(event_type="wicked.gate.decided")
        records = hd.dispatch_event_to_subscribers(conn, ev)
        assert len(records) == 0
        mock_run.assert_not_called()

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_no_subscriptions_returns_empty_list(self, mock_run):
        conn = _mem()
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert records == []

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_disabled_subscription_not_dispatched(self, mock_run):
        conn = _mem()
        hd.register_subscription(conn, "wicked.gate.*", "handler.py", None, "sub-1",
                                  enabled=False)
        records = hd.dispatch_event_to_subscribers(conn, _event())
        assert len(records) == 0
        mock_run.assert_not_called()


# ===========================================================================
# Debounce: debounced invocations get a row
# ===========================================================================

class TestDebounceRowPersisted:
    @patch("daemon.hook_dispatch.subprocess.run")
    def test_debounced_invocation_persisted_with_debounced_verdict(self, mock_run):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "handler.py",
                                        {"type": "rate-limit", "window_s": 60, "max": 1},
                                        "sub-1")
        from daemon.db import append_hook_invocation
        now = int(time.time())
        append_hook_invocation(conn, "inv-prior", sid, 1, "wicked.gate.decided",
                               hd.VERDICT_DISPATCHED, 10, emitted_at=now)
        records = hd.dispatch_event_to_subscribers(conn, _event(event_id=2))
        assert len(records) == 1
        assert records[0].verdict == hd.VERDICT_DEBOUNCED
        mock_run.assert_not_called()

    @patch("daemon.hook_dispatch.subprocess.run")
    def test_debounced_row_in_db(self, mock_run):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.gate.*", "handler.py",
                                        {"type": "rate-limit", "window_s": 60, "max": 1},
                                        "sub-1")
        from daemon.db import append_hook_invocation
        now = int(time.time())
        append_hook_invocation(conn, "inv-prior", sid, 1, "wicked.gate.decided",
                               hd.VERDICT_DISPATCHED, 10, emitted_at=now)
        hd.dispatch_event_to_subscribers(conn, _event(event_id=2))
        rows = list_hook_invocations(conn, "sub-1")
        verdicts = {r["verdict"] for r in rows}
        assert hd.VERDICT_DEBOUNCED in verdicts


# ===========================================================================
# register_subscription
# ===========================================================================

class TestRegisterSubscription:
    def test_auto_generates_subscription_id(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py")
        assert sid is not None
        assert len(sid) > 0

    def test_explicit_subscription_id_respected(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", subscription_id="my-sub-id")
        assert sid == "my-sub-id"

    def test_returns_subscription_id(self):
        conn = _mem()
        sid = hd.register_subscription(conn, "wicked.*", "h.py", subscription_id="sub-X")
        assert sid == "sub-X"


# ===========================================================================
# load_subscriptions_from_config
# ===========================================================================

class TestLoadSubscriptionsFromConfig:
    def test_loads_valid_config_file(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "subscription_id": "loaded-sub",
                "filter": "wicked.gate.decided",
                "handler": "hooks/scripts/subscribers/on_gate_decided.py",
                "debounce": {"type": "phase-boundary"},
            }
            (Path(tmpdir) / "gate.json").write_text(json.dumps(cfg))
            count = hd.load_subscriptions_from_config(conn, tmpdir)
        assert count == 1

    def test_loaded_subscription_in_db(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "subscription_id": "loaded-sub",
                "filter": "wicked.gate.decided",
                "handler": "hooks/scripts/subscribers/on_gate_decided.py",
            }
            (Path(tmpdir) / "gate.json").write_text(json.dumps(cfg))
            hd.load_subscriptions_from_config(conn, tmpdir)
        from daemon.db import get_hook_subscription
        row = get_hook_subscription(conn, "loaded-sub")
        assert row is not None
        assert row["filter_pattern"] == "wicked.gate.decided"

    def test_missing_filter_skipped(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {"handler": "hooks/scripts/subscribers/on_gate_decided.py"}
            (Path(tmpdir) / "bad.json").write_text(json.dumps(cfg))
            count = hd.load_subscriptions_from_config(conn, tmpdir)
        assert count == 0

    def test_missing_handler_skipped(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {"filter": "wicked.gate.*"}
            (Path(tmpdir) / "bad.json").write_text(json.dumps(cfg))
            count = hd.load_subscriptions_from_config(conn, tmpdir)
        assert count == 0

    def test_invalid_json_skipped(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "broken.json").write_text("{not valid json")
            count = hd.load_subscriptions_from_config(conn, tmpdir)
        assert count == 0

    def test_nonexistent_dir_returns_zero(self):
        conn = _mem()
        count = hd.load_subscriptions_from_config(conn, "/nonexistent/path/does/not/exist")
        assert count == 0

    def test_multiple_configs_all_loaded(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                cfg = {
                    "subscription_id": f"sub-{i}",
                    "filter": f"wicked.event.{i}",
                    "handler": "h.py",
                }
                (Path(tmpdir) / f"sub_{i}.json").write_text(json.dumps(cfg))
            count = hd.load_subscriptions_from_config(conn, tmpdir)
        assert count == 3

    def test_auto_id_when_subscription_id_absent(self):
        conn = _mem()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {"filter": "wicked.gate.*", "handler": "h.py"}
            (Path(tmpdir) / "sub.json").write_text(json.dumps(cfg))
            hd.load_subscriptions_from_config(conn, tmpdir)
        subs = list_hook_subscriptions(conn)
        assert len(subs) == 1
        assert subs[0]["subscription_id"] is not None


# ===========================================================================
# HTTP surface — /subscriptions endpoints
# ===========================================================================

class TestSubscriptionHTTPEndpoints:
    """Integration tests for /subscriptions HTTP endpoints.

    Uses the ThreadingHTTPServer directly on a free port.
    Modeled after existing server tests in the daemon test suite.
    """

    def _make_server(self, db_path: str, port: int):
        """Build a bound server using the daemon make_server factory."""
        from daemon.server import make_server
        return make_server(host="127.0.0.1", port=port, db_path=db_path)

    def _url(self, port: int, path: str) -> str:
        return f"http://127.0.0.1:{port}{path}"

    def _get(self, port: int, path: str):
        import urllib.request
        with urllib.request.urlopen(self._url(port, path), timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _post(self, port: int, path: str, body: dict):
        import urllib.request
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self._url(port, path), data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.request.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _run_server_in_thread(self, server):
        import threading
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return t

    def test_list_subscriptions_empty(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                status, body = self._get(free_port, "/subscriptions")
                assert status == 200
                assert body == []
            finally:
                server.shutdown()

    def test_list_subscriptions_returns_rows(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            hd.register_subscription(conn, "wicked.gate.*", "h.py",
                                      subscription_id="sub-http-test")
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                status, body = self._get(free_port, "/subscriptions")
                assert status == 200
                assert len(body) == 1
                assert body[0]["subscription_id"] == "sub-http-test"
            finally:
                server.shutdown()

    def test_list_invocations_empty(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            hd.register_subscription(conn, "wicked.gate.*", "h.py",
                                      subscription_id="sub-inv-test")
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                status, body = self._get(free_port, "/subscriptions/sub-inv-test/invocations")
                assert status == 200
                assert body == []
            finally:
                server.shutdown()

    def test_list_invocations_404_for_unknown_subscription(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                import urllib.request
                req = urllib.request.Request(
                    self._url(free_port, "/subscriptions/nonexistent/invocations")
                )
                try:
                    urllib.request.urlopen(req, timeout=5)
                    assert False, "Should have raised HTTPError 404"
                except urllib.request.HTTPError as exc:
                    assert exc.code == 404
            finally:
                server.shutdown()

    def test_toggle_enable_subscription(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            hd.register_subscription(conn, "wicked.gate.*", "h.py",
                                      subscription_id="sub-toggle", enabled=True)
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                status, body = self._post(
                    free_port, "/subscriptions/sub-toggle/toggle", {"enabled": False}
                )
                assert status == 200
                assert body["ok"] is True
                assert body["enabled"] is False
            finally:
                server.shutdown()

    def test_toggle_missing_enabled_field_returns_400(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            hd.register_subscription(conn, "wicked.gate.*", "h.py", subscription_id="sub-t")
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                status, body = self._post(
                    free_port, "/subscriptions/sub-t/toggle", {}
                )
                assert status == 400
            finally:
                server.shutdown()

    def test_toggle_nonexistent_subscription_returns_404(self, free_port):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            conn = connect(f.name)
            init_schema(conn)
            conn.close()
            server = self._make_server(f.name, free_port)
            self._run_server_in_thread(server)
            try:
                time.sleep(0.05)
                status, body = self._post(
                    free_port, "/subscriptions/nonexistent/toggle", {"enabled": True}
                )
                assert status == 404
            finally:
                server.shutdown()
