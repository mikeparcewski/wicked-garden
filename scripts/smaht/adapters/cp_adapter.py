"""
Manifest-driven Control Plane adapter for wicked-smaht.

Single adapter that queries ALL CP domains for context assembly.
Replaces the individual mem_adapter, kanban_adapter, crew_adapter,
jam_adapter, and search_adapter.

Strategy:
1. Query each domain's search/list endpoint via the CP client
2. Apply generic relevance scoring (keyword matching + status/type boosts)
3. Return ContextItems sorted by relevance
"""

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from _control_plane import get_client


# ---------------------------------------------------------------------------
# Domain query configuration
# ---------------------------------------------------------------------------

# Each entry defines how to query a CP domain for context:
#   source:     the resource collection to query
#   verb:       "search" if available, else "list"
#   query_key:  param name for search term (None = no search support)
#   label:      human-readable source label for ContextItems
#   title_fn:   callable(record) → title string
#   summary_fn: callable(record) → summary string
#   boost_fn:   callable(record) → float bonus (0.0-0.5)

_DOMAIN_QUERIES = {
    "memory": {
        "source": "memories",
        "verb": "search",
        "query_key": "q",
        "project_scoped": True,
        "label": "mem",
        "title_fn": lambda r: r.get("title", r.get("type", "memory")),
        "summary_fn": lambda r: (r.get("summary") or r.get("content") or "")[:200],
        "boost_fn": lambda r: {
            "decision": 0.3, "preference": 0.3, "procedural": 0.1,
            "working": 0.3, "episodic": 0.0,
        }.get(r.get("type", ""), 0.0),
    },
    "kanban": {
        "source": "tasks",
        "verb": "search",
        "query_key": "q",
        "project_scoped": True,
        "label": "kanban",
        "title_fn": lambda r: f"[{r.get('swimlane', '?')}] {r.get('name', '')}",
        "summary_fn": lambda r: (r.get("description") or r.get("name") or "")[:200],
        "boost_fn": lambda r: 0.2 if r.get("swimlane") in ("doing", "in_progress") else 0.0,
    },
    "crew": {
        "source": "projects",
        "verb": "list",
        "query_key": None,
        "project_scoped": False,
        "label": "crew",
        "title_fn": lambda r: f"Project: {r.get('name', '?')} ({r.get('current_phase', '?')} phase)",
        "summary_fn": lambda r: f"Phase: {r.get('current_phase', '?')}, Complexity: {r.get('complexity_score', 0)}/7",
        "boost_fn": lambda r: (
            0.4 if not r.get("archived", False) and r.get("current_phase") not in ("done", "review") else 0.0
        ),
    },
    "jam": {
        "source": "sessions",
        "verb": "search",
        "query_key": "q",
        "project_scoped": True,
        "label": "jam",
        "title_fn": lambda r: f"Brainstorm: {r.get('topic', '')}",
        "summary_fn": lambda r: (r.get("summary") or r.get("synthesis", {}).get("summary", ""))[:200],
        "boost_fn": lambda r: 0.0,
    },
    "knowledge": {
        "source": "graph",
        "verb": "search",
        "query_key": "q",
        "project_scoped": False,
        "label": "search",
        "title_fn": lambda r: _format_symbol_title(r),
        "summary_fn": lambda r: f"{r.get('type', 'symbol')}: {r.get('name', '')}",
        "boost_fn": lambda r: 0.0,
    },
}

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "may", "might", "must", "i", "you", "we", "they", "me", "my", "your",
    "this", "that", "these", "those", "what", "which", "who", "how", "why",
    "when", "where", "and", "or", "but", "if", "for", "of", "to", "from",
    "in", "on", "at", "by", "with", "about", "not", "so", "just", "also",
    "need", "want", "let", "get", "make", "test", "check", "fix", "work",
})


def _format_symbol_title(r: dict) -> str:
    name = r.get("name", "")
    file_path = r.get("file", "") or r.get("path", "")
    line = r.get("line", 0)
    short = Path(file_path).name if file_path else ""
    return f"{name} ({short}:{line})" if short else name


