"""tests/test_context_backend.py — the context-backend seam contract (estate-only).

Pins the seam between garden's context-assembly layer and wicked-estate
(scripts/_context_backend.py), post-S7 (wicked-brain retired):

  * WICKED_CONTEXT_BACKEND flag semantics (estate | off; legacy bridge
    values ``auto``/``brain`` and unknown values mean estate);
  * the estate two-call recall fusion (knowledge.recall + memory.recall,
    RRF-merged) including normalization and #96 source attribution;
  * fail-open degradation: estate dead ⇒ empty results, never an exception;
  * ``off`` mode: designed silence — empty results, no notes, no probes;
  * capture_memory (estate memory.capture);
  * stats TTL caching (per-session file cache — never re-probed per prompt).

Hermetic: the estate side is faked by planting a fake ``_estate_client``
module in sys.modules. No subprocess, no network.
"""

import sys
import time
import types

import pytest

import _context_backend as cb


@pytest.fixture(autouse=True)
def _clean_router(monkeypatch, tmp_path):
    """Isolate every test: default flag, tmp stats cache."""
    monkeypatch.delenv("WICKED_CONTEXT_BACKEND", raising=False)
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE", raising=False)
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE_PREFIX", raising=False)
    monkeypatch.delenv("WICKED_CONTEXT_STATS_TTL_SECS", raising=False)
    cache_file = tmp_path / "ctx-stats.json"
    monkeypatch.setattr(cb, "_stats_cache_path", lambda: cache_file)
    yield


def _plant_fake_estate(monkeypatch, **overrides):
    """Install a fake _estate_client module; returns it for call inspection."""
    fake = types.ModuleType("_estate_client")
    fake.calls = []

    def knowledge_recall(query, token_budget=2000, timeout=8.0):
        fake.calls.append(("knowledge_recall", query))
        return {"items": []}

    def recall(query, scope="", token_budget=2000, timeout=8.0, scope_prefix=None):
        fake.calls.append(("recall", query, scope, scope_prefix))
        return []

    def call(tool, arguments=None, timeout=8.0):
        fake.calls.append(("call", tool, arguments))
        return None

    def resolve_mcp_bin():
        return "/fake/wicked-estate-mcp"

    fake.knowledge_recall = knowledge_recall
    fake.recall = recall
    fake.call = call
    fake.resolve_mcp_bin = resolve_mcp_bin
    for name, fn in overrides.items():
        setattr(fake, name, fn)
    monkeypatch.setitem(sys.modules, "_estate_client", fake)
    return fake


# ─────────────────────────────────────────────────────────────────────────────
# Flag semantics
# ─────────────────────────────────────────────────────────────────────────────

def test_backend_mode_defaults_to_estate():
    assert cb.backend_mode() == "estate"


def test_backend_mode_honors_flag(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "estate")
    assert cb.backend_mode() == "estate"
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "off")
    assert cb.backend_mode() == "off"


@pytest.mark.parametrize("legacy", ["auto", "brain", "banana", "  ESTATE  "])
def test_backend_mode_legacy_and_unknown_values_mean_estate(monkeypatch, legacy):
    """S7: the bridge-period values (auto/brain) and anything unknown fall
    back to estate — auto was 'estate primary' and the brain route is gone."""
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", legacy)
    assert cb.backend_mode() == "estate"


# ─────────────────────────────────────────────────────────────────────────────
# Estate search — fusion + normalization + attribution
# ─────────────────────────────────────────────────────────────────────────────

_K_ITEM = {
    "node_id": "kchunk 1",
    "class": "chunk",
    "label": "archetype detection",
    "body_snippet": "the v11 archetype detector routes prompts",
    "score": 0.7,
    "source": "wicked-brain://wicked-garden/chunks/extracted/scripts-crew-archetypes.md/chunk-001.md",
}
_M_ITEM = {
    "memory_id": "mem 9",
    "scope": "brain:wicked-garden/doc:mem-abc.md",
    "content": "Decision: gate policy lives in gate-policy.json\n\nbody text",
    "tier": "semantic",
    "score": 0.4,
}


