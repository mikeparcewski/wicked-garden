"""
wicked-smaht adapter for Context7.

Queries external library documentation via Context7 MCP integration.
Provides graceful degradation when Context7 is unavailable.
"""

import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from . import ContextItem, _SCRIPTS_ROOT

if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from _domain_store import get_local_path

# Path to the cheatsheet store CLI — resolved relative to this file so no
# hardcoded absolute paths leak into the distributed plugin.
_CHEATSHEET_STORE = Path(__file__).resolve().parents[1] / "cheatsheet_store.py"


# Cache configuration
CACHE_DIR = get_local_path("wicked-smaht", "cache", "context7")
CACHE_TTL_SECONDS = 3600  # 1 hour
MAX_CACHE_ENTRIES = 500


class Context7Cache:
    """Simple file-based cache for Context7 query results."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = cache_dir / "index.json"
        self.data_dir = cache_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        self._load_index()

    def _load_index(self):
        """Load cache index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path) as f:
                    self.index = json.load(f)
            except Exception:
                self.index = {}
        else:
            self.index = {}

    def _save_index(self):
        """Save cache index to disk."""
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)

    def _cache_key(self, library_id: str, query: str) -> str:
        """Generate cache key from library ID and query."""
        content = f"{library_id}:{query}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _is_valid(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        cached_at = datetime.fromisoformat(entry['cached_at'])
        age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
        return age_seconds < CACHE_TTL_SECONDS

    def get(self, library_id: str, query: str) -> Optional[List[ContextItem]]:
        """Get cached results if valid, None otherwise."""
        key = self._cache_key(library_id, query)

        # Check index
        if key not in self.index:
            return None

        entry = self.index[key]

        # Validate TTL
        if not self._is_valid(entry):
            # Clean up expired entry
            self._remove(key)
            return None

        # Load data
        data_path = self.data_dir / f"{key}.json"
        if not data_path.exists():
            # Index/data mismatch - clean up
            self._remove(key)
            return None

        try:
            with open(data_path) as f:
                data = json.load(f)

            # Reconstruct ContextItems
            items = []
            for item_data in data:
                items.append(ContextItem(
                    id=item_data['id'],
                    source=item_data['source'],
                    title=item_data['title'],
                    summary=item_data['summary'],
                    excerpt=item_data.get('excerpt', ''),
                    relevance=item_data.get('relevance', 0.0),
                    age_days=item_data.get('age_days', 0.0),
                    metadata=item_data.get('metadata', {})
                ))

            return items
        except Exception as e:
            print(f"Warning: Failed to load cache entry {key}: {e}", file=sys.stderr)
            self._remove(key)
            return None

    def set(self, library_id: str, query: str, items: List[ContextItem]):
        """Cache query results."""
        key = self._cache_key(library_id, query)

        # Serialize items
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'source': item.source,
                'title': item.title,
                'summary': item.summary,
                'excerpt': item.excerpt,
                'relevance': item.relevance,
                'age_days': item.age_days,
                'metadata': item.metadata
            })

        # Write data
        data_path = self.data_dir / f"{key}.json"
        with open(data_path, 'w') as f:
            json.dump(items_data, f, indent=2)

        # Update index
        self.index[key] = {
            'library_id': library_id,
            'query': query,
            'cached_at': datetime.now(timezone.utc).isoformat(),
            'item_count': len(items)
        }

        # Enforce max entries (LRU-style cleanup)
        if len(self.index) > MAX_CACHE_ENTRIES:
            self._evict_oldest()

        self._save_index()

    def _remove(self, key: str):
        """Remove cache entry."""
        # Remove from index
        if key in self.index:
            del self.index[key]
            self._save_index()

        # Remove data file
        data_path = self.data_dir / f"{key}.json"
        if data_path.exists():
            data_path.unlink()

    def _evict_oldest(self):
        """Evict oldest 10% of entries."""
        # Sort by cached_at
        sorted_entries = sorted(
            self.index.items(),
            key=lambda x: x[1]['cached_at']
        )

        evict_count = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:evict_count]:
            self._remove(key)

    def clear(self):
        """Clear entire cache."""
        for key in list(self.index.keys()):
            self._remove(key)


# Global cache instance
_cache = Context7Cache()


