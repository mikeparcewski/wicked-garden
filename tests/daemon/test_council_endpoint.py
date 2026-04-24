"""tests/daemon/test_council_endpoint.py — Stream 5 HTTP endpoint tests for v8 PR-4.

Tests POST /council, GET /council/<session_id>, GET /councils via http.client
against a real ThreadingHTTPServer running in a background thread.

Scenarios:
1. POST /council with valid body returns CouncilResult envelope
2. POST /council with missing required fields returns 400
3. GET /council/<session_id> returns session + votes for an existing session
4. GET /council/<session_id> returns 404 for unknown session
5. GET /councils returns list; topic_prefix and since filtering work

T1: deterministic — mocked subprocesses, known DB state.
T3: isolated — each test class spins up its own server + in-memory DB.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #594 v8-PR-4 Stream 3.
"""

from __future__ import annotations

import http.client
import json
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from daemon.db import connect, init_schema  # noqa: E402
from daemon.server import make_server  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_process(stdout: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    proc.stderr = ""
    return proc


def _fake_approve_run(argv, capture_output, text, timeout):
    return _make_process(stdout="RECOMMENDATION: APPROVE\nThis is a good idea.")


class _ServerContext:
    """Spin up a ThreadingHTTPServer backed by a temp-file SQLite DB."""

    def __init__(self, port: int):
        self._db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._db_path = self._db_file.name
        self._db_file.close()

        conn = connect(self._db_path)
        init_schema(conn)
        conn.close()

        self.server = make_server("127.0.0.1", port, self._db_path)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        self.port = port
        self.db_path = self._db_path

    def stop(self):
        self.server.shutdown()
        self._thread.join(timeout=5)
        Path(self._db_path).unlink(missing_ok=True)

    def post(self, path: str, body: Any) -> tuple[int, dict]:
        encoded = json.dumps(body).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request(
            "POST", path, body=encoded,
            headers={"Content-Type": "application/json",
                     "Content-Length": str(len(encoded))},
        )
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        return resp.status, data

    def get(self, path: str) -> tuple[int, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", path)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        return resp.status, data


# ---------------------------------------------------------------------------
# Scenario 1: POST /council — valid request
# ---------------------------------------------------------------------------

class TestPostCouncilValid:
    """POST /council with valid body returns 200 and CouncilResult envelope."""

    def test_returns_200_with_session_id(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            with (
                patch("shutil.which", return_value=None),  # all CLIs unavailable — fast path
            ):
                status, data = ctx.post("/council", {
                    "topic": "Should we migrate to PostgreSQL?",
                    "question": "Evaluate migrating from SQLite to PostgreSQL for our production workload.",
                })
            assert status == 200
            assert "session_id" in data
            assert len(data["session_id"]) > 0
        finally:
            ctx.stop()

    def test_returns_raw_votes_key(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            with patch("shutil.which", return_value=None):
                status, data = ctx.post("/council", {
                    "topic": "t", "question": "q",
                })
            assert status == 200
            assert "raw_votes" in data
            assert isinstance(data["raw_votes"], list)
        finally:
            ctx.stop()

    def test_returns_hitl_decision_key(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            with patch("shutil.which", return_value=None):
                status, data = ctx.post("/council", {
                    "topic": "t", "question": "q",
                })
            assert status == 200
            assert "hitl_decision" in data
            assert "pause" in data["hitl_decision"]
        finally:
            ctx.stop()

    def test_cli_list_subset_respected(self, free_port):
        """cli_list in body limits which CLIs are probed."""
        ctx = _ServerContext(free_port)
        try:
            with (
                patch("shutil.which", return_value="/usr/bin/fake"),
                patch("subprocess.run", side_effect=_fake_approve_run),
            ):
                status, data = ctx.post("/council", {
                    "topic": "t", "question": "q",
                    "cli_list": ["gemini"],
                })
            assert status == 200
            assert len(data["raw_votes"]) == 1
            assert data["raw_votes"][0]["model"] == "gemini"
        finally:
            ctx.stop()


# ---------------------------------------------------------------------------
# Scenario 2: POST /council — validation errors
# ---------------------------------------------------------------------------

class TestPostCouncilValidation:
    """POST /council with bad inputs returns 400."""

    def test_missing_topic_returns_400(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            status, data = ctx.post("/council", {"question": "q"})
            assert status == 400
            assert "topic" in data.get("error", "").lower()
        finally:
            ctx.stop()

    def test_missing_question_returns_400(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            status, data = ctx.post("/council", {"topic": "t"})
            assert status == 400
            assert "question" in data.get("error", "").lower()
        finally:
            ctx.stop()

    def test_invalid_cli_list_type_returns_400(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            status, data = ctx.post("/council", {
                "topic": "t", "question": "q",
                "cli_list": "should-be-a-list",
            })
            assert status == 400
        finally:
            ctx.stop()

    def test_invalid_json_body_returns_400(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            encoded = b"not json"
            conn = http.client.HTTPConnection("127.0.0.1", free_port)
            conn.request(
                "POST", "/council", body=encoded,
                headers={"Content-Type": "application/json",
                         "Content-Length": str(len(encoded))},
            )
            resp = conn.getresponse()
            assert resp.status == 400
        finally:
            ctx.stop()


# ---------------------------------------------------------------------------
# Scenario 3: GET /council/<session_id>
# ---------------------------------------------------------------------------

class TestGetCouncilSession:
    """GET /council/<session_id> returns session + votes."""

    def _create_session(self, db_path: str, session_id: str, topic: str):
        conn = connect(db_path)
        from daemon.db import insert_council_session, upsert_council_vote, complete_council_session
        insert_council_session(conn, session_id, topic, "question text", 1_700_000_000)
        upsert_council_vote(conn, session_id, "gemini", "APPROVE", 0.8, "looks good", "full text", 1200, 1_700_000_001)
        upsert_council_vote(conn, session_id, "codex", "APPROVE", 0.9, "agree", "full text", 900, 1_700_000_002)
        complete_council_session(conn, session_id, "APPROVE", 0.9, False, "council.auto-proceed", 1_700_000_010)
        conn.close()

    def test_returns_200_with_votes(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            self._create_session(ctx.db_path, "test-session-get", "test topic")
            status, data = ctx.get("/council/test-session-get")
            assert status == 200
            assert data["id"] == "test-session-get"
            assert data["topic"] == "test topic"
            assert "votes" in data
            assert len(data["votes"]) == 2
        finally:
            ctx.stop()

    def test_vote_shape_contains_expected_fields(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            self._create_session(ctx.db_path, "sess-shape", "topic")
            status, data = ctx.get("/council/sess-shape")
            assert status == 200
            vote = data["votes"][0]
            assert "model" in vote
            assert "verdict" in vote
            assert "rationale" in vote
            assert "latency_ms" in vote
        finally:
            ctx.stop()

    def test_unknown_session_returns_404(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            status, data = ctx.get("/council/nonexistent-session-xyz")
            assert status == 404
        finally:
            ctx.stop()


# ---------------------------------------------------------------------------
# Scenario 4: GET /councils — list and filtering
# ---------------------------------------------------------------------------

class TestListCouncils:
    """GET /councils returns list; topic_prefix and since filtering work."""

    def _insert_session(self, db_path, session_id, topic, started_at):
        conn = connect(db_path)
        from daemon.db import insert_council_session
        insert_council_session(conn, session_id, topic, "q", started_at)
        conn.close()

    def test_returns_empty_list_when_no_sessions(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            status, data = ctx.get("/councils")
            assert status == 200
            assert data == []
        finally:
            ctx.stop()

    def test_returns_all_sessions(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            self._insert_session(ctx.db_path, "s1", "arch", 1_000)
            self._insert_session(ctx.db_path, "s2", "db", 2_000)
            status, data = ctx.get("/councils")
            assert status == 200
            assert len(data) == 2
        finally:
            ctx.stop()

    def test_topic_prefix_filter(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            self._insert_session(ctx.db_path, "t1", "arch: event sourcing", 1_000)
            self._insert_session(ctx.db_path, "t2", "db: postgres vs sqlite", 2_000)
            status, data = ctx.get("/councils?topic_prefix=arch%3A")
            assert status == 200
            assert len(data) == 1
            assert data[0]["topic"].startswith("arch:")
        finally:
            ctx.stop()

    def test_since_filter(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            self._insert_session(ctx.db_path, "e1", "topic", 500)
            self._insert_session(ctx.db_path, "e2", "topic", 1_500)
            self._insert_session(ctx.db_path, "e3", "topic", 2_500)
            status, data = ctx.get("/councils?since=1000")
            assert status == 200
            started_ats = {d["started_at"] for d in data}
            assert 500 not in started_ats
            assert 1_500 in started_ats
            assert 2_500 in started_ats
        finally:
            ctx.stop()

    def test_invalid_limit_returns_400(self, free_port):
        ctx = _ServerContext(free_port)
        try:
            status, data = ctx.get("/councils?limit=notanumber")
            assert status == 400
        finally:
            ctx.stop()
