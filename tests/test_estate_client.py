"""tests/test_estate_client.py — the estate reach-shim contract.

Pins the seam that lets garden's Python hooks reach wicked-estate's **stdio**
MCP binary (there is no HTTP port — this is the estate analogue of
`test_brain_port.py`). Two layers:

  * Hermetic unit tests (always run): binary/DB resolution, fail-open on an
    unreachable estate, envelope unwrapping, and the transport seam — proving a
    persistent broker can replace spawn-per-call via `set_dispatch` with no
    change to any public function.

  * A live round-trip smoke test (`slow`, skipped when the estate binaries are
    absent): indexes a tiny fixture with `wicked-estate index`, then drives a
    real `wicked-estate-mcp` through the shim and asserts a `SearchEntity` call
    returns the known symbol. This is the S2 proof that the seam actually
    reaches estate.
"""

import json
import subprocess

import pytest

import _estate_client


@pytest.fixture(autouse=True)
def _restore_dispatch():
    """Save/restore the transport seam so a swap in one test cannot leak."""
    original = _estate_client._active_dispatch
    yield
    _estate_client.set_dispatch(original)


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
# Live round-trip — the S2 proof (spawns a real wicked-estate-mcp)
# ─────────────────────────────────────────────────────────────────────────────

_MCP_BIN = _estate_client.resolve_mcp_bin()
_CLI_BIN = _estate_client.resolve_estate_bin()


@pytest.mark.slow
@pytest.mark.skipif(
    _MCP_BIN is None or _CLI_BIN is None,
    reason="wicked-estate / wicked-estate-mcp not installed — live round-trip skipped",
)
def test_live_roundtrip_to_estate(tmp_path, monkeypatch):
    """Index a tiny fixture, then reach estate through the shim end-to-end."""
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
        [_CLI_BIN, "index", str(src), "--db", str(db)],
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