def test_estate_search_fuses_knowledge_and_memory(monkeypatch):
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: {"items": [_K_ITEM]},
        recall=lambda q, scope="", token_budget=2000, timeout=8.0, scope_prefix=None: [_M_ITEM],
    )
    results = cb.search("how does gate policy work", limit=10)
    assert len(results) == 2
    kinds = {r["kind"] for r in results}
    assert kinds == {"chunk", "memory"}
    # RRF: both are rank-0 in their lists → equal fused scores
    assert results[0]["score"] == pytest.approx(results[1]["score"])


def test_estate_search_recalls_the_full_memory_subtree(monkeypatch):
    """estate #98: the memory leg sends scope_prefix="" (root subtree) so
    migrated leaf-scoped memories (brain:…/doc:…) are fused in — they were
    invisible under the ancestor-only `scope` filter."""
    fake = _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: {"items": []},
    )
    cb.search("gh account switch 403", limit=10)
    recall_calls = [c for c in fake.calls if c[0] == "recall"]
    assert recall_calls == [("recall", "gh account switch 403", "", "")]


def test_memory_scope_prefix_defaults_and_overrides(monkeypatch):
    # Default: root subtree — every memory, migrated subtrees included.
    assert cb._memory_scope_prefix() == ""
    # A pinned custom scope keeps its ancestor-visible meaning (param omitted).
    monkeypatch.setenv("WICKED_ESTATE_MEMORY_SCOPE", "org:acme")
    assert cb._memory_scope_prefix() is None
    # The explicit prefix override wins over both.
    monkeypatch.setenv("WICKED_ESTATE_MEMORY_SCOPE_PREFIX", "brain:wicked-garden")
    assert cb._memory_scope_prefix() == "brain:wicked-garden"


def test_estate_search_degrades_to_knowledge_only_when_memory_leg_fails(monkeypatch):
    """An older binary rejecting scope_prefix (or any memory-leg blowup) must
    degrade the fusion to knowledge-only — never estate-down, never a raise."""

    def recall_pre_98(query, scope="", token_budget=2000, timeout=8.0):
        raise TypeError("recall() got an unexpected keyword argument 'scope_prefix'")

    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: {"items": [_K_ITEM]},
        recall=recall_pre_98,
    )
    results = cb.search("how does gate policy work", limit=10)
    assert [r["kind"] for r in results] == ["chunk"]
    assert results[0]["backend"] == "estate"


def test_recall_memories_uses_the_subtree_prefix_too(monkeypatch):
    """Memory-only recall gets the same #98 subtree visibility as the fusion."""
    fake = _plant_fake_estate(monkeypatch)
    assert cb.recall_memories("gate policy decisions") == []
    recall_calls = [c for c in fake.calls if c[0] == "recall"]
    assert recall_calls == [("recall", "gate policy decisions", "", "")]


def test_estate_search_surfaces_source_attribution(monkeypatch):
    """#96: estate `source` (knowledge) and scope (memory) survive normalization."""
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: {"items": [_K_ITEM]},
        recall=lambda q, scope="", token_budget=2000, timeout=8.0, scope_prefix=None: [_M_ITEM],
    )
    results = cb.search("gate policy", limit=10)
    by_kind = {r["kind"]: r for r in results}
    assert by_kind["chunk"]["source"].startswith("wicked-brain://wicked-garden/chunks/")
    assert by_kind["memory"]["scope"] == "brain:wicked-garden/doc:mem-abc.md"
    assert by_kind["memory"]["source"] == "brain:wicked-garden/doc:mem-abc.md"
    assert by_kind["memory"]["title"].startswith("Decision: gate policy")
    assert all(r["backend"] == "estate" for r in results)


