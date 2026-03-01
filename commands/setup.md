---
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write"]
description: "Configure wicked-garden to connect to a local or remote control plane"
---

# /wicked-garden:setup

Interactive setup wizard for connecting to the wicked-control-plane backend.

## Instructions

### 1. Check Current State

Resolve the wicked-garden config path:
```bash
WG_ROOT=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-garden)
```

Read `${WG_ROOT}/../config.json` if it exists. If `setup_complete` is true, inform the user that setup is already complete and ask if they want to reconfigure.

### 2. Ask Connection Type

Use AskUserQuestion:

```
Which control plane setup do you want?
- Local (recommended): Run the control plane on your machine (localhost:18889)
- Remote: Connect to a shared team server
- Offline: Use local file storage only (no control plane)
```

### 3. Local Setup

If the user chose Local:

1. Check if the control plane is already running:
   ```bash
   curl -s --connect-timeout 2 http://localhost:18889/health 2>/dev/null
   ```

2. If not running, check if source is available:
   ```bash
   ls ~/Projects/wicked-viewer/package.json 2>/dev/null
   ```

3. If source exists, ask the user to confirm or change the path:
   ```
   Where is your wicked-viewer source? (default: ~/Projects/wicked-viewer)
   ```

4. If source exists but `node_modules/` is missing, install dependencies:
   ```bash
   cd {viewer_path} && pnpm install
   ```

5. Start the full stack (backend on PORT=18889 + Vite frontend):
   ```bash
   cd {viewer_path} && PORT=18889 pnpm run dev &
   ```

6. Wait for backend health:
   ```bash
   for i in $(seq 1 10); do
     curl -s --connect-timeout 1 http://localhost:18889/health 2>/dev/null && break
     sleep 1
   done
   ```

7. Open the dashboard:
   ```bash
   open http://localhost:5173
   ```

8. Verify connection:
   ```bash
   curl -s --connect-timeout 3 http://localhost:18889/health
   ```

9. Write config:
   ```json
   {
     "endpoint": "http://localhost:18889",
     "auth_token": null,
     "api_version": "v1",
     "mode": "local-install",
     "viewer_path": "~/Projects/wicked-viewer",
     "health_check_interval_seconds": 60,
     "connect_timeout_seconds": 3,
     "request_timeout_seconds": 10,
     "setup_complete": true
   }
   ```

   Use the actual `viewer_path` the user confirmed. Store with `~` prefix (not expanded).

### 4. Remote Setup

If the user chose Remote:

1. Ask for the endpoint URL using AskUserQuestion
2. Ask if authentication is needed; if yes, ask for the auth token
3. Verify connection:
   ```bash
   curl -s --connect-timeout 3 -H "Authorization: Bearer {token}" {endpoint}/health
   ```
4. Write config with the remote endpoint, auth token, and `mode: "remote"`:
   ```json
   {
     "endpoint": "{user-provided-endpoint}",
     "auth_token": "{user-provided-token-or-null}",
     "api_version": "v1",
     "mode": "remote",
     "health_check_interval_seconds": 60,
     "connect_timeout_seconds": 3,
     "request_timeout_seconds": 10,
     "setup_complete": true
   }
   ```

### 5. Offline Setup

If the user chose Offline:

Write config:
```json
{
  "endpoint": null,
  "auth_token": null,
  "api_version": "v1",
  "mode": "offline",
  "health_check_interval_seconds": 60,
  "connect_timeout_seconds": 3,
  "request_timeout_seconds": 10,
  "setup_complete": true
}
```

Show the user where their data will be stored:

```markdown
### Offline Storage

All data is stored locally (paths resolved by StorageManager):
- **Storage root**: Resolved by `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-garden`
- **Sync queue**: `{storage_root}/_queue.jsonl` (operations pending sync)
- **Failed replays**: `{storage_root}/_queue_failed.jsonl`

Data is organized by domain (crew, kanban, mem, etc.) under the storage root.
When you connect to a control plane later, queued operations will sync automatically.
```

List any existing subdirectories under the local storage path.

Re-run `/wicked-garden:setup` to connect later.

### 6. Verify and Report

After writing config, verify by loading it back and report:

```markdown
## Setup Complete

**Mode**: {Local | Remote | Offline}
**Endpoint**: {url or "none (offline)"}
**Status**: Connected / Offline

### Available Domains
- Search: {connected/offline}
- Memory: {connected/offline}
- Kanban: {connected/offline}
- Crew: {connected/offline}
- Jam: {connected/offline}
- Delivery: {connected/offline}
- Agents: {connected/offline}

Run `/wicked-garden:setup` again to reconfigure at any time.
```

### 7. Auto-trigger Onboarding

After setup is confirmed, check if the current project has been onboarded:

```bash
python3 -c "
import sqlite3; from pathlib import Path
db = Path.home() / '.something-wicked' / 'wicked-search' / 'unified_search.db'
print('indexed' if db.exists() else 'not-indexed')
"
```

If not indexed, immediately run:

```
/wicked-garden:smaht:onboard
```

Do not ask for confirmation — onboarding is the expected next step after setup.

Note: On subsequent session starts, the bootstrap hook will auto-start the control plane (local mode), open the browser, and trigger onboarding if needed — no manual steps required.
