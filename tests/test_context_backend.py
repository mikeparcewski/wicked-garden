"""tests/test_context_backend.py — the S4 context-backend router contract.

Pins the seam that retargets garden's context-assembly layer from
wicked-brain onto wicked-estate (scripts/_context_backend.py):

  * the symbolish classifier (identifier-shaped queries route to brain
    while the bridge is alive — per the S3 parity bench);
  * WICKED_CONTEXT_BACKEND flag semantics (estate | brain | auto);
  * the estate two-call recall fusion (knowledge.recall + memory.recall,
    RRF-merged) including normalization and #96 source attribution;
  * fail-open degradation: estate dead + brain dead ⇒ empty results, never
    an exception (the exact brain-absent behavior hooks rely on today);
  * capture_memory routing (estate memory.capture primary; legacy brain
    path under the flag);
  * stats TTL caching (per-session file cache — never re-probed per prompt).

Hermetic: the estate side is faked by planting a fake ``_estate_client``
module in sys.modules; the brain side by monkeypatching ``_brain_api`` /
``brain_alive``. No subprocess, no network.
"""

import json
import sys
import time
import types

import pytest

import _context_backend as cb


@pytest.fixture(autouse=True)
def _clean_router(monkeypatch, tmp_path):
    """Isolate every test: default flag, cold probe memo, tmp stats cache."""
    monkeypatch.delenv("WICKED_CONTEXT_BACKEND", raising=False)
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE", raising=False)
    monkeypatch.delenv("WICKED_CONTEXT_STATS_TTL_SECS", raising=False)
    cb._reset_probe_cache()
    cache_file = tmp_path / "ctx-stats.json"
    monkeypatch.setattr(cb, "_stats_cache_path", lambda: cache_file)
    yield
    cb._reset_probe_cache()
    sys.modules.pop("_fake_estate_marker", None)


def _plant_fake_estate(monkeypatch, **overrides):
    """Install a fake _estate_client module; returns it for call inspection."""
    fake = types.ModuleType("_estate_client")
    fake.calls = []

    def knowledge_recall(query, token_budget=2000, timeout=8.0):
        fake.calls.append(("knowledge_recall", query))
        return {"items": []}

    def recall(query, scope="", token_budget=2000, timeout=8.0):
        fake.calls.append(("recall", query, scope))
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
# Classifier
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "where is resolve_port used",                # snake_case
    "explain SessionState.load behavior",        # dotted + CamelCase
    "fix the bug in prompt_submit.py",           # bare code filename
    "from _brain_port import resolve_port",      # import-like
    "hooks/scripts/bootstrap.py brain gate",     # path-like
    "what does _PersistentBroker do",            # CamelCase-ish snake mix
    "wicked_estate::GraphStore lifetime",        # rust path
])
def test_is_symbolish_positives(query):
    assert cb.is_symbolish(query) is True


@pytest.mark.parametrize("query", [
    "how does the acceptance pipeline decide a verdict",
    "what are the constraints around memory decay",
    "explain the crew workflow phases",
    "why does onboarding require a wizard",
    "e.g. the general case, i.e. plain English",  # 1-char dotted segments
    "",
])
def test_is_symbolish_negatives(query):
    assert cb.is_symbolish(query) is False


# ─────────────────────────────────────────────────────────────────────────────
# Flag semantics + routing
# ─────────────────────────────────────────────────────────────────────────────

def test_backend_mode_defaults_to_auto():
    assert cb.backend_mode() == "auto"


def test_backend_mode_honors_flag(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "estate")
    assert cb.backend_mode() == "estate"
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "brain")
    assert cb.backend_mode() == "brain"


def test_backend_mode_unknown_value_falls_back_to_auto(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "banana")
    assert cb.backend_mode() == "auto"


def test_route_estate_flag_is_absolute(monkeypatch):
    """estate mode never consults brain, even for symbolish queries."""
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "estate")
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert cb.route("resolve_port usage") == "estate"


def test_route_brain_flag_is_absolute(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "brain")
    assert cb.route("plain english question") == "brain"


def test_route_auto_symbolish_goes_to_brain_while_alive(monkeypatch):
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert cb.route("where is resolve_port used") == "brain"


def test_route_auto_symbolish_degrades_to_estate_when_brain_gone(monkeypatch):
    """The incremental-retire property: brain absent ⇒ auto is estate-only."""
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    assert cb.route("where is resolve_port used") == "estate"


def test_route_auto_nonsymbolish_goes_to_estate_even_with_brain_alive(monkeypatch):
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert cb.route("how does the crew workflow decide phases") == "estate"