def test_rrf_fusion_ranks_earlier_items_higher():
    a = [{"id": f"a{i}", "snippet": ""} for i in range(3)]
    fused = cb._rrf_fuse([a], limit=10)
    assert [r["id"] for r in fused] == ["a0", "a1", "a2"]
    assert fused[0]["score"] > fused[1]["score"] > fused[2]["score"]


def test_rrf_fusion_dedupes_by_id_and_sums_scores():
    a = [{"id": "x", "snippet": "s"}]
    b = [{"id": "x", "snippet": "s"}]
    fused = cb._rrf_fuse([a, b], limit=10)
    assert len(fused) == 1
    assert fused[0]["score"] == pytest.approx(2.0 / (cb._RRF_K + 1))


def test_estate_search_empty_is_a_valid_answer(monkeypatch):
    """A reachable-but-empty estate answer stays [] — a valid result."""
    _plant_fake_estate(monkeypatch)  # both recalls return empty
    assert cb.search("plain english question") == []


# ─────────────────────────────────────────────────────────────────────────────
# Fail-open degradation
# ─────────────────────────────────────────────────────────────────────────────

def test_search_fails_open_when_estate_dead(monkeypatch):
    """The keystone guarantee: estate dead ⇒ [] — never a raise."""
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: None,
    )
    assert cb.search("anything at all") == []


def test_search_fails_open_when_estate_module_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "_estate_client", None)  # import → error
    assert cb.search("anything at all") == []


def test_recall_memories_fails_open_when_estate_module_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "_estate_client", None)
    assert cb.recall_memories("anything") == []


# ─────────────────────────────────────────────────────────────────────────────
# off mode — designed silence, no probes
# ─────────────────────────────────────────────────────────────────────────────

def test_off_mode_search_is_empty_and_never_touches_estate(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "off")
    fake = _plant_fake_estate(monkeypatch)
    assert cb.search("anything") == []
    assert cb.recall_memories("anything") == []
    assert fake.calls == []


def test_off_mode_capture_returns_none_without_probing(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "off")
    fake = _plant_fake_estate(monkeypatch)
    assert cb.capture_memory("t", "c") is None
    assert fake.calls == []


def test_off_mode_stats_and_notes_are_silent(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "off")
    fake = _plant_fake_estate(monkeypatch)
    assert cb.stats() is None
    assert cb.health() is False
    assert cb.gate_note() is None
    assert cb.staleness_note() is None
    assert cb.estate_dependency() == (None, None)
    assert fake.calls == []


# ─────────────────────────────────────────────────────────────────────────────
# capture_memory
# ─────────────────────────────────────────────────────────────────────────────

def test_capture_memory_calls_memory_capture(monkeypatch):
    captured = {}

    def call(tool, arguments=None, timeout=8.0):
        captured["tool"] = tool
        captured["args"] = arguments
        return {"memory_id": "mem xyz"}

    _plant_fake_estate(monkeypatch, call=call)
    mem_id = cb.capture_memory(
        "Session goal (turn 1)", "do the thing", tier="working",
        tags=["session-goal", "auto-captured"],
    )
    assert mem_id == "mem xyz"
    assert captured["tool"] == "memory.capture"
    assert captured["args"]["kind"] == "working"
    assert captured["args"]["tier"] == "working"
    assert captured["args"]["about"] == ["session-goal", "auto-captured"]
    assert captured["args"]["content"].startswith("Session goal (turn 1)")


def test_capture_memory_fails_open_when_estate_dead(monkeypatch):
    _plant_fake_estate(monkeypatch)  # call() returns None → write failed
    assert cb.capture_memory("t", "c") is None


def test_capture_memory_rejects_empty_content(monkeypatch):
    fake = _plant_fake_estate(monkeypatch)
    assert cb.capture_memory("", "") is None
    assert fake.calls == []


