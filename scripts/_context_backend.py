"""
Context-backend seam — the single interface between garden's hooks/adapters
and the knowledge layer (estate-only since S7 of the brain→estate
consolidation; wicked-brain is retired).

Backend
-------
**wicked-estate**'s stdio MCP binary, reached through the persistent-broker
shim (``scripts/_estate_client.py``). Retrieval is a two-call fusion:
``knowledge.recall`` (hybrid FTS+vector over the migrated chunks/wiki) +
``memory.recall``, merged with reciprocal-rank fusion. The P5 exit gate
verified retrieval at/above brain parity on every query class (parity bench
results-v2: overall r@10 0.849, symbolish 0.769, hookstyle 0.854).

Flag
----
``WICKED_CONTEXT_BACKEND = estate | off`` (default ``estate``).

* ``estate`` — the knowledge layer answers through wicked-estate.
* ``off``    — context assembly is disabled by design: search/recall return
  ``[]``, capture returns ``None``, stats/health report absent, and every
  hook-facing note stays silent. This is designed silence, not degradation.

Legacy bridge-period values (``auto``, ``brain``) and any unknown value mean
``estate``: ``auto`` was "estate primary" and collapsed to estate-only when
wicked-brain retired at S7; the ``brain`` route was deleted with it.

Fail-open contract
------------------
Every public function is fail-open: missing module, missing binary, dead
broker, malformed payload — all degrade to a safe empty value (``None`` /
``[]`` / ``False``). No exception ever escapes to a hook. Pure stdlib;
cross-platform (no shell, no Unix-only calls).
"""

import json
import os
import time
from pathlib import Path
from typing import Any, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Flag
# ─────────────────────────────────────────────────────────────────────────────

_FLAG_ENV = "WICKED_CONTEXT_BACKEND"
_VALID_MODES = ("estate", "off")


def backend_mode() -> str:
    """The configured mode: "estate" or "off".

    Unknown values — including the legacy bridge-period ``auto``/``brain`` —
    fall back to ``estate``.
    """
    mode = os.environ.get(_FLAG_ENV, "estate").strip().lower()
    return mode if mode in _VALID_MODES else "estate"


def _disabled() -> bool:
    """True when the operator turned context assembly off."""
    return backend_mode() == "off"


# ─────────────────────────────────────────────────────────────────────────────
# Estate retrieval — knowledge.recall + memory.recall, RRF-fused
# ─────────────────────────────────────────────────────────────────────────────

_RRF_K = 60  # standard reciprocal-rank-fusion constant


def _memory_scope() -> str:
    """Scope for estate memory capture/recall.

    Default is the root scope (""): estate visibility is ancestor-visible,
    so root-scope memories are recallable from every scoped query — and the
    hooks' own captures round-trip. Override via WICKED_ESTATE_MEMORY_SCOPE.
    """
    return os.environ.get("WICKED_ESTATE_MEMORY_SCOPE", "")


def _memory_scope_prefix() -> Optional[str]:
    """Subtree filter for estate memory recall (estate #98 ``scope_prefix``).

    The ancestor-visible ``scope`` filter alone cannot see leaf-scoped
    memories — the migrated brain memories live at scopes like
    ``brain:wicked-garden/doc:<id>`` and were invisible to root recalls.
    ``scope_prefix`` REPLACES that filter with subtree matching; the default
    ``""`` (root subtree) sees ALL memories: root + every migrated subtree.

    When the operator pinned a custom recall scope via
    WICKED_ESTATE_MEMORY_SCOPE, honor it — return None (param omitted,
    inheritance semantics) so the pin keeps meaning what it meant.
    Explicit override: WICKED_ESTATE_MEMORY_SCOPE_PREFIX.
    """
    prefix = os.environ.get("WICKED_ESTATE_MEMORY_SCOPE_PREFIX")
    if prefix is not None:
        return prefix
    if os.environ.get("WICKED_ESTATE_MEMORY_SCOPE"):
        return None  # custom scope pinned — keep ancestor-visible semantics
    return ""


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _norm_knowledge(item: dict) -> dict:
    """Estate knowledge.recall item → normalized result dict."""
    return {
        "id": str(item.get("node_id", "")),
        "kind": str(item.get("class", "chunk")),
        "title": str(item.get("label", "")).strip()[:80],
        "snippet": str(item.get("body_snippet", "")),
        "raw_score": _f(item.get("score")),
        "source": str(item.get("source", "")),
        "scope": "",
        "backend": "estate",
    }


