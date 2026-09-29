#!/usr/bin/env python3
"""The MCP shim: a governed worker's one way to an MCP tool (DES-MCP-TOOLS-001 S4).

    wicked-garden run scripts/mcp/shim.py list
    wicked-garden run scripts/mcp/shim.py call <mcp:server/tool> [--args JSON | --args-file PATH|-]

A worker never talks to an MCP server itself. wicked-crew's broker holds every upstream
connection and every secret, judges each call through steering policy, and records it. A
governed unit's environment carries the broker's address (``WICKED_CREW_URL``) and a capability
token bound to that unit (``WICKED_MCP_TOKEN``); this shim sends them, and nothing else, to:

    list  -> POST <WICKED_CREW_URL>/api/v1/mcp/tools {token}
             the tools this unit may try, each with its class and whether a call runs
             (``allow``) or waits for the operator's approval (``ask``); denied tools are left out
    call  -> POST <WICKED_CREW_URL>/api/v1/mcp/call  {token, subject, args}
             the broker's answer: ``outcome`` plus ``result`` (only on ``ok``), or ``reason``
             and ``remedy`` for a call that did not run or whose result is withheld

It prints exactly one JSON object on stdout, the broker's answer or a local error, and exits:

    0  ok (``call``: the tool ran; its result may itself be a tool error, ``isError``)
    2  usage, or no MCP channel in this environment (not a governed unit)
    3  denied or withheld: blocked by policy; the unit continues without it
    4  pending_approval: the operator has not approved it yet; do other work, do not retry
    5  budget_exhausted, breaker_open or upstream_error: the tool is unavailable for now
    1  anything else: an invalid token, a guard error, the broker unreachable

The token is never printed. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN_ENV = "WICKED_MCP_TOKEN"
CREW_URL_ENV = "WICKED_CREW_URL"
DEFAULT_TIMEOUT_S = 150.0
MAX_ARGS_BYTES = 1_000_000

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_DENIED = 3
EXIT_PENDING = 4
EXIT_UNAVAILABLE = 5

OUTCOME_EXIT = {
    "ok": EXIT_OK,
    "denied": EXIT_DENIED,
    "withheld": EXIT_DENIED,
    "pending_approval": EXIT_PENDING,
    "budget_exhausted": EXIT_UNAVAILABLE,
    "breaker_open": EXIT_UNAVAILABLE,
    "upstream_error": EXIT_UNAVAILABLE,
    "guard_error": EXIT_FAIL,
}


class ShimError(Exception):
    def __init__(self, code: str, reason: str, exit_code: int):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.exit_code = exit_code


def channel(env: dict) -> tuple[str, str]:
    """The broker URL and this unit's token, or a usage error naming what is missing."""
    token = (env.get(TOKEN_ENV) or "").strip()
    url = (env.get(CREW_URL_ENV) or "").strip().rstrip("/")
    missing = [name for name, value in ((TOKEN_ENV, token), (CREW_URL_ENV, url)) if not value]
    if missing:
        raise ShimError(
            "no_mcp_channel",
            f"{' and '.join(missing)} not set: MCP tools are reachable only from a governed "
            "wicked-crew unit; continue without them",
            EXIT_USAGE,
        )
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ShimError("no_mcp_channel", f"{CREW_URL_ENV} is not an http(s) URL", EXIT_USAGE)
    return url, token


def normalize_subject(subject: str) -> str:
    """``mcp:<server>/<tool>``; the ``mcp:`` prefix may be omitted."""
    s = subject.strip()
    if not s.startswith("mcp:"):
        s = f"mcp:{s}"
    server, sep, tool = s[len("mcp:"):].partition("/")
    if not sep or not server or not tool or "/" in tool:
        raise ShimError("bad_request", f"a subject is mcp:<server>/<tool> (got {subject!r})", EXIT_USAGE)
    return s


