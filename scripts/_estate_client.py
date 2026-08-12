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
**Persistent stdio broker** (default): a single `wicked-estate-mcp` subprocess
is kept alive for the Python process lifetime. All dispatches are serialized
through a lock; the initialize handshake is done once at startup, so hot-path
calls pay only the JSON encode/decode + pipe round-trip cost (~1ms vs ~80ms for
spawn-per-call). On subprocess death the broker reconnects once; on a second
death it degrades gracefully. Set `WICKED_ESTATE_PERSISTENT=0` to fall back to
spawn-per-call (useful for debugging or when strict process isolation matters).

**Spawn-per-call** (fallback / escape hatch): each call spawns
`wicked-estate-mcp`, does the `initialize` handshake, issues one `tools/call`,
parses the result, and lets the process exit on stdin EOF. Available via
`set_dispatch(_dispatch)` or `WICKED_ESTATE_PERSISTENT=0` env var.

The spawn-vs-broker choice is an implementation detail behind a single seam:
`_dispatch()` / `_PersistentBroker.__call__()` (installed as `_active_dispatch`
and swappable via `set_dispatch()`). Every public function routes through it, so
**no caller changes** when the transport does.

Fail-open contract
------------------
Every public function is fail-open: on a missing binary, spawn failure,
timeout, non-zero exit, malformed JSON, or a tool `isError`, it returns a safe
empty value (`False` / `None` / `[]`) and never raises. Hooks degrade; they do
not crash.

Cross-platform
--------------
Pure stdlib. `subprocess` with an argv list (no shell). `shutil.which` resolves
`.exe`/`.cmd` on Windows. All paths via `pathlib`; all wire framing via `json`.
The broker uses `threading.Lock` + `queue.Queue` — both stdlib, cross-platform.
"""

import atexit
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
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

    # Fail-open contract: a non-zero exit means the server died mid-batch —
    # any output it managed to emit is suspect, so degrade to {} rather than
    # hand back a partial round-trip as success. (A clean stdin-EOF shutdown
    # exits 0; wicked-estate-mcp's main loop returns Ok(()) on EOF.)
    if proc.returncode != 0:
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
    exactly like `_dispatch`. This is the single seam that lets the transport
    be swapped with no change to any public function or caller.
    """
    global _active_dispatch
    _active_dispatch = fn


# ─────────────────────────────────────────────────────────────────────────────
# Persistent stdio broker — one subprocess per Python process, lock-serialized
# ─────────────────────────────────────────────────────────────────────────────