def _norm_memory(item: dict) -> dict:
    """Estate memory.recall item → normalized result dict.

    The memory's scope doubles as its source attribution (migrated brain
    memories carry ``brain:wicked-garden/...`` scopes).
    """
    content = str(item.get("content", ""))
    first_line = content.strip().splitlines()[0][:80] if content.strip() else ""
    scope = str(item.get("scope", ""))
    return {
        "id": str(item.get("memory_id", "")),
        "kind": "memory",
        "title": first_line,
        "snippet": content[:400],
        "raw_score": _f(item.get("score")),
        "source": scope or "estate://memory",
        "scope": scope,
        "tier": str(item.get("tier", "")),
        "backend": "estate",
    }


def _rrf_fuse(ranked_lists: List[List[dict]], limit: int) -> List[dict]:
    """Reciprocal-rank fusion across result lists. Dedupes by id."""
    fused: dict = {}
    for items in ranked_lists:
        for rank, item in enumerate(items):
            key = item.get("id") or item.get("source") or item.get("snippet", "")[:80]
            entry = fused.get(key)
            if entry is None:
                entry = dict(item)
                entry["score"] = 0.0
                fused[key] = entry
            entry["score"] += 1.0 / (_RRF_K + rank + 1)
    return sorted(fused.values(), key=lambda d: d["score"], reverse=True)[:limit]


def _estate_search(query: str, limit: int = 10, timeout: float = 5.0) -> Optional[List[dict]]:
    """Two-call estate retrieval. None = estate unreachable.

    knowledge.recall is the primary signal; memory.recall is fused in when it
    has anything to say — with ``scope_prefix`` (estate #98) so the fusion
    sees ALL memories, migrated ``brain:…`` subtrees included. An
    empty-but-reachable answer is a valid [] — only a dead estate returns
    None. A memory-leg failure (e.g. an older binary rejecting
    ``scope_prefix``) degrades the fusion to knowledge-only — knowledge
    already answered, so it is not treated as estate-down.
    """
    try:
        import _estate_client
    except Exception:
        return None
    try:
        k_budget = max(1600, int(limit) * 300)
        payload = _estate_client.knowledge_recall(query, token_budget=k_budget, timeout=timeout)
        if payload is None:
            return None  # unreachable / tool error — fail toward the caller
        k_items = payload.get("items", []) if isinstance(payload, dict) else []
        try:
            m_items = _estate_client.recall(
                query,
                scope=_memory_scope(),
                scope_prefix=_memory_scope_prefix(),
                token_budget=800,
                timeout=timeout,
            )
        except Exception:
            m_items = []  # memory leg failed — knowledge-only fusion, as before
        k_norm = [_norm_knowledge(i) for i in k_items if isinstance(i, dict)]
        m_norm = [_norm_memory(i) for i in m_items if isinstance(i, dict)]
        return _rrf_fuse([k_norm, m_norm], limit)
    except Exception:
        return None


def search(query: str, limit: int = 10, timeout: float = 5.0) -> List[dict]:
    """Context search. Always returns a list (fail-open []).

    Result dicts: {id, kind, title, snippet, score, raw_score, source, scope,
    backend} — ``source`` carries estate's #96 attribution, ``scope`` the
    memory scope where applicable.
    """
    if not query or not str(query).strip():
        return []
    try:
        if _disabled():
            return []
        est = _estate_search(query, limit=limit, timeout=timeout)
        return est if est is not None else []
    except Exception:
        return []


