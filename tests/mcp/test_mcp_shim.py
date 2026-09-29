"""The `wicked-garden-mcp` skill's shim: a governed worker reaches MCP tools only through the broker.

DES-MCP-TOOLS-001 S4. Black-box over the real script (``scripts/mcp/shim.py``) and a local HTTP
server that answers exactly as wicked-crew's broker does (``POST /api/v1/mcp/tools`` and
``POST /api/v1/mcp/call``, the status codes and bodies of ``src/mcp/broker.ts``). The end-to-end
proof against the real broker and a real unit's token lives in wicked-crew
(``tests/integration/mcp-shim-e2e.test.ts``), where only core's carriers can mint a token.

Pinned here:
- ``list`` and ``call`` send the unit's token and the request, and print the broker's answer;
- every outcome maps to its exit code, so a worker can tell a blocked call (continue without
  it) from one waiting for approval (do not retry) from a broken channel;
- outside a governed unit (no token or no broker URL) nothing is sent and the shim says why;
- bad arguments are refused before anything is sent;
- the token never appears in the shim's output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SHIM = REPO / "scripts" / "mcp" / "shim.py"
SKILL = REPO / "skills" / "mcp" / "SKILL.md"
TOKEN = "wmt_0123456789abcdef0123456789abcdef"
TIMEOUT_S = 30

# The broker's answers, keyed by subject (status, body): src/mcp/broker.ts OUTCOME_STATUS.
CALL_ANSWERS = {
    "mcp:fx/echo": (200, {"outcome": "ok", "subject": "mcp:fx/echo", "callId": "c1",
                          "result": {"content": [{"type": "text", "text": "hi"}]}, "ruleIds": []}),
    "mcp:fx/note": (403, {"outcome": "denied", "subject": "mcp:fx/note", "callId": "c2", "denied": True,
                          "ruleIds": ["engine:mcp-phase-role"], "reason": "an evaluator phase never writes",
                          "remedy": "report it instead"}),
    "mcp:fx/new": (409, {"outcome": "pending_approval", "subject": "mcp:fx/new", "callId": "c3",
                         "pending_approval": "mcp:fx/new", "ruleIds": ["MCP-FIRST-USE"]}),
    "mcp:fx/out": (403, {"outcome": "withheld", "subject": "mcp:fx/out", "callId": "c4", "denied": True, "ruleIds": ["OUT-NO"]}),
    "mcp:fx/spent": (429, {"outcome": "budget_exhausted", "subject": "mcp:fx/spent", "callId": "c5", "ruleIds": []}),
    "mcp:fx/open": (503, {"outcome": "breaker_open", "subject": "mcp:fx/open", "callId": "c6", "ruleIds": []}),
    "mcp:fx/down": (502, {"outcome": "upstream_error", "subject": "mcp:fx/down", "callId": "c7", "ruleIds": []}),
    "mcp:fx/guard": (500, {"outcome": "guard_error", "subject": "mcp:fx/guard", "callId": None, "ruleIds": []}),
}
TOOLS = {"unit": {"runId": "r1", "ord": 2, "attempt": 0, "phase": "unit-2", "seat": "pi"},
         "tools": [{"subject": "mcp:fx/echo", "class": "read", "decision": "allow", "ruleIds": [],
                    "description": "echo", "inputSchema": {"type": "object"}}]}


class FakeBroker(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):  # noqa: N802 (http.server's name)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeBroker.received.append((self.path, body))
        if body.get("token") != TOKEN:
            status, answer = 401, {"error": "invalid_token: the MCP token is not bound to a running unit",
                                   "code": "invalid_token"}
        elif self.path == "/api/v1/mcp/tools":
            status, answer = 200, TOOLS
        elif self.path == "/api/v1/mcp/call":
            status, answer = CALL_ANSWERS[body["subject"]]
        else:
            status, answer = 404, {"error": "no route"}
        raw = json.dumps(answer).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        pass


@pytest.fixture()
def broker():
    FakeBroker.received = []
    server = HTTPServer(("127.0.0.1", 0), FakeBroker)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _shim(*args: str, url: str | None, token: str | None = TOKEN, stdin: str | None = None) -> tuple[int, dict, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("WICKED_MCP_TOKEN", "WICKED_CREW_URL")}
    if url is not None:
        env["WICKED_CREW_URL"] = url
    if token is not None:
        env["WICKED_MCP_TOKEN"] = token
    proc = subprocess.run([sys.executable, str(SHIM), *args], capture_output=True, text=True,
                          env=env, input=stdin, timeout=TIMEOUT_S)
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1, f"one JSON object on stdout, got: {proc.stdout!r} (stderr {proc.stderr!r})"
    return proc.returncode, json.loads(lines[0]), proc.stdout + proc.stderr


def test_list_sends_the_token_and_prints_the_units_tools(broker):
    code, out, raw = _shim("list", url=broker)
    assert code == 0
    assert out == TOOLS
    assert FakeBroker.received == [("/api/v1/mcp/tools", {"token": TOKEN})]
    assert TOKEN not in raw


def test_call_sends_subject_and_args_and_prints_the_result(broker):
    code, out, raw = _shim("call", "mcp:fx/echo", "--args", '{"text": "hi"}', url=broker)
    assert code == 0
    assert out["outcome"] == "ok"
    assert out["result"]["content"][0]["text"] == "hi"
    assert FakeBroker.received == [("/api/v1/mcp/call", {"token": TOKEN, "subject": "mcp:fx/echo", "args": {"text": "hi"}})]
    assert TOKEN not in raw


@pytest.mark.parametrize("subject,exit_code", [
    ("mcp:fx/note", 3), ("mcp:fx/out", 3), ("mcp:fx/new", 4),
    ("mcp:fx/spent", 5), ("mcp:fx/open", 5), ("mcp:fx/down", 5), ("mcp:fx/guard", 1),
])
def test_each_refusal_has_its_exit_code_and_the_brokers_reason(broker, subject, exit_code):
    code, out, raw = _shim("call", subject, url=broker)
    assert code == exit_code
    assert out == CALL_ANSWERS[subject][1]
    assert TOKEN not in raw


def test_a_subject_without_the_prefix_and_args_from_stdin_are_accepted(broker):
    code, out, _ = _shim("call", "fx/echo", "--args-file", "-", url=broker, stdin='{"text": "hi"}')
    assert code == 0
    assert FakeBroker.received[0][1]["subject"] == "mcp:fx/echo"
    assert FakeBroker.received[0][1]["args"] == {"text": "hi"}


def test_a_token_the_broker_does_not_know_fails_without_echoing_it(broker):
    code, out, raw = _shim("list", url=broker, token="wmt_forged_token_value")
    assert code == 1
    assert out["status"] == 401 and out["code"] == "invalid_token"
    assert "wmt_forged_token_value" not in raw


@pytest.mark.parametrize("url,token", [(None, TOKEN), ("http://127.0.0.1:9", None), (None, None)])
def test_outside_a_governed_unit_nothing_is_sent(url, token):
    code, out, _ = _shim("list", url=url, token=token)
    assert code == 2
    assert out["code"] == "no_mcp_channel"
    assert "governed" in out["reason"]


@pytest.mark.parametrize("args", [
    ("call", "mcp:fx/echo", "--args", "[1, 2]"),
    ("call", "mcp:fx/echo", "--args", "{not json"),
    ("call", "mcp:fx", "--args", "{}"),
    ("call", "mcp:fx/echo", "--args", "{}", "--args-file", "-"),
])
def test_bad_arguments_are_refused_before_anything_is_sent(broker, args):
    code, out, _ = _shim(*args, url=broker)
    assert code == 2
    assert out["code"] == "bad_request"
    assert FakeBroker.received == []


def test_an_unreachable_broker_is_a_failure_not_a_result():
    code, out, raw = _shim("list", url="http://127.0.0.1:9", token=TOKEN)
    assert code == 1
    assert out["code"] == "broker_unreachable"
    assert TOKEN not in raw


def test_the_skill_names_the_command_and_the_exit_codes():
    text = SKILL.read_text(encoding="utf-8")
    assert "wicked-garden run scripts/mcp/shim.py list" in text
    assert "wicked-garden run scripts/mcp/shim.py call" in text
    for code in ("`0`", "`2`", "`3`", "`4`", "`5`", "`1`"):
        assert code in text, code
