# Connection Modes

Two modes, configured via `/wicked-garden:setup` and stored in `{storage_root}/config.json`.

## local (Default)

CP runs on your machine at `localhost:18889`. The SessionStart hook auto-starts it from the `wicked-control-plane` source. When CP is unavailable, all operations fall back to local JSON files.

```json
{
  "mode": "local",
  "setup_complete": true
}
```

**Startup sequence** (bootstrap.py, 15s budget):
1. Check if CP is already healthy at configured endpoint
2. If not running, start `cd {viewer_path} && PORT=18889 pnpm run dev:backend` as detached process
3. Poll `/health` every 0.5s for up to 10s
4. If healthy: drain offline queue, mark session online, open browser to dashboard
5. If timeout: mark session as fallback mode (local JSON files)

**Data flow**: CP primary → local JSON fallback on miss → queued writes replayed on reconnect.

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

**Data flow**: Same as local — CP primary, local JSON fallback, queue replay.

## Mode Doesn't Change the API

Scripts using `StorageManager` work identically in both modes. The routing is transparent:

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