def recall_memories(query: str, limit: int = 10, timeout: float = 5.0) -> List[dict]:
    """Memory-only recall (estate memory.recall).

    Same subtree visibility as the fusion: ``scope_prefix`` (estate #98) so
    migrated ``brain:…`` leaf memories are recallable here too.
    """
    if not query or not str(query).strip():
        return []
    try:
        if _disabled():
            return []
        import _estate_client

        items = _estate_client.recall(
            query,
            scope=_memory_scope(),
            scope_prefix=_memory_scope_prefix(),
            token_budget=max(800, limit * 200),
            timeout=timeout,
        )
        return [_norm_memory(i) for i in items if isinstance(i, dict)][:limit]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Memory capture — estate memory.capture
# ─────────────────────────────────────────────────────────────────────────────

_ESTATE_TIERS = ("working", "episodic", "semantic", "procedural", "archival")


def capture_memory(title, content, tier="working", tags=None, timeout: float = 5.0):
    """Store a memory in estate. Returns an id string or None.

    Fail-open (None) — never raises.
    """
    try:
        text = f"{title}\n\n{content}" if title else str(content or "")
        if not text.strip():
            return None
        if _disabled():
            return None
        import _estate_client

        payload = _estate_client.call(
            "memory.capture",
            {
                "content": text,
                "kind": "working" if tier == "working" else "episode",
                "tier": tier if tier in _ESTATE_TIERS else "working",
                "scope": _memory_scope(),
                "about": list(tags or []),
            },
            timeout=timeout,
        )
        if isinstance(payload, dict):
            mem_id = payload.get("memory_id") or payload.get("id")
            if mem_id:
                return str(mem_id)
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Stats — cached per session/TTL (never per-prompt; the estate probes cost
# a broker spawn + ~200-500ms cold, which is fine once per TTL, not per turn)
# ─────────────────────────────────────────────────────────────────────────────

_STATS_TTL_ENV = "WICKED_CONTEXT_STATS_TTL_SECS"
_STATS_TTL_DEFAULT = 300.0
_STATS_FAIL_TTL = 60.0  # cached failure re-probes sooner than cached success


def _stats_cache_path() -> Path:
    """Project-scoped cache file; tempdir fallback when _paths is unavailable."""
    try:
        from _paths import get_local_file

        return get_local_file("smaht", "context-backend-stats.json")
    except Exception:
        import hashlib
        import tempfile

        cwd_hash = hashlib.sha256(str(Path.cwd()).encode()).hexdigest()[:8]
        return Path(tempfile.gettempdir()) / f"wicked-garden-ctx-stats-{cwd_hash}.json"


def _read_stats_cache() -> Optional[dict]:
    """The cached record {ok, stats, ts} if fresh, else None."""
    try:
        raw = json.loads(_stats_cache_path().read_text(encoding="utf-8"))
        ts = float(raw.get("ts", 0))
        ttl = float(os.environ.get(_STATS_TTL_ENV, _STATS_TTL_DEFAULT))
        if not raw.get("ok"):
            ttl = min(ttl, _STATS_FAIL_TTL)
        if time.time() - ts <= ttl:
            return raw
        return None
    except Exception:
        return None


def _write_stats_cache(stats_result: Optional[dict]) -> None:
    try:
        record = {"ok": stats_result is not None, "stats": stats_result, "ts": time.time()}
        _stats_cache_path().write_text(json.dumps(record), encoding="utf-8")
    except Exception:
        pass  # cache is an optimization, never a requirement


def _estate_stats(timeout: float = 6.0) -> Optional[dict]:
    """Coverage totals for the context layer's estate stores. None = unreachable."""
    try:
        import _estate_client
    except Exception:
        return None
    try:
        kc = _estate_client.call("knowledge.coverage", {}, timeout=timeout)
        mc = _estate_client.call("memory.coverage", {}, timeout=timeout)
        if not isinstance(kc, dict) and not isinstance(mc, dict):
            return None
        k_total = int(kc.get("total", 0)) if isinstance(kc, dict) else 0
        m_total = int(mc.get("total", 0)) if isinstance(mc, dict) else 0
        return {
            "backend": "estate",
            "knowledge_total": k_total,
            "memory_total": m_total,
            "total": k_total + m_total,
        }
    except Exception:
        return None


def stats() -> Optional[dict]:
    """Estate index stats, TTL-cached across hook processes.

    Shape: {backend, knowledge_total, memory_total, total}. None = backend
    unreachable (or context assembly is off).
    """
    try:
        if _disabled():
            return None
        cached = _read_stats_cache()
        if cached is not None and cached.get("ok"):
            return cached.get("stats")
        if cached is not None:
            return None  # fresh failure record — skip the re-probe
        estate_result = _estate_stats()
        _write_stats_cache(estate_result)
        return estate_result
    except Exception:
        return None


def health() -> bool:
    """True if the context backend is answering (cached via stats)."""
    return stats() is not None


# ─────────────────────────────────────────────────────────────────────────────
# Hook-facing note/directive builders — all Optional[str], None = silence
# ─────────────────────────────────────────────────────────────────────────────

def memory_directive_target() -> str:
    """Skill name that hooks should reference in memory-capture directives.

    Names the wicked-garden-mem skill (whose `store` action writes through
    estate ``memory.capture``) rather than the raw MCP tool: the PostToolUse
    memory-compliance reset watches for the mem skill, so the directive and
    the reset must point at the same surface.
    """
    return "the wicked-garden-mem skill (store action)"


def grounding_directive_lines() -> List[str]:
    """Numbered grounding steps for the Context Assembly directive."""
    return [
        "1. Ground in the knowledge layer via the wicked-garden-mem skill "
        "(recall/answer over wicked-estate knowledge + memory) — concepts, "
        "files, and past decisions, with source attribution; use the estate "
        "MCP SearchEntity tool for symbol lookup.",
        "2. Open the cited sources with Read before answering; do not answer "
        "from recall snippets alone.",
    ]


def gate_note() -> Optional[str]:
    """Per-prompt reachability note (prompt_submit). None = healthy/silent."""
    try:
        if _disabled():
            return None  # off by operator choice — designed silence
        if stats() is not None:
            return None
        return (
            "[wicked-context] Context backend (wicked-estate) is unreachable. "
            "Context assembly is degraded for this session — hooks "
            "fail open, nothing is blocked. Check the wicked-estate install "
            "(`wicked-estate-mcp` on PATH or ~/.local/bin) and the stores under ~/.wicked/."
        )
    except Exception:
        return None


def staleness_note() -> Optional[str]:
    """SessionStart index-health note (bootstrap). None = healthy/silent."""
    try:
        if _disabled():
            return None
        s = stats()
        if s is None:
            return (
                "Context backend (wicked-estate) unreachable — knowledge/memory recall "
                "is degraded this session (fail-open). Check the wicked-estate install."
            )
        if s.get("total", 0) == 0:
            return (
                "wicked-estate knowledge/memory stores are empty — ingest content "
                "(the wicked-garden-mem skill's `ingest` action, or knowledge.ingest "
                "directly) so context assembly has something to recall."
            )
        return None
    except Exception:
        return None


def estate_dependency() -> tuple:
    """(available, note) for bootstrap's dependency check.

    available: True when the estate MCP binary resolves, False when missing,
    None on internal error or when context assembly is off (caller treats as
    unknown, fail-open). note is an informational string or None.
    """
    try:
        if _disabled():
            return None, None
        from _estate_client import resolve_mcp_bin

        if resolve_mcp_bin() is None:
            note = (
                "[wicked-estate] context-backend binary not found.\n"
                "Install wicked-estate so hooks can reach the knowledge layer "
                "(binary `wicked-estate-mcp` on PATH or ~/.local/bin)."
            )
            return False, note
        if stats() is None:
            return True, (
                "[wicked-estate] binary present but the MCP server did not answer — "
                "context assembly degraded for this session (fail-open)."
            )
        return True, None
    except Exception:
        return None, None
