"""
DomainStore adapter for wicked-smaht.

Queries kanban tasks, crew projects, and jam sessions via DomainStore
directly (local JSON with optional MCP routing). Replaces cp_adapter.py
which queried the same data via HTTP.

Strategy:
1. Query each domain using DomainStore (local JSON primary store)
2. Apply generic relevance scoring (keyword matching + status/type boosts)
3. Return ContextItems sorted by relevance
"""

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))


# ---------------------------------------------------------------------------
# Stop words for keyword extraction
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "may", "might", "must", "i", "you", "we", "they", "me", "my", "your",
    "this", "that", "these", "those", "what", "which", "who", "how", "why",
    "when", "where", "and", "or", "but", "if", "for", "of", "to", "from",
    "in", "on", "at", "by", "with", "about", "not", "so", "just", "also",
    "need", "want", "let", "get", "make", "test", "check", "fix", "work",
})


# ---------------------------------------------------------------------------
# Domain query configuration (mirrors cp_adapter._DOMAIN_QUERIES structure)
# Each entry defines how to fetch data from a DomainStore domain.
#
#   domain_name:  DomainStore("wicked-{name}") argument
#   source:       DomainStore collection name (first arg to .list()/.search())
#   label:        ContextItem source label
#   project_key:  record field used for project scoping (None = no scoping)
#   title_fn:     callable(record) → title string
#   summary_fn:   callable(record) → summary string
#   boost_fn:     callable(record) → float bonus (0.0-0.5)
# ---------------------------------------------------------------------------

_DOMAIN_QUERIES = [
    {
        "domain_name": "wicked-kanban",
        "source": "tasks",
        "label": "kanban",
        "project_key": "project_id",
        "title_fn": lambda r: f"[{r.get('swimlane', '?')}] {r.get('name', '')}",
        "summary_fn": lambda r: (r.get("description") or r.get("name") or "")[:200],
        "boost_fn": lambda r: 0.2 if r.get("swimlane") in ("doing", "in_progress") else 0.0,
    },
    {
        "domain_name": "wicked-crew",
        "source": "projects",
        "label": "crew",
        "project_key": None,  # crew projects are not sub-scoped
        "title_fn": lambda r: f"Project: {r.get('name', '?')} ({r.get('current_phase', '?')} phase)",
        "summary_fn": lambda r: f"Phase: {r.get('current_phase', '?')}, Complexity: {r.get('complexity_score', 0)}/7",
        "boost_fn": lambda r: (
            0.4 if not r.get("archived", False) and r.get("current_phase") not in ("done", "review") else 0.0
        ),
    },
    {
        "domain_name": "jam",
        "source": "sessions",
        "label": "jam",
        "project_key": "project",
        "title_fn": lambda r: f"Brainstorm: {r.get('topic', '')}",
        "summary_fn": lambda r: (r.get("summary") or r.get("synthesis", {}).get("summary", ""))[:200],
        "boost_fn": lambda r: 0.0,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Per-domain query (runs in thread pool)
# ---------------------------------------------------------------------------

def _query_domain(config: dict, keywords: str, project: str = "") -> list:
    """Query a single DomainStore domain. Runs in thread pool.

    Uses _skip_discovery=True to bypass integration-discovery (MCP routing).
    This is a read-only context query — smaht never needs to delegate reads
    to external tools, and discovery can block for up to 3 s when brain is
    slow, which exceeds the fast-path 0.5 s timeout (issue #374).

    Returns a list of raw record dicts, or [] on any error.
    """
    try:
        from _domain_store import DomainStore

        ds = DomainStore(config["domain_name"], _skip_discovery=True)

        params: dict = {}
        if keywords:
            params["q"] = keywords
        if project and config.get("project_key"):
            params[config["project_key"]] = project

        records = ds.list(config["source"], **params)
        return records if isinstance(records, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public async query function
# ---------------------------------------------------------------------------

async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query kanban, crew, and jam via DomainStore for relevant context.

    Args:
        prompt: The user's query/prompt text.
        project: Optional project filter (applied to project-scoped domains).

    Returns:
        List of ContextItems sorted by relevance descending.
    """
    keywords = _extract_keywords(prompt)
    if not keywords:
        return []

    prompt_lower = prompt.lower()
    items: list[ContextItem] = []
    now = datetime.now(timezone.utc)

    # Query all domains in parallel to avoid serial blocking (issue #374).
    # Previously a serial for-loop meant a slow first domain (e.g. wicked-kanban
    # during cold session) would delay every subsequent domain query.
    domain_results = await asyncio.gather(
        *[run_in_thread(_query_domain, config, keywords, project or "")
          for config in _DOMAIN_QUERIES],
        return_exceptions=True,
    )

    for config, records in zip(_DOMAIN_QUERIES, domain_results):
        # Skip domains that raised (run_in_thread wraps; gather returns exception objects)
        if isinstance(records, Exception) or not isinstance(records, list):
            continue

        for record in records[:10]:  # Cap per domain
            # Skip archived or deleted records
            if record.get("archived") or record.get("deleted"):
                continue

            title = config["title_fn"](record)
            summary = config["summary_fn"](record)

            # Score: base + keyword match + domain-specific boost
            base = 0.3
            kw_score = _keyword_score(prompt_lower, f"{title} {summary}")
            boost = config["boost_fn"](record)
            relevance = min(base + kw_score + boost, 1.0)

            # Calculate age in days
            age_days = 0.0
            created = record.get("created_at") or record.get("created") or ""
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (now - dt).days
                except Exception:
                    pass  # fail open: age_days defaults to 0

            items.append(ContextItem(
                id=record.get("id", record.get("name", "")),
                source=config["label"],
                title=title,
                summary=summary,
                excerpt=summary,
                relevance=relevance,
                age_days=age_days,
                metadata={
                    "domain": config["domain_name"],
                    "semantic_score": relevance,
                },
            ))

    # Sort by relevance descending
    items.sort(key=lambda x: x.relevance, reverse=True)
    return items
