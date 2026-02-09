"""
wicked-search adapter for wicked-smaht.

Queries code symbols, documentation, and cross-references.
"""

import json
import sys
from pathlib import Path
from typing import List

from . import ContextItem, run_subprocess


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-search for relevant code and docs."""
    items = []

    # Find wicked-search script
    search_paths = [
        Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / "wicked-search",
        Path(__file__).parent.parent.parent.parent / "wicked-search",
    ]

    search_script = None
    for base in search_paths:
        candidates = list(base.glob("*/scripts/unified_search.py")) + [base / "scripts" / "unified_search.py"]
        for c in candidates:
            if c.exists():
                search_script = c
                break
        if search_script:
            break

    if not search_script:
        return items

    # Extract search terms from prompt
    search_terms = _extract_search_terms(prompt)
    if not search_terms:
        return items

    # Query wicked-search using async subprocess
    cmd = ["python3", str(search_script), "search", search_terms, "--limit", "5", "--json"]
    returncode, stdout, stderr = await run_subprocess(cmd, timeout=10.0, cwd=str(Path.cwd()))

    if returncode == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            results = data.get("results", [])

            for res in results:
                name = res.get("name", "")
                file_path = res.get("file", "")
                node_type = res.get("type", "symbol")
                line = res.get("line", 0)
                score = res.get("score", 0.5)

                # Format title
                if file_path:
                    short_path = Path(file_path).name
                    title = f"{name} ({short_path}:{line})"
                else:
                    title = name

                items.append(ContextItem(
                    id=f"{file_path}:{line}:{name}",
                    source="search",
                    title=title,
                    summary=f"{node_type}: {name}",
                    excerpt=res.get("context", ""),
                    age_days=0,  # Code is considered "current"
                    metadata={
                        "file": file_path,
                        "line": line,
                        "type": node_type,
                        "semantic_score": score,
                    }
                ))
        except json.JSONDecodeError as e:
            print(f"Warning: wicked-search JSON parse failed: {e}", file=sys.stderr)
    elif stderr and stderr != "timeout":
        print(f"Warning: wicked-search query failed: {stderr}", file=sys.stderr)

    return items


def _extract_search_terms(prompt: str) -> str:
    """Extract meaningful search terms from prompt."""
    # Remove common words
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
