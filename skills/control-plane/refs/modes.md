# Connection Modes

Three modes, configured via `/wicked-garden:setup` and stored in `~/.something-wicked/wicked-garden/config.json`.

## local-install (Default)

CP runs on your machine at `localhost:18889`. The SessionStart hook auto-starts it from `wicked-viewer` source.

```json
{
  "endpoint": "http://localhost:18889",
  "mode": "local-install",
  "viewer_path": "~/Projects/wicked-viewer"
}
```

**Startup sequence** (bootstrap.py, 15s budget):
1. Check if CP is already healthy at configured endpoint
2. If not running, start `cd {viewer_path} && PORT=18889 pnpm run dev` as detached process
3. Poll `/health` every 0.5s for up to 6s
4. If healthy: drain offline queue, mark session online, open browser to dashboard
5. If timeout: mark session as fallback mode (local files only)

**Data flow**: CP primary → local fallback on miss → queued writes replayed on reconnect.

## remote

CP on a shared team server. Requires endpoint URL and optional auth token.

```json
{
  "endpoint": "https://team.example.com",
  "auth_token": "your-token",
  "mode": "remote"
}
```

**Startup sequence**:
1. Health check against configured endpoint (3s timeout)
2. If healthy: drain offline queue, mark session online
3. If unreachable: mark session as fallback mode

**Auth**: Bearer token sent in `Authorization` header. Never logged or echoed in error output.

**Data flow**: Same as local-install — CP primary, local fallback, queue replay.

## offline

No CP at all. Everything stays on disk.

```json
{
  "endpoint": null,
  "mode": "offline"
}
```

**Startup sequence**:
1. Skip all CP checks
2. Report local storage location

**Data flow**: All reads from local JSON files. All writes saved locally AND enqueued in `_queue.jsonl`. When user runs `/wicked-garden:setup` to connect later, queued writes replay automatically.

**Storage location**:
```
~/.something-wicked/wicked-garden/local/
├── _queue.jsonl              # Writes pending CP sync
├── _queue_failed.jsonl       # Failed replay attempts
├── wicked-mem/memories/      # Memory records
├── wicked-kanban/tasks/      # Kanban tasks
├── wicked-crew/projects/     # Crew projects
└── ...                       # Other domains
```

## Mode Doesn't Change the API

Scripts using `StorageManager` work identically in all three modes. The routing is transparent:

```python
sm = StorageManager("memory")
sm.list("memories")  # same call regardless of mode
```

The only difference is where data lives and how fast it responds.

## Session State

Mode decisions are tracked in session state (`_session.py`) so hooks don't re-check on every invocation:

| Field | Meaning |
|-------|---------|
| `cp_available` | Health check passed at session start |
| `cp_version` | Reported CP version string |
| `fallback_mode` | CP was unreachable, using local files |
| `setup_complete` | config.json has `setup_complete: true` |

Use `SessionState.load().is_online()` to check if CP is available in the current session.

## Reconnection

If the session starts in fallback mode, `prompt_submit.py` re-checks CP health periodically (default: every 60s, configurable via `health_check_interval_seconds`). On successful reconnect:

1. Queue is drained (offline writes replayed to CP)
2. Session state updated to `cp_available: true, fallback_mode: false`
3. Subsequent StorageManager calls go to CP
