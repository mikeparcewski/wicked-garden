"""tests/mem/test_estate_memory.py — the mem domain's estate backend contract.

FOLD-1/2/3 (Phase 5-S7): `scripts/mem/estate_memory.py` is the deterministic
seam between the `wicked-garden-mem` skill surface and wicked-estate's
memory/knowledge engines. Two layers:

  * Hermetic unit tests (always run): action → estate-tool argument mapping,
    kind/tier vocabulary + defaults, the kind-guarded erase, batch-capture
    partial-failure accounting, and the fail-open degrade (estate missing →
    ``{"ok": false}``, exit 0 — usage errors are the only exit-1 path).

  * Live round-trip tests (``slow``, skipped when the estate binary is
    absent): the exact CLI invocation the skills use, against scratch stores
    (WICKED_MEMORY_DB / WICKED_KNOWLEDGE_DB in a tmp dir):
    store→recall, ingest→sources-with-citation, and forget.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import _estate_client  # noqa: E402
from mem import estate_memory  # noqa: E402

_BACKEND = _REPO_ROOT / "scripts" / "mem" / "estate_memory.py"


# ── helpers ───────────────────────────────────────────────────────────────────

class _Recorder:
    """Stub for `_estate_client.call` that records (tool, arguments) and
    returns canned payloads keyed by tool name (None = unreachable)."""

    def __init__(self, payloads=None):
        self.calls: list[tuple[str, dict]] = []
        self.payloads = payloads or {}

    def __call__(self, tool, arguments=None, timeout=8.0):
        self.calls.append((tool, arguments or {}))
        return self.payloads.get(tool)


def _run(monkeypatch, capsys, action, args, recorder=None):
    """Drive estate_memory.main() in-process; return (exit_code, parsed_json)."""
    recorder = recorder or _Recorder()
    monkeypatch.setattr(estate_memory._estate_client, "call", recorder)
    code = estate_memory.main([action, json.dumps(args)])
    out = capsys.readouterr().out.strip()
    return code, json.loads(out), recorder


# ── store ─────────────────────────────────────────────────────────────────────

def test_store_maps_defaults_onto_memory_capture(monkeypatch, capsys):
    rec = _Recorder({"memory.capture": {"memory_id": "mem-1"}})
    code, out, rec = _run(monkeypatch, capsys, "store",
                          {"content": "we decided X", "about": ["x", "y"]}, rec)
    assert code == 0 and out["ok"] is True and out["memory_id"] == "mem-1"
    tool, arguments = rec.calls[0]
    assert tool == "memory.capture"
    assert arguments["kind"] == "fact"           # default kind
    assert arguments["tier"] == "semantic"       # fact's default tier
    assert arguments["scope"].startswith("project:")  # cwd-derived default
    assert arguments["about"] == ["x", "y"]


@pytest.mark.parametrize("kind,expected_tier", sorted(estate_memory.KIND_DEFAULT_TIER.items()))
def test_store_kind_default_tiers(monkeypatch, capsys, kind, expected_tier):
    rec = _Recorder({"memory.capture": {"memory_id": "m"}})
    code, out, rec = _run(monkeypatch, capsys, "store",
                          {"content": "c", "kind": kind}, rec)
    assert code == 0 and out["ok"] is True
    assert rec.calls[0][1]["tier"] == expected_tier


def test_store_rejects_unknown_kind_and_tier(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "store",
                        {"content": "c", "kind": "vibe"})
    assert code == 0 and out["ok"] is False and "unknown kind" in out["reason"]
    code, out, _ = _run(monkeypatch, capsys, "store",
                        {"content": "c", "tier": "eternal"})
    assert code == 0 and out["ok"] is False and "unknown tier" in out["reason"]


def test_store_fails_open_when_estate_unreachable(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "store", {"content": "c"})
    assert code == 0
    assert out["ok"] is False and "failed" in out["reason"]


# ── recall ────────────────────────────────────────────────────────────────────

def test_recall_defaults_to_root_scope_prefix(monkeypatch, capsys):
    rec = _Recorder({"memory.recall": {"items": [{"content": "hit"}]}})
    code, out, rec = _run(monkeypatch, capsys, "recall", {"query": "q"}, rec)
    assert code == 0 and out["items"] == [{"content": "hit"}]
    arguments = rec.calls[0][1]
    assert arguments["scope_prefix"] == ""       # recall-everything convention
    assert "scope" not in arguments


def test_recall_scope_only_uses_inheritance_semantics(monkeypatch, capsys):
    rec = _Recorder({"memory.recall": {"items": []}})
    _run(monkeypatch, capsys, "recall", {"query": "q", "scope": "project:x"}, rec)
    arguments = rec.calls[0][1]
    assert arguments["scope"] == "project:x" and "scope_prefix" not in arguments


def test_recall_requires_query(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "recall", {})
    assert code == 1 and "query" in out["error"]


# ── forget (kind-guarded erase) ───────────────────────────────────────────────

def test_forget_requires_kind_id_segment(monkeypatch, capsys):
    for bad in ("", "*", "everything", "project"):
        code, out, rec = _run(monkeypatch, capsys, "forget", {"scope_prefix": bad})
        assert code == 1, f"unguarded erase allowed for {bad!r}"
        assert "kind:id" in out["error"]
        assert rec.calls == []  # never reached estate


def test_forget_erases_subtree(monkeypatch, capsys):
    rec = _Recorder({"memory.erase": {"deleted_count": 3}})
    code, out, rec = _run(monkeypatch, capsys, "forget",
                          {"scope_prefix": "brain:old"}, rec)
    assert code == 0 and out["deleted_count"] == 3
    assert rec.calls[0] == ("memory.erase", {"scope_prefix": "brain:old"})


def test_forget_erase_all_needs_explicit_confirmation(monkeypatch, capsys):
    rec = _Recorder({"memory.erase": {"deleted_count": 9}})
    code, out, rec = _run(monkeypatch, capsys, "forget",
                          {"scope_prefix": "", "confirm_erase_all": True}, rec)
    assert code == 0 and out["deleted_count"] == 9
    assert rec.calls[0][1] == {"scope_prefix": ""}


# ── capture-batch (FOLD-3) ────────────────────────────────────────────────────

def test_capture_batch_accounts_partial_failures(monkeypatch, capsys):
    rec = _Recorder({"memory.capture": {"memory_id": "m"}})
    code, out, rec = _run(monkeypatch, capsys, "capture-batch", {"memories": [
        {"content": "a decision", "kind": "fact"},
        {"content": ""},                        # dropped: empty
        {"content": "a pattern", "kind": "skill"},
        {"content": "x", "kind": "nope"},       # dropped: bad kind
    ]}, rec)
    assert code == 0
    assert out["stored"] == 2 and out["failed"] == 2
    assert [f["index"] for f in out["failures"]] == [1, 3]
    # only the two valid items hit estate
    assert [t for t, _ in rec.calls] == ["memory.capture", "memory.capture"]


def test_capture_batch_requires_memories(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "capture-batch", {})
    assert code == 1 and "memories" in out["error"]


# ── ingest / write (FOLD-2 seam) ──────────────────────────────────────────────

def test_ingest_maps_onto_knowledge_ingest(monkeypatch, capsys):
    rec = _Recorder({"knowledge.ingest": {"doc_id": "kdoc-1"}})
    code, out, rec = _run(monkeypatch, capsys, "ingest",
                          {"title": "T", "chunks": ["c1", "c2"],
                           "source": "doc.pdf", "scope": "project:p"}, rec)
    assert code == 0 and out["doc_id"] == "kdoc-1" and out["chunks"] == 2
    tool, arguments = rec.calls[0]
    assert tool == "knowledge.ingest"
    assert arguments == {"title": "T", "chunks": ["c1", "c2"],
                         "scope": "project:p", "source": "doc.pdf"}


def test_ingest_requires_title_and_chunks(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "ingest", {"title": "T"})
    assert code == 1 and "chunks" in out["error"]


def test_write_maps_onto_knowledge_write(monkeypatch, capsys):
    rec = _Recorder({"knowledge.write": {"node_id": "k-1"}})
    code, out, rec = _run(monkeypatch, capsys, "write",
                          {"content": "a fact", "class": "concept"}, rec)
    assert code == 0 and out["ok"] is True
    tool, arguments = rec.calls[0]
    assert tool == "knowledge.write" and arguments["class"] == "concept"
    assert arguments["scope"].startswith("project:")


# ── sources (cited-answer feed) ───────────────────────────────────────────────

def test_sources_merges_knowledge_and_memory(monkeypatch, capsys):
    rec = _Recorder({
        "knowledge.recall": {"items": [{"body_snippet": "b", "source": "doc.md"}]},
        "memory.recall": {"items": [{"content": "m", "scope": "project:x"}]},
    })
    code, out, rec = _run(monkeypatch, capsys, "sources", {"query": "q"}, rec)
    assert code == 0 and out["ok"] is True
    assert out["knowledge"][0]["source"] == "doc.md"   # citation on the wire
    assert out["memories"][0]["scope"] == "project:x"
    tools = [t for t, _ in rec.calls]
    assert tools == ["knowledge.recall", "memory.recall"]


def test_sources_fails_open_when_both_stores_unreachable(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "sources", {"query": "q"})
    assert code == 0 and out["ok"] is False


# ── CLI plumbing ──────────────────────────────────────────────────────────────

def test_unknown_action_is_a_usage_error(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "explode", {})
    assert code == 1 and "usage" in out["error"]


def test_stdin_json_args(monkeypatch, capsys):
    rec = _Recorder({"memory.recall": {"items": []}})
    monkeypatch.setattr(estate_memory._estate_client, "call", rec)
    monkeypatch.setattr(estate_memory.sys, "stdin",
                        __import__("io").StringIO('{"query": "from stdin"}'))
    code = estate_memory.main(["recall", "-"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] is True
    assert rec.calls[0][1]["query"] == "from stdin"


# ── live round-trips (slow; the exact CLI path the skills invoke) ─────────────

_ESTATE_PRESENT = _estate_client.resolve_mcp_bin() is not None


def _cli(tmp_home: Path, action: str, payload: dict):
    env = dict(os.environ)
    env.update({
        "WICKED_MEMORY_DB": str(tmp_home / "memory.db"),
        "WICKED_KNOWLEDGE_DB": str(tmp_home / "knowledge.db"),
        "WICKED_XEDGE_DB": str(tmp_home / "xedge.db"),
        "WICKED_ESTATE_DB": ":memory:",
        "WICKED_ESTATE_PERSISTENT": "0",   # spawn-per-call: env re-read per call
    })
    proc = subprocess.run(
        [sys.executable, str(_BACKEND), action, json.dumps(payload)],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.slow
@pytest.mark.skipif(not _ESTATE_PRESENT, reason="wicked-estate-mcp not installed")
def test_live_store_recall_forget_round_trip(tmp_path):
    stored = _cli(tmp_path, "store", {
        "content": "Round-trip: the mem router stores through estate",
        "kind": "fact", "scope": "project:mem-live-test",
    })
    assert stored["ok"] is True and stored["memory_id"]

    recalled = _cli(tmp_path, "recall", {"query": "mem router stores through estate"})
    assert recalled["ok"] is True
    assert any("Round-trip" in item.get("content", "") for item in recalled["items"])

    erased = _cli(tmp_path, "forget", {"scope_prefix": "project:mem-live-test"})
    assert erased["ok"] is True and erased["deleted_count"] >= 1


@pytest.mark.slow
@pytest.mark.skipif(not _ESTATE_PRESENT, reason="wicked-estate-mcp not installed")
def test_live_ingest_yields_cited_sources(tmp_path):
    ingested = _cli(tmp_path, "ingest", {
        "title": "Live Fixture",
        "chunks": ["The zanzibar gate opens at dawn in the live fixture."],
        "scope": "project:mem-live-test",
        "source": "fixtures/live-fixture.md",
    })
    assert ingested["ok"] is True and ingested["doc_id"]

    sources = _cli(tmp_path, "sources", {"query": "zanzibar gate dawn"})
    assert sources["ok"] is True
    hits = [k for k in sources["knowledge"] if "zanzibar" in k.get("body_snippet", "")]
    assert hits and hits[0]["source"] == "fixtures/live-fixture.md", (
        "ingested chunk must come back citing its source"
    )
