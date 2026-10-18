"""tests/test_estate_client_broker.py — the estate shim's broker relay (wicked-core#1018).

A seat on wicked-crew's container floor has no estate of its own (no store is mounted, no
`wicked-estate-mcp` is installed, no store pin reaches it). It holds crew's broker channel
(`WICKED_CREW_URL` + a unit-bound `WICKED_MCP_TOKEN`), and wicked-core marks it with
`WICKED_ESTATE_BROKER=1`. These tests pin that the shim then relays every call through
`POST /api/v1/mcp/call` as `mcp:estate/<tool>`, with no caller change, and that it still fails
closed, with a reason, when a governed unit has neither a pinned store nor the channel.

A real HTTP server on loopback plays the broker (stdlib `http.server`); no estate binary runs.
"""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import _estate_client

_ENV = (
    _estate_client.GOVERNED_MARKERS
    + (_estate_client.GOVERNED_ENV, _estate_client.READONLY_ENV)
    + _estate_client.STORE_PIN_ENV
    + (_estate_client.RUN_PROJECT_ENV, _estate_client.BROKER_ENV,
       _estate_client.CREW_URL_ENV, _estate_client.MCP_TOKEN_ENV)
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "_estate_client.py"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    original = _estate_client._active_dispatch
    _estate_client.set_readonly(False)
    _estate_client.set_governed(False)
    _estate_client.set_db(None)
    yield
    _estate_client.set_dispatch(original)
    _estate_client.set_readonly(False)
    _estate_client.set_governed(False)
    _estate_client.set_db(None)


class FakeBroker:
    """Answers `/api/v1/mcp/call` and `/api/v1/mcp/tools` from `self.answer(subject, args)`."""

    def __init__(self):
        self.seen: list = []
        self.answer = lambda subject, args: (200, {
            "outcome": "ok", "subject": subject, "callId": "c1", "ruleIds": [],
            "result": {"content": [{"type": "text", "text": json.dumps({"matches": [{"name": "arm"}]})},
                                   {"type": "text", "text": "STALENESS: 0 commits behind"}],
                       "isError": False}})
        broker = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 — http.server's spelling
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
                broker.seen.append((self.path, body))
                if self.path == "/api/v1/mcp/tools":
                    status, out = (200, {"unit": {}, "tools": []}) if body.get("token") == "wmt_good" \
                        else (401, {"error": "invalid_token: not bound", "code": "invalid_token"})
                else:
                    status, out = broker.answer(body.get("subject"), body.get("args"))
                raw = json.dumps(out).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def broker():
    b = FakeBroker()
    yield b
    b.close()


def _container_seat(monkeypatch, url, token="wmt_good"):
    """The env wicked-core hands a container seat: run markers, the channel, the relay marker."""
    monkeypatch.setenv("WICKED_RUN_ID", "run-b445")
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, token)
    monkeypatch.setenv(_estate_client.BROKER_ENV, "1")


def _no_local_spawn(monkeypatch):
    """Any attempt to spawn a local estate fails the test."""
    def boom(*a, **k):
        raise AssertionError("a relayed call must never spawn a local wicked-estate-mcp")
    monkeypatch.setattr(_estate_client.subprocess, "Popen", boom)


def test_a_container_seat_relays_a_lookup_and_keeps_its_diagnostics(monkeypatch, broker):
    _container_seat(monkeypatch, broker.url)
    _no_local_spawn(monkeypatch)
    assert _estate_client.transport_name() == "broker"
    assert _estate_client.governed_refusal() is None
    got = _estate_client.call_blocks("SearchEntity", {"name": "arm"})
    assert got == {"result": {"matches": [{"name": "arm"}]}, "diagnostics": ["STALENESS: 0 commits behind"]}
    path, body = broker.seen[-1]
    assert path == "/api/v1/mcp/call"
    assert body == {"token": "wmt_good", "subject": "mcp:estate/SearchEntity", "args": {"name": "arm"}}


def test_the_skills_wrappers_work_unchanged_through_the_relay(monkeypatch, broker):
    _container_seat(monkeypatch, broker.url)
    _no_local_spawn(monkeypatch)
    assert _estate_client.search("arm") == [{"name": "arm"}]
    broker.answer = lambda subject, args: (200, {"outcome": "ok", "subject": subject, "callId": "c", "ruleIds": [],
                                                 "result": {"content": [{"type": "text", "text": json.dumps({"items": [{"memory_id": "m1"}]})}]}})
    assert _estate_client.recall("container floor", scope_prefix="") == [{"memory_id": "m1"}]
    assert broker.seen[-1][1]["subject"] == "mcp:estate/memory.recall"


def test_a_proposal_lands_through_the_relay_and_keeps_its_shape_error_code(monkeypatch, broker):
    _container_seat(monkeypatch, broker.url)
    monkeypatch.setenv(_estate_client.RUN_PROJECT_ENV, "proj_abc")
    _no_local_spawn(monkeypatch)
    broker.answer = lambda subject, args: (200, {"outcome": "ok", "subject": subject, "callId": "c", "ruleIds": [],
                                                 "result": {"content": [{"type": "text", "text": json.dumps({"id": "prop-1"})}], "isError": False}})
    assert _estate_client.propose("memory", {"content": "x", "tier": "semantic"}) == {"ok": True, "id": "prop-1"}
    assert broker.seen[-1][1]["subject"] == "mcp:estate/proposal.submit"
    assert broker.seen[-1][1]["args"]["facets"] == {"project": "proj_abc"}
    rpc = {"code": -32602, "message": "invalid memory tier"}
    broker.answer = lambda subject, args: (200, {"outcome": "ok", "subject": subject, "callId": "c", "ruleIds": [],
                                                 "result": {"content": [{"type": "text", "text": rpc["message"]}], "isError": True, "rpcError": rpc}})
    assert _estate_client.propose("memory", {"content": "x", "tier": "durable"}) == {
        "ok": False, "reason": "invalid memory tier", "code": -32602}


