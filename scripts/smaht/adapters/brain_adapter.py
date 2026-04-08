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
    # English filler that passes len>2 but over-constrains FTS5 AND matching
    "one", "two", "all", "any", "some", "out", "use", "via", "per",
    "without", "going", "through", "using", "into", "onto", "upon",
    "there", "their", "then", "than", "its", "our", "has",
    # Prepositions / general connectors that look content-y but aren't
    "between", "across", "along", "around", "before", "after",
    "exist", "exists", "show", "tell", "give", "take",
})


def _extract_keywords(prompt: str, limit: int = 3) -> str:
    """Extract up to `limit` keywords for FTS5 AND query.

    Position-order preserves the prompt's intent; the first non-stop words
    are almost always the topic. Callers pass limit=2 for retry fallback.
    """
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    seen: set[str] = set()
    unique = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return " ".join(unique[:limit]) if unique else ""


def _query_brain(prompt: str) -> list:
    """Query brain FTS5 index with automatic recall fallback.

    FTS5 uses AND — more terms = fewer results. Try 3 terms first (higher
    precision); if < 2 results, try two 2-term combinations and pick the
    one with more results:
      - first + third (drop middle — often the most generic term)
      - first + second (standard narrowing)
    """
    keywords = _extract_keywords(prompt, limit=3).split()
    if not keywords:
        return []

    query = " ".join(keywords)

    try:
        port = int(os.environ.get("WICKED_BRAIN_PORT", "4242"))

        def _search(q: str) -> list:
            payload = json.dumps({
                "action": "search",
                "params": {"query": q, "limit": 10},
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://localhost:{port}/api",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8")).get("results", [])

        results = _search(query)
        if len(results) < 2 and len(keywords) >= 3:
            # Try dropping the middle keyword (often the least specific)
            alt_a = f"{keywords[0]} {keywords[2]}"  # first + third
            alt_b = f"{keywords[0]} {keywords[1]}"  # first + second
            ra = _search(alt_a)
            rb = _search(alt_b)
            # Prefer whichever returns more results (wider recall)
            results = ra if len(ra) >= len(rb) else rb
        elif len(results) < 2 and len(keywords) == 2:
            # Already at 2 terms; nothing further to try
            pass
        return results
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


def _readable_title(source_file: str) -> str:
    """Convert a chunk source path to a human-readable title.

    e.g. "skills-crew-workflow-refs-specialist-routing-rules.md"
      → "crew / specialist-routing-rules"
    """
    import re as _re
    # Strip leading domain prefix like "skills-", "commands-", "agents-", "hooks-"
    name = _re.sub(r'^(skills|commands|agents|hooks|scenarios|scripts|docs)-', '', source_file)
    # Strip .md extension
    name = name.removesuffix('.md')
    # Split on '-' to get components; find the domain and the tail
    parts = name.split('-')
    if len(parts) >= 2:
        # First part is domain; rest is description
        domain = parts[0]
        # Skip "refs" and numeric-looking chunks
        desc_parts = [p for p in parts[1:] if p != 'refs' and not p.startswith('chunk')]
        if desc_parts:
            return f"{domain} / {'-'.join(desc_parts)}"
    return name


def _clean_snippet(raw: str) -> str:
    """Strip YAML frontmatter lines and FTS highlight tags from snippet.

    FTS5 snippets contain frontmatter when the brain server re-indexes full
    chunk files. Strip aggressively: snake_case keys, floats, timestamps,
    list tags, and separator markers.
    """
    import re as _re

    # Remove FTS5 highlight markers and ellipsis separators
    text = _re.sub(r"<[^>]+>", "", raw)
    text = text.replace("…", " ").replace("...", " ")

    # Patterns that indicate frontmatter / metadata noise — skip these lines
    _yaml_key   = _re.compile(r'^[a-z][a-z_]+:\s*')        # snake_case key: value
    _bare_float = _re.compile(r'^\d+\.\d+$')               # e.g. "0.7"
    _timestamp  = _re.compile(r'^\d{4}-\d{2}-\d{2}')       # ISO date
    _tag_list   = _re.compile(r'^- [a-z][\w\-]*$')         # bare YAML tag list items
    _flag_list  = _re.compile(r'^- --[\w\-]+')             # CLI flag list items: - --flag
    _uuid_like  = _re.compile(r'^[a-f0-9\-]{8,}$')         # UUIDs
    # Leftover path values after their YAML key was stripped
    _file_path  = _re.compile(r'^[\w/.\- ]+\.(md|py|js|ts|jsx|tsx|json|yaml|yml|sh|txt)$')
    # chunk-ID paths: "source-name/chunk-NNN" or bare "chunk-NNN"
    _chunk_id   = _re.compile(r'(^|/)chunk-\d+')
    # Markdown table rows: any line starting with | (data rows and separators)
    _table_row  = _re.compile(r'^\|')

    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if (_yaml_key.match(stripped)
                or _bare_float.match(stripped)
                or _timestamp.match(stripped)
                or _tag_list.match(stripped)
                or _flag_list.match(stripped)
                or _uuid_like.match(stripped)
                or _file_path.match(stripped)
                or _chunk_id.search(stripped)
                or _table_row.match(stripped)):
            continue
        lines.append(stripped)

    result = " ".join(lines).strip()
    return result[:160] if result else ""


async def query(prompt: str) -> List[ContextItem]:
    """Query brain for code and document context relevant to the prompt."""
    results = await run_in_thread(_query_brain, prompt)
    if not results:
        return []

    import re
    # Score against extracted keywords only (not full prompt) so incidental
    # words in the prompt (e.g. "crew" in "without going through the crew
    # workflow") don't boost unrelated documents that happen to mention them.
    score_against = _extract_keywords(prompt, limit=3) or prompt.lower()

    # First pass: build items grouped by source file (deduplicate chunks → 1 item per source)
    best_by_source: dict[str, dict] = {}

    for r in results:
        path = r.get("path", "") or r.get("id", "")
        snippet = r.get("snippet", "")

        # Determine source file from chunk path
        source_file = ""
        if "chunks/extracted/" in path:
            part = path.replace("chunks/extracted/", "").split("/chunk-")[0]
            source_file = part
        else:
            source_file = path

        clean_snippet = _clean_snippet(snippet)
        kw_score = _keyword_score(score_against, f"{source_file} {clean_snippet}")
        # Items with no readable snippet get a relevance floor of 0.2 so they
        # rank below items that survived cleaning and only appear if budget allows.
        base = 0.2 if not clean_snippet else 0.3
        relevance = min(base + kw_score, 1.0)

        # Keep only the highest-scoring chunk per source file
        existing = best_by_source.get(source_file)
        if existing is None or relevance > existing["relevance"]:
            best_by_source[source_file] = {
                "path": path,
                "source_file": source_file,
                "snippet": clean_snippet,
                "relevance": relevance,
            }

    # Second pass: convert to ContextItems
    items: List[ContextItem] = []
    for source_file, entry in best_by_source.items():
        title = _readable_title(source_file)
        items.append(ContextItem(
            id=entry["path"],
            source="brain",
            title=title,
            summary=entry["snippet"],
            excerpt=entry["snippet"][:100],
            relevance=entry["relevance"],
            metadata={"brain_path": entry["path"]},
        ))

    items.sort(key=lambda x: x.relevance, reverse=True)
    return items
