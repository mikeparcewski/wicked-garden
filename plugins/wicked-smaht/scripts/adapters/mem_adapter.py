"""
wicked-mem adapter for wicked-smaht.

Queries memories, decisions, and procedural knowledge.
"""

import json
import sys
from pathlib import Path
from typing import List

from . import ContextItem, discover_script, run_subprocess


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


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-mem for relevant memories."""
    items = []

    mem_script = discover_script("wicked-mem", "memory.py")
    if not mem_script:
        return items

    # Extract meaningful keywords for ripgrep OR matching
    search_query = _extract_keywords(prompt)
    if not search_query:
        return items

    # Query memories using async subprocess (text output, no --json flag)
    # --all-projects searches core + all project memories for best recall
    cmd = [sys.executable, str(mem_script), "recall", "--query", search_query, "--limit", "5", "--all-projects"]
    returncode, stdout, stderr = await run_subprocess(cmd, timeout=5.0)

    if returncode == 0 and stdout.strip():
        # Parse text output format:
        #   [id] type [project]: title
        #     Tags: tag1, tag2
        #     Summary: text...
        import re
        blocks = re.split(r'(?=^\[)', stdout.strip(), flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            # Parse header: [id] type [project]: title  OR  [id] type: title
            header_match = re.match(
                r'\[([^\]]+)\]\s+(\w+)(?:\s+\[[^\]]*\])?:\s*(.*)', block
            )
            if not header_match:
                continue
            mem_id = header_match.group(1)
            mem_type = header_match.group(2)
            title = header_match.group(3).strip()

            # Parse tags
            tags = []
            tags_match = re.search(r'Tags:\s*(.*)', block)
            if tags_match:
                tags = [t.strip() for t in tags_match.group(1).split(",") if t.strip()]

            # Parse summary
            summary = ""
            summary_match = re.search(r'Summary:\s*(.*)', block)
            if summary_match:
                summary = summary_match.group(1).strip()

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
                id=mem_id,
                source="mem",
                title=title or mem_type,
                summary=summary[:200],
                excerpt=summary,
                relevance=relevance,
                age_days=0,
                metadata={
                    "type": mem_type,
                    "tags": tags,
                    "semantic_score": relevance,
                }
            ))
    elif stderr and stderr != "timeout":
        print(f"Warning: wicked-mem query failed: {stderr}", file=sys.stderr)

    return items
