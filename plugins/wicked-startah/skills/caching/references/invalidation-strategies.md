# Cache Invalidation Strategies

Choose the right invalidation mode for your use case.

## Three Modes

| Mode | Trigger | Best For |
|------|---------|----------|
| **File** | Source file mtime/size changes | Schema caching, file analysis |
| **TTL** | Time expires | API responses, temporary data |
| **Manual** | Explicit `invalidate()` call | Configuration, persistent data |

## File-Based Invalidation

Automatically invalidates when source file changes.

```python
# Store with file tracking
cache.set("schema:data.csv", schema, source_file="./data.csv")

# Later: get() returns None if data.csv was modified
schema = cache.get("schema:data.csv")
```

**Use when:**
- Data is derived from a specific file
- You want automatic freshness
- File changes are the invalidation trigger

## TTL-Based Invalidation

Expires after specified time.

```python
cache.set("api:response", data, options={
    "mode": "ttl",
    "ttl_seconds": 300  # 5 minutes
})
```

**Use when:**
- Data is acceptable to be slightly stale
- No clear invalidation trigger
- Reducing external API load

## Manual Invalidation

Never auto-invalidates; you control it.

```python
# Store
cache.set("config", settings, options={"mode": "manual"})

# Later: explicitly invalidate when needed
cache.invalidate("config")
```

**Use when:**
- You know exactly when data becomes stale
- Configuration or settings
- Data that rarely changes

## Combining Strategies

Different keys can use different strategies:

```python
cache = namespace("my-plugin")

# File-based for schemas
cache.set("schema:data.csv", schema, source_file="./data.csv")

# TTL for API calls
cache.set("api:users", users, options={"mode": "ttl", "ttl_seconds": 300})

# Manual for config
cache.set("settings", config, options={"mode": "manual"})
```

## Decision Tree

```
Is data derived from a local file?
├── Yes → Use file-based (source_file=)
└── No
    ├── Is slight staleness acceptable?
    │   ├── Yes → Use TTL
    │   └── No → Use manual + explicit invalidation
    └── Is data configuration/settings?
        └── Yes → Use manual
```
