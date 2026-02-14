#!/usr/bin/env python3
"""
List cache contents across all namespaces.

Usage: python cache_list.py
"""

import sys
from pathlib import Path

# Add scripts dir to path to import cache module
sys.path.insert(0, str(Path(__file__).parent))
from cache import _get_base_path


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
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def main():
    """List all cache entries across namespaces."""
    base_path = _get_base_path()
    namespaces_path = base_path / "namespaces"

    if not namespaces_path.exists():
        print("⚠ Cache not initialized. Run `/wicked-cache:setup` first.")
        return 1

    # Find all namespaces
    namespaces = [d.name for d in namespaces_path.iterdir() if d.is_dir()]

    if not namespaces:
        print("No cached data. Namespaces will be created automatically when plugins use the cache.")
        return 0

    print("## Cache Contents\n")

    total_entries = 0
    total_size = 0

    for ns_name in sorted(namespaces):
        from cache import namespace
        cache = namespace(ns_name)
        entries = cache.list_entries()

        if not entries:
            continue

        print(f"### Namespace: {ns_name}")
        print("| Key | Size | Valid | Age | Source |")
        print("|-----|------|-------|-----|--------|")

        for entry in sorted(entries, key=lambda e: e["key"]):
            valid_mark = "✓" if entry["valid"] else "✗"
            size_str = format_size(entry["size"])
            age_str = format_time(entry["age"])
            source = entry.get("source_file", "-")
            if source and len(source) > 40:
                source = "..." + source[-37:]

            print(f"| {entry['key']} | {size_str} | {valid_mark} | {age_str} | {source} |")

            total_entries += 1
            total_size += entry["size"]

        print()

    # Summary
    print("### Summary")
    print(f"- Total entries: {total_entries}")
    print(f"- Total size: {format_size(total_size)}")
    print(f"- Namespaces: {len(namespaces)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
