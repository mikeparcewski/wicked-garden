"""
Wicked Cache - Unified Caching Infrastructure

Standalone caching for Wicked Garden marketplace plugins.
Provides namespace isolation, TTL support, and file-based invalidation.

All data flows through StorageManager("wicked-startah") which routes to the
Control Plane when available and falls back to local JSON files.

API Usage:
    from cache import namespace

    cache = namespace("my-plugin")
    cache.set("key", value, source_file="./data.csv")
    result = cache.get("key")  # Returns None if source file changed
"""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

# Resolve _storage from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager


class InvalidationMode(Enum):
    """Cache invalidation strategies."""

    FILE = "file"  # Invalidate when source file changes (mtime + size)
    TTL = "ttl"  # Invalidate after time-to-live expires
    MANUAL = "manual"  # Never auto-invalidate


@dataclass
class CacheEntry:
    """Metadata for a cached value."""

    key: str
    source_file: Optional[str]
    source_mtime: Optional[int]  # Nanoseconds since epoch
    source_size: Optional[int]  # Bytes
    cached_at: str  # ISO8601 timestamp
    ttl_seconds: Optional[int]
    mode: str  # InvalidationMode value


class NamespacedCache:
    """Scoped cache client for a specific namespace, backed by StorageManager."""

    def __init__(self, namespace: str, sm: StorageManager):
        self.namespace = namespace
        self._sm = sm

    def _cache_id(self, key: str) -> str:
        """Build a composite ID for StorageManager: namespace:key."""
        return f"{self.namespace}:{key}"

    def _dict_to_entry(self, d: dict) -> CacheEntry:
        """Convert dict to CacheEntry."""
        return CacheEntry(
            key=d.get("key", ""),
            source_file=d.get("source_file"),
            source_mtime=d.get("source_mtime"),
            source_size=d.get("source_size"),
            cached_at=d.get("cached_at", ""),
            ttl_seconds=d.get("ttl_seconds"),
            mode=d.get("mode", "manual"),
        )

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if valid, None if miss or invalid."""
        record = self._sm.get("cache", self._cache_id(key))
        if record is None:
            return None

        entry = self._dict_to_entry(record)
        if not self._is_valid(entry):
            return None

        return record.get("value")

    def set(
        self,
        key: str,
        value: Any,
        source_file: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> str:
        """Store value in cache."""
        opts = options or {}
        mode_str = opts.get("mode", "file" if source_file else "manual")
        mode = InvalidationMode(mode_str)

        source_mtime = None
        source_size = None
        if source_file:
            source_mtime = self._get_mtime(source_file)
            source_size = self._get_size(source_file)

        record = {
            "id": self._cache_id(key),
            "namespace": self.namespace,
            "key": key,
            "value": value,
            "source_file": source_file,
            "source_mtime": source_mtime,
            "source_size": source_size,
            "cached_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ttl_seconds": opts.get("ttl_seconds"),
            "mode": mode.value,
        }

        existing = self._sm.get("cache", self._cache_id(key))
        if existing:
            self._sm.update("cache", self._cache_id(key), record)
        else:
            self._sm.create("cache", record)

        return key

    def invalidate(self, key: str) -> bool:
        """Explicitly invalidate a cache entry."""
        return self._sm.delete("cache", self._cache_id(key))

    def clear(self) -> int:
        """Clear all entries. Returns count cleared."""
        entries = self._sm.list("cache", namespace=self.namespace)
        count = len(entries)
        for entry in entries:
            entry_id = entry.get("id", self._cache_id(entry.get("key", "")))
            self._sm.delete("cache", entry_id)
        return count

    def list_entries(self) -> list:
        """List all cache entries with metadata."""
        records = self._sm.list("cache", namespace=self.namespace)
        entries = []
        for record in records:
            entry = self._dict_to_entry(record)
            valid = self._is_valid(entry)

            # Estimate size from stored value
            value = record.get("value")
            size = len(json.dumps(value).encode()) if value is not None else 0

            cached_at_str = entry.cached_at
            age_seconds = 0
            if cached_at_str:
                try:
                    cached_at = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
                    age_seconds = int((datetime.now(cached_at.tzinfo) - cached_at).total_seconds())
                except Exception:
                    pass

            entries.append({
                "key": entry.key,
                "valid": valid,
                "size": size,
                "age": age_seconds,
                "source_file": entry.source_file,
            })
        return entries

    def stats(self) -> dict:
        """Get namespace statistics."""
        entries = self.list_entries()
        total_size = sum(e["size"] for e in entries)
        oldest_age = max((e["age"] for e in entries), default=0)

        return {
            "entry_count": len(entries),
            "total_size": total_size,
            "hit_count": 0,
            "miss_count": 0,
            "oldest_entry_age": oldest_age,
        }

    # Private methods

    def _is_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid."""
        mode = InvalidationMode(entry.mode)

        if mode == InvalidationMode.MANUAL:
            return True

        elif mode == InvalidationMode.TTL:
            if entry.ttl_seconds is None:
                return True
            cached_at = datetime.fromisoformat(entry.cached_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(cached_at.tzinfo) - cached_at).total_seconds()
            return elapsed < entry.ttl_seconds

        elif mode == InvalidationMode.FILE:
            if entry.source_file is None:
                return True
            current_mtime = self._get_mtime(entry.source_file)
            current_size = self._get_size(entry.source_file)
            if current_mtime is None or current_size is None:
                return False
            return (
                current_mtime == entry.source_mtime
                and current_size == entry.source_size
            )

        return False

    def _get_mtime(self, filepath: str) -> Optional[int]:
        """Get file modification time in nanoseconds."""
        try:
            stat = os.stat(filepath)
            return int(stat.st_mtime_ns)
        except OSError:
            return None

    def _get_size(self, filepath: str) -> Optional[int]:
        """Get file size in bytes."""
        try:
            stat = os.stat(filepath)
            return stat.st_size
        except OSError:
            return None


