#!/usr/bin/env python3
"""
Show cache statistics.

Usage:
    python cache_stats.py              # Global stats
    python cache_stats.py <namespace>  # Namespace-specific stats
"""

import sys
from pathlib import Path

# Add scripts dir to path to import cache module
sys.path.insert(0, str(Path(__file__).parent))
from cache import _get_base_path, namespace


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_time(seconds: int) -> str:
    """Format seconds to human-readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"


def calculate_hit_rate(hits: int, misses: int) -> str:
    """Calculate hit rate percentage."""
    total = hits + misses
    if total == 0:
        return "N/A"
    return f"{(hits / total * 100):.1f}%"


def main():
    """Show cache statistics."""
    base_path = _get_base_path()
    namespaces_path = base_path / "namespaces"

    if not namespaces_path.exists():
        print("⚠ Cache not initialized. Run `/wicked-cache:setup` first.")
        return 1

    # Check if specific namespace requested
    if len(sys.argv) > 1:
        ns_name = sys.argv[1]

        # Check if namespace exists
        ns_path = namespaces_path / ns_name
        if not ns_path.exists():
            available = [d.name for d in namespaces_path.iterdir() if d.is_dir()]
            print(f"⚠ Namespace '{ns_name}' not found.")
            if available:
                print(f"Available: {', '.join(sorted(available))}")
            return 1

        # Namespace-specific stats
        cache = namespace(ns_name)
        stats = cache.stats()

        print(f"## Cache Statistics: {ns_name}\n")
        print("| Metric | Value |")
        print("|--------|-------|")
        print(f"| Entry count | {stats['entry_count']} |")
        print(f"| Total size | {format_size(stats['total_size'])} |")
        print(f"| Cache hits | {stats['hit_count']} |")
        print(f"| Cache misses | {stats['miss_count']} |")
        print(f"| Hit rate | {calculate_hit_rate(stats['hit_count'], stats['miss_count'])} |")

        if stats['oldest_entry_age'] > 0:
            print(f"| Oldest entry | {format_time(stats['oldest_entry_age'])} |")

    else:
        # Global stats
        namespaces = [d.name for d in namespaces_path.iterdir() if d.is_dir()]

        if not namespaces:
            print("No cached data. Namespaces will be created automatically when plugins use the cache.")
            return 0

        print("## Cache Statistics\n")

        total_entries = 0
        total_size = 0
        total_hits = 0
        total_misses = 0

        print("### By Namespace\n")
        print("| Namespace | Entries | Size | Hits | Misses | Hit Rate |")
        print("|-----------|---------|------|------|--------|----------|")

        for ns_name in sorted(namespaces):
            cache = namespace(ns_name)
            stats = cache.stats()

            entries = stats['entry_count']
            size = stats['total_size']
            hits = stats['hit_count']
            misses = stats['miss_count']
            hit_rate = calculate_hit_rate(hits, misses)

            print(f"| {ns_name} | {entries} | {format_size(size)} | {hits} | {misses} | {hit_rate} |")

            total_entries += entries
            total_size += size
            total_hits += hits
            total_misses += misses

        print("\n### Overall\n")
        print("| Metric | Value |")
        print("|--------|-------|")
        print(f"| Total namespaces | {len(namespaces)} |")
        print(f"| Total entries | {total_entries} |")
        print(f"| Total size | {format_size(total_size)} |")
        print(f"| Total hits | {total_hits} |")
        print(f"| Total misses | {total_misses} |")
        print(f"| Overall hit rate | {calculate_hit_rate(total_hits, total_misses)} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())
