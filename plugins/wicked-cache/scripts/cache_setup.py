#!/usr/bin/env python3
"""
Initialize wicked-cache cache directories and configuration.

Usage: python cache_setup.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path to import cache module
sys.path.insert(0, str(Path(__file__).parent))
from cache import _get_base_path


def main():
    """Initialize cache infrastructure."""
    base_path = _get_base_path()

    # Check if already initialized
    config_path = base_path / "config.md"
    stats_path = base_path / "stats.json"
    namespaces_path = base_path / "namespaces"

    if config_path.exists() and stats_path.exists():
        print("⚠ Cache already initialized.")
        print(f"Cache location: {base_path}")
        print("\nTo reset, delete the directory and run setup again.")
        return 0

    # Create directory structure
    base_path.mkdir(parents=True, exist_ok=True)
    namespaces_path.mkdir(exist_ok=True)

    # Create config file
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    config_content = f"""---
version: 1.0.0
created: {timestamp}
max_namespace_size_mb: 100
default_ttl_hours: 24
---

# wicked-cache Configuration

This is the unified cache for Wicked Garden plugins.

## Storage Layout

Each plugin gets its own namespace under `namespaces/<plugin-name>/`.

## Limits

- Max namespace size: 100 MB (soft limit, warning only)
- Default TTL: 24 hours (if not specified)

## Namespaces

Namespaces are created automatically when first used.
"""

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_content)

    # Create stats file
    stats_content = {"initialized": timestamp, "version": "1.0.0", "namespaces": {}}

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats_content, f, indent=2)

    # Success message
    print("✓ wicked-cache cache initialized\n")
    print(f"Cache location: {base_path}")
    print(f"Configuration: {config_path}")
    print("\nReady for use by all plugins.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
