"""tests/test_estate_client_broker.py — the estate shim's broker relay (wicked-core#1018).

A seat on wicked-crew's container floor has no estate of its own (no store is mounted, no
`wicked-estate-mcp` is installed, no store pin reaches it). It holds crew's broker channel
(`WICKED_CREW_URL` + a unit-bound `WICKED_MCP_TOKEN`), and wicked-core marks it with
`WICKED_ESTATE_BROKER=1`. These tests pin that the shim then relays every call through
`POST /api/v1/mcp/call` as `mcp:estate/<tool>`, with no caller change, and that it still fails
closed, with a reason, when a governed unit has neither a pinned store nor the channel.

A real HTTP server on loopback plays the broker (stdlib `http.server`); no estate binary runs.
"""

import io
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

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
    _estate_client._set_broker_refusal(None)  # never leaks into the next test's output
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
    assert "no code graph" in _estate_client._get_broker_refusal()
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
    assert "did not answer" in (_estate_client._get_broker_refusal() or "")
    assert _estate_client.propose("memory", {"content": "x"}, {"project": "p"})["code"] is None


@pytest.fixture()
def dead_relay(monkeypatch):
    _container_seat(monkeypatch, "http://broker.invalid")
    _no_local_spawn(monkeypatch)

    def unreachable(*args, **kwargs):
        raise _estate_client.urllib.error.URLError("relay offline")

    monkeypatch.setattr(_estate_client.urllib.request, "urlopen", unreachable)


@pytest.mark.parametrize("method", ["search", "context"])
def test_unreachable_relay_graph_consumers_raise(dead_relay, method):
    with pytest.raises(_estate_client.EstateUnavailable, match="did not answer"):
        getattr(_estate_client, method)("x")
    assert _estate_client.last_failure() == {
        "kind": "unavailable", "reason": _estate_client._get_broker_refusal()}


@pytest.mark.parametrize("action", ["search", "context"])
def test_cli_unreachable_relay_graph_consumers_fail(dead_relay, capsys, action):
    code = _estate_client.main([action, '{"query":"x"}'])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["ok"] is False
    assert "did not answer" in out["reason"]


def test_cli_unreachable_relay_call_keeps_its_empty_contract(dead_relay, capsys):
    assert _estate_client.main(["call", '{"tool":"SearchEntity"}']) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["result"] is None
    assert "did not answer" in out["broker_refusal"]


def test_unreachable_relay_without_a_reason_records_generic_failure(dead_relay, monkeypatch):
    monkeypatch.setattr(_estate_client, "_broker_post", lambda *args: (None, None, None))
    with pytest.raises(_estate_client.EstateUnavailable, match="no handshake"):
        _estate_client.search("x")
    assert _estate_client.last_failure()["kind"] == "unavailable"


def test_overlapping_relay_failures_keep_each_threads_reason(monkeypatch):
    _container_seat(monkeypatch, "http://broker.invalid")
    _no_local_spawn(monkeypatch)
    first_refused = threading.Barrier(2, timeout=5)
    second_refused = threading.Barrier(2, timeout=5)
    broker_dispatch = _estate_client._broker_dispatch
    reasons = {"first": "relay failure X", "second": "relay failure Y"}

    def post(url, body, timeout):
        return None, None, reasons[body["args"]["name"]]

    def overlapping_dispatch(requests, *, db, timeout):
        name = requests[-1]["params"]["arguments"]["name"]
        # Hold A before _rpc reads its refusal until B has reset/set its own reason Y.
        if name == "second":
            first_refused.wait()
        responses = broker_dispatch(requests, db=db, timeout=timeout)
        if name == "first":
            first_refused.wait()
        second_refused.wait()
        return responses

    monkeypatch.setattr(_estate_client, "_broker_post", post)
    monkeypatch.setattr(_estate_client, "_broker_dispatch", overlapping_dispatch)

    def read(name):
        result = _estate_client.call("SearchEntity", {"name": name})
        return result, _estate_client.last_failure(), _estate_client._get_broker_refusal()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(read, "first")
        second = pool.submit(read, "second")
        outcomes = {"first": first.result(timeout=10), "second": second.result(timeout=10)}

    for name, reason in reasons.items():
        assert outcomes[name] == (None, {"kind": "unavailable", "reason": reason}, reason)


