"""tests/test_estate_client.py — the estate reach-shim contract.

Pins the seam that lets garden's Python hooks reach wicked-estate's **stdio**
MCP binary (there is no HTTP port — this is the estate analogue of
`test_brain_port.py`). Three layers:

  * Hermetic unit tests (always run): binary/DB resolution, fail-open on an
    unreachable estate, envelope unwrapping, the transport seam, and the
    persistent broker — proving set_dispatch() is a true drop-in, the broker is
    thread-safe, and the degrade/reconnect policy is enforced.

  * A live round-trip smoke test (``slow``, skipped when estate binaries are
    absent): indexes a tiny fixture with ``wicked-estate index``, then drives a
    real ``wicked-estate-mcp`` through the shim and asserts a SearchEntity call
    returns the known symbol.

  * A transport benchmark (``slow``): measures spawn-per-call vs persistent
    broker p50/p95 over 20 sequential health() calls and asserts the broker is
    materially faster.
"""

import json
import subprocess
import sys
import textwrap
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

import _estate_client


@pytest.fixture(autouse=True)
def _restore_dispatch():
    """Save/restore the transport seam so a swap in one test cannot leak."""
    original = _estate_client._active_dispatch
    yield
    _estate_client.set_dispatch(original)


# ── minimal fake MCP server (used in broker integration tests) ────────────────
# Written to a tempfile and invoked via sys.executable so it runs on any OS
# that has Python — no shebang dependency, no chmod required on Windows.

_FAKE_MCP_SRC = textwrap.dedent("""\
    import sys, json
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        if req.get("id") is None:
            continue  # notification — no response
        rid = req["id"]
        method = req.get("method", "")
        if method == "initialize":
            resp = {
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "serverInfo": {"name": "wicked-estate"},
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                }
            }
        else:
            resp = {
                "jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": "{}"}], "isError": False}
            }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
""")


@pytest.fixture()
def fake_mcp_bin(tmp_path, monkeypatch):
    """Write _FAKE_MCP_SRC to a temp file, point WICKED_ESTATE_MCP_BIN at it.

    Uses sys.executable so it works cross-platform without a Unix shebang.
    resolve_mcp_bin() is monkeypatched to return the launcher command so the
    broker spawns [sys.executable, script_path] rather than [binary_path].

    Returns: the path to the script (the Popen argv is patched separately).
    """
    script = tmp_path / "fake_estate_mcp.py"
    script.write_text(_FAKE_MCP_SRC)
    exe = sys.executable
    script_str = str(script)

    def _patched_resolve():
        return exe

    # We also need Popen to use [exe, script] not just [exe].
    # Patch subprocess.Popen inside the broker's _start() so it gets the script.
    original_popen = subprocess.Popen

    def _patched_popen(argv, **kwargs):
        # Inject the script path after the Python executable.
        if argv and argv[0] == exe:
            argv = [exe, script_str] + list(argv[1:])
        return original_popen(argv, **kwargs)

    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", _patched_resolve)
    monkeypatch.setattr(_estate_client.subprocess, "Popen", _patched_popen)
    return script_str


# ─────────────────────────────────────────────────────────────────────────────
# Resolution
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_db_prefers_env(monkeypatch):
    monkeypatch.setenv("WICKED_ESTATE_DB", "/tmp/whatever/graph.db")
    assert _estate_client.resolve_db() == "/tmp/whatever/graph.db"


def test_resolve_db_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("WICKED_ESTATE_DB", raising=False)
    monkeypatch.chdir(tmp_path)  # no .wicked-estate/graph.db here
    assert _estate_client.resolve_db() is None


def test_resolve_mcp_bin_env_override(tmp_path, monkeypatch):
    fake = tmp_path / "wicked-estate-mcp"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("WICKED_ESTATE_MCP_BIN", str(fake))
    assert _estate_client.resolve_mcp_bin() == str(fake)


# ─────────────────────────────────────────────────────────────────────────────
# Fail-open — an unreachable estate must degrade, never raise
# ─────────────────────────────────────────────────────────────────────────────

def test_fail_open_when_transport_dead(monkeypatch):
    """Transport returns {} (nothing round-tripped) → safe empty values."""
    _estate_client.set_dispatch(lambda requests, *, db, timeout: {})
    assert _estate_client.health() is False
    assert _estate_client.search("anything") == []
    assert _estate_client.recall("anything") == []
    assert _estate_client.knowledge_recall("anything") is None
    assert _estate_client.call("SearchEntity", {"name": "x"}) is None
    assert _estate_client.list_tools() == []


