"""
Local memory adapter for wicked-smaht slow path.

Queries wicked-mem local storage directly via MemoryStore, surfacing
decision, preference, and procedural memories regardless of CP availability.

This adapter exists alongside cp_adapter: cp_adapter handles memories when
the control plane is online (with richer search); this adapter handles the
local fallback so stored memories are always surfaced in the slow path.

Deduplication: items already returned by cp_adapter (same title) will score
lower here due to cp_adapter's higher relevance weights, so the budget
enforcer will naturally prefer one over the other.
"""

import sys
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))


_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "may", "might", "must", "i", "you", "we", "they", "me", "my", "your",
    "this", "that", "these", "those", "what", "which", "who", "how", "why",
    "when", "where", "and", "or", "but", "if", "for", "of", "to", "from",
    "in", "on", "at", "by", "with", "about", "not", "so", "just", "also",
    "need", "want", "let", "get", "make", "test", "check", "fix", "work",
})

# Memory types to prioritise — decisions and preferences are most actionable
_HIGH_VALUE_TYPES = {"decision", "preference", "procedural"}

# Relevance boosts by memory type
_TYPE_BOOSTS = {
    "decision": 0.3,
    "preference": 0.3,
    "procedural": 0.15,
    "working": 0.2,
    "episodic": 0.0,
}


def _extract_keywords(prompt: str) -> str:
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords[:8]) if keywords else ""


def _keyword_score(prompt_lower: str, text: str) -> float:
    """Score text by keyword overlap with prompt."""
    if not text:
        return 0.0
    text_lower = text.lower()
    score = 0.0
    for word in prompt_lower.split():
        if len(word) > 3 and word in text_lower:
            score += 0.15
    return min(score, 0.45)


def _query_local_memories(prompt: str) -> list:
    """Query MemoryStore local storage. Runs in thread pool."""
    try:
        mem_scripts = _SCRIPTS_ROOT / "mem"
        if str(mem_scripts) not in sys.path:
            sys.path.insert(0, str(mem_scripts))
        from memory import MemoryStore, MemoryType

        store = MemoryStore()
        query_str = _extract_keywords(prompt)
        if not query_str:
            return []

        # Search across all types; MemoryStore.recall() applies keyword search
        memories = store.recall(query=query_str, limit=15)
        return memories
    except Exception:
        return []


async def query(prompt: str) -> List[ContextItem]:
    """Query local wicked-mem storage for relevant memories.

    Always queries local storage directly so memories are surfaced even
    when the control plane is offline. Returns ContextItems tagged with
    source="mem" so the slow path briefing formatter labels them correctly.
    """
    memories = await run_in_thread(_query_local_memories, prompt)
    if not memories:
        return []

    prompt_lower = prompt.lower()
    items: list[ContextItem] = []

    for memory in memories:
        title = memory.title or "Untitled"
        summary = memory.summary or memory.content[:200]

        # Score: base + keyword overlap + type boost
        base = 0.25
        kw_score = _keyword_score(prompt_lower, f"{title} {summary}")
        type_boost = _TYPE_BOOSTS.get(memory.type, 0.0)
        # Importance: 2=low, 5=medium, 8=high → add up to 0.1 bonus
        importance_bonus = min((memory.importance - 2) / 60, 0.1)
        relevance = min(base + kw_score + type_boost + importance_bonus, 1.0)

        # Calculate age in days
        age_days = 0.0
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(memory.created.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - dt).days
        except Exception:
            pass

        items.append(ContextItem(
            id=memory.id,
            source="mem",
            title=title,
            summary=summary[:200],
            excerpt=summary[:100],
            relevance=relevance,
            age_days=age_days,
            metadata={
                "type": memory.type,
                "importance": memory.importance,
                "tags": memory.tags,
            },
        ))

    # Sort by relevance; budget enforcer will cap total items across sources
    items.sort(key=lambda x: x.relevance, reverse=True)
    return items