@pytest.mark.parametrize("tool", ["SearchEntity", "rules.recall"])
def test_unresolved_relay_names_the_runs_graph(monkeypatch, tool):
    _container_seat(monkeypatch, "http://broker.invalid")
    monkeypatch.setenv("WICKED_ESTATE_DB", ":memory:")
    if tool == "rules.recall":
        # On a pinned host seat this tool still relays: the tool must select the transport.
        monkeypatch.delenv(_estate_client.BROKER_ENV)
        monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "fake-estate-mcp")
    blocks = _estate_client.flag_unresolved(
        {"result": {"resolved": False}, "diagnostics": []}, tool=tool)
    line, = blocks["diagnostics"]
    assert "Store searched: the run's own graph (answered by crew's broker)" in line
    assert ":memory:" not in line
    assert "--db" not in line


@pytest.mark.parametrize("all_pages", [False, True])
def test_cli_unresolved_relay_names_the_runs_graph(monkeypatch, capsys, all_pages):
    _container_seat(monkeypatch, "http://broker.invalid")
    monkeypatch.setattr(_estate_client, "_broker_post", lambda *args: (200, {
        "outcome": "ok", "result": {"content": [
            {"type": "text", "text": '{"resolved":false}'}]}}, None))
    assert _estate_client.main(["call", json.dumps({
        "tool": "BlastRadius", "all_pages": all_pages})]) == 0
    out = json.loads(capsys.readouterr().out)
    line, = out["diagnostics"]
    assert "Store searched: the run's own graph (answered by crew's broker)" in line
    assert "--db" not in line


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


def test_a_pinned_host_seat_relays_the_visible_filtered_knowledge_reads(monkeypatch, broker):
    """DES-KNOWLEDGE-DATA-001 §4.3: only crew knows what the unit may see, so knowledge.recall,
    source_catalog and neighbors relay whenever the channel is there; everything else stays local."""
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    monkeypatch.setenv("WICKED_ESTATE_DB", "/srv/x.db")
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "wicked-estate-mcp")
    _no_local_spawn(monkeypatch)
    assert _estate_client.use_broker() is False
    broker.answer = lambda subject, args: (200, {"outcome": "ok", "subject": subject, "callId": "c", "ruleIds": [],
                                                 "result": {"content": [{"type": "text", "text": json.dumps({"items": [{"node_id": "k"}]})}]}})
    assert _estate_client.is_governed() is True
    required = {"knowledge.recall": {"query": "open tickets"},
                "knowledge.source_catalog": {"sourceId": "3f0c"},
                "knowledge.neighbors": {"id": "kdoc synthetic source:3f0c/support.tickets:"}}
    assert set(_estate_client.VISIBLE_TOOLS) == set(required)
    for tool, args in required.items():
        assert _estate_client.use_broker_for(tool) is True
        assert _estate_client.transport_name(tool) == "broker"
        assert _estate_client.call(tool, args) == {"items": [{"node_id": "k"}]}
        assert broker.seen[-1][1]["subject"] == f"mcp:estate/{tool}"
        assert broker.seen[-1][1]["args"] == args
        assert tool in _estate_client.BROKER_TOOLS
    assert _estate_client.use_broker_for("SearchEntity") is False
    assert _estate_client.transport_name() == "local"


def test_a_pinned_host_seat_pulls_the_rules_in_force_from_crew(monkeypatch, broker):
    """ctx-pull: a host seat's local store is the run's code graph, which holds no steering rules, so
    `rules.recall` in a governed unit goes to crew, which answers the set the rule judge reads."""
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    monkeypatch.setenv("WICKED_ESTATE_DB", "/srv/run/code-graph.db")
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "wicked-estate-mcp")
    _no_local_spawn(monkeypatch)
    assert _estate_client.use_broker() is False  # a host seat: everything else stays local
    rules = {"rules": [{"id": "POL-2500", "statement": "the whole statement"}], "returned": 1, "total": 1,
             "missing": ["nope"], "source": "considerRules"}
    broker.answer = lambda subject, args: (200, {"outcome": "ok", "subject": subject, "callId": "c", "ruleIds": [],
                                                 "result": {"content": [{"type": "text", "text": json.dumps(rules)}], "isError": False}})
    assert _estate_client.RULES_TOOL in _estate_client.CREW_ANSWERED_TOOLS
    assert _estate_client.transport_name("rules.recall") == "broker"
    assert _estate_client.call("rules.recall", {"ids": ["POL-2500", "nope"]}) == rules
    assert broker.seen[-1][1]["subject"] == "mcp:estate/rules.recall"
    assert broker.seen[-1][1]["args"] == {"ids": ["POL-2500", "nope"]}
    assert _estate_client.transport_name("SearchEntity") == "local"