def test_fail_open_when_bin_missing(tmp_path, monkeypatch):
    """No binary anywhere → real _dispatch returns {}, health False, no raise."""
    monkeypatch.setenv("WICKED_ESTATE_MCP_BIN", "")
    monkeypatch.setenv("WICKED_ESTATE_BIN", "")
    monkeypatch.setattr(_estate_client, "_which_or_local", lambda name: None)
    assert _estate_client.health() is False
    assert _estate_client.search("x") == []
    assert _estate_client.stats() is None


def test_fail_open_when_server_dies_mid_batch(monkeypatch):
    """Non-zero exit → {} even if valid JSON-RPC lines landed on stdout.

    Pins the fail-open contract's 'non-zero exit' clause: a server that dies
    mid-batch may have emitted a partial response set; treating it as success
    would hand callers a half-round-trip. (A clean stdin-EOF shutdown exits 0.)
    """
    init_resp = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "wicked-estate"}}}
    )

    class _DyingProc:
        returncode = 1

        def communicate(self, input=None, timeout=None):
            return (init_resp + "\n", "")

    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: "fake-estate-mcp")
    monkeypatch.setattr(_estate_client.subprocess, "Popen", lambda *a, **k: _DyingProc())
    assert _estate_client._dispatch([json.loads(init_resp)], db=None, timeout=5) == {}
    assert _estate_client.health() is False


# ─────────────────────────────────────────────────────────────────────────────
# Envelope unwrapping
# ─────────────────────────────────────────────────────────────────────────────

def _envelope(payload, is_error=False):
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": is_error},
    }


def test_unwrap_parses_inner_json():
    env = _envelope({"matches": [{"name": "Foo"}], "total": 1})
    assert _estate_client._unwrap(env) == {"matches": [{"name": "Foo"}], "total": 1}


def test_unwrap_returns_none_on_iserror():
    assert _estate_client._unwrap(_envelope({"oops": True}, is_error=True)) is None


def test_unwrap_returns_none_on_garbage():
    assert _estate_client._unwrap(None) is None
    assert _estate_client._unwrap({"result": {}}) is None


# ─────────────────────────────────────────────────────────────────────────────
# The transport seam — a broker can replace spawn-per-call transparently
# ─────────────────────────────────────────────────────────────────────────────

def test_broker_seam_swaps_transport_without_touching_callers():
    """`set_dispatch` installs a fake transport; the public API routes through
    it unchanged — the exact property that lets a persistent broker replace
    spawn-per-call later. No subprocess is spawned here."""
    canned = {"matches": [{"name": "ReachShimProbe", "kind": "class"}], "total": 1}

    def fake_dispatch(requests, *, db, timeout):
        # Handshake always leads with id=1 initialize; a tool call adds id=2.
        methods = {r.get("id"): r.get("method") for r in requests if r.get("id") is not None}
        assert methods.get(1) == "initialize"
        out = {1: {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "wicked-estate"}}}}
        if 2 in methods:
            assert methods[2] == "tools/call"
            out[2] = _envelope(canned)
        return out

    _estate_client.set_dispatch(fake_dispatch)
    assert _estate_client.health() is True                 # initialize-only batch
    assert _estate_client.search("ReachShimProbe") == canned["matches"]  # +tools/call


# ─────────────────────────────────────────────────────────────────────────────
# Persistent broker — drop-in contract, thread-safety, reconnect/degrade
# ─────────────────────────────────────────────────────────────────────────────

def test_persistent_broker_is_drop_in_via_set_dispatch(fake_mcp_bin):
    """_PersistentBroker installed via set_dispatch() is a true drop-in.

    health() and search() work identically to the spawn-per-call path — no
    caller changes required. Pins the seam contract that the original shim PR
    described and the broker PR delivers.
    """
    broker = _estate_client._PersistentBroker()
    _estate_client.set_dispatch(broker)

    # health: should return True (initialize round-trips through fake MCP).
    assert _estate_client.health(timeout=10) is True

    # search: should return [] (fake MCP returns empty-object payload).
    result = _estate_client.search("anything", timeout=10)
    assert isinstance(result, list)

    # A second health() hits the cached init response — no re-spawn.
    assert _estate_client.health(timeout=10) is True