def test_route_queryless_operations_default_to_estate(monkeypatch):
    """Writes and stats (no query) route estate-first in auto."""
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert cb.route() == "estate"


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
        recall=lambda q, scope="", token_budget=2000, timeout=8.0: [_M_ITEM],
    )
    results = cb.search("how does gate policy work", limit=10)
    assert len(results) == 2
    kinds = {r["kind"] for r in results}
    assert kinds == {"chunk", "memory"}
    # RRF: both are rank-0 in their lists → equal fused scores
    assert results[0]["score"] == pytest.approx(results[1]["score"])


def test_estate_search_surfaces_source_attribution(monkeypatch):
    """#96: estate `source` (knowledge) and scope (memory) survive normalization."""
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: {"items": [_K_ITEM]},
        recall=lambda q, scope="", token_budget=2000, timeout=8.0: [_M_ITEM],
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


def test_estate_search_empty_is_a_valid_answer_no_brain_bounce(monkeypatch):
    """A reachable-but-empty estate answer stays [] — no bounce to brain."""
    _plant_fake_estate(monkeypatch)  # both recalls return empty
    called = {"brain": False}

    def brain_search(q, limit=10):
        called["brain"] = True
        return []

    monkeypatch.setattr(cb, "_brain_search", brain_search)
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert cb.search("plain english question") == []
    assert called["brain"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Fallback routing — auto mode
# ─────────────────────────────────────────────────────────────────────────────

def test_auto_falls_back_to_brain_when_estate_unreachable(monkeypatch):
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: None,  # dead
    )
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    monkeypatch.setattr(
        cb, "_brain_api",
        lambda action, params=None, timeout=3.0: (
            {"results": [{"id": "c1", "path": "chunks/extracted/x.md/chunk-001.md",
                          "snippet": "hit"}]}
            if action == "search" else {"status": "ok"}
        ),
    )
    results = cb.search("plain english question")
    assert len(results) == 1
    assert results[0]["backend"] == "brain"
    assert results[0]["source"].startswith("wicked-brain://")


def test_auto_symbolish_falls_back_to_estate_when_brain_dies_midway(monkeypatch):
    """brain_alive said yes but the search call failed → estate covers."""
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    monkeypatch.setattr(cb, "_brain_search", lambda q, limit=10: None)  # dead
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: {"items": [_K_ITEM]},
    )
    results = cb.search("where is resolve_port used")
    assert len(results) == 1
    assert results[0]["backend"] == "estate"


def test_search_fails_open_when_both_backends_dead(monkeypatch):
    """The keystone guarantee: estate dead + brain dead ⇒ [] — never a raise."""
    _plant_fake_estate(
        monkeypatch,
        knowledge_recall=lambda q, token_budget=2000, timeout=8.0: None,
    )
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    assert cb.search("anything at all") == []


def test_search_fails_open_when_estate_module_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "_estate_client", None)  # import → error
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    assert cb.search("anything at all") == []


def test_brain_mode_does_not_touch_estate(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "brain")
    fake = _plant_fake_estate(monkeypatch)
    monkeypatch.setattr(
        cb, "_brain_api",
        lambda action, params=None, timeout=3.0: {"results": []},
    )
    assert cb.search("query") == []
    assert fake.calls == []


def test_brain_search_retries_with_two_term_combinations(monkeypatch):
    """The legacy FTS5 AND-narrowing retry moved here from brain_adapter."""
    queries = []

    def brain_api(action, params=None, timeout=3.0):
        queries.append(params["query"])
        if params["query"] == "alpha gamma":
            return {"results": [{"id": "1", "path": "p1", "snippet": "s"},
                                {"id": "2", "path": "p2", "snippet": "s"}]}
        return {"results": []}

    monkeypatch.setattr(cb, "_brain_api", brain_api)
    results = cb._brain_search("alpha beta gamma", limit=10)
    assert queries == ["alpha beta gamma", "alpha gamma", "alpha beta"]
    assert len(results) == 2


# ─────────────────────────────────────────────────────────────────────────────
# capture_memory
# ─────────────────────────────────────────────────────────────────────────────

def test_capture_memory_estate_path_calls_memory_capture(monkeypatch):
    captured = {}

    def call(tool, arguments=None, timeout=8.0):
        captured["tool"] = tool
        captured["args"] = arguments
        return {"memory_id": "mem xyz"}

    _plant_fake_estate(monkeypatch, call=call)
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
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


