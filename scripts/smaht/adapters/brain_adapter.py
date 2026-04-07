"""
Brain adapter for wicked-smaht context assembly.

Queries the wicked-brain FTS5 index for code and document context
relevant to the current prompt. Returns ContextItems tagged with
source="brain" so the slow path briefing formatter labels them correctly.

This replaces the old search adapter — brain is the unified knowledge layer.
When brain is unavailable, returns empty (agent falls back to Grep/Glob).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List

from . import ContextItem, run_in_thread

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "may", "might", "must", "i", "you", "we", "they", "me", "my", "your",
    "this", "that", "these", "those", "what", "which", "who", "how", "why",
    "when", "where", "and", "or", "but", "if", "for", "of", "to", "from",
    "in", "on", "at", "by", "with", "about", "not", "so", "just", "also",
    "need", "want", "let", "get", "make", "test", "check", "fix", "work",
})


def _extract_keywords(prompt: str) -> str:
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords[:10]) if keywords else ""


def _query_brain(prompt: str) -> list:
    """Query brain FTS5 index. Runs in thread pool."""
    query = _extract_keywords(prompt)
    if not query:
        return []

    try:
        port = int(os.environ.get("WICKED_BRAIN_PORT", "4242"))
        payload = json.dumps({
            "action": "search",
            "params": {"query": query, "limit": 10},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except Exception:
        return []


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


async def query(prompt: str) -> List[ContextItem]:
    """Query brain for code and document context relevant to the prompt."""
    results = await run_in_thread(_query_brain, prompt)
    if not results:
        return []

    import re
    prompt_lower = prompt.lower()
    items: List[ContextItem] = []

    for r in results:
        path = r.get("path", "") or r.get("id", "")
        snippet = r.get("snippet", "")
        clean_snippet = re.sub(r"<[^>]+>", "", snippet)[:200]

        # Determine source file from chunk path
        source_file = ""
        if "chunks/extracted/" in path:
            part = path.replace("chunks/extracted/", "").split("/chunk-")[0]
            source_file = part

        title = source_file or path
        kw_score = _keyword_score(prompt_lower, f"{title} {clean_snippet}")
        relevance = min(0.3 + kw_score, 1.0)

        items.append(ContextItem(
            id=path,
            source="brain",
            title=title,
            summary=clean_snippet,
            excerpt=clean_snippet[:100],
            relevance=relevance,
            metadata={"brain_path": path},
        ))

    items.sort(key=lambda x: x.relevance, reverse=True)
    return items