def test_persistent_broker_concurrency_safe():
    """10 concurrent health() calls on the same broker complete without deadlock.

    Uses a threading.Barrier to deterministically release all threads at the
    same moment, guaranteeing lock contention without relying on sleep timing.
    All 10 must return True and exactly 10 dispatch calls must be recorded.
    """
    init_resp = {
        "jsonrpc": "2.0", "id": 1,
        "result": {"serverInfo": {"name": "wicked-estate"}},
    }
    N = 10
    barrier = threading.Barrier(N)
    call_count = [0]
    count_lock = threading.Lock()

    def counting_dispatch(requests, *, db, timeout):
        barrier.wait()   # release all threads simultaneously for guaranteed contention
        with count_lock:
            call_count[0] += 1
        return {1: init_resp}

    _estate_client.set_dispatch(counting_dispatch)

    with ThreadPoolExecutor(max_workers=N) as pool:
        futures = [pool.submit(_estate_client.health) for _ in range(N)]
        results = [f.result() for f in as_completed(futures)]

    assert all(r is True for r in results), (
        f"some health() calls returned non-True: {results}"
    )
    assert call_count[0] == N, f"expected {N} dispatches, got {call_count[0]}"


def test_persistent_broker_concurrency_safe_with_real_broker(fake_mcp_bin):
    """10 concurrent health() calls through a real _PersistentBroker.

    Verifies the lock serializes correctly with a real subprocess — no
    interleaved reads, no corrupted responses, no deadlock.
    """
    broker = _estate_client._PersistentBroker()
    _estate_client.set_dispatch(broker)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_estate_client.health, 10.0) for _ in range(10)]
        results = [f.result() for f in as_completed(futures)]

    assert all(r is True for r in results), (
        f"concurrent broker health() calls returned non-True: {results}"
    )


def test_persistent_broker_reconnects_once_on_mid_exchange_death(tmp_path, monkeypatch):
    """Broker reconnects once when the process dies mid-exchange.

    The dying script handles the initialize handshake then exits immediately.
    When the broker then calls list_tools() (which sends a tools/list request
    via _exchange), the reader queue gets an EOF sentinel — _exchange returns
    None, triggering the reconnect path.  The second process (working fake)
    handles the tools/list and returns successfully.

    This test is deterministic: the reconnect is triggered through the
    _exchange → None path (not the _is_alive() between-call path), so there
    is no OS-level poll() race.
    """
    # Script that responds to initialize then exits — simulates a server that
    # crashes right after the handshake.
    dying_script = tmp_path / "dying_mcp.py"
    dying_script.write_text(textwrap.dedent("""\
        import sys, json
        for line in sys.stdin:
            line = line.strip()
            if not line: continue
            req = json.loads(line)
            if req.get("id") is None: continue  # skip notification
            resp = {"jsonrpc":"2.0","id":req["id"],
                    "result":{"serverInfo":{"name":"wicked-estate"},
                              "protocolVersion":"2024-11-05","capabilities":{}}}
            sys.stdout.write(json.dumps(resp) + "\\n")
            sys.stdout.flush()
            sys.exit(0)  # die after the first id-bearing message (initialize)
    """))

    working_script = tmp_path / "working_mcp.py"
    working_script.write_text(_FAKE_MCP_SRC)

    exe = sys.executable
    call_num = [0]
    original_popen = subprocess.Popen

    def popen_factory(argv, **kwargs):
        call_num[0] += 1
        script = str(dying_script) if call_num[0] == 1 else str(working_script)
        # argv[0] is the binary path from resolve_mcp_bin (patched to exe below);
        # pass the script as the next arg so Python runs it as a script file.
        return original_popen([exe, script] + list(argv[1:]), **kwargs)

    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: exe)
    monkeypatch.setattr(_estate_client.subprocess, "Popen", popen_factory)

    broker = _estate_client._PersistentBroker()
    _estate_client.set_dispatch(broker)

    # list_tools() goes through _exchange (sends tools/list after handshake).
    # The dying process exits after initialize, so _exchange sees EOF on the
    # first real request → reconnect_used is set → working process starts.
    tools = _estate_client.list_tools(timeout=10)

    # Observable: call completed without exception; result is a list.
    assert isinstance(tools, list), f"list_tools() returned {tools!r}, expected list"

    # Reconnect budget was consumed.
    assert broker._reconnect_used is True, "expected _reconnect_used after process death"

    # Broker is still functional — working process handles subsequent calls.
    assert _estate_client.health(timeout=10) is True