# ─────────────────────────────────────────────────────────────────────────────
# stats — TTL cache, never per-prompt
# ─────────────────────────────────────────────────────────────────────────────

def _coverage_call(counter):
    def call(tool, arguments=None, timeout=8.0):
        counter["n"] += 1
        if tool == "knowledge.coverage":
            return {"total": 11719}
        if tool == "memory.coverage":
            return {"total": 205}
        return None
    return call


def test_stats_estate_shape_and_totals(monkeypatch):
    _plant_fake_estate(monkeypatch, call=_coverage_call({"n": 0}))
    s = cb.stats()
    assert s == {
        "backend": "estate",
        "knowledge_total": 11719,
        "memory_total": 205,
        "total": 11924,
    }


def test_stats_second_call_is_served_from_cache(monkeypatch):
    counter = {"n": 0}
    _plant_fake_estate(monkeypatch, call=_coverage_call(counter))
    first = cb.stats()
    probes_after_first = counter["n"]
    second = cb.stats()
    assert counter["n"] == probes_after_first  # no re-probe within TTL
    assert second == first


def test_stats_cache_expires_after_ttl(monkeypatch):
    counter = {"n": 0}
    _plant_fake_estate(monkeypatch, call=_coverage_call(counter))
    monkeypatch.setenv("WICKED_CONTEXT_STATS_TTL_SECS", "0")
    cb.stats()
    probes_after_first = counter["n"]
    time.sleep(0.01)
    cb.stats()
    assert counter["n"] > probes_after_first


def test_stats_failure_is_cached_with_short_ttl(monkeypatch, tmp_path):
    """A dead estate is not re-probed on every prompt — the failure record
    short-circuits until its (shorter) TTL lapses."""
    counter = {"n": 0}

    def dead_call(tool, arguments=None, timeout=8.0):
        counter["n"] += 1
        return None

    _plant_fake_estate(monkeypatch, call=dead_call)
    assert cb.stats() is None
    probes_after_first = counter["n"]
    assert cb.stats() is None
    assert counter["n"] == probes_after_first  # served from failure record


# ─────────────────────────────────────────────────────────────────────────────
# Hook-facing notes + directive targets
# ─────────────────────────────────────────────────────────────────────────────

def test_gate_note_silent_when_estate_healthy(monkeypatch):
    _plant_fake_estate(monkeypatch, call=_coverage_call({"n": 0}))
    assert cb.gate_note() is None


def test_gate_note_degraded_when_estate_dead(monkeypatch):
    _plant_fake_estate(monkeypatch)
    note = cb.gate_note()
    assert note is not None
    assert "fail open" in note or "degraded" in note


def test_staleness_note_empty_estate_store_points_at_ingest(monkeypatch):
    def empty_call(tool, arguments=None, timeout=8.0):
        return {"total": 0}

    _plant_fake_estate(monkeypatch, call=empty_call)
    note = cb.staleness_note()
    assert note is not None and "empty" in note


def test_memory_directive_target_names_the_mem_skill():
    """The directive must name the same surface the PostToolUse compliance
    reset watches (the wicked-garden-mem skill), not the raw MCP tool."""
    target = cb.memory_directive_target()
    assert "wicked-garden-mem" in target
    assert "brain" not in target


def test_grounding_lines_are_estate_worded():
    lines = cb.grounding_directive_lines()
    assert any("wicked-garden-mem" in line for line in lines)
    assert not any("wicked-brain" in line for line in lines)


def test_estate_dependency_missing_binary(monkeypatch):
    _plant_fake_estate(monkeypatch, resolve_mcp_bin=lambda: None)
    available, note = cb.estate_dependency()
    assert available is False
    assert "wicked-estate" in note


def test_estate_dependency_healthy(monkeypatch):
    _plant_fake_estate(monkeypatch, call=_coverage_call({"n": 0}))
    available, note = cb.estate_dependency()
    assert available is True
    assert note is None
