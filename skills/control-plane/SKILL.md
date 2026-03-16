---
name: control-plane
description: |
  Storage layer guide — DomainStore (local JSON + integration-discovery) and SqliteStore (direct SQLite).
  wicked-garden uses local-first storage. No external server required.

  Use when: "storage internals", "DomainStore API", "persistence issue", "integration routing",
  "local storage", "SqliteStore", "FTS5 search", "debugging persistence"
user-invocable: false
---

# Storage Layer

> **Note**: The control plane (Fastify + SQLite server) was eliminated in v1.30.0.
> Storage is now **local-first**: DomainStore writes local JSON files, with optional
> integration-discovery routing to external tools (Linear MCP, Jira MCP, etc.).

## The Pattern: DomainStore for Everything

```python
from _domain_store import DomainStore

ds = DomainStore("wicked-mem")
items = ds.list("memories", project="my-project")
item  = ds.get("memories", "abc123")
new   = ds.create("memories", {"title": "...", "content": "..."})
ds.update("memories", "abc123", {"title": "new title"})
ds.delete("memories", "abc123")
```

### Storage Paths

```
~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json
```

### Integration Discovery

DomainStore checks for configured MCP tools (Linear, Jira, Notion, Miro) via
`_integration_resolver.py`. When an external tool is authenticated and preferred,
DomainStore routes CRUD through the MCP adapter. Otherwise, local JSON is canonical.

```python
# Hook mode skips discovery (fast, no external calls)
ds = DomainStore("wicked-mem", hook_mode=True)
```

## SqliteStore (Search + FTS)

For full-text search and indexed queries, SqliteStore provides FTS5 + BM25:

```python
from _sqlite_store import SqliteStore

store = SqliteStore("/path/to/wicked-garden.db")
results = store.search("deployment", domain="wicked-mem", limit=10)
store.close()
```

## Domain Mapping

| Domain | DomainStore Name | Sources |
|--------|-----------------|---------|
| Memory | `wicked-mem` | memories |
| Kanban | `wicked-kanban` | tasks, projects, initiatives, comments |
| Crew | `wicked-crew` | projects |
| Jam | `wicked-jam` | sessions, transcripts |
| QE | `wicked-qe` | registry |
| Observability | `wicked-observability` | traces, health |
| Smaht | `wicked-smaht` | cheatsheets, cache |

## Path Resolution

For ephemeral files (caches, temp state), use `get_local_path`:

```python
from _domain_store import get_local_path
cache_dir = get_local_path("wicked-smaht", "cache", "context7")
```

Or from commands:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" <domain>
```

## Further Reading

- [refs/usage.md](refs/usage.md) — DomainStore API details, hook_mode, integration routing
- [refs/modes.md](refs/modes.md) — Local storage, SqliteStore, migration from CP
