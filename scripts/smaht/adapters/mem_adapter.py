"""
wicked-mem adapter for wicked-smaht.

Queries memories, decisions, and procedural knowledge via Control Plane.
"""

import sys
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

# Resolve _control_plane from the scripts root
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from _control_plane import get_client


_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "may", "might", "must", "i", "you", "we", "they", "me", "my", "your",
    "this", "that", "these", "those", "what", "which", "who", "how", "why",
    "when", "where", "and", "or", "but", "if", "for", "of", "to", "from",
    "in", "on", "at", "by", "with", "about", "not", "so", "just", "also",
    "need", "want", "let", "get", "make", "test", "check", "fix", "work",
}


def _extract_keywords(prompt: str) -> str:
    """Extract meaningful keywords for search."""
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords[:5]) if keywords else ""


def _recall_memories(search_query: str) -> list:
    """Query CP for memories."""
    try:
        cp = get_client()
        # Search across all memory sources
        results = []
        for source in ["episodic", "procedural", "decision", "preference", "working"]:
            resp = cp.request("wicked-mem", source, "list", params={"q": search_query})
            if resp and isinstance(resp.get("data"), list):
                results.extend(resp["data"])
        return results[:5]
    except Exception:
        return []


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-mem for relevant memories."""
    items = []

    search_query = _extract_keywords(prompt)
    if not search_query:
        return items

    memories = await run_in_thread(_recall_memories, search_query)

    for m in memories:
        tags = m.get("tags", [])
        mem_type = m.get("type", "episodic")

        type_boost = {
            "decision": 0.3,
            "preference": 0.3,
            "procedural": 0.1,
            "working": 0.4 if "goal" in tags else 0.2,
            "episodic": 0.0,
        }.get(mem_type, 0.0)
        relevance = min(0.5 + type_boost, 1.0)

        items.append(ContextItem(
            id=m.get("id", ""),
            source="mem",
            title=m.get("title", mem_type),
            summary=m.get("summary", "")[:200],
            excerpt=m.get("summary", ""),
            relevance=relevance,
            age_days=0,
            metadata={
                "type": mem_type,
                "tags": tags,
                "semantic_score": relevance,
            }
        ))

    return items
