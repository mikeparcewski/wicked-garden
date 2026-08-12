"""
Context-backend router — the single seam between garden's hooks/adapters and
the knowledge layer (Stage S4 of the brain→estate consolidation).

Backends
--------
* **estate** — wicked-estate's stdio MCP binary, reached through the
  persistent-broker shim (``scripts/_estate_client.py``). Retrieval is a
  two-call fusion: ``knowledge.recall`` (hybrid FTS+vector over the migrated
  chunks/wiki) + ``memory.recall``, merged with reciprocal-rank fusion. The
  S3 parity bench scored the knowledge side alone at r@10 0.703 vs brain
  0.437 — estate wins the general class outright.
* **brain** — the legacy wicked-brain HTTP server (``scripts/_brain_port.py``).
  Kept for the bridge period because "symbolish" queries (identifiers,
  dotted/snake_case/CamelCase code tokens, import-like strings) still score
  better on brain (r@10 0.786 vs estate 0.494 per the same bench).

Routing flag
------------
``WICKED_CONTEXT_BACKEND = estate | brain | auto`` (default ``auto``).

* ``estate`` — estate only; brain is never consulted.
* ``brain``  — brain only; legacy behavior, byte-for-byte directives.
* ``auto``   — estate primary, with two bridge-period exceptions:
    - symbolish queries route to brain **while brain is alive**;
    - when estate is unreachable, brain covers (when alive).
  When brain is retired (S7), every brain probe fails open, so ``auto``
  silently degrades to estate-only: hooks behave exactly as they do today
  when the brain server is absent — empty results plus a stderr marker,
  never a crash.

Writes (``capture_memory``) route estate-first in ``auto`` so fresh memories
land in the store that survives retirement; ``brain`` mode keeps the legacy
file-write + FTS-index path.

Fail-open contract
------------------
Every public function is fail-open: missing module, missing binary, dead
broker, dead brain server, malformed payload — all degrade to a safe empty
value (``None`` / ``[]`` / ``False``). No exception ever escapes to a hook.
Pure stdlib; cross-platform (no shell, no Unix-only calls).
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Flag + routing
# ─────────────────────────────────────────────────────────────────────────────

_FLAG_ENV = "WICKED_CONTEXT_BACKEND"
_VALID_MODES = ("estate", "brain", "auto")

# "Symbolish" query classifier — identifier-shaped tokens route to brain
# during the bridge (S3 bench: brain r@10 0.786 vs estate 0.494 on this
# class). Regex is deliberately simple; precision over cleverness.
_SNAKE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
_DOTTED = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]+(?:\.[A-Za-z_][A-Za-z0-9_]+)*\b"
)
_CAMEL = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_UNDERSCORE_ID = re.compile(r"(?:^|[\s'\"`(])_[A-Za-z][A-Za-z0-9_]*")
_PATHY = re.compile(r"(?:[\w.\-]+[/\\])+[\w.\-]+")
# import-like: real import statements, require()/include<...>, and Rust/C++
# path or arrow tokens. Bare English "require"/"from" must NOT trip this.
_IMPORTISH = re.compile(
    r"\bfrom\s+[\w.]+\s+import\b|\bimport\s+[A-Za-z_][\w.]*"
    r"|\brequire\s*\(|\binclude\s*[<\"']|::\w|->\s*\w"
)
_FILEEXT = re.compile(
    r"\b[\w\-]{2,}\.(?:py|rs|ts|tsx|js|jsx|mjs|go|java|kt|rb|json|yaml|yml|toml|md|sh|sql|c|h|hpp|cpp|cs)\b",
    re.IGNORECASE,
)
_SYMBOLISH_PATTERNS = (
    _SNAKE, _DOTTED, _CAMEL, _UNDERSCORE_ID, _PATHY, _IMPORTISH, _FILEEXT,
)


def backend_mode() -> str:
    """The configured routing mode. Unknown values fall back to ``auto``."""
    mode = os.environ.get(_FLAG_ENV, "auto").strip().lower()
    return mode if mode in _VALID_MODES else "auto"


def is_symbolish(query: str) -> bool:
    """True when the query contains an identifier-shaped token.

    Matches snake_case, dotted paths (min 2 chars/segment, so "e.g." and
    version numbers don't trip it), CamelCase (two+ humps), path-like tokens,
    import-like phrases, and bare code filenames.
    """
    if not query:
        return False
    text = str(query)
    return any(p.search(text) for p in _SYMBOLISH_PATTERNS)


def route(query: Optional[str] = None) -> str:
    """Resolve the backend for one operation. Returns "estate" or "brain".

    ``estate``/``brain`` modes are absolute. ``auto`` routes symbolish
    queries to brain while brain is alive (per-class bench fallback) and
    everything else — including writes and query-less operations — to estate.
    """
    mode = backend_mode()
    if mode in ("estate", "brain"):
        return mode
    if query and is_symbolish(query) and brain_alive():
        return "brain"
    return "estate"


def _bridge_active() -> bool:
    """True while directives should still name brain surfaces.

    The model-facing memory/grounding skills stay brain-worded while the
    brain bridge is installed and answering (they still work, and the estate
    MCP surface may not be attached to the session). Once brain is gone the
    wording degrades to the estate surfaces silently.
    """
    mode = backend_mode()
    if mode == "brain":
        return True
    if mode == "estate":
        return False
    return brain_alive()


# ─────────────────────────────────────────────────────────────────────────────
# Liveness probes — memoized per process (a hook run is one short process)
# ─────────────────────────────────────────────────────────────────────────────

_PROBE_CACHE: dict = {}


def _reset_probe_cache() -> None:
    """Test seam: forget memoized liveness probes."""
    _PROBE_CACHE.clear()


def _brain_api(action: str, params: Optional[dict] = None, timeout: float = 3.0) -> Optional[dict]:
    """POST one action to the brain HTTP API. None on any failure (fail-open)."""
    try:
        import urllib.request

        from _brain_port import resolve_port

        payload = json.dumps({"action": action, "params": params or {}}).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{resolve_port()}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosem: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL is localhost with int port from resolve_port()
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def brain_alive(timeout: float = 1.0) -> bool:
    """True if the brain server answers a health call. Memoized per process."""
    if "brain" in _PROBE_CACHE:
        return _PROBE_CACHE["brain"]
    alive = _brain_api("health", {}, timeout=timeout) is not None
    _PROBE_CACHE["brain"] = alive
    return alive


def _ensure_brain(wait_secs: float = 2.0) -> bool:
    """Deterministic brain auto-start (bridge only). Fail-open."""
    try:
        from _brain_port import ensure_server

        if ensure_server(wait_secs=wait_secs):
            _PROBE_CACHE["brain"] = True
            return True
        return False
    except Exception:
        return False


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


def _norm_brain(item: dict) -> dict:
    """Brain FTS search result → normalized result dict."""
    path = str(item.get("path", "") or item.get("id", ""))
    return {
        "id": path,
        "kind": "chunk",
        "title": "",
        "snippet": str(item.get("snippet", "")),
        "raw_score": _f(item.get("score")),
        "source": f"wicked-brain://{path}" if path else "wicked-brain://",
        "scope": "",
        "backend": "brain",
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
    """Two-call estate retrieval. None = estate unreachable (caller may fall back).

    knowledge.recall is the primary signal (bench r@10 0.703); memory.recall
    is fused in when it has anything to say. An empty-but-reachable answer is
    a valid [] — only a dead estate returns None.
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
        m_items = _estate_client.recall(
            query, scope=_memory_scope(), token_budget=800, timeout=timeout
        )
        k_norm = [_norm_knowledge(i) for i in k_items if isinstance(i, dict)]
        m_norm = [_norm_memory(i) for i in m_items if isinstance(i, dict)]
        return _rrf_fuse([k_norm, m_norm], limit)
    except Exception:
        return None


def _brain_search(query: str, limit: int = 10) -> Optional[List[dict]]:
    """Brain FTS search with the legacy 3-term→2-term recall retry.

    None = brain unreachable. FTS5 uses AND, so fewer terms = wider recall:
    when the full query lands < 2 hits, retry first+third (drop the middle,
    often the most generic term) and first+second, keeping the wider set.
    """
    tokens = [t for t in str(query).split() if t]
    if not tokens:
        return []
    raw = _brain_api("search", {"query": " ".join(tokens), "limit": limit}, timeout=3)
    if raw is None:
        return None
    results = raw.get("results", []) if isinstance(raw, dict) else []
    if len(results) < 2 and len(tokens) >= 3:
        ra = _brain_api("search", {"query": f"{tokens[0]} {tokens[2]}", "limit": limit}, timeout=3)
        rb = _brain_api("search", {"query": f"{tokens[0]} {tokens[1]}", "limit": limit}, timeout=3)
        la = ra.get("results", []) if isinstance(ra, dict) else []
        lb = rb.get("results", []) if isinstance(rb, dict) else []
        results = la if len(la) >= len(lb) else lb
    return [_norm_brain(r) for r in results if isinstance(r, dict)]


def search(query: str, limit: int = 10, timeout: float = 5.0) -> List[dict]:
    """Routed context search. Always returns a list (fail-open []).

    Result dicts: {id, kind, title, snippet, score, raw_score, source, scope,
    backend} — ``source`` carries estate's #96 attribution (or a
    wicked-brain:// URI), ``scope`` the memory scope where applicable.
    """
    if not query or not str(query).strip():
        return []
    try:
        backend = route(query)
        if backend == "brain":
            results = _brain_search(query, limit=limit)
            if results is not None:
                return results
            if backend_mode() == "auto":  # brain died mid-route — estate covers
                est = _estate_search(query, limit=limit, timeout=timeout)
                return est if est is not None else []
            return []
        est = _estate_search(query, limit=limit, timeout=timeout)
        if est is not None:
            return est
        if backend_mode() == "auto" and brain_alive():  # estate dead — bridge covers
            results = _brain_search(query, limit=limit)
            return results if results is not None else []
        return []
    except Exception:
        return []


def recall_memories(query: str, limit: int = 10, timeout: float = 5.0) -> List[dict]:
    """Memory-only recall (estate memory.recall; brain search under brain mode)."""
    if not query or not str(query).strip():
        return []
    try:
        if route(query) == "brain":
            results = _brain_search(query, limit=limit)
            return results if results is not None else []
        import _estate_client

        items = _estate_client.recall(
            query, scope=_memory_scope(), token_budget=max(800, limit * 200), timeout=timeout
        )
        return [_norm_memory(i) for i in items if isinstance(i, dict)][:limit]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Memory capture — estate memory.capture; legacy brain file+index under brain
# ─────────────────────────────────────────────────────────────────────────────

_ESTATE_TIERS = ("working", "episodic", "semantic", "procedural", "archival")


def _brain_capture(title, content, tier="episodic", tags=None, mem_type=None, importance=5):
    """Legacy brain memory write: chunk file under ~/.wicked-brain + FTS index.

    Single surviving copy of the _write_brain_memory helper that used to be
    duplicated in prompt_submit.py and pre_compact.py. Bridge-only; deleted
    with the rest of the brain path at S7.
    """
    try:
        import uuid
        from datetime import datetime, timezone

        mem_id = str(uuid.uuid4())
        chunk_id = f"memories/{tier}/mem-{mem_id}"
        chunk_path = Path.home() / ".wicked-brain" / f"{chunk_id}.md"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)

        tags_list = list(tags or [])
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        lines = ["---"]
        lines.append("source: wicked-brain:memory")
        lines.append(f"memory_type: {mem_type or tier}")
        lines.append(f"memory_tier: {tier}")
        lines.append(f"title: {title}")
        lines.append(f"importance: {importance}")
        lines.append("contains:")
        for t in tags_list:
            lines.append(f"  - {t}")
        lines.append(f'indexed_at: "{now}"')
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(content)

        chunk_path.write_text("\n".join(lines), encoding="utf-8")

        _ensure_brain(wait_secs=2.0)
        search_text = f"{title} {content} {' '.join(tags_list)}"
        _brain_api(
            "index",
            {
                "id": f"{chunk_id}.md",
                "path": f"{chunk_id}.md",
                "content": search_text,
                "brain_id": "wicked-brain",
            },
        )
        return chunk_id
    except Exception:
        return None


