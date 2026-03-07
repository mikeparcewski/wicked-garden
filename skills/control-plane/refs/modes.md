# Storage Modes

## Local-First (Default)

All storage is local JSON files. No server required.

```
~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json
```

This is the only mode since v1.30.0. The control plane server was eliminated.

## Integration Discovery (Optional Enhancement)

DomainStore can route CRUD to external tools when configured:

```python
ds = DomainStore("wicked-kanban")
# If Linear MCP is configured and authenticated → routes to Linear
# Otherwise → local JSON (always works)
```

### Supported Integrations

Resolved via `_integration_resolver.py` + MCP adapter stubs in `scripts/_adapters/`:

| Integration | Adapter | Status |
|------------|---------|--------|
| Linear | `linear_adapter.py` | Stub (returns None → local fallback) |
| Jira | `jira_adapter.py` | Stub |
| Notion | `notion_adapter.py` | Stub |
| Miro | `miro_adapter.py` | Stub |

Adapters return `None` for all operations, causing DomainStore to fall back to local JSON.
When a real MCP tool is available and preferred, the adapter delegates to it.

### Preference Storage

Integration preferences are stored in wicked-mem:
```bash
/wicked-garden:mem:store "Use Linear for kanban tasks" --type preference --tags integration
```

`_integration_resolver.py` checks these preferences during DomainStore initialization.

## SqliteStore Mode

For domains that need full-text search (wicked-search, wicked-mem recall):

```python
from _sqlite_store import SqliteStore
store = SqliteStore("~/.something-wicked/wicked-garden/wicked-garden.db")
```

Records can be migrated from local JSON → SQLite via `_migrate_local.py`.

## Session State

Session-level state is tracked in `_session.py`:

| Field | Meaning |
|-------|---------|
| `setup_complete` | Onboarding wizard has run |
| `storage_mode` | Always `"local"` since v1.30.0 |
| `dangerous_mode` | AskUserQuestion auto-completes (see CLAUDE.md) |

Use `SessionState.load()` to read session state in hook scripts.
