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
import os
import re
import shutil
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


# ── The TypeScript template (fastmcp + OpenTelemetry + loglayer) ─────────────────────────────

TS_SCRIPTS = {"build", "typecheck", "lint", "test", "start"}
SPDX_LINE = "// SPDX-License-Identifier: MIT"


def _scaffold_ts(out: Path, name: str = "acme-notes", *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), "--name", name, "--out", str(out), *extra],
        capture_output=True, text=True, timeout=TIMEOUT_S,
    )


def test_typescript_is_the_default_and_stamps_the_name(tmp_path):
    made = _scaffold_ts(tmp_path)
    assert made.returncode == 0, made.stderr
    report = json.loads(made.stdout)

    assert report["lang"] == "typescript"
    assert report["envNames"] == ["ACME_NOTES_TOKEN"]
    assert report["run"] == "npm install && npm run build && node dist/server.js"
    assert report["probe"].startswith("wicked-garden run scripts/mcp/probe.py --env ACME_NOTES_TOKEN -- node ")
    assert report["probe"].endswith(f'"{tmp_path / "dist" / "server.js"}"')
    package = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "acme-notes"
    assert TS_SCRIPTS <= set(package["scripts"])
    assert package["engines"]["node"].startswith(">=22")
    assert package["type"] == "module"
    assert set(package["files"]) == {"dist", "tools.json", "mcp-server.config.json"}
    config = json.loads((tmp_path / "mcp-server.config.json").read_text(encoding="utf-8"))
    assert config["key"] == "acme-notes" and config["version"] == "0.1.0"
    assert config["auth"]["scheme"] == "bearer"
    assert json.loads((tmp_path / "tools.json").read_text(encoding="utf-8")) == {"tools": []}
    assert "__SERVER_NAME__" not in (tmp_path / "src" / "server.ts").read_text(encoding="utf-8")
    assert "acme-notes" in (tmp_path / "src" / "server.ts").read_text(encoding="utf-8")
    assert (tmp_path / ".gitignore").is_file() and (tmp_path / ".env.example").is_file()
    assert "ACME_NOTES_TOKEN=" in (tmp_path / ".env.example").read_text(encoding="utf-8")


def test_typescript_files_carry_spdx_and_no_placeholder_or_secret(tmp_path):
    assert _scaffold_ts(tmp_path).returncode == 0
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    ts_files = [p for p in files if p.suffix == ".ts"]
    assert len(ts_files) >= 10
    env_names = [line.split("=", 1)[0].lstrip("# ").strip()
                 for line in (tmp_path / ".env.example").read_text(encoding="utf-8").splitlines()
                 if "=" in line]
    assert "ACME_NOTES_TOKEN" in env_names
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(tmp_path)
        for marker in ("__SERVER_NAME__", "__SERVER_ENV__", "__YEAR__"):
            assert marker not in text, f"{rel} keeps {marker}"
        for leak in ("AKIA", "sk-"):
            assert leak not in text, f"{rel} carries {leak!r}"
        # `Bearer ${...}` builds the header from the secret; a literal token never appears.
        assert not re.search(r"Bearer [A-Za-z0-9._~+/=-]{12,}", text), f"{rel} carries a bearer value"
        for name in env_names:  # .env.example names a variable, never a value
            for line in text.splitlines():
                stripped = line.strip().lstrip("# ")
                if stripped.startswith(f"{name}="):
                    assert stripped == f"{name}=", f"{rel} sets a value for {name}"
    for path in ts_files:
        assert path.read_text(encoding="utf-8").splitlines()[0] == SPDX_LINE, path


def test_typescript_scaffolds_into_a_dir_holding_unrelated_files(tmp_path):
    (tmp_path / "README.other.md").write_text("keep me", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "unrelated.py").write_text("x = 1\n", encoding="utf-8")

    made = _scaffold_ts(tmp_path, "acme-notes", "--lang", "typescript")

    assert made.returncode == 0, made.stderr
    assert (tmp_path / "README.other.md").read_text(encoding="utf-8") == "keep me"
    assert (tmp_path / "src" / "unrelated.py").is_file()
    assert (tmp_path / "src" / "server.ts").is_file()


