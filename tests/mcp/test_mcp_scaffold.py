"""The `wicked-garden-mcp-scaffold` skill: scaffold an MCP server, then prove it answers.

DES-MCP-TOOLS-001 S5b. Proving test: a scaffolded server answers ``initialize`` and
``tools/list`` over stdio, for every template the skill ships. Black-box over the real
scripts (``scripts/mcp/scaffold.py`` writes the server, ``scripts/mcp/probe.py`` speaks
MCP to it) and the real interpreters (``node`` for the Node template, this Python for the
Python one).

Also pinned: the probe derives each tool's class exactly as the crew broker does
(§4.2 — ``readOnlyHint: true`` → read; ``destructiveHint`` absent or true → destructive;
otherwise write; NO annotations → write), a server that never answers fails the probe,
and the scaffold refuses a bad name or an existing file instead of overwriting it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCAFFOLD = REPO / "scripts" / "mcp" / "scaffold.py"
PROBE = REPO / "scripts" / "mcp" / "probe.py"
SKILL = REPO / "skills" / "mcp-scaffold" / "SKILL.md"

TEMPLATES = {
    "node": ("server.mjs", ["node"]),
    "python": ("server.py", [sys.executable]),
}
TIMEOUT_S = 30


def _scaffold(tmp_path: Path, lang: str, name: str = "acme-notes") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), "--name", name, "--lang", lang, "--out", str(tmp_path)],
        capture_output=True, text=True, timeout=TIMEOUT_S,
    )


def _probe(*command: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(PROBE), "--", *command],
        capture_output=True, text=True, timeout=TIMEOUT_S,
    )
    return proc.returncode, json.loads(proc.stdout)


def _server_command(tmp_path: Path, lang: str) -> list[str]:
    filename, interpreter = TEMPLATES[lang]
    return [*interpreter, str(tmp_path / filename)]


@pytest.mark.parametrize("lang", sorted(TEMPLATES))
def test_scaffolded_server_answers_initialize_and_tools_list(tmp_path, lang):
    made = _scaffold(tmp_path, lang)
    assert made.returncode == 0, made.stderr
    report = json.loads(made.stdout)
    assert Path(report["path"]) == tmp_path / TEMPLATES[lang][0]

    code, probed = _probe(*_server_command(tmp_path, lang))

    assert code == 0, probed
    assert probed["ok"] is True
    assert probed["serverInfo"]["name"] == "acme-notes"
    assert probed["protocolVersion"]
    classes = {tool["name"]: tool["class"] for tool in probed["tools"]}
    assert classes == {"echo": "read", "counter_increment": "write"}
    assert probed["warnings"] == []


@pytest.mark.parametrize("lang", sorted(TEMPLATES))
def test_scaffolded_server_serves_calls_and_rejects_unknowns(tmp_path, lang):
    assert _scaffold(tmp_path, lang).returncode == 0
    frames = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "1999-01-01", "capabilities": {},
                    "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": "hi"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "counter_increment", "arguments": {"by": 2}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}},
        {"jsonrpc": "2.0", "id": 5, "method": "no/such/method"},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "echo", "arguments": "oops"}},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": None},
        {"jsonrpc": "2.0", "id": 8, "method": "initialize", "params": []},
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": 7}}},
    ]
    stdin = "".join(json.dumps(f) + "\n" for f in frames)
    proc = subprocess.run(_server_command(tmp_path, lang), input=stdin,
                          capture_output=True, text=True, timeout=TIMEOUT_S)
    replies = {r["id"]: r for r in map(json.loads, proc.stdout.splitlines())}

    assert sorted(replies) == list(range(1, 10)), "a notification must get no reply"
    # An unsupported client version is answered with the server's own latest, not echoed.
    assert replies[1]["result"]["protocolVersion"] != "1999-01-01"
    assert replies[2]["result"]["content"] == [{"type": "text", "text": "hi"}]
    assert replies[3]["result"]["content"] == [{"type": "text", "text": "2"}]
    assert replies[4]["error"]["code"] == -32602
    assert replies[5]["error"]["code"] == -32601
    # Malformed params/arguments are the same -32602 in both templates, never -32603.
    assert [replies[i]["error"]["code"] for i in (6, 7, 8)] == [-32602] * 3
    # A well-formed call with a bad value is a tool error: the caller's turn continues.
    assert replies[9]["result"]["isError"] is True


def test_probe_derives_tool_class_like_the_broker(tmp_path):
    server = tmp_path / "fixture_server.py"
    server.write_text(textwrap.dedent('''
        import json, sys
        TOOLS = [
            {"name": "bare", "inputSchema": {"type": "object"}},
            {"name": "reader", "inputSchema": {"type": "object"},
             "annotations": {"readOnlyHint": True}},
            {"name": "maybe_destroys", "inputSchema": {"type": "object"},
             "annotations": {"readOnlyHint": False}},
            {"name": "writer", "inputSchema": {"type": "object"},
             "annotations": {"readOnlyHint": False, "destructiveHint": False}},
        ]
        for line in sys.stdin:
            msg = json.loads(line)
            if "id" not in msg:
                continue
            if msg["method"] == "initialize":
                result = {"protocolVersion": msg["params"]["protocolVersion"],
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "fixture", "version": "0"}}
            else:
                result = {"tools": TOOLS}
            print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
    '''), encoding="utf-8")

    code, probed = _probe(sys.executable, str(server))

    assert code == 0, probed
    classes = {tool["name"]: tool["class"] for tool in probed["tools"]}
    assert classes == {"bare": "write", "reader": "read",
                       "maybe_destroys": "destructive", "writer": "write"}
    assert any("bare" in w and "write" in w for w in probed["warnings"])


def test_probe_fails_when_the_server_never_answers(tmp_path):
    code, probed = _probe(sys.executable, "-c", "import sys; sys.exit(0)")

    assert code == 1
    assert probed["ok"] is False
    assert probed["error"]


def test_scaffold_refuses_an_existing_file_and_a_bad_name(tmp_path):
    assert _scaffold(tmp_path, "node").returncode == 0
    target = tmp_path / "server.mjs"
    before = target.read_text(encoding="utf-8")

    again = _scaffold(tmp_path, "node")
    bad = _scaffold(tmp_path / "other", "python", name="Bad Name!")

    assert again.returncode != 0 and "exists" in again.stderr
    assert target.read_text(encoding="utf-8") == before
    assert bad.returncode != 0 and "name" in bad.stderr
    assert not (tmp_path / "other").exists()


def test_skill_names_both_scripts_through_the_launcher():
    body = SKILL.read_text(encoding="utf-8")

    assert "wicked-garden run scripts/mcp/scaffold.py" in body
    assert "wicked-garden run scripts/mcp/probe.py" in body
