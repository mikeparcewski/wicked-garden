"""
Wicked Cache - Unified Caching Infrastructure

Standalone caching for Wicked Garden marketplace plugins.
Provides namespace isolation, TTL support, and file-based invalidation.

Storage Structure:
    ~/.something-wicked/wicked-cache/
    ├── namespaces/
    │   ├── {namespace}/
    │   │   ├── index.json      # Metadata: key -> CacheEntry
    │   │   └── data/
    │   │       ├── {key}.json  # Actual cached value
    │   │       └── ...
    └── stats.json

API Usage:
    from cache import namespace

    cache = namespace("my-plugin")
    cache.set("key", value, source_file="./data.csv")
    result = cache.get("key")  # Returns None if source file changed
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


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
    """Scoped cache client for a specific namespace."""

    def __init__(self, namespace: str, base_path: Path):
        self.namespace = namespace
        self.path = base_path / "namespaces" / namespace
        self.path.mkdir(parents=True, exist_ok=True)
        self._data_path = self.path / "data"
        self._data_path.mkdir(parents=True, exist_ok=True)
        self._index_path = self.path / "index.json"
        self._stats_path = base_path / "stats.json"
        self._base_path = base_path
        self._index: Dict[str, dict] = {}
        self._load_index()

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if valid, None if miss or invalid.

        Validation depends on mode:
        - FILE: Check source file mtime and size
        - TTL: Check if TTL has expired
        - MANUAL: Always valid (until explicitly invalidated)
        """
        entry = self._get_entry(key)
        if entry is None:
            self._record_miss()
            return None

        if not self._is_valid(entry):
            self._record_miss()
            return None

        # Load the actual value
        value = self._load_value(key)
        if value is None:
            self._record_miss()
            return None

        self._record_hit()
        return value

    def set(
        self,
        key: str,
        value: Any,
        source_file: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> str:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            source_file: Path to source file for file-based invalidation
            options: Dict with optional keys:
                - mode: "file" (default), "ttl", or "manual"
                - ttl_seconds: TTL in seconds (required for ttl mode)

        Returns:
            The cache key
        """
        opts = options or {}
        mode_str = opts.get("mode", "file" if source_file else "manual")
        mode = InvalidationMode(mode_str)

        # Get source file metadata if provided
        source_mtime = None
        source_size = None
        if source_file:
            source_mtime = self._get_mtime(source_file)
            source_size = self._get_size(source_file)

        entry = CacheEntry(
            key=key,
            source_file=source_file,
            source_mtime=source_mtime,
            source_size=source_size,
            cached_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            ttl_seconds=opts.get("ttl_seconds"),
            mode=mode.value,
        )

        # Save the value
        self._save_value(key, value)

        # Save the entry metadata
        self._save_entry(entry)

        self._record_set()
        return key

    def invalidate(self, key: str) -> bool:
        """Explicitly invalidate a cache entry."""
        return self._remove_entry(key)

    def clear(self) -> int:
        """Clear all entries. Returns count cleared."""
        count = len(self._index)

        # Remove all data files
        for key in list(self._index.keys()):
            self._remove_entry(key)

        self._index = {}
        self._save_index()
        return count

    def list_entries(self) -> list:
        """List all cache entries with metadata."""
        entries = []
        for key, entry_dict in self._index.items():
            entry = self._dict_to_entry(entry_dict)
            valid = self._is_valid(entry)

            # Get data file size
            data_file = self._data_path / f"{key}.json"
            size = data_file.stat().st_size if data_file.exists() else 0

            # Calculate age
            cached_at = datetime.fromisoformat(entry.cached_at.replace("Z", "+00:00"))
            age_seconds = (datetime.now(cached_at.tzinfo) - cached_at).total_seconds()

            entries.append(
                {
                    "key": key,
                    "valid": valid,
                    "size": size,
                    "age": int(age_seconds),
                    "source_file": entry.source_file,
                }
            )
        return entries

    def stats(self) -> dict:
        """Get namespace statistics."""
        global_stats = self._load_global_stats()
        ns_stats = global_stats.get("namespaces", {}).get(
            self.namespace, {"hits": 0, "misses": 0, "sets": 0}
        )

        # Calculate additional stats
        entries = self.list_entries()
        total_size = sum(e["size"] for e in entries)
        oldest_age = max((e["age"] for e in entries), default=0)

        return {
            "entry_count": len(entries),
            "total_size": total_size,
            "hit_count": ns_stats.get("hits", 0),
            "miss_count": ns_stats.get("misses", 0),
            "oldest_entry_age": oldest_age,
        }

    # Private methods

    def _load_index(self):
        """Load index from disk."""
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f)
        else:
            self._index = {}

    def _save_index(self):
        """Save index to disk."""
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get entry metadata from index."""
        if key not in self._index:
            return None
        return self._dict_to_entry(self._index[key])

    def _dict_to_entry(self, d: dict) -> CacheEntry:
        """Convert dict to CacheEntry."""
        return CacheEntry(
            key=d["key"],
            source_file=d.get("source_file"),
            source_mtime=d.get("source_mtime"),
            source_size=d.get("source_size"),
            cached_at=d["cached_at"],
            ttl_seconds=d.get("ttl_seconds"),
            mode=d.get("mode", "manual"),
        )

    def _save_entry(self, entry: CacheEntry):
        """Save entry metadata to index."""
        self._index[entry.key] = asdict(entry)
        self._save_index()

    def _remove_entry(self, key: str) -> bool:
        """Remove entry from index and delete data file."""
        if key not in self._index:
            return False

        # Remove data file
        data_file = self._data_path / f"{key}.json"
        if data_file.exists():
            data_file.unlink()

        # Remove from index
        del self._index[key]
        self._save_index()
        return True

    def _load_value(self, key: str) -> Optional[Any]:
        """Load cached value from data file."""
        data_file = self._data_path / f"{key}.json"
        if not data_file.exists():
            return None
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_value(self, key: str, value: Any):
        """Save value to data file."""
        data_file = self._data_path / f"{key}.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2)

    def _is_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid."""
        mode = InvalidationMode(entry.mode)

        if mode == InvalidationMode.MANUAL:
            # Manual mode: always valid
            return True

        elif mode == InvalidationMode.TTL:
            # TTL mode: check expiration
            if entry.ttl_seconds is None:
                return True
            cached_at = datetime.fromisoformat(entry.cached_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(cached_at.tzinfo) - cached_at).total_seconds()
            return elapsed < entry.ttl_seconds

        elif mode == InvalidationMode.FILE:
            # File mode: check source file mtime and size
            if entry.source_file is None:
                return True

            current_mtime = self._get_mtime(entry.source_file)
            current_size = self._get_size(entry.source_file)

            if current_mtime is None or current_size is None:
                # Source file doesn't exist
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

    def _load_global_stats(self) -> dict:
        """Load global stats file."""
        if self._stats_path.exists():
            with open(self._stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"namespaces": {}}

    def _save_global_stats(self, stats: dict):
        """Save global stats file."""
        with open(self._stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

    def _record_hit(self):
        """Record a cache hit."""
        stats = self._load_global_stats()
        if "namespaces" not in stats:
            stats["namespaces"] = {}
        if self.namespace not in stats["namespaces"]:
            stats["namespaces"][self.namespace] = {"hits": 0, "misses": 0, "sets": 0}
        stats["namespaces"][self.namespace]["hits"] += 1
        self._save_global_stats(stats)

    def _record_miss(self):
        """Record a cache miss."""
        stats = self._load_global_stats()
        if "namespaces" not in stats:
            stats["namespaces"] = {}
        if self.namespace not in stats["namespaces"]:
            stats["namespaces"][self.namespace] = {"hits": 0, "misses": 0, "sets": 0}
        stats["namespaces"][self.namespace]["misses"] += 1
        self._save_global_stats(stats)

    def _record_set(self):
        """Record a cache set."""
        stats = self._load_global_stats()
        if "namespaces" not in stats:
            stats["namespaces"] = {}
        if self.namespace not in stats["namespaces"]:
            stats["namespaces"][self.namespace] = {"hits": 0, "misses": 0, "sets": 0}
        stats["namespaces"][self.namespace]["sets"] += 1
        self._save_global_stats(stats)


# Module-level cache base path
_BASE_PATH: Optional[Path] = None


def _get_base_path() -> Path:
    """Get the base path for cache storage."""
    global _BASE_PATH
    if _BASE_PATH is None:
        # Store cache in ~/.something-wicked/wicked-cache/ (standardized naming)
        _BASE_PATH = Path.home() / ".something-wicked" / "wicked-cache"
        _BASE_PATH.mkdir(parents=True, exist_ok=True)
    return _BASE_PATH


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
    base_path = _get_base_path()
    return NamespacedCache(name, base_path)


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