def test_typescript_refuses_a_collision_before_writing_anything(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "server.ts").write_text("mine\n", encoding="utf-8")

    made = _scaffold_ts(tmp_path)

    assert made.returncode == 2
    assert "server.ts" in made.stderr and "exists" in made.stderr
    assert (tmp_path / "src" / "server.ts").read_text(encoding="utf-8") == "mine\n"
    assert not (tmp_path / "package.json").exists(), "nothing is written when one file collides"


def test_typescript_default_has_rest_off_and_no_rest_report(tmp_path):
    made = _scaffold_ts(tmp_path)
    assert made.returncode == 0, made.stderr
    assert "rest" not in json.loads(made.stdout)
    config = json.loads((tmp_path / "mcp-server.config.json").read_text(encoding="utf-8"))
    assert config["transport"] == "stdio"
    assert config["rest"] == {"enabled": False, "basePath": "/api"}


def test_rest_flag_turns_rest_on_and_keeps_the_stdio_transport(tmp_path):
    """garden#1339: `--rest` changes ONE committed field. The transport stays stdio, so the server
    still installs for MCP clients (they spawn it); REST is served under MCP_TRANSPORT=httpStream."""
    plain, rest = tmp_path / "plain", tmp_path / "rest"
    assert _scaffold_ts(plain).returncode == 0
    made = _scaffold_ts(rest, "acme-notes", "--rest")
    assert made.returncode == 0, made.stderr
    report = json.loads(made.stdout)

    want = json.loads((plain / "mcp-server.config.json").read_text(encoding="utf-8"))
    want["rest"]["enabled"] = True
    assert json.loads((rest / "mcp-server.config.json").read_text(encoding="utf-8")) == want
    assert report["files"] == json.loads(_scaffold_ts(tmp_path / "again").stdout)["files"]
    assert {"src/http-api.ts", "test/rest-api.test.ts"} <= set(report["files"])
    assert report["probe"] == json.loads(_scaffold_ts(tmp_path / "p2").stdout)["probe"].replace(
        str(tmp_path / "p2"), str(rest))
    block = report["rest"]
    assert block["enabled"] is True and block["envNames"] == ["MCP_SERVER_BEARER"]
    assert block["run"] == f'MCP_TRANSPORT=httpStream node "{rest / "dist" / "server.js"}"'
    assert block["openapi"] == "http://127.0.0.1:8080/api/openapi.json"
    assert len(block["smoke"]) == 2
    for line in block["smoke"]:  # the bearer by NAME only
        assert line.startswith('curl -fsS -H "Authorization: Bearer $MCP_SERVER_BEARER"')
    assert block["smoke"][0].endswith("/api/openapi.json")
    assert block["smoke"][1].endswith("-d '{\"text\":\"hi\"}' http://127.0.0.1:8080/api/tools/echo")


@pytest.mark.parametrize("lang", sorted(TEMPLATES))
def test_rest_flag_refuses_the_one_file_templates_before_writing(tmp_path, lang):
    made = subprocess.run(
        [sys.executable, str(SCAFFOLD), "--name", "acme-notes", "--lang", lang, "--rest", "--out", str(tmp_path)],
        capture_output=True, text=True, timeout=TIMEOUT_S,
    )
    assert made.returncode == 2
    assert "--rest needs --lang typescript" in made.stderr
    assert list(tmp_path.iterdir()) == []


def test_skill_and_template_readme_document_the_rest_option():
    skill = SKILL.read_text(encoding="utf-8")
    assert "[--rest]" in skill and "MCP-only stays the default" in skill
    readme = (REPO / "skills" / "mcp-scaffold" / "assets" / "typescript" / "README.md").read_text(encoding="utf-8")
    assert "## REST API (optional)" in readme and "GET /api/openapi.json" in readme


