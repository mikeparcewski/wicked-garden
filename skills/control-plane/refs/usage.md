# CP Usage Patterns

## StorageManager (Preferred)

All domain scripts should use StorageManager. It handles mode routing, fallback, and offline queueing automatically.

```python
from _storage import StorageManager

sm = StorageManager("memory")  # or "wicked-mem" — both work

# Read
items = sm.list("memories", project="my-project")  # list with filters
item  = sm.get("memories", "abc123")                # single record by ID

# Write
new = sm.create("memories", {"title": "...", "content": "..."})
sm.update("memories", "abc123", {"title": "new title"})
sm.delete("memories", "abc123")
```

### What StorageManager does for you

1. **CP available**: Sends request to CP, returns response
2. **CP unavailable**: Reads/writes local JSON files under `~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json`
3. **Writes when offline**: Saves locally AND enqueues for replay in `_queue.jsonl`
4. **Queue drain**: On next CP connection, replays queued writes with dedup (business key matching for creates, last-write-wins for updates)

### Domain names

StorageManager accepts either plugin names or CP domain names:

| Plugin Name | CP Domain |
|-------------|-----------|
| `wicked-mem` | `memory` |
| `wicked-kanban` | `kanban` |
| `wicked-crew` | `crew` |
| `wicked-jam` | `jam` |
| `wicked-delivery` | `delivery` |

## Direct Client (For Discovery and Queries)

Use `ControlPlaneClient` only for manifest, health checks, and SQL queries — not for CRUD (use StorageManager instead).

```python
from _control_plane import get_client

cp = get_client()

# Discovery
manifest = cp.manifest()                                      # full API catalog
detail   = cp.manifest_detail("memory", "memories", "create") # endpoint schema

# Health
ok, version = cp.check_health()

# Cross-domain query
result = cp.query("SELECT COUNT(*) as n FROM memories WHERE importance >= 7")
```

## Hook Scripts

Hooks run under a 15s timeout. Use `hook_mode=True` for tighter budgets and no retries:

```python
from _control_plane import get_client

cp = get_client(hook_mode=True)  # 2s connect, 2s request, no retry
ok, version = cp.check_health()
```

| Context | Connect Timeout | Request Timeout | Retry |
|---------|----------------|-----------------|-------|
| Hooks | 2s | 2s | No |
| Commands | 3s (configurable) | 10s (configurable) | 1 retry after 500ms |

## Responses

All CP responses use an envelope:

```json
{
  "data": { ... },
  "meta": { "total": 1, "source": "control-plane", "timestamp": "..." }
}
```

- `data` is an array for `list`/`search`, an object for `get`/`create`/`update`
- StorageManager unwraps this automatically — you get the data directly
- `meta.source` tells you whether the response came from `"control-plane"` or `"local"`

## Error Handling

All errors return `None`. Callers should treat `None` as "use fallback" or "empty result":

```python
result = sm.list("memories", project="x")
# result is always a list — [] on any error

item = sm.get("memories", "abc123")
# item is dict or None
```

No exceptions are raised. Errors are logged to stderr with `[wicked-garden]` prefix.