def test_a_governed_seat_without_the_channel_never_reads_rules_from_its_local_store(monkeypatch, capsys):
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    monkeypatch.setenv("WICKED_ESTATE_DB", "/srv/run/code-graph.db")
    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "wicked-estate-mcp")
    _no_local_spawn(monkeypatch)
    assert _estate_client.call("rules.recall", {"ids": ["POL-2500"]}) is None
    assert "only crew answers rules.recall" in (_estate_client._get_broker_refusal() or "")
    code = _estate_client.main(["--readonly", "call", json.dumps({"tool": "rules.recall", "arguments": {"ids": ["POL-2500"]}})])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0 and out["result"] is None and "no broker channel" in out["broker_refusal"]


def test_outside_a_run_rules_recall_stays_local(monkeypatch, broker):
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    assert _estate_client.use_broker_for("rules.recall") is False


def test_outside_a_run_the_visible_reads_stay_local(monkeypatch, broker):
    monkeypatch.setenv(_estate_client.CREW_URL_ENV, broker.url)
    monkeypatch.setenv(_estate_client.MCP_TOKEN_ENV, "wmt_good")
    assert _estate_client.is_governed() is False
    assert _estate_client.use_broker() is False
    for tool in ("knowledge.recall", "knowledge.source_catalog", "knowledge.neighbors"):
        assert _estate_client.use_broker_for(tool) is False


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


def test_cli_relay_tool_errors_keep_their_failure_output(monkeypatch, capsys):
    _container_seat(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setattr(_estate_client, "_broker_post", lambda *args: (200, {
        "outcome": "ok", "result": {"isError": True, "content": [
            {"type": "text", "text": "tool failed"},
            {"type": "text", "text": "CLAMPED: limit=200"},
        ]}}, None))
    assert _estate_client.main(["call", '{"tool":"SearchEntity"}']) == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": "tool failed", "diagnostics": ["CLAMPED: limit=200"]}


def test_persistent_start_reports_stderr_tempfile_failure(monkeypatch):
    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "fake-estate-mcp")

    def cannot_capture(**kwargs):
        raise OSError("temporary storage full")

    monkeypatch.setattr(_estate_client.tempfile, "TemporaryFile", cannot_capture)
    persistent = _estate_client._PersistentBroker()
    assert persistent._start(None) is False
    assert _estate_client.last_failure() == {
        "kind": "unavailable",
        "reason": "estate did not start: cannot capture estate stderr: temporary storage full",
    }


def test_persistent_start_failure_survives_unreadable_stderr():
    class UnreadableStderr(io.StringIO):
        def read(self, *args):
            raise OSError("stderr file unreadable")

    stderr = UnreadableStderr()
    proc = SimpleNamespace(kill=lambda: None, wait=lambda **kwargs: None)
    persistent = _estate_client._PersistentBroker()
    _estate_client._set_failure(None)
    persistent._start_failed(proc, stderr)
    assert stderr.closed
    assert _estate_client.last_failure() == {
        "kind": "unavailable",
        "reason": "estate did not start: no handshake (binary missing, timed out, or exited)",
    }


def test_persistent_failed_retry_closes_process_and_stderr(monkeypatch):
    persistent = _estate_client._PersistentBroker()
    sessions = []

    def start(db):
        proc = SimpleNamespace(stdin=io.StringIO(), poll=lambda: None, wait=lambda **kwargs: None)
        stderr = io.StringIO()
        sessions.append((proc, stderr))
        persistent._proc = proc
        persistent._stderr = stderr
        persistent._init_resp = {"id": 1, "result": {"serverInfo": {"name": "wicked-estate"}}}
        return True

    monkeypatch.setattr(persistent, "_start", start)
    monkeypatch.setattr(persistent, "_exchange", lambda *args, **kwargs: None)
    try:
        assert persistent([{"id": 2, "method": "tools/call"}], db=None, timeout=1) == {}
        assert persistent._failed is True
        assert len(sessions) == 2
        assert all(proc.stdin.closed and stderr.closed for proc, stderr in sessions)
        assert persistent._proc is None and persistent._stderr is None
    finally:
        persistent._close()