def _free_port() -> int:
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _rest_journey(npm: str, built: Path, out: Path) -> None:
    """The `--rest` journey (garden#1339): scaffold with --rest, build and run the project's own
    suite, then the report's run line on a free port and its two smoke calls (document, tool).
    It reuses `built`'s node_modules: the two projects differ only in mcp-server.config.json."""
    import shlex
    import time
    import urllib.error
    import urllib.request

    made = _scaffold_ts(out, "acme-notes", "--rest")
    assert made.returncode == 0, made.stderr
    report = json.loads(made.stdout)["rest"]
    try:
        os.symlink(built / "node_modules", out / "node_modules", target_is_directory=True)
    except OSError:
        shutil.copytree(built / "node_modules", out / "node_modules", symlinks=True)
    for step in (["run", "build"], ["test"]):
        done = subprocess.run([npm, *step], cwd=out, capture_output=True, text=True, timeout=600,
                              env={**os.environ, "ACME_NOTES_TOKEN": "dummy"})
        assert done.returncode == 0, (step, done.stdout[-4000:], done.stderr[-4000:])
    # The report's run line itself: its leading VAR=value words are its environment.
    words = shlex.split(report["run"])
    run_env = dict(w.split("=", 1) for w in words if re.fullmatch(r"[A-Z_][A-Z0-9_]*=.*", w))
    argv = [w for w in words if not re.fullmatch(r"[A-Z_][A-Z0-9_]*=.*", w)]
    assert run_env == {"MCP_TRANSPORT": "httpStream"} and argv == ["node", str(out / "dist" / "server.js")]
    port, bearer = _free_port(), "e2e-rest-bearer"  # ggignore: a made-up local test bearer
    env = {**os.environ, **run_env, "ACME_NOTES_TOKEN": "dummy", "MCP_PORT": str(port), "MCP_SERVER_BEARER": bearer}
    child = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    openapi = report["openapi"].replace(":8080/", f":{port}/")
    auth = {"Authorization": f"Bearer {bearer}"}
    try:
        doc = None
        for _ in range(120):
            try:
                with urllib.request.urlopen(urllib.request.Request(openapi, headers=auth), timeout=5) as r:
                    doc = json.loads(r.read())
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.25)
        assert doc is not None and doc["openapi"] == "3.1.0" and "/tools/echo" in doc["paths"]
        # The report's two smoke lines, run as printed (only the port differs), with the bearer
        # in the environment by name.
        answers = []
        for line in report["smoke"]:
            done = subprocess.run(["bash", "-c", line.replace(":8080/", f":{port}/")], capture_output=True,
                                  text=True, timeout=30, env=env)
            assert done.returncode == 0, (line, done.stderr[-2000:])
            answers.append(json.loads(done.stdout))
        assert answers[0] == doc
        assert answers[1] == {"content": [{"type": "text", "text": "hi"}]}
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(urllib.request.Request(openapi), timeout=5)
        assert refused.value.code == 401
    finally:
        child.kill()
        child.wait(timeout=10)


def test_probe_passes_only_the_named_variable_and_reports_it_by_name(tmp_path, monkeypatch):
    server = tmp_path / "needs_token.py"
    server.write_text(textwrap.dedent('''
        import json, os, sys
        if not os.environ.get("ACME_NOTES_TOKEN"):
            sys.stderr.write("ACME_NOTES_TOKEN is not set\\n")
            sys.exit(1)
        assert "OTHER_SECRET" not in os.environ
        for line in sys.stdin:
            msg = json.loads(line)
            if "id" not in msg:
                continue
            if msg["method"] == "initialize":
                result = {"protocolVersion": msg["params"]["protocolVersion"],
                          "capabilities": {"tools": {}}, "serverInfo": {"name": "t", "version": "0"}}
            else:
                result = {"tools": []}
            print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
    '''), encoding="utf-8")
    monkeypatch.setenv("OTHER_SECRET", "nope")
    monkeypatch.delenv("ACME_NOTES_TOKEN", raising=False)

    missing = subprocess.run([sys.executable, str(PROBE), "--env", "ACME_NOTES_TOKEN", "--",
                              sys.executable, str(server)], capture_output=True, text=True,
                             timeout=TIMEOUT_S)
    monkeypatch.setenv("ACME_NOTES_TOKEN", "dummy-value")
    present = subprocess.run([sys.executable, str(PROBE), "--env", "ACME_NOTES_TOKEN", "--",
                              sys.executable, str(server)], capture_output=True, text=True,
                             timeout=TIMEOUT_S)

    assert missing.returncode == 1
    assert json.loads(missing.stdout)["stderrNames"] == ["ACME_NOTES_TOKEN"]
    assert present.returncode == 0, present.stdout
    assert "dummy-value" not in present.stdout + missing.stdout


