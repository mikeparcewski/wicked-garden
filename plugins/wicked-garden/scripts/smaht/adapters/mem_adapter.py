"""
wicked-mem adapter for wicked-smaht.

Queries memories, decisions, and procedural knowledge.
Uses direct import of mem.memory since all scripts are co-located.
"""

import sys
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

# Direct import of the memory module (co-located under scripts/mem/)
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from mem.memory import MemoryStore, MemoryType


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
    """Extract meaningful keywords and join with | for ripgrep OR matching."""
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    # Take top 5 keywords for focused search
    return "|".join(keywords[:5]) if keywords else ""


def _recall_memories(search_query: str) -> list:
    """Synchronous memory recall — called via run_in_thread for async."""
    try:
        store = MemoryStore()
        memories = store.recall(
            query=search_query,
            limit=5,
            all_projects=True,
        )
        return memories
    except Exception:
        return []


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-mem for relevant memories."""
    items = []

    # Extract meaningful keywords for ripgrep OR matching
    search_query = _extract_keywords(prompt)
    if not search_query:
        return items

    # Query memories via direct call (run in thread since it may do disk I/O)
    memories = await run_in_thread(_recall_memories, search_query)

    for m in memories:
        tags = getattr(m, "tags", [])
        mem_type = getattr(m, "type", "episodic")

        # Boost relevance based on memory type
        type_boost = {
            "decision": 0.3,
            "preference": 0.3,
            "procedural": 0.1,
            "working": 0.4 if "goal" in tags else 0.2,
            "episodic": 0.0,
        }.get(mem_type, 0.0)
        relevance = min(0.5 + type_boost, 1.0)

        items.append(ContextItem(
            id=getattr(m, "id", ""),
            source="mem",
            title=getattr(m, "title", mem_type),
            summary=getattr(m, "summary", "")[:200],
            excerpt=getattr(m, "summary", ""),
            relevance=relevance,
            age_days=0,
            metadata={
                "type": mem_type,
                "tags": tags,
                "semantic_score": relevance,
            }
        ))

    return items