def _extract_keywords(prompt: str) -> str:
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords[:5]) if keywords else ""


def _keyword_score(prompt_lower: str, text: str, weight: float = 0.2) -> float:
    """Score text by keyword overlap with prompt."""
    if not text:
        return 0.0
    text_lower = text.lower()
    score = 0.0
    for word in prompt_lower.split():
        if len(word) > 3 and word in text_lower:
            score += weight
    return min(score, 0.5)


def _emit_smaht_trace(entry: dict) -> None:
    """Write a smaht adapter trace to the observability store. Fire-and-forget."""
    try:
        from _control_plane import ControlPlaneClient
        from _session import SessionState
        state = SessionState.load()
        if not state.cp_available:
            return
        client = ControlPlaneClient(hook_mode=True)
        client.request("observability", "traces", "create", payload=entry)
    except Exception:
        pass  # Traces are observability data — never block on failure


def _query_domain(domain: str, config: dict, keywords: str,
                  cp_project_id: str = "") -> list:
    """Query a single CP domain. Runs in thread pool."""
    start_ns = time.monotonic_ns()
    result_count = 0
    error = None
    try:
        cp = get_client()
        params = {}
        if config["query_key"] and keywords:
            params[config["query_key"]] = keywords

        if config.get("project_scoped") and cp_project_id:
            params["project_id"] = cp_project_id

        resp = cp.request(
            domain, config["source"], config["verb"],
            params=params if params else None,
        )
        if resp and isinstance(resp.get("data"), list):
            records = resp["data"]
            result_count = len(records)
            return records
        return []
    except Exception as exc:
        error = str(exc)
        return []
    finally:
        duration_ms = (time.monotonic_ns() - start_ns) // 1_000_000
        entry = {
            "trace_type": "smaht_adapter",
            "event": "smaht.adapter.query",
            "adapter": "cp_adapter",
            "domain": domain,
            "source": config.get("source", ""),
            "verb": config.get("verb", ""),
            "project_scoped": config.get("project_scoped", False),
            "latency_ms": duration_ms,
            "duration_ms": duration_ms,
            "item_count": result_count,
            "result_count": result_count,
            "error": error,
            "project_id": cp_project_id or None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        threading.Thread(
            target=_emit_smaht_trace,
            args=(entry,),
            daemon=True,
        ).start()


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query all CP domains for relevant context.

    Args:
        prompt: The user's query/prompt text.
        project: Optional project filter.

    Returns:
        List of ContextItems from all available domains.
    """
    keywords = _extract_keywords(prompt)
    if not keywords:
        return []

    # Load session-cached CP project UUID for scoped queries.
    # Fail open: empty string disables scoping without breaking queries.
    cp_project_id = ""
    try:
        from _session import SessionState
        session_state = SessionState.load()
        cp_project_id = session_state.cp_project_id or ""
    except Exception:
        pass

    prompt_lower = prompt.lower()
    items: list[ContextItem] = []
    now = datetime.now(timezone.utc)

    for domain, config in _DOMAIN_QUERIES.items():
        records = await run_in_thread(_query_domain, domain, config, keywords, cp_project_id)

        for record in records[:10]:  # Cap per domain
            # Skip archived/deleted
            if record.get("archived") or record.get("deleted"):
                continue

            title = config["title_fn"](record)
            summary = config["summary_fn"](record)

            # Score: base + keyword match + domain-specific boost
            base = 0.3
            kw_score = _keyword_score(prompt_lower, f"{title} {summary}")
            boost = config["boost_fn"](record)
            relevance = min(base + kw_score + boost, 1.0)

            # Calculate age
            age_days = 0.0
            created = record.get("created_at") or record.get("created") or ""
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (now - dt).days
                except Exception:
                    pass

            items.append(ContextItem(
                id=record.get("id", record.get("name", "")),
                source=config["label"],
                title=title,
                summary=summary,
                excerpt=summary,
                relevance=relevance,
                age_days=age_days,
                metadata={
                    "domain": domain,
                    "semantic_score": relevance,
                },
            ))

    # Sort by relevance descending
    items.sort(key=lambda x: x.relevance, reverse=True)
    return items