def test_a_broker_refusal_is_empty_and_says_why(monkeypatch, broker):
    _container_seat(monkeypatch, broker.url)
    _no_local_spawn(monkeypatch)
    broker.answer = lambda subject, args: (403, {
        "outcome": "denied", "subject": subject, "callId": "c", "ruleIds": ["estate:no-code-graph"], "denied": True,
        "reason": "this run has no code graph", "remedy": "continue without graph lookups"})
    assert _estate_client.call("RankHotspots", {"limit": 20}) is None
    assert "no code graph" in _estate_client._last_broker_refusal
    res = _estate_client.propose("memory", {"content": "x"}, {"project": "p"})
    assert res["ok"] is False and res["code"] is None and "broker denied" in res["reason"]


def test_health_asks_the_broker_and_spends_no_call(monkeypatch, broker):
    _container_seat(monkeypatch, broker.url)
    _no_local_spawn(monkeypatch)
    assert _estate_client.health() is True
    assert [p for p, _ in broker.seen] == ["/api/v1/mcp/tools"]
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_revoked")
    assert _estate_client.health() is False


def test_an_unreachable_broker_degrades_with_a_reason(monkeypatch):
    _container_seat(monkeypatch, "http://127.0.0.1:9")  # discard port: nothing listens
    _no_local_spawn(monkeypatch)
    assert _estate_client.call("SearchEntity", {"name": "x"}) is None
    assert "did not answer" in (_estate_client._last_broker_refusal or "")
    assert _estate_client.propose("memory", {"content": "x"}, {"project": "p"})["code"] is None


def test_an_unpinned_governed_unit_with_the_channel_relays_even_without_the_marker(monkeypatch, broker):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    _no_local_spawn(monkeypatch)
    assert _estate_client.use_broker() is True
    assert _estate_client.call("SearchEntity", {"name": "arm"}) == {"matches": [{"name": "arm"}]}


def test_a_pinned_host_seat_with_a_local_estate_keeps_the_local_spawn(monkeypatch, broker):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    monkeypatch.setenv("WICKED_ESTATE_DB", "/srv/x.db")
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "wicked-estate-mcp")
    assert _estate_client.use_broker() is False
    assert _estate_client.transport_name() == "local"


def test_outside_a_run_the_channel_alone_never_relays(monkeypatch, broker):
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    monkeypatch.setenv(_estate_client.BROKER_ENV, "1")
    assert _estate_client.use_broker() is False


def test_neither_a_pin_nor_the_channel_still_fails_closed_and_names_both_fixes(monkeypatch, tmp_path):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    monkeypatch.setenv(_estate_client.BROKER_ENV, "1")  # a marker without the channel is not a channel
    monkeypatch.chdir(tmp_path)
    _no_local_spawn(monkeypatch)
    reason = _estate_client.governed_refusal()
    assert reason and "WICKED_RUN_ID" in reason
    assert _estate_client.CREW_URL_ENV in reason and _estate_client.MCP_TOKEN_ENV in reason
    assert _estate_client.transport_name() is None
    assert _estate_client.call("SearchEntity", {"name": "x"}) is None


def test_the_cli_reports_the_relay_and_why_a_call_came_back_empty(broker, tmp_path):
    env = {k: v for k, v in __import__("os").environ.items() if k not in _ENV}
    env.update({"WICKED_RUN_ID": "run-b445", _estate_client.CREW_URL_ENV: broker.url,
                _estate_client.MCP_TOKEN_ENV: "wmt_good", _estate_client.BROKER_ENV: "1",
                "WICKED_ESTATE_PERSISTENT": "0"})
    mode = json.loads(subprocess.run([sys.executable, str(SCRIPT), "mode"], env=env, cwd=tmp_path,
                                     capture_output=True, text=True, check=True).stdout)
    assert mode["transport"] == "broker" and mode["broker"] is True and mode["refusal"] is None
    out = json.loads(subprocess.run(
        [sys.executable, str(SCRIPT), "--readonly", "call", '{"tool":"SearchEntity","arguments":{"name":"arm"}}'],
        env=env, cwd=tmp_path, capture_output=True, text=True, check=True).stdout)
    assert out["result"] == {"matches": [{"name": "arm"}]}
    assert out["diagnostics"] == ["STALENESS: 0 commits behind"]
    assert "broker_refusal" not in out
    broker.answer = lambda subject, args: (403, {"outcome": "denied", "subject": subject, "callId": "c",
                                                 "ruleIds": ["estate:not-relayed"], "reason": "not relayed"})
    out = json.loads(subprocess.run(
        [sys.executable, str(SCRIPT), "--readonly", "call", '{"tool":"memory.capture","arguments":{}}'],
        env=env, cwd=tmp_path, capture_output=True, text=True, check=True).stdout)
    assert out["result"] is None and "not relayed" in out["broker_refusal"]