def capture_memory(title, content, tier="working", tags=None, timeout: float = 5.0):
    """Store a memory in the routed backend. Returns an id string or None.

    Writes route estate-first in ``auto`` (fresh memories must land in the
    store that survives brain retirement); ``brain`` mode keeps the legacy
    path. On an estate write failure in ``auto``, the brain bridge covers
    while it is alive. Fail-open (None) — never raises.
    """
    try:
        text = f"{title}\n\n{content}" if title else str(content or "")
        if not text.strip():
            return None
        if route() == "brain":
            return _brain_capture(title, content, tier=tier, tags=tags)
        try:
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
        except Exception:
            pass
        if backend_mode() == "auto" and brain_alive():
            return _brain_capture(title, content, tier=tier, tags=tags)
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
    """Routed index stats. Estate results are TTL-cached across hook processes.

    Estate shape: {backend, knowledge_total, memory_total, total}. Brain shape:
    the brain server's own stats payload + backend="brain". Both expose
    ``total`` so emptiness checks port unchanged. None = backend unreachable.
    """
    try:
        mode = backend_mode()
        if mode == "brain":
            s = _brain_api("stats", {}, timeout=2)
            return dict(s, backend="brain") if isinstance(s, dict) else None

        cached = _read_stats_cache()
        if cached is not None and cached.get("ok"):
            return cached.get("stats")
        if cached is not None:
            estate_result = None  # fresh failure record — skip the re-probe
        else:
            estate_result = _estate_stats()
            _write_stats_cache(estate_result)
        if estate_result is not None:
            return estate_result
        if mode == "auto" and brain_alive():
            s = _brain_api("stats", {}, timeout=2)
            if isinstance(s, dict):
                return dict(s, backend="brain")
        return None
    except Exception:
        return None


