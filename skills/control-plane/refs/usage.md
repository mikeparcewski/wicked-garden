# DomainStore Usage Patterns

## DomainStore (Standard API)

All domain scripts use DomainStore. It handles local JSON persistence and optional integration-discovery routing.

```python
from _domain_store import DomainStore

ds = DomainStore("wicked-mem")

# Read
items = ds.list("memories", project="my-project")  # list with filters
item  = ds.get("memories", "abc123")                # single record by ID

# Write
new = ds.create("memories", {"title": "...", "content": "..."})
ds.update("memories", "abc123", {"title": "new title"})
ds.delete("memories", "abc123")
```

### What DomainStore does for you

1. **Local JSON**: Reads/writes JSON files under `~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json`
2. **Integration routing**: Checks for configured MCP tools (Linear, Jira, Notion, Miro) via `_integration_resolver.py`
3. **Fallback**: If external tool fails, falls back to local JSON
4. **ID generation**: Auto-generates UUIDs for new records

### Domain names

DomainStore accepts plugin-style names:

| DomainStore Name | Used By |
|-----------------|---------|
| `wicked-mem` | Memory scripts |
| `wicked-kanban` | Kanban scripts |
| `wicked-crew` | Crew scripts |
| `wicked-jam` | Jam scripts |
| `wicked-qe` | QE registry |
| `wicked-observability` | Traces, health probes |
| `wicked-smaht` | Cheatsheets, cache |

## Hook Mode

Hooks run under tight time budgets. Use `hook_mode=True` to skip integration-discovery:

```python
ds = DomainStore("wicked-mem", hook_mode=True)  # local-only, no external calls
```

| Context | Integration Discovery | External Tools |
|---------|----------------------|----------------|
| Commands | Yes | Yes (if configured) |
| Hook scripts | No (hook_mode=True) | No |

## SqliteStore (Search + FTS)

For full-text search across domains:

```python
from _sqlite_store import SqliteStore

store = SqliteStore("/path/to/wicked-garden.db")
results = store.search("deployment", domain="wicked-mem", limit=10)
store.close()
```

SqliteStore uses FTS5 + BM25 ranking. Records can be migrated from local JSON via `_migrate_local.py`.

## Path Resolution

For ephemeral files (caches, temp state) that don't need CRUD:

```python
from _domain_store import get_local_path
cache_dir = get_local_path("wicked-smaht", "cache", "context7")
```

## Error Handling

All errors return `None` or `[]`. Callers should treat `None` as "use fallback" or "empty result":

```python
result = ds.list("memories", project="x")
# result is always a list — [] on any error

item = ds.get("memories", "abc123")
# item is dict or None
```

No exceptions are raised. Errors are logged to stderr.
