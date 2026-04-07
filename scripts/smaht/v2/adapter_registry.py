#!/usr/bin/env python3
"""
wicked-smaht v2: Unified Adapter Registry

Single load point for all smaht adapters. Replaces the duplicated
_load_adapters() method that previously existed in both fast_path.py
and slow_path.py.

Provides:
  - AdapterRegistry: loads all adapters once with graceful ImportError handling
  - timed_query: coroutine wrapping adapter.query() with cache + timing
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

# Add parent to path for adapter imports (mirrors fast_path.py / slow_path.py)
sys.path.insert(0, str(Path(__file__).parent.parent))


class AdapterRegistry:
    """Single load point for all smaht adapters.

    Loads all known adapters once at init with graceful degradation.
    Callers request adapters by name via get(names).
    No adapter is queried automatically — callers pass explicit name lists.
    """

    # Canonical mapping of adapter name -> module path.
    # All known adapters are registered here. Changing this is the single
    # place to add or rename an adapter.
    KNOWN_ADAPTERS: dict[str, str] = {
        "domain":     "adapters.domain_adapter",
        "brain":      "adapters.brain_adapter",
        "events":     "adapters.events_adapter",
        "context7":   "adapters.context7_adapter",
        "tools":      "adapters.startah_adapter",
        "delegation": "adapters.delegation_adapter",
    }

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all known adapters. Failed imports log to stderr and are skipped."""
        for name, module_path in self.KNOWN_ADAPTERS.items():
            try:
                mod = __import__(module_path, fromlist=[module_path])
                self._adapters[name] = mod
            except ImportError as e:
                print(f"smaht: adapter '{name}' unavailable: {e}", file=sys.stderr)

    def get(self, names: list[str]) -> dict[str, Any]:
        """Return a dict of {name: module} for the requested names.

        Names not present in the registry (failed import or unknown) are
        silently omitted. Callers check for missing names via sources_failed.
        """
        return {name: self._adapters[name] for name in names if name in self._adapters}

    def available(self) -> list[str]:
        """Return list of successfully loaded adapter names."""
        return list(self._adapters.keys())


# Default set of adapters that bypass caching (always-fresh requirement).
# Defined here so all call sites share one constant.
CACHE_BYPASS: frozenset = frozenset({"mem"})


async def timed_query(
    adapter_mod: Any,
    name: str,
    prompt: str,
    timeout: float,
    timing_accumulator: dict,
    call_cache: "dict | None" = None,
    cache_bypass: frozenset = frozenset(),
) -> list:
    """Query adapter with timing, optional within-call deduplication, and bypass support.

    Updates timing_accumulator in-place with call_count, total_ms, cache_hits,
    and failures for the given adapter name.

    Cache semantics:
    - call_cache=None: no-caching mode — adapter is always called
    - name in cache_bypass: adapter always called, result NOT written to cache
      (used for mem adapter: TTL=0 / always-fresh requirement)
    - name in call_cache: cache hit — return stored result, increment cache_hits
    - otherwise: cache miss — call adapter, store result, record timing

    Raises on adapter failure so the caller can mark sources_failed.
    Does NOT swallow exceptions — callers (assemblers) catch and handle.
    """
    # Guard: treat call_cache=None as no-caching mode (Gap G-1)
    cache_active = call_cache is not None

    # Bypass check (e.g. mem adapter, AC-1.3)
    in_bypass = name in cache_bypass

    # Cache hit path — only when cache is active and name is not bypassed
    if cache_active and not in_bypass and name in call_cache:
        acc = timing_accumulator.setdefault(name, {
            "total_ms": 0, "call_count": 0, "cache_hits": 0, "failures": 0,
        })
        acc["cache_hits"] += 1
        return call_cache[name]

    # Cache miss (or bypass, or no-cache mode) — call the adapter
    try:
        t0 = time.monotonic()
        result = await asyncio.wait_for(adapter_mod.query(prompt), timeout=timeout)
        elapsed_ms = (time.monotonic() - t0) * 1000

        # Record successful call timing
        acc = timing_accumulator.setdefault(name, {
            "total_ms": 0, "call_count": 0, "cache_hits": 0, "failures": 0,
        })
        acc["total_ms"] += elapsed_ms
        acc["call_count"] += 1

        # Write to cache only when: cache is active AND name is not bypassed (Gap G-2)
        if cache_active and not in_bypass:
            call_cache[name] = result

        return result

    except Exception:
        # Record failure — do NOT update total_ms (Gap G-3 guard: call_count stays 0)
        acc = timing_accumulator.setdefault(name, {
            "total_ms": 0, "call_count": 0, "cache_hits": 0, "failures": 0,
        })
        acc["failures"] += 1
        # Re-raise so the assembler can mark this adapter as sources_failed
        raise