@pytest.mark.skipif(os.environ.get("WICKED_GARDEN_E2E_NPM") != "1",
                    reason="needs the npm registry: set WICKED_GARDEN_E2E_NPM=1")
def test_typescript_template_installs_builds_tests_and_probes(tmp_path):
    out = tmp_path / "acme"
    assert _scaffold_ts(out).returncode == 0
    npm = shutil.which("npm")
    for step in (["install", "--no-audit", "--no-fund"], ["run", "build"], ["run", "lint"],
                 ["test"]):
        done = subprocess.run([npm, *step], cwd=out, capture_output=True, text=True, timeout=600,
                              env={**os.environ, "ACME_NOTES_TOKEN": "dummy"})
        assert done.returncode == 0, (step, done.stdout[-4000:], done.stderr[-4000:])
    proc = subprocess.run([sys.executable, str(PROBE), "--timeout", "30", "--env", "ACME_NOTES_TOKEN", "--", "node",
                           str(out / "dist" / "server.js")], capture_output=True, text=True,
                          timeout=TIMEOUT_S, env={**os.environ, "ACME_NOTES_TOKEN": "dummy"})
    probed = json.loads(proc.stdout)
    assert probed["ok"] is True, probed
    assert {t["name"]: t["class"] for t in probed["tools"]} == {"echo": "read"}
    _rest_journey(npm, out, tmp_path / "acme-rest")  # garden#1339: scaffold --rest, build, test, run, smoke

    # Branch A (garden#1249): with a generated tools.json the BUILT server must still start and
    # list exactly the generated tools — a raw JSON Schema handed to fastmcp kills it at startup.
    (out / "tools.json").write_text(json.dumps({"tools": [GENERATED_TOOL]}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(PROBE), "--timeout", "30", "--env", "ACME_NOTES_TOKEN", "--", "node",
                           str(out / "dist" / "server.js")], capture_output=True, text=True,
                          timeout=TIMEOUT_S * 2, env={**os.environ, "ACME_NOTES_TOKEN": "dummy"})
    probed = json.loads(proc.stdout)
    assert probed["ok"] is True, probed
    assert {t["name"]: t["class"] for t in probed["tools"]} == {"get_note": "read"}


GENERATED_TOOL = {
    "name": "get_note", "description": "Read one note", "class": "read",
    "inputSchema": {"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}},
                    "required": ["id"]},
    "rest": {"method": "GET", "pathTemplate": "/notes/{id}", "pathMap": {"id": "id"}, "queryMap": {},
             "headerMap": {}, "bodyMap": None, "bodyArg": None, "argAllowlist": ["id"],
             "timeoutMs": 5000},
}


def test_typescript_generated_tools_reach_fastmcp_as_a_standard_schema(tmp_path):
    """garden#1249, pinned without npm: generated tools go through jsonSchemaAdapter (ajv is a
    direct dependency, not a hoisting accident), the example tool only stands in while
    tools.json is empty, upstream error bodies are scrubbed, and the base-URL override keeps
    the committed origin. The npm E2E above and the template's own conformance suite boot it."""
    assert _scaffold_ts(tmp_path).returncode == 0
    generated = (tmp_path / "src" / "tools" / "generated.ts").read_text(encoding="utf-8")
    assert "parameters: jsonSchemaAdapter(" in generated
    assert "t.inputSchema as unknown as ToolParameters" not in generated
    assert "upstreamError(result.status" in generated
    deps = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))["dependencies"]
    assert {"ajv", "ajv-formats"} <= set(deps)
    server = (tmp_path / "src" / "server.ts").read_text(encoding="utf-8")
    assert "if (generated === 0) registerExampleTools(server, config);" in server
    assert "committed baseUrl origin" in (tmp_path / "src" / "config.ts").read_text(encoding="utf-8")
    conformance = (tmp_path / "test" / "conformance.test.ts").read_text(encoding="utf-8")
    assert "generated tools (branch A)" in conformance

