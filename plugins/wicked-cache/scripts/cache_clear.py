#!/usr/bin/env python3
"""
Clear cache entries for a namespace or all namespaces.

Usage:
    python cache_clear.py <namespace>       # Clear specific namespace
    python cache_clear.py --all             # Clear all namespaces
"""

import sys
from pathlib import Path

# Add scripts dir to path to import cache module
sys.path.insert(0, str(Path(__file__).parent))
from cache import _get_base_path, namespace


def main():
    """Clear cache entries."""
    if len(sys.argv) < 2:
        print("Error: Missing argument.")
        print("Usage: python cache_clear.py <namespace>")
        print("       python cache_clear.py --all")
        return 1

    base_path = _get_base_path()
    namespaces_path = base_path / "namespaces"

    if not namespaces_path.exists():
        print("⚠ Cache not initialized. Run `/wicked-cache:setup` first.")
        return 1

    arg = sys.argv[1]

    if arg == "--all":
        # Clear all namespaces
        namespaces = [d.name for d in namespaces_path.iterdir() if d.is_dir()]

        if not namespaces:
            print("No namespaces to clear.")
            return 0

        total_cleared = 0
        for ns_name in namespaces:
            cache = namespace(ns_name)
            count = cache.clear()
            total_cleared += count
            print(f"✓ Cleared {count} entries from {ns_name}")

        print(f"\nTotal cleared: {total_cleared} entries from {len(namespaces)} namespaces")

    else:
        # Clear specific namespace
        ns_name = arg

        # Check if namespace exists
        ns_path = namespaces_path / ns_name
        if not ns_path.exists():
            available = [d.name for d in namespaces_path.iterdir() if d.is_dir()]
            print(f"⚠ Namespace '{ns_name}' not found.")
            if available:
                print(f"Available: {', '.join(sorted(available))}")
            return 1

        cache = namespace(ns_name)
        count = cache.clear()
        print(f"✓ Cleared {count} entries from {ns_name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
