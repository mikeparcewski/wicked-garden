"""The `openapi` action (scripts/mcp/openapi.py): OpenAPI 3 → tools.json through wicked-crew's
conversion service (`POST /api/v1/mcp/servers/preview`, kind rest). DES-mcp-server-workflow §6.

Against a local http.server playing the daemon: two operations → two tools with their classes
and mappings, the config's baseUrl set; a 400 → exit 1 carrying the daemon's message; nothing
listening → exit 2 with the branch-B sentence; the request never carries `secret`/`auth`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from daemon_fixture import FakeDaemon, closed_origin

REPO = Path(__file__).resolve().parent.parent.parent
OPENAPI = REPO / "scripts" / "mcp" / "openapi.py"
PREVIEW = "/api/v1/mcp/servers/preview"

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "notes", "version": "1"},
    "paths": {
        "/notes/{id}": {"get": {"operationId": "get_note",
                                "parameters": [{"name": "id", "in": "path", "required": True,
                                                "schema": {"type": "string"}}]}},
        "/notes": {"post": {"operationId": "create_note",
                            "requestBody": {"content": {"application/json": {"schema": {
                                "type": "object", "properties": {"title": {"type": "string"}}}}}}}},
    },
}


def _mapping(method, path, **kw):
    base = {"method": method, "pathTemplate": path, "pathMap": {}, "queryMap": {}, "headerMap": {},
            "bodyMap": None, "bodyArg": None, "argAllowlist": [], "timeoutMs": 30000}
    base.update(kw)
    return base


ANSWER = {
    "tools": [
        {"name": "get_note", "description": "get", "class": "read",
         "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
         "annotations": {"readOnlyHint": True},
         "rest": _mapping("GET", "/notes/{id}", pathMap={"id": "id"}, argAllowlist=["id"])},
        {"name": "create_note", "description": "create", "class": "write",
         "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}},
         "annotations": {"readOnlyHint": False, "destructiveHint": False},
         "rest": _mapping("POST", "/notes", bodyMap={"title": "title"}, argAllowlist=["title"])},
    ],
    "skipped": [{"operation": "GET /health", "reason": "no operationId"}],
    "previewHash": "h1",
}


def _server_dir(tmp_path: Path) -> Path:
    out = tmp_path / "srv"
    out.mkdir(parents=True)
    (out / "tools.json").write_text('{\n  "tools": []\n}\n', encoding="utf-8")
    (out / "mcp-server.config.json").write_text(json.dumps(
        {"key": "acme-notes", "version": "0.1.0", "baseUrl": "https://api.example.com"}),
        encoding="utf-8")
    return out


def _run(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os
    env = {k: v for k, v in os.environ.items() if k != "WICKED_CREW_URL"}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(OPENAPI), *args], capture_output=True, text=True,
                          timeout=60, env=env)


def test_two_operations_become_two_tools_and_set_the_base_url(tmp_path):
    out = _server_dir(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC), encoding="utf-8")
    with FakeDaemon() as daemon:
        daemon.routes[("POST", PREVIEW)] = (200, ANSWER)
        done = _run("--name", "acme-notes", "--base-url", "https://notes.example.com/v1",
                    "--spec", str(spec), "--out", str(out), "--crew-url", daemon.origin)

    assert done.returncode == 0, done.stderr
    summary = json.loads(done.stdout)
    assert summary["tools"] == 2 and summary["classes"] == {"read": 1, "write": 1}
    assert summary["skipped"] == ANSWER["skipped"]
    tools = json.loads((out / "tools.json").read_text(encoding="utf-8"))
    assert [t["name"] for t in tools["tools"]] == ["get_note", "create_note"]
    assert {t["name"]: t["class"] for t in tools["tools"]} == {"get_note": "read", "create_note": "write"}
    assert tools["tools"][0]["rest"]["pathMap"] == {"id": "id"}
    assert tools["tools"][1]["rest"]["bodyMap"] == {"title": "title"}
    assert tools["skipped"] == ANSWER["skipped"]
    assert tools["source"]["specFile"] == str(spec)
    assert tools["source"]["baseUrl"] == "https://notes.example.com/v1" and tools["source"]["convertedAt"]
    config = json.loads((out / "mcp-server.config.json").read_text(encoding="utf-8"))
    assert config["baseUrl"] == "https://notes.example.com/v1"
    (req,) = daemon.requests
    assert req["body"] == {"name": "acme-notes", "kind": "rest", "url": "https://notes.example.com/v1",
                           "openapi": SPEC}
    assert "secret" not in req["raw"] and "auth" not in req["raw"]


def test_spec_url_and_operations_are_forwarded_and_env_origin_is_used(tmp_path):
    out = _server_dir(tmp_path)
    with FakeDaemon() as daemon:
        daemon.routes[("POST", PREVIEW)] = (200, ANSWER)
        done = _run("--name", "acme-notes", "--base-url", "https://notes.example.com",
                    "--spec-url", "https://notes.example.com/openapi.json",
                    "--operations", "get_note, create_note", "--out", str(out),
                    env_extra={"WICKED_CREW_URL": daemon.origin})

    assert done.returncode == 0, done.stderr
    (req,) = daemon.requests
    assert req["body"]["openapiUrl"] == "https://notes.example.com/openapi.json"
    assert req["body"]["operations"] == ["get_note", "create_note"]
    assert "openapi" not in req["body"]
    assert json.loads((out / "tools.json").read_text(encoding="utf-8"))["source"]["specUrl"]


def test_a_daemon_refusal_exits_1_with_its_message(tmp_path):
    out = _server_dir(tmp_path)
    with FakeDaemon() as daemon:
        daemon.routes[("POST", PREVIEW)] = (400, {"error": "openapi: not an OpenAPI 3 document"})
        done = _run("--name", "acme-notes", "--base-url", "https://notes.example.com",
                    "--spec-url", "https://notes.example.com/x.json", "--out", str(out),
                    "--crew-url", daemon.origin)

    assert done.returncode == 1
    assert "not an OpenAPI 3 document" in done.stderr
    assert json.loads((out / "tools.json").read_text(encoding="utf-8")) == {"tools": []}


def test_no_daemon_exits_2_with_the_branch_b_sentence(tmp_path):
    out = _server_dir(tmp_path)
    origin = closed_origin()
    done = _run("--name", "acme-notes", "--base-url", "https://notes.example.com",
                "--spec-url", "https://notes.example.com/x.json", "--out", str(out),
                "--crew-url", origin)

    assert done.returncode == 2
    assert (f"the conversion service is the wicked-crew daemon; none answered at {origin} "
            "— write the tools by hand (branch B)") in done.stderr
    assert json.loads((out / "tools.json").read_text(encoding="utf-8")) == {"tools": []}


def test_refuses_to_overwrite_generated_tools_and_bad_urls(tmp_path):
    out = _server_dir(tmp_path)
    (out / "tools.json").write_text(json.dumps({"tools": [{"name": "x"}]}), encoding="utf-8")
    kept = _run("--name", "acme-notes", "--base-url", "https://notes.example.com",
                "--spec-url", "https://notes.example.com/x.json", "--out", str(out),
                "--crew-url", closed_origin())
    bad = _run("--name", "acme-notes", "--base-url", "https://user:pw@notes.example.com",
               "--spec-url", "https://notes.example.com/x.json", "--out", str(tmp_path / "o"),
               "--crew-url", closed_origin())

    assert kept.returncode == 2 and "refusing to overwrite" in kept.stderr
    assert bad.returncode == 2 and "credentials" in bad.stderr


def test_a_yaml_spec_without_pyyaml_says_pass_spec_url(tmp_path):
    try:
        import yaml  # noqa: F401
        pytest.skip("PyYAML is installed here")
    except ImportError:
        pass
    spec = tmp_path / "spec.yaml"
    spec.write_text("openapi: 3.0.3\n", encoding="utf-8")
    done = _run("--name", "acme-notes", "--base-url", "https://n.example.com", "--spec", str(spec),
                "--out", str(_server_dir(tmp_path)), "--crew-url", closed_origin())
    assert done.returncode == 2 and "--spec-url" in done.stderr


def test_a_malformed_config_or_empty_operations_is_refused_before_posting(tmp_path):
    out = _server_dir(tmp_path)
    (out / "mcp-server.config.json").write_text("{not json", encoding="utf-8")
    with FakeDaemon() as daemon:
        daemon.routes[("POST", PREVIEW)] = (200, ANSWER)
        broken = _run("--name", "acme-notes", "--base-url", "https://n.example.com",
                      "--spec-url", "https://n.example.com/x.json", "--out", str(out),
                      "--crew-url", daemon.origin)
        empty = _run("--name", "acme-notes", "--base-url", "https://n.example.com",
                     "--spec-url", "https://n.example.com/x.json", "--operations", " , ",
                     "--out", str(_server_dir(tmp_path / "b")), "--crew-url", daemon.origin)

    assert broken.returncode == 2 and "not valid JSON" in broken.stderr
    assert empty.returncode == 2 and "--operations" in empty.stderr
    assert daemon.requests == []
    assert json.loads((out / "tools.json").read_text(encoding="utf-8")) == {"tools": []}
