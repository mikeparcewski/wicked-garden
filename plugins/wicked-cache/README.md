# wicked-cache

Make expensive operations instant. Unified caching with file-based, TTL, and manual invalidation - from 500ms to <1ms.

## Quick Start

```bash
# Install
claude plugin install wicked-cache@wicked-garden

# Initialize cache directories
/wicked-cache:setup

# View cache statistics
/wicked-cache:cache stats

# Clear a namespace
/wicked-cache:cache clear my-plugin
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-cache:setup` | Initialize cache directories | `/wicked-cache:setup` |
| `/wicked-cache:cache list` | Show all cached data | `/wicked-cache:cache list` |
| `/wicked-cache:cache stats` | Hit/miss statistics | `/wicked-cache:cache stats wicked-data` |
| `/wicked-cache:cache clear` | Clear a namespace or everything | `/wicked-cache:cache clear --all` |

## Invalidation Modes

| Mode | Trigger | Best For |
|------|---------|----------|
| **File** | Source file changes (mtime/size) | Schema caching, file analysis |
| **TTL** | Time expires | API responses, temporary data |
| **Manual** | Explicit `invalidate()` call | Configuration, persistent data |

## Python API

```python
from cache import namespace

cache = namespace("my-plugin")

# File-based (invalidates when file changes)
cache.set("schema:data.csv", schema, source_file="./data.csv")

# TTL-based (expires after 5 minutes)
cache.set("api-response", data, options={"mode": "ttl", "ttl_seconds": 300})

# Manual (persistent until cleared)
cache.set("config", settings)

# Retrieve
data = cache.get("key")  # None on miss

# Stats
stats = cache.stats()  # hit_count, miss_count, entry_count
```

## Storage

```
~/.something-wicked/wicked-cache/
├── stats.json
└── namespaces/
    ├── wicked-data/
    ├── wicked-search/
    └── wicked-mem/
```

Every plugin gets its own namespace with independent stats and lifecycle.

## Who Uses This

Other wicked plugins use wicked-cache to speed up repeated operations:
- **wicked-data**: Cached schema parsing
- **wicked-search**: Cached search results
- **wicked-mem**: Cached memory lookups
- **wicked-smaht**: Cached context assembly

Install wicked-cache and these plugins automatically get faster.

## License

MIT
