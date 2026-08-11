"""
Reach-shim: let garden's Python hooks (and other non-MCP callers) reach
wicked-estate's **stdio** MCP server.

Background
----------
wicked-estate ships a single stdio JSON-RPC 2.0 MCP binary
(`wicked-estate-mcp`): newline-delimited requests on stdin, one response per
request on stdout. There is no HTTP daemon and no port — so the brain-era
pattern (`_brain_port.resolve_port()` → POST http://localhost:PORT/api) does
not apply. This module is the estate analogue of `_brain_port.py`: it owns
binary/DB resolution, a health probe, and a fail-open call surface, so a hook
never hard-crashes when estate is missing or slow.

Transport
---------
**Spawn-per-call** today (simplest correct thing): each call spawns
`wicked-estate-mcp`, does the `initialize` handshake, issues one `tools/call`,
parses the result, and lets the process exit on stdin EOF. This is slower than
a long-lived server but requires zero lifecycle management and cannot leak
processes.

The spawn-vs-broker choice is an implementation detail behind a single seam:
`_dispatch()` (installed as `_active_dispatch`). A future persistent stdio
broker replaces **that one function** via `set_dispatch()` — every public
function here routes through it, so **no caller changes** when the transport
does. Callers only ever touch the stable API below (or the `__main__` CLI,
which is the `wicked-estate-call` entry point).

Fail-open contract
------------------
Every public function is fail-open: on a missing binary, spawn failure,
timeout, non-zero exit, malformed JSON, or a tool `isError`, it returns a safe
empty value (`False` / `None` / `[]`) and never raises. Hooks degrade; they do
not crash.

Cross-platform
--------------
Pure stdlib. `subprocess` with an argv list (no shell). `shutil.which` resolves
`.exe`/`.cmd` on Windows. `communicate(timeout=...)` is the portable timeout
(no Unix-only signals). All paths via `pathlib`; all wire framing via `json`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Resolution — binary + graph DB (mirrors the binary's own --db > env > default)
# ─────────────────────────────────────────────────────────────────────────────

_MCP_BIN_NAME = "wicked-estate-mcp"
_CLI_BIN_NAME = "wicked-estate"
_DEFAULT_DB_REL = ".wicked-estate/graph.db"


def _which_or_local(name: str) -> Optional[str]:
    """Resolve an executable: PATH first, then the common ~/.local/bin install.

    `shutil.which` already appends the right extensions on Windows; the
    ~/.local/bin fallback checks the bare name and a `.exe` sibling so a
    user-local cargo/npm install is found even when it is not on PATH.
    """
    found = shutil.which(name)
    if found:
        return found
    local = Path.home() / ".local" / "bin"
    for candidate in (local / name, local / f"{name}.exe"):
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_mcp_bin() -> Optional[str]:
    """Path to the `wicked-estate-mcp` binary, or None if unresolvable.

    Order: WICKED_ESTATE_MCP_BIN env override > PATH > ~/.local/bin.
    """
    override = os.environ.get("WICKED_ESTATE_MCP_BIN")
    if override and Path(override).is_file():
        return override
    return _which_or_local(_MCP_BIN_NAME)


def resolve_estate_bin() -> Optional[str]:
    """Path to the `wicked-estate` CLI (used by stats()), or None.

    Order: WICKED_ESTATE_BIN env override > PATH > ~/.local/bin.
    """
    override = os.environ.get("WICKED_ESTATE_BIN")
    if override and Path(override).is_file():
        return override
    return _which_or_local(_CLI_BIN_NAME)


def resolve_db() -> Optional[str]:
    """Resolve the graph DB path, mirroring the binary's own resolution.

    Order: WICKED_ESTATE_DB env > <cwd>/.wicked-estate/graph.db (if present) >
    None. When None, callers omit `--db` and let the binary apply its default,
    so we never fight the binary's resolution — we only *pin* it when we have a
    concrete answer. `:memory:` is honoured (passed through) for tests.
    """
    env_db = os.environ.get("WICKED_ESTATE_DB")
    if env_db:
        return env_db
    try:
        candidate = Path.cwd() / _DEFAULT_DB_REL
        if candidate.is_file():
            return str(candidate)
    except OSError:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Transport seam — spawn-per-call today; swappable for a broker later
# ─────────────────────────────────────────────────────────────────────────────

def _dispatch(requests: list, *, db: Optional[str], timeout: float) -> dict:
    """Spawn-per-call transport. Return {id: response} for id-bearing requests.

    THIS IS THE ONLY FUNCTION A PERSISTENT BROKER NEEDS TO REPLACE (via
    `set_dispatch`). It receives a fully-formed batch of JSON-RPC requests
    (the handshake is already included by `_rpc`), writes them to a fresh
    `wicked-estate-mcp`, closes stdin, and returns every response line keyed by
    its `id`. Notifications (no `id`) produce no output and are simply absent.

    Fail-open: any failure returns {} — the caller treats a missing id as a
    dead call and degrades.
    """
    exe = resolve_mcp_bin()
    if not exe:
        return {}
    argv = [exe]
    if db:
        argv += ["--db", db]
    payload = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in requests)
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, ValueError):
        return {}
    try:
        out, _ = proc.communicate(input=payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        return {}
    except (OSError, ValueError):
        try:
            proc.kill()
        except Exception:
            pass
        return {}

    responses: dict = {}
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "id" in obj and obj["id"] is not None:
            responses[obj["id"]] = obj
    return responses


# Indirection so a broker can install itself without touching any caller.
_active_dispatch: Callable[..., dict] = _dispatch


def set_dispatch(fn: Callable[..., dict]) -> None:
    """Install an alternative transport (e.g. a persistent stdio broker).

    `fn` must accept `(requests, *, db, timeout)` and return {id: response},
    exactly like `_dispatch`. This is the single seam that lets the
    spawn-per-call transport be swapped for a long-lived broker later with no
    change to any public function or caller.
    """
    global _active_dispatch
    _active_dispatch = fn


# ─────────────────────────────────────────────────────────────────────────────
# JSON-RPC — handshake + one tool call, all fail-open
# ─────────────────────────────────────────────────────────────────────────────

def _rpc(method: str, params: dict, *, timeout: float) -> Optional[dict]:
    """Run one MCP method behind the initialize handshake. Return its response.

    Every spawn-per-call invocation must (re)handshake, so we always send:
      1. initialize                (id=1)
      2. notifications/initialized (notification — no id, no response)
      3. <method>                  (id=2)  ← the response we return
    Returns the id=2 response dict, or None if the call did not round-trip.
    """
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "wicked-garden-estate-shim", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
    ]
    responses = _active_dispatch(requests, db=resolve_db(), timeout=timeout)
    if 1 not in responses:  # handshake never landed → estate unreachable
        return None
    return responses.get(2)


def _unwrap(envelope: Optional[dict]) -> Optional[Any]:
    """Extract a tool's payload from an MCP tools/call envelope.

    Estate wraps results as {"result": {"content": [{"type":"text","text": …}],
    "isError": bool}}. The text is the tool's own JSON string. Returns the
    parsed payload, or None on error / isError=true / malformed shape.
    """
    if not isinstance(envelope, dict):
        return None
    result = envelope.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        return None
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return None
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # Some tools may return plain text; hand it back verbatim.
        return text


# ─────────────────────────────────────────────────────────────────────────────
# Stable call surface — what the hooks will target (see brain: search/stats/
# health/context). All fail-open. S4 rewires the hooks onto these.
# ─────────────────────────────────────────────────────────────────────────────

def health(timeout: float = 5.0) -> bool:
    """True if estate is reachable: binary resolves + initialize round-trips.

    The estate analogue of `_brain_port._health_ok()`. Spawn-per-call means a
    successful `initialize` proves the whole path (resolve → spawn → handshake).
    """
    try:
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            }
        ]
        responses = _active_dispatch(requests, db=resolve_db(), timeout=timeout)
        resp = responses.get(1)
        return bool(
            isinstance(resp, dict)
            and isinstance(resp.get("result"), dict)
            and resp["result"].get("serverInfo", {}).get("name") == "wicked-estate"
        )
    except Exception:
        return False


def call(tool: str, arguments: Optional[dict] = None, timeout: float = 8.0) -> Optional[Any]:
    """Generic seam: call any estate MCP tool, return its parsed payload or None.

    This is the low-level door the convenience wrappers below sit on, and the
    escape hatch for tools without a wrapper. Fail-open.
    """
    try:
        env = _rpc("tools/call", {"name": tool, "arguments": arguments or {}}, timeout=timeout)
        return _unwrap(env)
    except Exception:
        return None


def call_raw(tool: str, arguments: Optional[dict] = None, timeout: float = 8.0) -> Optional[dict]:
    """Like `call`, but return the full MCP envelope (for callers that need
    `isError` / staleness diagnostics). Fail-open (None)."""
    try:
        return _rpc("tools/call", {"name": tool, "arguments": arguments or {}}, timeout=timeout)
    except Exception:
        return None


def list_tools(timeout: float = 5.0) -> list:
    """Names of the tools estate currently advertises (capability probe).

    Also a liveness signal: a non-empty list means the handshake + tools/list
    round-tripped. Fail-open ([])."""
    try:
        env = _rpc("tools/list", {}, timeout=timeout)
        tools = (env or {}).get("result", {}).get("tools", [])
        return [t.get("name") for t in tools if isinstance(t, dict) and t.get("name")]
    except Exception:
        return []


def search(name: str, limit: int = 20, timeout: float = 8.0) -> list:
    """Symbol search → estate `SearchEntity`. Returns the `matches` list.

    NOTE: estate's SearchEntity is graph-symbol search (name substring), which
    is narrower than brain's FTS-over-documents. S4 owns the exact semantic
    mapping for each hook; S2 only guarantees the seam is reachable. Fail-open.
    """
    payload = call("SearchEntity", {"name": name, "limit": limit}, timeout=timeout)
    if isinstance(payload, dict):
        matches = payload.get("matches")
        return matches if isinstance(matches, list) else []
    return []


def context(
    query: Optional[str] = None,
    symbol: Optional[str] = None,
    budget: int = 8000,
    timeout: float = 8.0,
) -> Optional[Any]:
    """Packed context bundle → estate `ContextBundle`.

    Provide exactly one seed: `query` (FTS text; top hit is used) or `symbol`
    (stable SymbolId). Returns the parsed bundle, or None. Fail-open.
    """
    args: dict = {"budget": budget}
    if symbol:
        args["symbol"] = symbol
    elif query:
        args["query"] = query
    else:
        return None
    return call("ContextBundle", args, timeout=timeout)


def recall(query: str, scope: str = "", token_budget: int = 2000, timeout: float = 8.0) -> list:
    """Memory recall → estate `memory.recall`. Returns the `items` list.

    Requires the memory domain store (WICKED_MEMORY_DB / $WICKED_HOME/memory.db)
    to be present; when it is not, the tool returns an error and this yields [].
    Fail-open.
    """
    payload = call(
        "memory.recall",
        {"query": query, "scope": scope, "token_budget": token_budget},
        timeout=timeout,
    )
    if isinstance(payload, dict):
        items = payload.get("items")
        return items if isinstance(items, list) else []
    return []


def knowledge_recall(query: str, token_budget: int = 2000, timeout: float = 8.0) -> Optional[Any]:
    """Knowledge recall → estate `knowledge.recall` (hybrid FTS+vector). Fail-open."""
    return call("knowledge.recall", {"query": query, "token_budget": token_budget}, timeout=timeout)


def stats(timeout: float = 8.0) -> Optional[dict]:
    """Index summary → the `wicked-estate stats` CLI, parsed to a dict.

    The brain analogue of the `stats` action (used by hooks to detect an empty
    index). Estate does not expose stats as an MCP *tool* (the MCP surface is
    read-only graph retrieval), so this shells the estate CLI's `stats`
    subcommand — the same estate, a different, read-only entrypoint. Returns
    e.g. {"nodes": N, "edges": N, "files": N} or None. Fail-open.
    """
    exe = resolve_estate_bin()
    if not exe:
        return None
    argv = [exe, "stats"]
    db = resolve_db()
    if db:
        argv += ["--db", db]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout or ""
    result: dict = {}
    # First line looks like: "nodes=4 edges=4 files=1 db=0.2MB"
    for token in out.split():
        if "=" in token:
            key, _, val = token.partition("=")
            if key in ("nodes", "edges", "files"):
                try:
                    result[key] = int(val)
                except ValueError:
                    pass
    return result or None


# ─────────────────────────────────────────────────────────────────────────────
# CLI — the `wicked-estate-call` entry for non-Python / shell / markdown callers
#   python3 scripts/_estate_client.py <action> [json-args]
# Prints JSON to stdout; exit 0 always on a clean (even empty) result, 1 only on
# a usage error. Never crashes a caller.
# ─────────────────────────────────────────────────────────────────────────────

def _emit(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")


def main(argv: list) -> int:
    if not argv:
        _emit({"error": "usage: _estate_client.py <health|search|context|recall|"
                        "knowledge-recall|stats|list-tools|call> [json-args]"})
        return 1
    action = argv[0]
    raw = argv[1] if len(argv) > 1 else "{}"
    try:
        args = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        # Convenience: a bare positional is treated as the primary string arg.
        args = {"_": raw}

    if action == "health":
        _emit({"reachable": health()})
    elif action == "list-tools":
        _emit({"tools": list_tools()})
    elif action == "stats":
        _emit(stats() or {})
    elif action == "search":
        name = args.get("name") or args.get("query") or args.get("_", "")
        _emit({"matches": search(name, int(args.get("limit", 20)))})
    elif action == "context":
        _emit(context(query=args.get("query") or args.get("_"),
                      symbol=args.get("symbol"),
                      budget=int(args.get("budget", 8000))) or {})
    elif action == "recall":
        q = args.get("query") or args.get("_", "")
        _emit({"items": recall(q, args.get("scope", ""), int(args.get("token_budget", 2000)))})
    elif action == "knowledge-recall":
        q = args.get("query") or args.get("_", "")
        _emit(knowledge_recall(q, int(args.get("token_budget", 2000))) or {})
    elif action == "call":
        tool = args.get("tool") or args.get("name")
        if not tool:
            _emit({"error": "call requires {\"tool\": \"<ToolName>\", \"arguments\": {...}}"})
            return 1
        _emit({"result": call(tool, args.get("arguments", {}))})
    else:
        _emit({"error": f"unknown action: {action}"})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
