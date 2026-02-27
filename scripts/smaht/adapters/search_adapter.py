"""
wicked-search adapter for wicked-smaht.

Queries code symbols, documentation, and cross-references via Control Plane.
"""

import sys
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT


# Resolve _control_plane from the scripts root
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from _control_plane import get_client

from . import run_in_thread


def _search_symbols(search_terms: str) -> list:
    """Query CP for code symbols matching search terms."""
    try:
        cp = get_client()
        resp = cp.request(
            "wicked-search", "symbols", "search",
            params={"q": search_terms, "limit": 5}
        )
        if resp and isinstance(resp.get("data"), list):
            return resp["data"]
        return []
    except Exception:
        return []


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-search for relevant code and docs."""
    items = []

    # Extract search terms from prompt
    search_terms = _extract_search_terms(prompt)
    if not search_terms:
        return items

    results = await run_in_thread(_search_symbols, search_terms)

    for result in results:
        name = result.get("name", "")
        file_path = result.get("file", "") or result.get("path", "")
        line = result.get("line", 0)
        node_type = result.get("type", "code:symbol")
        score = result.get("score", 50) / 100.0  # Normalize to 0-1

        short_path = Path(file_path).name if file_path else ""
        title = f"{name} ({short_path}:{line})" if short_path else name

        items.append(ContextItem(
            id=f"{file_path}:{line}:{name}",
            source="search",
            title=title,
            summary=f"{node_type}: {name}",
            excerpt="",
            age_days=0,
            metadata={
                "file": file_path,
                "line": line,
                "type": node_type,
                "semantic_score": score,
            }
        ))

    return items


def _extract_search_terms(prompt: str) -> str:
    """Extract meaningful search terms from prompt."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "can", "may", "might", "must", "shall",
        "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our",
        "their", "this", "that", "these", "those", "what", "which",
        "who", "whom", "where", "when", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "and", "but", "if", "or",
        "because", "as", "until", "while", "of", "at", "by", "for",
        "with", "about", "against", "between", "into", "through",
        "during", "before", "after", "above", "below", "to", "from",
        "up", "down", "in", "out", "on", "off", "over", "under",
    }

    words = prompt.lower().split()
    terms = [w for w in words if w not in stop_words and len(w) > 2]

    # Take first 5 meaningful terms
    return " ".join(terms[:5])