class _PersistentBroker:
    """Keep one wicked-estate-mcp subprocess alive per Python process.

    The initialize handshake is done once at first use. Subsequent calls pay
    only the JSON encode/decode + pipe round-trip — no per-call spawn or
    handshake overhead. All dispatches are serialized through `_lock`, so the
    class is thread-safe without request-ID multiplexing.

    Reconnect policy
    ----------------
    On subprocess death detected during a call, the broker attempts one
    reconnect. If the reconnect itself fails or the new process dies on its
    first use, `_failed` is set and every subsequent call returns {} (permanent
    degrade). The reconnect budget is per Python-process-lifetime.

    Escape hatch
    ------------
    ``WICKED_ESTATE_PERSISTENT=0`` prevents auto-install at import time.
    ``set_dispatch(_dispatch)`` restores spawn-per-call at runtime.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None   # type: ignore[type-arg]
        self._init_resp: Optional[dict] = None           # cached after handshake
        self._db: Optional[str] = None                   # db the process was started with
        self._q: queue.Queue = queue.Queue()             # response lines from reader thread
        self._failed: bool = False                        # permanent-degrade flag
        self._reconnect_used: bool = False               # one reconnect per lifetime
        atexit.register(self._close)

    # ── subprocess lifecycle ──────────────────────────────────────────────────

    def _start(self, db: Optional[str]) -> bool:
        """Spawn and handshake. Returns True on success; cleans up on failure."""
        exe = resolve_mcp_bin()
        if not exe:
            return False
        argv = [exe]
        if db:
            argv += ["--db", db]

        # Fresh queue per session: a previous reader thread may enqueue an EOF
        # sentinel *after* any drain loop runs, corrupting the new session.
        # Creating a new Queue guarantees cross-session isolation.
        self._q = queue.Queue()

        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (OSError, ValueError):
            return False

        # Start the reader thread *before* writing so no response line is lost.
        threading.Thread(
            target=self._reader_loop,
            args=(proc.stdout, self._q),
            daemon=True,
        ).start()

        # Send initialize + notifications/initialized.
        init_req = _initialize_request()
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        try:
            proc.stdin.write(json.dumps(init_req, separators=(",", ":")) + "\n")
            proc.stdin.write(json.dumps(notif, separators=(",", ":")) + "\n")
            proc.stdin.flush()
        except OSError:
            self._kill(proc)
            return False

        # Read and validate the initialize response (5 s timeout — not the
        # caller's timeout; this is the one-time startup handshake).
        line = self._dequeue(5.0)
        if line is None:
            self._kill(proc)
            return False
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            self._kill(proc)
            return False
        if not (
            isinstance(resp, dict)
            and isinstance(resp.get("result"), dict)
            and resp["result"].get("serverInfo", {}).get("name") == "wicked-estate"
        ):
            self._kill(proc)
            return False

        self._proc = proc
        self._init_resp = resp
        self._db = db
        return True

    @staticmethod
    def _reader_loop(stdout: Any, q: "queue.Queue[tuple]") -> None:
        """Daemon thread: stream stdout lines into q, put ("eof", None) on close."""
        try:
            for line in stdout:
                stripped = line.rstrip("\n")
                if stripped:
                    q.put(("data", stripped))
        except Exception:
            pass
        q.put(("eof", None))

    def _dequeue(self, timeout: float) -> Optional[str]:
        """Pull the next response line from the reader queue.

        Returns the line string on success, None on timeout or EOF.
        An EOF sentinel is re-enqueued so later callers also see it.
        """
        try:
            kind, value = self._q.get(timeout=timeout)
        except queue.Empty:
            return None
        if kind == "eof":
            self._q.put(("eof", None))   # re-enqueue: future callers must see EOF too
            return None
        return value                     # kind == "data"

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
        try:
            proc.kill()
        except Exception:
            pass

    def _close(self) -> None:
        """atexit / planned teardown: close stdin so the server exits on EOF."""
        proc = self._proc
        self._proc = None
        self._init_resp = None
        if proc is None:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=1)
            except Exception:
                pass
        except Exception:
            pass

    # ── exchange ─────────────────────────────────────────────────────────────

    def _exchange(self, real: list, *, timeout: float) -> Optional[dict]:
        """Write id-bearing non-initialize requests, collect one response each.

        Returns {req_id: response} on success, None if a write or read fails
        (caller interprets None as process death and triggers reconnect logic).
        """
        try:
            for req in real:
                self._proc.stdin.write(json.dumps(req, separators=(",", ":")) + "\n")
            self._proc.stdin.flush()
        except OSError:
            return None

        responses: dict = {}
        for req in real:
            # Read until we get the id-bearing response for this request.
            # Notifications (id absent or None) are silently skipped so that
            # any server-initiated notification cannot displace a real response.
            while True:
                line = self._dequeue(timeout)
                if line is None:
                    return None
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("id") is not None:
                    responses[obj["id"]] = obj
                    break
                # Notification — skip and read the next line.
        return responses

    # ── dispatch (public callable) ────────────────────────────────────────────

    def __call__(self, requests: list, *, db: Optional[str], timeout: float) -> dict:
        """Drop-in replacement for ``_dispatch``. Identical signature; persistent
        transport. Thread-safe: all work happens under ``self._lock``."""
        with self._lock:
            return self._locked(requests, db=db, timeout=timeout)

    def _locked(self, requests: list, *, db: Optional[str], timeout: float) -> dict:
        """Called under self._lock. Returns {id: response}, {} on any failure."""
        if self._failed:
            return {}

        # Ensure the process is running. Three cases:
        #  (a) First start: no process, no init_resp yet — start freely.
        #  (b) Unexpected death between calls: process gone, init_resp present —
        #      consumes the one reconnect budget; degrade if budget exhausted.
        #  (c) Planned restart: DB changed while process is still alive —
        #      close + restart, NOT counted against the reconnect budget.
        if not self._is_alive() or self._db != db:
            previously_started = self._init_resp is not None
            if not self._is_alive() and previously_started:
                # Case (b): death between calls.
                if self._reconnect_used:
                    self._failed = True
                    return {}
                self._reconnect_used = True
            elif self._is_alive() and self._db != db:
                # Case (c): DB changed — close old process before restarting.
                self._close()
            if not self._start(db):
                # Only mark permanently failed when this is a reconnect path
                # (previously_started). A first-start failure is transient
                # (binary not yet installed, temporary spawn error) and must
                # not permanently degrade the broker for the process lifetime.
                if previously_started:
                    self._failed = True
                return {}

        # Partition: skip initialize + notifications (already done at startup).
        real = [
            r for r in requests
            if r.get("id") is not None and r.get("method") != "initialize"
        ]

        # Health / initialize-only probe → return cached init response directly.
        if not real:
            return {1: self._init_resp}

        # Send requests and collect responses.
        result = self._exchange(real, timeout=timeout)
        if result is None:
            # Process died mid-exchange. One reconnect attempt allowed per lifetime.
            self._close()
            if self._reconnect_used:
                self._failed = True
                return {}
            self._reconnect_used = True
            if not self._start(db):
                self._failed = True
                return {}
            result = self._exchange(real, timeout=timeout)
            if result is None:
                self._failed = True
                return {}

        return {1: self._init_resp, **result}


def _maybe_install_broker() -> None:
    """Install the persistent broker at module import unless opted out.

    Escape hatch: ``WICKED_ESTATE_PERSISTENT=0`` keeps spawn-per-call.
    Callers can also call ``set_dispatch(_dispatch)`` at runtime to revert,
    or ``set_dispatch(_PersistentBroker())`` to get a fresh broker instance.
    """
    if os.environ.get("WICKED_ESTATE_PERSISTENT", "1") == "0":
        return
    set_dispatch(_PersistentBroker())


_maybe_install_broker()


# ─────────────────────────────────────────────────────────────────────────────
# JSON-RPC — handshake + one tool call, all fail-open
# ─────────────────────────────────────────────────────────────────────────────

def _initialize_request() -> dict:
    """The ONE initialize request every handshake uses (id=1).

    Single source of truth so `health()` probes with exactly the same shape a
    real tool call sends — if the server ever gets stricter about initialize
    fields, health and the call path cannot diverge.
    """
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "wicked-garden-estate-shim", "version": "0"},
        },
    }


def _rpc(method: str, params: dict, *, timeout: float) -> Optional[dict]:
    """Run one MCP method behind the initialize handshake. Return its response.

    Every spawn-per-call invocation must (re)handshake, so we always send:
      1. initialize                (id=1)
      2. notifications/initialized (notification — no id, no response)
      3. <method>                  (id=2)  ← the response we return
    Returns the id=2 response dict, or None if the call did not round-trip.
    """
    requests = [
        _initialize_request(),
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
    "isError": bool}}. The text is usually the tool's own JSON string, which is
    parsed and returned; a tool that emits plain (non-JSON) text gets its text
    handed back verbatim as a str. Returns None on error / isError=true /
    a malformed envelope shape.
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
        requests = [_initialize_request()]
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


def recall(
    query: str,
    scope: str = "",
    token_budget: int = 2000,
    timeout: float = 8.0,
    scope_prefix: Optional[str] = None,
) -> list:
    """Memory recall → estate `memory.recall`. Returns the `items` list.

    ``scope_prefix`` (estate #98): when not None it is sent on the wire and
    REPLACES the ancestor-visible ``scope`` filter with subtree matching —
    ``""`` means the root subtree, i.e. every memory including migrated
    leaf scopes like ``brain:wicked-garden/doc:<id>``. None omits the param
    (inheritance behavior, and the only shape pre-#98 binaries understand).
    An older binary that rejects the param surfaces as a tool error → [] —
    the same fail-open degrade as any other recall failure.

    Requires the memory domain store (WICKED_MEMORY_DB / $WICKED_HOME/memory.db)
    to be present; when it is not, the tool returns an error and this yields [].
    Fail-open.
    """
    arguments: dict = {"query": query, "scope": scope, "token_budget": token_budget}
    if scope_prefix is not None:
        arguments["scope_prefix"] = scope_prefix
    payload = call("memory.recall", arguments, timeout=timeout)
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
        _emit({"items": recall(q, args.get("scope", ""), int(args.get("token_budget", 2000)),
                               scope_prefix=args.get("scope_prefix"))})
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