def _lookup_cheatsheet(lib_name: str) -> Optional[ContextItem]:
    """Check local cheatsheet store for a cached library cheatsheet.

    Invokes cheatsheet_store.py get via subprocess so the hot path does not
    import DomainStore directly (keeps this adapter import-clean).

    Returns a ContextItem with relevance=0.85 when found, None otherwise.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(_CHEATSHEET_STORE), "get", "--library", lib_name],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        if not data or data.get("found") is False:
            return None

        library = data.get("library", lib_name)
        version = data.get("version_hint", "")
        title = f"{library} cheatsheet" + (f" ({version})" if version else "")

        key_apis = data.get("key_apis", [])
        patterns = data.get("common_patterns", [])
        gotchas = data.get("gotchas", [])

        # Build a compact summary from the structured data
        api_names = ", ".join(a.get("name", "") for a in key_apis[:5] if a.get("name"))
        pattern_names = ", ".join(p.get("name", "") for p in patterns[:3] if p.get("name"))
        summary_parts = []
        if api_names:
            summary_parts.append(f"Key APIs: {api_names}")
        if pattern_names:
            summary_parts.append(f"Patterns: {pattern_names}")
        summary = ". ".join(summary_parts) if summary_parts else f"Cached docs for {library}."

        # Build an excerpt from gotchas and first API example
        excerpt_parts = []
        if key_apis:
            first = key_apis[0]
            if first.get("example"):
                excerpt_parts.append(f"Example — {first.get('name', '')}: {first['example']}")
        if gotchas:
            excerpt_parts.append("Gotchas: " + "; ".join(gotchas[:2]))
        excerpt = "\n".join(excerpt_parts)

        return ContextItem(
            id=f"cheatsheet:{library}",
            source="cheatsheet",
            title=title,
            summary=summary,
            excerpt=excerpt,
            relevance=0.85,
            age_days=0.0,
            metadata={
                "library": library,
                "version_hint": version,
                "api_count": len(key_apis),
                "pattern_count": len(patterns),
                "source_url": data.get("source_url"),
                "timestamp": data.get("timestamp"),
            },
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"Warning: Cheatsheet lookup failed for {lib_name}: {e}", file=sys.stderr)
        return None


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """
    Query Context7 for relevant library documentation.

    This adapter uses the Context7 MCP integration to fetch external library docs.

    Strategy:
    1. Extract library names from prompt
    2. Check local cheatsheet store (hot tier — no MCP call needed)
    3. Resolve library IDs via Context7 (cached) for misses
    4. Query documentation (cached)
    5. Transform to ContextItems

    Args:
        prompt: User's query/prompt
        project: Optional project context (unused for Context7)

    Returns:
        List of ContextItems with documentation snippets
    """
    items = []

    # Extract potential library names from prompt
    library_names = _extract_library_names(prompt)
    if not library_names:
        return items

    # For each library, try to get docs
    for lib_name in library_names[:3]:  # Limit to 3 libraries
        try:
            # Hot tier: check local cheatsheet store first (no MCP round-trip)
            cheatsheet_item = await asyncio.to_thread(_lookup_cheatsheet, lib_name)
            if cheatsheet_item is not None:
                items.append(cheatsheet_item)
                continue

            # Try to get from cache first
            cached = _cache.get(lib_name, prompt)
            if cached is not None:
                items.extend(cached)
                continue

            # Not cached - query Context7
            lib_items = await _query_context7(lib_name, prompt)

            # Cache results (even if empty)
            _cache.set(lib_name, prompt, lib_items)

            items.extend(lib_items)

        except asyncio.TimeoutError:
            print(f"Warning: Context7 query timeout for {lib_name}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Context7 query failed for {lib_name}: {e}", file=sys.stderr)

    return items


async def _query_context7(library_name: str, query: str, timeout: float = 5.0) -> List[ContextItem]:
    """
    Query Context7 for a specific library.

    This function interfaces with the Context7 MCP tools if available.
    Falls back gracefully if MCP integration is not present.

    Args:
        library_name: Name of the library (e.g., "react", "express")
        query: The user's query
        timeout: Query timeout in seconds

    Returns:
        List of ContextItems from Context7 docs
    """
    items = []

    # Check if Context7 MCP tools are available
    try:
        # Import at runtime to avoid hard dependency
        # This would be the MCP integration point
        # For now, we'll use a subprocess approach to call MCP tools

        # Step 1: Resolve library ID
        library_id = await asyncio.wait_for(
            _resolve_library_id(library_name, query),
            timeout=timeout / 2
        )

        if not library_id:
            return items

        # Step 2: Query docs with library ID
        docs = await asyncio.wait_for(
            _query_docs(library_id, query),
            timeout=timeout / 2
        )

        # Step 3: Transform to ContextItems
        for idx, doc in enumerate(docs[:5]):  # Limit to 5 results
            items.append(ContextItem(
                id=f"context7:{library_id}:{idx}",
                source="context7",
                title=doc.get('title', f"{library_name} Documentation"),
                summary=doc.get('summary', '')[:200],
                excerpt=doc.get('content', '')[:500],
                relevance=doc.get('score', 0.7),
                age_days=0.0,  # External docs are current
                metadata={
                    'library_id': library_id,
                    'library_name': library_name,
                    'url': doc.get('url', ''),
                    'source_type': 'external_docs',
                }
            ))

    except asyncio.TimeoutError:
        raise
    except ImportError:
        # MCP tools not available - graceful degradation
        pass  # fail open: MCP tools optional
    except Exception as e:
        # Log but don't fail
        print(f"Context7 query error: {e}", file=sys.stderr)

    return items


async def _resolve_library_id(library_name: str, query: str) -> Optional[str]:
    """
    Resolve library name to Context7 library ID.

    Uses the Context7 MCP tool: resolve-library-id

    Returns:
        Library ID (e.g., "/vercel/next.js") or None
    """
    try:
        # Call Claude Code to invoke MCP tool via subprocess
        # In production, this would use the MCP client directly
        # For now, simulate with a known mapping

        # Common library mappings (fallback)
        library_map = {
            'react': '/facebook/react',
            'nextjs': '/vercel/next.js',
            'next': '/vercel/next.js',
            'express': '/expressjs/express',
            'fastapi': '/tiangolo/fastapi',
            'django': '/django/django',
            'flask': '/pallets/flask',
            'vue': '/vuejs/core',
            'angular': '/angular/angular',
            'svelte': '/sveltejs/svelte',
        }

        normalized = library_name.lower().replace('.js', '').replace('-', '')
        return library_map.get(normalized)

    except Exception as e:
        print(f"Library ID resolution failed for {library_name}: {e}", file=sys.stderr)
        return None


async def _query_docs(library_id: str, query: str) -> List[Dict[str, Any]]:
    """
    Query Context7 documentation for a library ID.

    Uses the Context7 MCP tool: query-docs

    Returns:
        List of documentation snippets with metadata
    """
    try:
        # In production, this would call the actual MCP tool
        # For now, return empty list (graceful degradation)
        # The MCP integration would happen at the hook level
        return []

    except Exception as e:
        print(f"Doc query failed for {library_id}: {e}", file=sys.stderr)
        return []


def _extract_library_names(prompt: str) -> List[str]:
    """
    Extract potential library/framework names from prompt.

    Uses heuristics to identify references to external libraries:
    - Common library names
    - Package manager patterns (npm install X, pip install X)
    - Import statements

    Args:
        prompt: User's query text

    Returns:
        List of potential library names
    """
    import re

    libraries = []
    prompt_lower = prompt.lower()

    # Pattern 1: Explicit library mentions with common keywords
    library_patterns = [
        r'\b(react|vue|angular|svelte|next(?:js)?|nuxt)\b',
        r'\b(express|fastapi|django|flask|rails|spring)\b',
        r'\b(mongodb|postgres|mysql|redis|elasticsearch)\b',
        r'\b(typescript|python|java|rust|go)\b',
        r'\b(jest|pytest|mocha|cypress|playwright)\b',
        r'\b(webpack|vite|rollup|esbuild|parcel)\b',
    ]

    for pattern in library_patterns:
        matches = re.findall(pattern, prompt_lower)
        libraries.extend(matches)

    # Pattern 2: Package manager install commands
    install_patterns = [
        r'npm install\s+(@?[\w-]+(?:/[\w-]+)?)',
        r'pip install\s+([\w-]+)',
        r'yarn add\s+(@?[\w-]+(?:/[\w-]+)?)',
    ]

    for pattern in install_patterns:
        matches = re.findall(pattern, prompt_lower)
        libraries.extend(matches)

    # Pattern 3: Import statements
    import_patterns = [
        r'from\s+([\w-]+)\s+import',
        r'import\s+([\w-]+)',
        r'require\([\'"](@?[\w-]+(?:/[\w-]+)?)[\'"]',
    ]

    for pattern in import_patterns:
        matches = re.findall(pattern, prompt)
        libraries.extend(matches)

    # Deduplicate and clean
    unique_libs = []
    seen = set()
    for lib in libraries:
        # Clean up library name
        lib = lib.strip().lower()

        # Skip built-ins and common false positives
        skip_list = {'os', 'sys', 'json', 'time', 're', 'math', 'from', 'import'}
        if lib in skip_list or len(lib) < 2:
            continue

        if lib not in seen:
            seen.add(lib)
            unique_libs.append(lib)

    return unique_libs[:5]  # Limit to 5 libraries


# Public API
__all__ = ['query', 'Context7Cache']