def read_args(inline: str | None, path: str | None, stdin=None) -> dict:
    """The call's arguments: a JSON object from ``--args`` or ``--args-file`` (``-`` = stdin)."""
    if inline is not None and path is not None:
        raise ShimError("bad_request", "give --args or --args-file, not both", EXIT_USAGE)
    if path is not None:
        try:
            if path == "-":
                text = (stdin or sys.stdin).read(MAX_ARGS_BYTES + 1)
            else:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read(MAX_ARGS_BYTES + 1)
        except OSError as err:
            raise ShimError("bad_request", f"--args-file unreadable: {err.strerror}", EXIT_USAGE) from None
    elif inline is not None:
        text = inline
    else:
        return {}
    if len(text.encode("utf-8")) > MAX_ARGS_BYTES:
        raise ShimError("bad_request", f"arguments exceed {MAX_ARGS_BYTES} bytes", EXIT_USAGE)
    try:
        value = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as err:
        raise ShimError("bad_request", f"arguments are not JSON: {err.msg} at {err.pos}", EXIT_USAGE) from None
    if not isinstance(value, dict):
        raise ShimError("bad_request", "arguments must be a JSON object", EXIT_USAGE)
    return value


def post(url: str, body: dict, timeout_s: float, opener=urllib.request.urlopen) -> tuple[int, dict]:
    """POST JSON; every HTTP status is an answer (the broker answers refusals with a body)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with opener(req, timeout=timeout_s) as res:
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    except (urllib.error.URLError, OSError, TimeoutError) as err:
        reason = getattr(err, "reason", err)
        raise ShimError("broker_unreachable", f"the broker at {url} did not answer: {reason}", EXIT_FAIL) from None
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ShimError("bad_response", f"the broker answered {status} with a body that is not JSON", EXIT_FAIL) from None
    if not isinstance(parsed, dict):
        raise ShimError("bad_response", f"the broker answered {status} with a JSON {type(parsed).__name__}", EXIT_FAIL)
    return status, parsed


def run_list(url: str, token: str, timeout_s: float, opener=urllib.request.urlopen) -> tuple[dict, int]:
    status, body = post(f"{url}/api/v1/mcp/tools", {"token": token}, timeout_s, opener)
    if status == 200 and isinstance(body.get("tools"), list):
        return body, EXIT_OK
    return {"ok": False, "status": status, **body}, EXIT_FAIL


def run_call(url: str, token: str, subject: str, args: dict, timeout_s: float,
             opener=urllib.request.urlopen) -> tuple[dict, int]:
    status, body = post(f"{url}/api/v1/mcp/call", {"token": token, "subject": subject, "args": args}, timeout_s, opener)
    outcome = body.get("outcome")
    if isinstance(outcome, str) and outcome in OUTCOME_EXIT:
        return body, OUTCOME_EXIT[outcome]
    return {"ok": False, "status": status, **body}, EXIT_FAIL


class _Parser(argparse.ArgumentParser):
    """Usage errors become the shim's one JSON object (exit 2), never argparse's bare stderr."""

    def error(self, message: str):
        raise ShimError("bad_request", f"usage: {message}", EXIT_USAGE)


def parser() -> argparse.ArgumentParser:
    p = _Parser(prog="wicked-garden run scripts/mcp/shim.py",
                description="Reach MCP tools through the wicked-crew broker.")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds to wait for the broker")
    sub = p.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    sub.add_parser("list", help="the tools this unit may try")
    call = sub.add_parser("call", help="call one tool")
    call.add_argument("subject", help="mcp:<server>/<tool>")
    call.add_argument("--args", dest="args_json", help="the arguments as a JSON object")
    call.add_argument("--args-file", dest="args_file", help="a file holding the JSON arguments ('-' = stdin)")
    return p


def main(argv: list[str] | None = None, env: dict | None = None, opener=urllib.request.urlopen) -> int:
    try:
        ns = parser().parse_args(argv)
        if ns.timeout <= 0:
            raise ShimError("bad_request", "--timeout must be positive", EXIT_USAGE)
        if ns.verb == "call":
            subject = normalize_subject(ns.subject)
            args = read_args(ns.args_json, ns.args_file)
        url, token = channel(os.environ if env is None else env)
        if ns.verb == "list":
            out, code = run_list(url, token, ns.timeout, opener)
        else:
            out, code = run_call(url, token, subject, args, ns.timeout, opener)
    except ShimError as err:
        out, code = {"ok": False, "code": err.code, "reason": err.reason}, err.exit_code
    sys.stdout.write(json.dumps(out) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
