---
name: caching
description: |
  Unified caching infrastructure for Wicked Garden plugins with namespace isolation,
  TTL support, and file-based invalidation. Use when plugins need to cache data between
  sessions, store analysis results, or implement cache invalidation strategies.
triggers:
  - "cache data"
  - "store between sessions"
  - "cache invalidation"
  - "TTL expiration"
  - "wicked-cache"
  - "namespace cache"
---

# Caching Infrastructure

Unified cache API for Wicked Garden plugins.

## Quick Start

```python
import sys
from pathlib import Path

# Add wicked-cache to path
cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

# Get a namespaced cache client
cache = namespace("my-plugin")

# Store and retrieve
cache.set("key", {"data": "value"})
data = cache.get("key")  # Returns None on miss
```

## Core API

| Method | Purpose |
|--------|---------|
| `namespace(name)` | Get scoped cache client |
| `cache.set(key, value, ...)` | Store value |
| `cache.get(key)` | Retrieve (None on miss) |
| `cache.invalidate(key)` | Explicitly invalidate |
| `cache.clear()` | Clear namespace |
| `cache.stats()` | Get statistics |

## Invalidation Modes

| Mode | Use Case | Example |
|------|----------|---------|
| **File** | Schema/analysis caching | `cache.set(key, val, source_file="./data.csv")` |
| **TTL** | API responses | `cache.set(key, val, options={"mode": "ttl", "ttl_seconds": 300})` |
| **Manual** | Configuration | `cache.set(key, val, options={"mode": "manual"})` |

## Workflow Guides

For specific use cases, read the appropriate guide from `references/`:

| Task | Guide |
|------|-------|
| Caching file schemas/analysis | `references/schema-caching.md` |
| Caching API responses | `references/api-response-caching.md` |
| Choosing invalidation strategy | `references/invalidation-strategies.md` |

## Commands

```bash
/wicked-cache:setup              # Initialize
/wicked-cache:cache list         # List keys
/wicked-cache:cache stats        # Statistics
/wicked-cache:cache clear <ns>   # Clear namespace
```

## Security

- Namespace validation prevents path traversal
- Key validation: alphanumeric + hyphens + colons
- Don't cache sensitive/PII data