def health() -> bool:
    """True if the routed context backend is answering (cached via stats)."""
    return stats() is not None


# ─────────────────────────────────────────────────────────────────────────────
# Hook-facing note/directive builders — all Optional[str], None = silence
# ─────────────────────────────────────────────────────────────────────────────

def memory_directive_target() -> str:
    """Skill/tool name that hooks should reference in memory-capture directives.

    Brain wording while the bridge is installed and answering (the skill still
    works and is what the model has today); estate wording once brain is gone.
    """
    if _bridge_active():
        return "wicked-brain:memory"
    return "the wicked-estate `memory.capture` tool"


def grounding_directive_lines() -> List[str]:
    """Numbered grounding steps for the Context Assembly directive."""
    if _bridge_active():
        return [
            "1. Call wicked-brain:query for conceptual grounding ('how does X work', "
            "'what are the constraints around Y').",
            "2. Call wicked-brain:search for specific symbols, files, or past decisions. "
            "Drill into wiki hits with wicked-brain:read depth=2.",
        ]
    return [
        "1. Ground in the knowledge layer via the wicked-garden-search skill "
        "(wicked-estate knowledge + memory recall) — concepts, symbols, files, "
        "and past decisions, with source attribution.",
        "2. Open the cited sources with Read before answering; do not answer "
        "from recall snippets alone.",
    ]