def test_capture_memory_brain_mode_uses_legacy_path(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "brain")
    fake = _plant_fake_estate(monkeypatch)
    monkeypatch.setattr(
        cb, "_brain_capture",
        lambda title, content, tier="episodic", tags=None, **kw: "memories/working/mem-1",
    )
    assert cb.capture_memory("t", "c", tier="working") == "memories/working/mem-1"
    assert fake.calls == []  # estate never touched


def test_capture_memory_auto_falls_back_to_brain_on_estate_write_failure(monkeypatch):
    _plant_fake_estate(monkeypatch)  # call() returns None → write failed
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    monkeypatch.setattr(
        cb, "_brain_capture",
        lambda title, content, tier="episodic", tags=None, **kw: "memories/working/mem-2",
    )
    assert cb.capture_memory("t", "c", tier="working") == "memories/working/mem-2"


def test_capture_memory_fails_open_when_everything_is_dead(monkeypatch):
    _plant_fake_estate(monkeypatch)
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
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
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    assert cb.stats() is None
    probes_after_first = counter["n"]
    assert cb.stats() is None
    assert counter["n"] == probes_after_first  # served from failure record


def test_stats_brain_mode_passes_through_brain_payload(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "brain")
    monkeypatch.setattr(
        cb, "_brain_api",
        lambda action, params=None, timeout=3.0: {"total": 42} if action == "stats" else None,
    )
    assert cb.stats() == {"total": 42, "backend": "brain"}


def test_stats_auto_falls_back_to_brain_when_estate_dead(monkeypatch):
    _plant_fake_estate(monkeypatch)  # coverage → None
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    monkeypatch.setattr(
        cb, "_brain_api",
        lambda action, params=None, timeout=3.0: {"total": 7} if action == "stats" else {"status": "ok"},
    )
    assert cb.stats() == {"total": 7, "backend": "brain"}


# ─────────────────────────────────────────────────────────────────────────────
# Hook-facing notes + directive targets
# ─────────────────────────────────────────────────────────────────────────────

def test_gate_note_silent_when_estate_healthy(monkeypatch):
    _plant_fake_estate(monkeypatch, call=_coverage_call({"n": 0}))
    assert cb.gate_note() is None


def test_gate_note_degraded_when_everything_is_dead(monkeypatch):
    _plant_fake_estate(monkeypatch)
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    monkeypatch.setattr(cb, "_ensure_brain", lambda wait_secs=2.0: False)
    note = cb.gate_note()
    assert note is not None
    assert "fail open" in note or "degraded" in note


def test_gate_note_brain_covers_when_estate_dead_in_auto(monkeypatch):
    _plant_fake_estate(monkeypatch)
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    # brain stats also answers, so stats() falls back to brain → healthy
    monkeypatch.setattr(
        cb, "_brain_api",
        lambda action, params=None, timeout=3.0: {"total": 5},
    )
    assert cb.gate_note() is None  # brain fallback made stats() healthy


def test_staleness_note_empty_estate_store_points_at_migration(monkeypatch):
    def empty_call(tool, arguments=None, timeout=8.0):
        return {"total": 0}

    _plant_fake_estate(monkeypatch, call=empty_call)
    note = cb.staleness_note()
    assert note is not None and "empty" in note


def test_memory_directive_target_brain_while_bridge_alive(monkeypatch):
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert cb.memory_directive_target() == "wicked-brain:memory"


def test_memory_directive_target_estate_after_retirement(monkeypatch):
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    assert "memory.capture" in cb.memory_directive_target()


def test_memory_directive_target_estate_mode_ignores_brain(monkeypatch):
    monkeypatch.setenv("WICKED_CONTEXT_BACKEND", "estate")
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert "memory.capture" in cb.memory_directive_target()


def test_grounding_lines_follow_the_bridge(monkeypatch):
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: True)
    assert any("wicked-brain:query" in line for line in cb.grounding_directive_lines())
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    cb._reset_probe_cache()
    assert any("wicked-garden-search" in line for line in cb.grounding_directive_lines())


def test_estate_dependency_missing_binary(monkeypatch):
    _plant_fake_estate(monkeypatch, resolve_mcp_bin=lambda: None)
    monkeypatch.setattr(cb, "brain_alive", lambda timeout=1.0: False)
    available, note = cb.estate_dependency()
    assert available is False
    assert "wicked-estate" in note


def test_estate_dependency_healthy(monkeypatch):
    _plant_fake_estate(monkeypatch, call=_coverage_call({"n": 0}))
    available, note = cb.estate_dependency()
    assert available is True
    assert note is None