def test_persistent_broker_reconnects_on_between_call_death(tmp_path, monkeypatch):
    """Broker handles process death detected between calls (not mid-exchange).

    The dying process exits after the handshake.  We explicitly wait for it to
    die before making the next call so _is_alive() deterministically returns
    False.  The broker should restart (consuming the reconnect budget) and serve
    the second call normally.
    """
    dying_script = tmp_path / "dying_mcp.py"
    dying_script.write_text(textwrap.dedent("""\
        import sys, json
        for line in sys.stdin:
            line = line.strip()
            if not line: continue
            req = json.loads(line)
            if req.get("id") is None: continue
            resp = {"jsonrpc":"2.0","id":req["id"],
                    "result":{"serverInfo":{"name":"wicked-estate"},
                              "protocolVersion":"2024-11-05","capabilities":{}}}
            sys.stdout.write(json.dumps(resp) + "\\n")
            sys.stdout.flush()
            sys.exit(0)
    """))

    working_script = tmp_path / "working_mcp.py"
    working_script.write_text(_FAKE_MCP_SRC)

    exe = sys.executable
    call_num = [0]
    original_popen = subprocess.Popen

    def popen_factory(argv, **kwargs):
        call_num[0] += 1
        script = str(dying_script) if call_num[0] == 1 else str(working_script)
        return original_popen([exe, script] + list(argv[1:]), **kwargs)

    monkeypatch.setattr(_estate_client, "resolve_mcp_bin", lambda: exe)
    monkeypatch.setattr(_estate_client.subprocess, "Popen", popen_factory)

    broker = _estate_client._PersistentBroker()
    _estate_client.set_dispatch(broker)

    # First call: starts the dying process, caches init response via health().
    assert _estate_client.health(timeout=10) is True

    # Wait explicitly for the dying process to exit so poll() is deterministic.
    assert broker._proc is not None
    try:
        broker._proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        pass  # should not happen — dying script exits immediately

    # Second call: _is_alive() returns False (proc exited), _init_resp is set
    # → counts as reconnect → working process starts → health succeeds.
    assert _estate_client.health(timeout=10) is True
    assert broker._reconnect_used is True, "expected _reconnect_used after between-call death"


def test_persistent_broker_degrades_permanently_after_reconnect_exhausted():
    """After one reconnect, a second process death causes permanent degrade.

    Verifies the fail-open contract: once _failed is set, every subsequent
    call returns {} without raising, and health() returns False.
    """
    init_resp = {
        "jsonrpc": "2.0", "id": 1,
        "result": {"serverInfo": {"name": "wicked-estate"}},
    }

    broker = _estate_client._PersistentBroker()

    # Pre-populate broker state: already started and used its reconnect budget.
    broker._init_resp = init_resp
    broker._db = None
    broker._reconnect_used = True   # reconnect budget exhausted

    # Simulate a dead process (poll() returns non-None).
    class _DeadProc:
        stdin = None
        def poll(self): return 1

    broker._proc = _DeadProc()

    # Install the broker directly — don't go through the module-level dispatch.
    # Test the broker.__call__ interface directly.
    requests = [_estate_client._initialize_request()]
    result = broker(requests, db=None, timeout=5.0)
    assert result == {}, f"expected {{}} from dead broker, got {result}"
    assert broker._failed is True, "broker should have set _failed after exhausting reconnects"

    # Subsequent calls must also return {} without raising.
    assert broker(requests, db=None, timeout=5.0) == {}


