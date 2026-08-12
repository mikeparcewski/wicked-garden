"""
Knowledge-layer adapter for wicked-smaht context assembly (S4: brain→estate).

Queries the routed context backend (wicked-estate recall fusion by default;
the legacy wicked-brain FTS5 index for symbolish queries while the bridge is
alive — see scripts/_context_backend.py) for code and document context
relevant to the current prompt. Returns ContextItems whose ``source`` names
the answering backend ("estate" / "brain") and whose metadata carries the
store-level source attribution (estate #96) and memory scope.

The knowledge layer degrades gracefully: when no backend is reachable, this
adapter logs a warning to stderr and returns empty — never raises.
"""

import sys
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
    """Extract up to `limit` keywords for the backend query.

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


def _query_backend(prompt: str) -> list:
    """Query the routed context backend with extracted keywords.

    Routing, the estate two-call recall fusion, and the brain-side FTS5
    3-term→2-term retry all live in _context_backend.search(). Returns
    normalized result dicts, or [] when no backend answers (fail-open).
    """
    keywords = _extract_keywords(prompt, limit=3)
    if not keywords:
        return []

    try:
        from _context_backend import search as _ctx_search

        return _ctx_search(keywords, limit=10)
    except Exception as _e:
        print(
            "smaht: context backend unreachable"
            f" — context assembly degraded: {type(_e).__name__}",
            file=sys.stderr,
        )
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

    Both backends can surface frontmatter (the brain server re-indexes full
    chunk files; estate's migrated chunks kept those bodies). Strip
    aggressively: snake_case keys, floats, timestamps, list tags, and
    separator markers.
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


def _source_file_of(item: dict) -> str:
    """Derive the originating source file from a normalized backend item.

    Estate items carry a ``source`` attribution URI like
    ``wicked-brain://wicked-garden/chunks/extracted/<slug>/chunk-001.md``;
    brain items carry ``wicked-brain://<chunk path>``. Memories have no
    source file — group them by their own id so each stays distinct.
    """
    if item.get("kind") == "memory":
        return item.get("id", "") or "memory"
    ref = item.get("source", "") or item.get("id", "")
    if "chunks/extracted/" in ref:
        return ref.split("chunks/extracted/", 1)[1].split("/chunk-")[0]
    return ref


async def query(prompt: str) -> List[ContextItem]:
    """Query the knowledge layer for context relevant to the prompt."""
    results = await run_in_thread(_query_backend, prompt)
    if not results:
        return []

    # Score against extracted keywords only (not full prompt) so incidental
    # words in the prompt (e.g. "crew" in "without going through the crew
    # workflow") don't boost unrelated documents that happen to mention them.
    score_against = _extract_keywords(prompt, limit=3) or prompt.lower()

    # First pass: build items grouped by source file (deduplicate chunks → 1 item per source)
    best_by_source: dict[str, dict] = {}

    for r in results:
        if not isinstance(r, dict):
            continue
        source_file = _source_file_of(r)
        clean_snippet = _clean_snippet(r.get("snippet", ""))
        kw_score = _keyword_score(score_against, f"{source_file} {clean_snippet}")
        # Items with no readable snippet get a relevance floor of 0.2 so they
        # rank below items that survived cleaning and only appear if budget allows.
        base = 0.2 if not clean_snippet else 0.3
        relevance = min(base + kw_score, 1.0)

        # Keep only the highest-scoring chunk per source file
        existing = best_by_source.get(source_file)
        if existing is None or relevance > existing["relevance"]:
            best_by_source[source_file] = {
                "item": r,
                "source_file": source_file,
                "snippet": clean_snippet,
                "relevance": relevance,
            }

    # Second pass: convert to ContextItems
    items: List[ContextItem] = []
    for source_file, entry in best_by_source.items():
        r = entry["item"]
        if r.get("kind") == "memory":
            # A memory's first content line is its natural title.
            title = r.get("title") or "memory"
        else:
            title = _readable_title(source_file)
        items.append(ContextItem(
            id=r.get("id", ""),
            source=r.get("backend", "estate"),
            title=title,
            summary=entry["snippet"],
            excerpt=entry["snippet"][:100],
            relevance=entry["relevance"],
            metadata={
                # Store-level attribution (estate #96) + scope for memories.
                "source": r.get("source", ""),
                "scope": r.get("scope", ""),
                "type": r.get("kind", ""),
                "backend": r.get("backend", ""),
            },
        ))

    items.sort(key=lambda x: x.relevance, reverse=True)
    return items
