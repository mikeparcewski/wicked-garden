"""scripts/mcp/rest_smoke.py: the portable REST smoke (garden#1339, coord round 2).

A stub server (Python, so no node or npm is needed) stands in for a scaffolded `--rest` server:
it serves `<basePath>/openapi.json` and `<basePath>/tools/<name>` on the MCP_HOST/MCP_PORT the
smoke gives it, behind the MCP_SERVER_BEARER the smoke makes. Each case breaks one property.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "scripts" / "mcp" / "rest_smoke.py"

STUB = textwrap.dedent('''
    import json, os, sys
    from http.server import BaseHTTPRequestHandler, HTTPServer
    MODE = os.environ.get("STUB_MODE", "good")
    if MODE == "needs-token" and not os.environ.get("ACME_NOTES_TOKEN"):
        sys.stderr.write("ACME_NOTES_TOKEN is not set\\n"); sys.exit(1)
    if os.environ.get("MCP_TRANSPORT") != "httpStream":
        sys.stderr.write("not started as httpStream\\n"); sys.exit(4)
    with open(os.environ["STUB_SEEN"], "w") as fh:  # the test checks the bearer never reaches the report
        fh.write(os.environ["MCP_SERVER_BEARER"])
    BASE = "/api"
    SCHEMA = {"type": "string"} if MODE == "no-object-tool" else {"type": "object"}
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def send(self, status, body=None):
            data = b"" if body is None else json.dumps(body).encode()
            self.send_response(status); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)
        def authed(self):
            return MODE == "no-auth" or self.headers.get("authorization") == "Bearer " + os.environ["MCP_SERVER_BEARER"]
        def do_GET(self):
            if not self.authed(): return self.send(401, {"error": "unauthorized"})
            if self.path == BASE + "/openapi.json":
                op = {"post": {"requestBody": {"content": {"application/json": {"schema": SCHEMA}}}}}
                return self.send(200, {"openapi": "3.1.0", "paths": {"/tools/echo": op}})
            self.send(404)
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("content-length") or 0))
            if not self.authed(): return self.send(401, {"error": "unauthorized"})
            if self.path != BASE + "/tools/echo" or MODE == "no-route": return self.send(404)
            value = json.loads(body or b"{}")
            if MODE == "runs-anything" or isinstance(value, dict):
                return self.send(200, {"content": [{"type": "text", "text": "ran"}]})
            self.send(400, {"error": "invalid arguments", "issues": []})
    HTTPServer((os.environ["MCP_HOST"], int(os.environ["MCP_PORT"])), H).serve_forever()
''')


def _server(tmp_path: Path, rest: dict | None = None) -> Path:
    (tmp_path / "dist").mkdir()
    script = tmp_path / "dist" / "server.py"
    script.write_text(STUB, encoding="utf-8")
    config = {"key": "acme-notes", "transport": "stdio", "rest": rest if rest is not None else {"enabled": True, "basePath": "/api"}}
    (tmp_path / "mcp-server.config.json").write_text(json.dumps(config), encoding="utf-8")
    return script


def _smoke(tmp_path: Path, script: Path, mode: str, *extra: str):
    import os
    env = {"PATH": os.environ.get("PATH", ""), "STUB_MODE": mode, "STUB_SEEN": str(tmp_path / "seen")}
    # the smoke passes only the probe's minimal env plus --env names: the stub's knobs go by name too
    done = subprocess.run([sys.executable, str(SMOKE), "--timeout", "20", "--env", "STUB_MODE", "--env", "STUB_SEEN",
                           *extra, "--", sys.executable, str(script)],
                          capture_output=True, text=True, timeout=60, env=env)
    return done.returncode, json.loads(done.stdout), done.stdout


def test_a_good_rest_surface_passes_without_running_the_tool(tmp_path):
    code, report, raw = _smoke(tmp_path, _server(tmp_path), "good")
    assert code == 0 and report["ok"] is True, report
    assert report["openapi"] == 200 and report["unauthenticated"] == 401 and report["tools"] == ["echo"]
    assert report["call"] == {"tool": "echo", "status": 400, "error": "invalid arguments"}
    bearer = (tmp_path / "seen").read_text(encoding="utf-8")
    assert len(bearer) >= 24 and bearer not in raw  # a throwaway bearer, never printed


@pytest.mark.parametrize("mode, needle", [
    ("no-auth", "not 401"),
    ("no-route", "answered 404"),
    ("runs-anything", "answered 200"),
])
def test_a_broken_rest_surface_fails_and_says_which_check(tmp_path, mode, needle):
    code, report, _ = _smoke(tmp_path, _server(tmp_path), mode)
    assert code == 1 and report["ok"] is False and needle in report["error"], report


def test_with_no_object_tool_the_call_is_skipped_not_forced(tmp_path):
    code, report, _ = _smoke(tmp_path, _server(tmp_path), "no-object-tool")
    assert code == 0 and "skipped" in report["call"], report


def test_a_server_that_wants_its_secret_is_named_not_echoed(tmp_path):
    code, report, _ = _smoke(tmp_path, _server(tmp_path), "needs-token", "--env", "ACME_NOTES_TOKEN")
    assert code == 1 and report["stderrNames"] == ["ACME_NOTES_TOKEN"], report


def test_the_named_variable_is_passed_through(tmp_path):
    import os
    script = _server(tmp_path)
    env = {"PATH": os.environ.get("PATH", ""), "STUB_MODE": "needs-token", "STUB_SEEN": str(tmp_path / "seen"),
           "ACME_NOTES_TOKEN": "dummy-token"}  # ggignore: a made-up local test value
    done = subprocess.run([sys.executable, str(SMOKE), "--env", "STUB_MODE", "--env", "STUB_SEEN",
                           "--env", "ACME_NOTES_TOKEN", "--", sys.executable, str(script)],
                          capture_output=True, text=True, timeout=60, env=env)
    assert done.returncode == 0, done.stdout
    assert "dummy-token" not in done.stdout


def test_a_config_without_rest_is_a_report_not_a_start(tmp_path):
    code, report, _ = _smoke(tmp_path, _server(tmp_path, rest={"enabled": False, "basePath": "/api"}), "good")
    assert code == 1 and "rest.enabled" in report["error"], report
    assert not (tmp_path / "seen").exists()


def test_the_smoke_names_no_shell_and_imports_only_the_standard_library():
    import ast
    tree = ast.parse(SMOKE.read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}, mods
    assert "shell=True" not in SMOKE.read_text(encoding="utf-8")
