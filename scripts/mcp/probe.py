#!/usr/bin/env python3
"""Probe a stdio MCP server: does it answer ``initialize`` and ``tools/list``?

    wicked-garden run scripts/mcp/probe.py [--timeout 10] [--env NAME]... -- <command> [args...]

Spawns ``<command>`` with a minimal environment (PATH, HOME and the OS system/temp
variables only — no secrets, no ambient tokens) plus exactly the variables named with
``--env`` (passed through from the caller's environment when set; a value is never
printed), runs the MCP handshake, lists every tool
(following ``nextCursor``) and derives each tool's class the way the wicked-crew broker does
(DES-MCP-TOOLS-001 §4.2):

    readOnlyHint == true      -> read
    destructiveHint != false  -> destructive   (the MCP default when annotations are present)
    otherwise                 -> write
    no annotations at all     -> write         (default D-4)

Prints one JSON object on stdout and exits 0 when the server answered both requests, 1
otherwise. The server's stderr is never echoed: on a failure the report lists only which
``--env`` NAMES it mentioned (``stderrNames``) — how a server that refuses to start without
its secret is told apart from a broken one. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
ENV_KEEP = ("PATH", "PATHEXT", "HOME", "USERPROFILE", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR",
            "COMSPEC", "TEMP", "TMP", "TMPDIR", "LANG")
MAX_PAGES = 50
STDERR_CAP = 64 * 1024
STOP_GRACE_S = 2.0


class ProbeError(Exception):
    pass


def tool_class(tool: dict) -> str:
    annotations = tool.get("annotations")
    if not isinstance(annotations, dict):
        return "write"
    if annotations.get("readOnlyHint") is True:
        return "read"
    if annotations.get("destructiveHint") is not False:
        return "destructive"
    return "write"


class Session:
    """One spawned server; frames are newline-delimited JSON-RPC on its stdio."""

    def __init__(self, command: list[str], timeout_s: float, pass_env: tuple[str, ...] = ()):
        env = {k: os.environ[k] for k in (*ENV_KEEP, *pass_env) if k in os.environ}
        try:
            self.proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8",
                errors="replace", bufsize=1,
            )
        except OSError as err:
            raise ProbeError(f"cannot start server: {err}") from err
        self.stderr = ""
        self._stderr_done = threading.Event()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self.deadline = time.monotonic() + timeout_s
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.next_id = 0
        threading.Thread(target=self._pump, daemon=True).start()

    def _drain_stderr(self) -> None:
        # Kept in memory, capped, for the stderrNames check only; never printed.
        for line in self.proc.stderr:
            if len(self.stderr) < STDERR_CAP:
                self.stderr += line
        self._stderr_done.set()

    def stderr_names(self, names: tuple[str, ...]) -> list[str]:
        self._stderr_done.wait(timeout=STOP_GRACE_S)
        return [n for n in names if n in self.stderr]

    def _pump(self) -> None:
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _write(self, frame: dict) -> None:
        try:
            self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", **frame}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as err:
            raise ProbeError(f"server closed its stdin ({err.__class__.__name__})") from err

    def notify(self, method: str) -> None:
        self._write({"method": method})

    def request(self, method: str, params: dict) -> dict:
        self.next_id += 1
        want = self.next_id
        self._write({"id": want, "method": method, "params": params})
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError(f"timed out waiting for the {method} reply")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                raise ProbeError(f"timed out waiting for the {method} reply") from None
            if line is None:
                raise ProbeError(f"server exited (code {self.proc.poll()}) before answering {method}")
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                raise ProbeError("server wrote a non-JSON line to stdout; stdout must carry "
                                 "protocol frames only (log to stderr)") from None
            if not isinstance(msg, dict) or msg.get("id") != want or "method" in msg:
                continue  # a server notification or request, not our reply
            if "error" in msg:
                err = msg["error"] if isinstance(msg["error"], dict) else {}
                raise ProbeError(f"{method} failed: {err.get('code')} {err.get('message')}")
            result = msg.get("result")
            if not isinstance(result, dict):
                raise ProbeError(f"{method} reply has no result object")
            return result

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=STOP_GRACE_S)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def probe(command: list[str], timeout_s: float, pass_env: tuple[str, ...] = ()) -> dict:
    session = Session(command, timeout_s, pass_env)
    try:
        init = session.request("initialize", {
            "protocolVersion": PROTOCOL_VERSIONS[0],
            "capabilities": {},
            "clientInfo": {"name": "wicked-garden-mcp-probe", "version": "1"},
        })
        version = init.get("protocolVersion")
        if version not in PROTOCOL_VERSIONS:
            raise ProbeError(f"unsupported protocolVersion {version!r}")
        capabilities = init.get("capabilities")
        if not isinstance(capabilities, dict) or not isinstance(capabilities.get("tools"), dict):
            raise ProbeError("server does not advertise the tools capability")
        session.notify("notifications/initialized")

        tools: list[dict] = []
        cursor = None
        for _ in range(MAX_PAGES):
            page = session.request("tools/list", {"cursor": cursor} if cursor else {})
            if not isinstance(page.get("tools"), list):
                raise ProbeError("tools/list reply has no tools array")
            tools.extend(page["tools"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        else:
            raise ProbeError(f"tools/list did not finish within {MAX_PAGES} pages")
    except ProbeError as err:
        session.close()
        err.stderr_names = session.stderr_names(pass_env)
        raise
    finally:
        session.close()
    return _report(init, version, tools)


def _report(init: dict, version: str, tools: list[dict]) -> dict:
    listed, warnings, seen = [], [], set()
    for tool in tools:
        name = tool.get("name") if isinstance(tool, dict) else None
        if not isinstance(name, str) or not name:
            raise ProbeError("a tool has no name")
        if name in seen:
            raise ProbeError(f"tool {name!r} is listed twice")
        seen.add(name)
        klass = tool_class(tool)
        if not isinstance(tool.get("annotations"), dict):
            warnings.append(f"{name}: no annotations, so it is treated as write; declare "
                            "readOnlyHint/destructiveHint")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            warnings.append(f"{name}: inputSchema must be a JSON Schema with type 'object'")
        if "/" in name:
            warnings.append(f"{name}: '/' cannot appear in an mcp:<server>/<tool> subject")
        listed.append({"name": name, "class": klass, "annotations": tool.get("annotations")})
    return {
        "ok": True,
        "protocolVersion": version,
        "serverInfo": init.get("serverInfo"),
        "tools": listed,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds for the whole probe")
    parser.add_argument("--env", action="append", default=[], metavar="NAME",
                        help="pass this one variable through to the server (repeatable)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- <command> [args...]")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the server command after --")
    try:
        report = probe(command, args.timeout, tuple(args.env))
    except ProbeError as err:
        failed = {"ok": False, "error": str(err)}
        if args.env:
            failed["stderrNames"] = getattr(err, "stderr_names", [])
        print(json.dumps(failed, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