def gate_note() -> Optional[str]:
    """Per-prompt reachability note (prompt_submit). None = healthy/silent."""
    try:
        mode = backend_mode()
        if mode == "brain":
            if brain_alive() or _ensure_brain(wait_secs=2.0):
                return None
            return (
                "[wicked-brain] Brain server is not running and auto-start failed.\n"
                "WICKED_CONTEXT_BACKEND=brain requires wicked-brain for context "
                "assembly and memory. Diagnose with: wicked-brain-call --start. "
                "If not installed: claude plugin install wicked-brain --scope project"
            )
        if stats() is not None:
            return None
        if mode == "auto" and (brain_alive() or _ensure_brain(wait_secs=2.0)):
            return (
                "[wicked-context] wicked-estate is unreachable — the wicked-brain "
                "bridge is covering context assembly for this session (fail-open)."
            )
        return (
            "[wicked-context] Context backend (wicked-estate) is unreachable and no "
            "fallback answered. Context assembly is degraded for this session — hooks "
            "fail open, nothing is blocked. Check the wicked-estate install "
            "(`wicked-estate-mcp` on PATH or ~/.local/bin) and the stores under ~/.wicked/."
        )
    except Exception:
        return None


def staleness_note() -> Optional[str]:
    """SessionStart index-health note (bootstrap). None = healthy/silent."""
    try:
        mode = backend_mode()
        if mode == "brain":
            s = _brain_api("stats", {}, timeout=2)
            if s is None and _ensure_brain():
                s = _brain_api("stats", {}, timeout=2)
            if s is None:
                return (
                    "Brain server unreachable and auto-start failed — run "
                    "`wicked-brain-call --start` to see the cause. Brain skills "
                    "auto-start the server on every call; do NOT skip brain usage."
                )
            if s.get("total", 0) == 0:
                return "Brain index is empty — run `wicked-brain:ingest` to index your codebase"
            return None
        s = stats()
        if s is None:
            return (
                "Context backend (wicked-estate) unreachable — knowledge/memory recall "
                "is degraded this session (fail-open). Check the wicked-estate install."
            )
        if s.get("total", 0) == 0:
            if s.get("backend") == "brain":
                return "Brain index is empty — run `wicked-brain:ingest` to index your codebase"
            return (
                "wicked-estate knowledge/memory stores are empty — run the brain→estate "
                "migration or ingest content (knowledge.ingest) so context assembly has "
                "something to recall."
            )
        return None
    except Exception:
        return None


def estate_dependency() -> tuple:
    """(available, note) for bootstrap's dependency check under estate/auto.

    available: True when the estate MCP binary resolves, False when missing,
    None on internal error (caller treats as unknown, fail-open). note is an
    informational string or None.
    """
    try:
        from _estate_client import resolve_mcp_bin

        if resolve_mcp_bin() is None:
            note = (
                "[wicked-estate] context-backend binary not found.\n"
                "Install wicked-estate so hooks can reach the knowledge layer "
                "(binary `wicked-estate-mcp` on PATH or ~/.local/bin)."
            )
            if backend_mode() == "auto" and brain_alive():
                note += " The wicked-brain bridge is covering context assembly meanwhile."
            return False, note
        if stats() is None:
            return True, (
                "[wicked-estate] binary present but the MCP server did not answer — "
                "context assembly degraded for this session (fail-open)."
            )
        return True, None
    except Exception:
        return None, None
