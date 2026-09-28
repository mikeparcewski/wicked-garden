#!/usr/bin/env python3
"""__SERVER_NAME__ — an MCP server over stdio (newline-delimited JSON-RPC 2.0).

Scaffolded by wicked-garden-mcp-scaffold. Standard library only; Python >= 3.9.

Rules this file keeps (the broker that registers it relies on them):
  - stdout carries protocol frames only; every log line goes to stderr.
  - every tool declares annotations honestly; a tool with none is treated as a WRITE.
  - a secret arrives in the environment (the broker injects it at call time);
    never log it, never return it, never take it as a tool argument.
"""

import json
import sys

SERVER = {"name": "__SERVER_NAME__", "version": "0.1.0"}
# Newest first. An unsupported client version is answered with SUPPORTED[0].
SUPPORTED = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]


class ToolError(Exception):
    """A bad call: returned as ``isError`` so the caller's turn continues."""


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# In-process state for the example write tool; replace with your own backend.
_state = {"counter": 0}


def _echo(args):
    text = args.get("text")
    if not isinstance(text, str):
        raise ToolError("text must be a string")
    return text


def _counter_increment(args):
    by = args.get("by", 1)
    if not isinstance(by, int) or isinstance(by, bool) or by < 1:
        raise ToolError("by must be a positive integer")
    _state["counter"] += by
    return str(_state["counter"])


# Each tool: its MCP description plus a handler(args) returning text.
TOOLS = {
    "echo": {
        "description": "Return the given text unchanged.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to return."}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "handler": _echo,
    },
    "counter_increment": {
        "description": "Add to an in-memory counter and return the new value.",
        "inputSchema": {
            "type": "object",
            "properties": {"by": {"type": "integer", "minimum": 1,
                                  "description": "Amount to add (default 1)."}},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False,
                        "idempotentHint": False, "openWorldHint": False},
        "handler": _counter_increment,
    },
}


def log(msg):
    sys.stderr.write("[%s] %s\n" % (SERVER["name"], msg))
    sys.stderr.flush()


def send(frame):
    sys.stdout.write(json.dumps(dict({"jsonrpc": "2.0"}, **frame)) + "\n")
    sys.stdout.flush()


def initialize(params):
    asked = params.get("protocolVersion")
    return {
        "protocolVersion": asked if asked in SUPPORTED else SUPPORTED[0],
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": SERVER,
    }


def list_tools(_params):
    return {"tools": [
        {"name": name, **{k: v for k, v in tool.items() if k != "handler"}}
        for name, tool in TOOLS.items()
    ]}


def call_tool(params):
    tool = TOOLS.get(params.get("name"))
    if tool is None:
        raise RpcError(-32602, "unknown tool: %s" % params.get("name"))
    try:
        text = tool["handler"](params.get("arguments") or {})
    except ToolError as err:
        return {"content": [{"type": "text", "text": str(err)}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


METHODS = {
    "initialize": initialize,
    "ping": lambda _params: {},
    "tools/list": list_tools,
    "tools/call": call_tool,
}


def handle(line):
    try:
        msg = json.loads(line)
    except ValueError:
        send({"id": None, "error": {"code": -32700, "message": "parse error"}})
        return
    if not isinstance(msg, dict) or "id" not in msg:
        return  # notifications (e.g. notifications/initialized) get no reply
    method = METHODS.get(msg.get("method"))
    try:
        if method is None:
            raise RpcError(-32601, "method not found: %s" % msg.get("method"))
        send({"id": msg["id"], "result": method(msg.get("params") or {})})
    except RpcError as err:
        send({"id": msg["id"], "error": {"code": err.code, "message": str(err)}})
    except Exception as err:  # noqa: BLE001 — one bad request must not end the server
        log("internal error in %s: %s" % (msg.get("method"), err))
        send({"id": msg["id"], "error": {"code": -32603, "message": "internal error"}})


def main():
    for line in sys.stdin:
        if line.strip():
            handle(line)


if __name__ == "__main__":
    main()
