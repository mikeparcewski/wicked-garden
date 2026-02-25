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

    # Find wicked-search script — prefer local sibling (has pyproject.toml for uv run)
    search_paths = [
        Path(__file__).parent.parent.parent.parent / "wicked-search",
        Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / "wicked-search",
    ]

    search_script = None
    for base in search_paths:
        candidates = [base / "scripts" / "unified_search.py"] + list(base.glob("*/scripts/unified_search.py"))
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

    # wicked-search deps (rapidfuzz) are system-installed, no pyproject.toml — use python3
    cmd = ["python3", str(search_script), "search", search_terms, "--limit", "5"]
    returncode, stdout, stderr = await run_subprocess(cmd, timeout=10.0, cwd=str(Path.cwd()))

    if returncode == 0 and stdout.strip():
        # Parse text output format:
        #   Search Results (N):
        #   ---...
        #     [code:type] name
        #       Location: path:line
        #       Score: N.N
        import re
        for match in re.finditer(
            r'\[(\w+:\w+)\]\s+(.*?)\n\s+Location:\s+(.*?):(\d+)\n\s+Score:\s+([\d.]+)',
            stdout
        ):
            node_type = match.group(1)
            name = match.group(2).strip()
            file_path = match.group(3).strip()
            line = int(match.group(4))
            score = float(match.group(5)) / 100.0  # Normalize to 0-1

            short_path = Path(file_path).name
            title = f"{name} ({short_path}:{line})"

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
    elif stderr and stderr != "timeout":
        # Filter out known non-error warnings
        real_errors = [l for l in stderr.splitlines()
                       if "pathspec not available" not in l
                       and "kreuzberg not installed" not in l
                       and l.strip()]
        if real_errors:
            print(f"Warning: wicked-search query failed: {chr(10).join(real_errors)}", file=sys.stderr)

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