# ─────────────────────────────────────────────────────────────────────────────
# Transport benchmark — spawn-per-call vs persistent broker (live, slow)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_broker_benchmark_vs_spawn_per_call():
    """Measure p50/p95 for spawn-per-call vs persistent broker over 20 calls.

    Requires wicked-estate-mcp to be installed. The broker must be materially
    faster (p50 broker < p50 spawn) since it eliminates the ~75ms spawn+handshake
    on every call. Aim: broker p50 ≤ 10ms (i.e., only the pipe round-trip cost).
    """
    if _estate_client.resolve_mcp_bin() is None:
        pytest.skip("wicked-estate-mcp not installed — benchmark skipped")

    N = 20
    WARMUP = 2   # discarded: first call primes the broker and OS caches

    def _percentile(data, p):
        """Linear-interpolation percentile (Python 3.10+ has statistics.quantiles)."""
        sorted_d = sorted(data)
        idx = (len(sorted_d) - 1) * p / 100
        lo, hi = int(idx), min(int(idx) + 1, len(sorted_d) - 1)
        return sorted_d[lo] + (idx - lo) * (sorted_d[hi] - sorted_d[lo])

    # ── spawn-per-call ────────────────────────────────────────────────────────
    _estate_client.set_dispatch(_estate_client._dispatch)
    spawn_ms: list = []
    for _ in range(WARMUP + N):
        t0 = time.perf_counter()
        _estate_client.health(timeout=15.0)
        spawn_ms.append((time.perf_counter() - t0) * 1000)
    spawn_ms = spawn_ms[WARMUP:]      # discard warmup

    spawn_p50 = _percentile(spawn_ms, 50)
    spawn_p95 = _percentile(spawn_ms, 95)

    # ── persistent broker ─────────────────────────────────────────────────────
    broker = _estate_client._PersistentBroker()
    _estate_client.set_dispatch(broker)
    broker_ms: list = []
    for _ in range(WARMUP + N):
        t0 = time.perf_counter()
        _estate_client.health(timeout=15.0)
        broker_ms.append((time.perf_counter() - t0) * 1000)
    broker_ms = broker_ms[WARMUP:]    # discard warmup (first call does handshake)

    broker_p50 = _percentile(broker_ms, 50)
    broker_p95 = _percentile(broker_ms, 95)

    speedup = spawn_p50 / broker_p50 if broker_p50 > 0 else float("inf")

    # Print to stdout so pytest -s shows the numbers (also captured in test log).
    print(
        f"\nTransport benchmark ({N} sequential health() calls, {WARMUP} warmup discarded):\n"
        f"  spawn-per-call  p50={spawn_p50:.1f}ms  p95={spawn_p95:.1f}ms\n"
        f"  persistent broker  p50={broker_p50:.1f}ms  p95={broker_p95:.1f}ms\n"
        f"  speedup: {speedup:.1f}x"
    )

    # Assertions: broker must be strictly faster at p50 and within a 10ms floor.
    assert broker_p50 < spawn_p50, (
        f"Broker p50 ({broker_p50:.1f}ms) is not faster than spawn p50 ({spawn_p50:.1f}ms)"
    )
    assert broker_p50 <= 10.0, (
        f"Broker p50 ({broker_p50:.1f}ms) exceeds 10ms — "
        "persistent transport overhead is unexpectedly high"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live round-trip — the S2 proof (spawns a real wicked-estate-mcp)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_live_roundtrip_to_estate(tmp_path, monkeypatch):
    """Index a tiny fixture, then reach estate through the shim end-to-end."""
    # Resolve at run time (not collection time) so the skip decision sees the
    # same environment the test itself runs under.
    mcp_bin = _estate_client.resolve_mcp_bin()
    cli_bin = _estate_client.resolve_estate_bin()
    if mcp_bin is None or cli_bin is None:
        pytest.skip(
            "wicked-estate / wicked-estate-mcp not installed — live round-trip skipped"
        )
    src = tmp_path / "src"
    src.mkdir()
    (src / "lib.py").write_text(
        "def wicked_estate_ping():\n"
        "    return 'pong'\n\n\n"
        "class ReachShimProbe:\n"
        "    def check(self):\n"
        "        return wicked_estate_ping()\n"
    )
    db = tmp_path / "graph.db"
    built = subprocess.run(
        [cli_bin, "index", str(src), "--db", str(db)],
        capture_output=True, text=True, timeout=120,
    )
    assert built.returncode == 0, f"index failed: {built.stderr}"
    assert db.is_file()

    monkeypatch.setenv("WICKED_ESTATE_DB", str(db))

    # 1. health — spawn + initialize handshake round-trips.
    assert _estate_client.health(timeout=30) is True

    # 2. capability probe — the full read-tool floor is advertised.
    tools = _estate_client.list_tools(timeout=30)
    assert "SearchEntity" in tools

    # 3. the S2 proof: a SearchEntity call returns the known symbol.
    matches = _estate_client.search("ReachShimProbe", limit=5, timeout=30)
    names = {m.get("name") for m in matches}
    assert "ReachShimProbe" in names, f"expected ReachShimProbe in {names}"

    # 4. stats CLI analogue reflects the indexed graph.
    st = _estate_client.stats(timeout=30)
    assert st and st.get("nodes", 0) >= 1
