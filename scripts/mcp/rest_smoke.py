#!/usr/bin/env python3
"""Smoke a scaffolded server's REST surface (garden#1339): is it mounted, authenticated, validated?

    wicked-garden run scripts/mcp/rest_smoke.py [--timeout 20] [--env NAME]... -- node <dist/server.js>

Starts the server the way its REST surface is served (``MCP_TRANSPORT=httpStream``, on
127.0.0.1 and a free port) with the probe's minimal environment (PATH, HOME and the OS
system/temp variables only) plus exactly the variables named with ``--env``, and a throwaway
``MCP_SERVER_BEARER`` made in this process. Then it checks, over HTTP:

1. ``GET <basePath>/openapi.json`` with the bearer answers 200 with the tools as paths;
2. the same request without the bearer answers 401;
3. ``POST <basePath>/tools/<one tool>`` with the bearer and a body that is not an object
   answers 400 ``invalid arguments``: the route is mounted, auth passed and the tool's own
   schema ran. The tool itself never runs, so the smoke has no side effects. Only a tool whose
   input schema is ``type: object`` is called; with none, the call is reported as skipped.

``basePath`` is read from the ``mcp-server.config.json`` beside the server's ``dist/``.
Prints one JSON object and exits 0 when every check passed, 1 otherwise, 2 on a usage error.
No bearer, token or variable value is ever printed; on a failure the report lists only which
``--env`` NAMES the server's stderr mentioned (``stderrNames``), as probe.py does. Standard
library only.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_KEEP = ("PATH", "PATHEXT", "HOME", "USERPROFILE", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR",
            "COMSPEC", "TEMP", "TMP", "TMPDIR", "LANG")
CONFIG_FILE = "mcp-server.config.json"
STDERR_CAP = 64 * 1024
STOP_GRACE_S = 2.0


class SmokeError(Exception):
    pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _base_path(command: list[str]) -> str:
    """``rest.basePath`` from the config two levels above ``dist/server.js`` (the template's SERVER_ROOT)."""
    script = next((Path(a) for a in command[1:] if Path(a).is_file()), None)
    if script is None:
        raise SmokeError("give the server as `node <dist/server.js>` (an existing file)")
    config_path = script.resolve().parent.parent / CONFIG_FILE
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise SmokeError(f"cannot read {CONFIG_FILE} beside the server: {err}") from None
    rest = config.get("rest") if isinstance(config, dict) else None
    if not isinstance(rest, dict) or rest.get("enabled") is not True:
        raise SmokeError(f"{CONFIG_FILE} has no rest.enabled: true (scaffold with --rest)")
    base = rest.get("basePath", "/api")
    if not isinstance(base, str) or not base.startswith("/"):
        raise SmokeError(f"{CONFIG_FILE} rest.basePath must start with '/'")
    return base.rstrip("/")


def _http(method: str, url: str, bearer: str | None, body: bytes | None = None) -> tuple[int, object]:
    headers = {"content-type": "application/json"} if body is not None else {}
    if bearer is not None:
        headers["authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - 127.0.0.1 only
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        return status, json.loads(raw.decode("utf-8")) if raw else None
    except ValueError:
        return status, None


class Server:
    def __init__(self, command: list[str], port: int, bearer: str, pass_env: tuple[str, ...]):
        env = {k: os.environ[k] for k in (*ENV_KEEP, *pass_env) if k in os.environ}
        env.update(MCP_TRANSPORT="httpStream", MCP_HOST="127.0.0.1", MCP_PORT=str(port), MCP_SERVER_BEARER=bearer)
        self.proc = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE)
        self._stderr = bytearray()
        threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self) -> None:
        # Kept in memory, capped, for the stderrNames check only; never printed.
        for chunk in iter(lambda: self.proc.stderr.read(4096), b""):
            if len(self._stderr) < STDERR_CAP:
                self._stderr.extend(chunk[: STDERR_CAP - len(self._stderr)])

    def stderr_names(self, names: tuple[str, ...]) -> list[str]:
        text = self._stderr.decode("utf-8", "replace")
        return [n for n in names if n in text]

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(STOP_GRACE_S)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


def smoke(command: list[str], timeout_s: float, pass_env: tuple[str, ...] = ()) -> dict:
    base_path = _base_path(command)
    port, bearer = _free_port(), secrets.token_urlsafe(24)
    origin = f"http://127.0.0.1:{port}"
    server = Server(command, port, bearer, pass_env)
    try:
        deadline = time.monotonic() + timeout_s
        doc_url = f"{origin}{base_path}/openapi.json"
        status, doc = 0, None
        while time.monotonic() < deadline:
            if server.proc.poll() is not None:
                raise SmokeError(f"the server exited ({server.proc.returncode}) before its REST surface answered")
            try:
                status, doc = _http("GET", doc_url, bearer)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        else:
            raise SmokeError(f"no answer on {base_path}/openapi.json within {timeout_s:g}s")
        paths = doc.get("paths") if isinstance(doc, dict) else None
        if status != 200 or not isinstance(paths, dict):
            raise SmokeError(f"GET {base_path}/openapi.json with the bearer answered {status}, not 200 with paths")
        anon, _ = _http("GET", doc_url, None)
        if anon != 401:
            raise SmokeError(f"GET {base_path}/openapi.json without the bearer answered {anon}, not 401")
        report = {"ok": True, "basePath": base_path, "tools": sorted(p.rsplit("/", 1)[-1] for p in paths),
                  "openapi": 200, "unauthenticated": 401}
        target = next((p for p, op in paths.items() if _object_schema(op)), None)
        if target is None:
            report["call"] = {"skipped": "no tool takes an object, so none can be refused without running it"}
            return report
        status, body = _http("POST", f"{origin}{base_path}{target}", bearer, b"[]")
        error = body.get("error") if isinstance(body, dict) else None
        if status != 400 or error != "invalid arguments":
            raise SmokeError(f"POST {base_path}{target} with a non-object body answered {status} {error!r}, "
                             f"not 400 'invalid arguments'")
        report["call"] = {"tool": target.rsplit("/", 1)[-1], "status": 400, "error": error}
        return report
    except SmokeError as err:
        err.stderr_names = server.stderr_names(pass_env)
        raise
    finally:
        server.close()


def _object_schema(operation: object) -> bool:
    try:
        schema = operation["post"]["requestBody"]["content"]["application/json"]["schema"]
    except (KeyError, TypeError):
        return False
    return isinstance(schema, dict) and schema.get("type") == "object"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=20.0, help="seconds for the server to answer")
    parser.add_argument("--env", action="append", default=[], metavar="NAME",
                        help="pass this one variable through to the server (repeatable)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- node <dist/server.js>")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the server command after --")
    try:
        report = smoke(command, args.timeout, tuple(args.env))
    except SmokeError as err:
        failed = {"ok": False, "error": str(err)}
        if args.env:
            failed["stderrNames"] = getattr(err, "stderr_names", [])
        print(json.dumps(failed, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