# Module-level StorageManager singleton
_SM: Optional[StorageManager] = None


def _get_sm() -> StorageManager:
    """Get or create the StorageManager for cache."""
    global _SM
    if _SM is None:
        _SM = StorageManager("wicked-startah")
    return _SM


def namespace(name: str) -> NamespacedCache:
    """
    Get a scoped cache client for the given namespace.

    Args:
        name: Namespace name (typically plugin name, e.g., "numbah-crunchah")

    Returns:
        NamespacedCache instance for the namespace

    Example:
        cache = namespace("my-plugin")
        cache.set("key", {"data": [1, 2, 3]}, source_file="./data.csv")
        result = cache.get("key")
    """
    return NamespacedCache(name, _get_sm())


def main():
    """CLI interface for testing cache operations."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Wicked Memory Cache Operations")
    parser.add_argument(
        "operation",
        choices=["set", "get", "invalidate", "stats", "list", "clear"],
        help="Operation to perform",
    )
    parser.add_argument("--namespace", "-n", required=True, help="Plugin namespace")
    parser.add_argument("--key", "-k", help="Cache key")
    parser.add_argument("--value", "-v", help="Value to store (JSON string)")
    parser.add_argument(
        "--source-file", "-s", help="Source file for file-based invalidation"
    )
    parser.add_argument("--ttl", type=int, help="Time-to-live in seconds")
    parser.add_argument(
        "--mode", choices=["file", "ttl", "manual"], help="Invalidation mode"
    )

    args = parser.parse_args()

    cache = namespace(args.namespace)

    if args.operation == "set":
        if not args.key or not args.value:
            print("Error: --key and --value required for set operation")
            return 1
        try:
            value = json.loads(args.value)
            options = {}
            if args.mode:
                options["mode"] = args.mode
            if args.ttl:
                options["ttl_seconds"] = args.ttl
            cache.set(
                args.key, value, source_file=args.source_file, options=options or None
            )
            print(f"✓ Set {args.namespace}:{args.key}")
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1

    elif args.operation == "get":
        if not args.key:
            print("Error: --key required for get operation")
            return 1
        value = cache.get(args.key)
        if value is not None:
            print(json.dumps(value, indent=2))
        else:
            print(f"✗ Key not found or invalid: {args.namespace}:{args.key}")
            return 1

    elif args.operation == "invalidate":
        if not args.key:
            print("Error: --key required for invalidate operation")
            return 1
        cache.invalidate(args.key)
        print(f"✓ Invalidated {args.namespace}:{args.key}")

    elif args.operation == "clear":
        count = cache.clear()
        print(f"✓ Cleared {count} entries from {args.namespace}")

    elif args.operation == "list":
        entries = cache.list_entries()
        if not entries:
            print(f"No entries in namespace {args.namespace}")
        else:
            print(f"{'KEY':<30} {'VALID':<6} {'SIZE':<10} {'AGE':<10} {'SOURCE'}")
            print("-" * 80)
            for e in entries:
                valid = "yes" if e["valid"] else "no"
                source = e["source_file"] or "-"
                print(
                    f"{e['key']:<30} {valid:<6} {e['size']:<10} {e['age']:<10} {source}"
                )

    elif args.operation == "stats":
        stats = cache.stats()
        print(json.dumps(stats, indent=2))

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
