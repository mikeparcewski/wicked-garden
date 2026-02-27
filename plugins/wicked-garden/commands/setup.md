---
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write"]
description: "Configure wicked-garden to connect to a local or remote control plane"
---

# /wicked-garden:setup

Interactive setup wizard for connecting to the wicked-control-plane backend.

## Instructions

### 1. Check Current State

Read `~/.something-wicked/wicked-garden/config.json` if it exists. If `setup_complete` is true, inform the user that setup is already complete and ask if they want to reconfigure.

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

2. If not running, check if it's installed:
   ```bash
   which wicked-control-plane 2>/dev/null || npm list -g wicked-control-plane 2>/dev/null
   ```

3. If not installed, offer to install:
   ```bash
   # Check if the source is available locally
   ls ~/Projects/wicked-viewer/package.json 2>/dev/null
   ```

   If source exists: `cd ~/Projects/wicked-viewer && pnpm install && pnpm run dev`

   If not: Guide the user to clone and set up

4. Verify connection:
   ```bash
   curl -s --connect-timeout 3 http://localhost:18889/health
   ```

5. Write config:
   ```json
   {
     "endpoint": "http://localhost:18889",
     "auth_token": null,
     "api_version": "v1",
     "health_check_interval_seconds": 60,
     "connect_timeout_seconds": 3,
     "request_timeout_seconds": 10,
     "setup_complete": true
   }
   ```

### 4. Remote Setup

If the user chose Remote:

1. Ask for the endpoint URL using AskUserQuestion
2. Ask if authentication is needed; if yes, ask for the auth token
3. Verify connection:
   ```bash
   curl -s --connect-timeout 3 -H "Authorization: Bearer {token}" {endpoint}/health
   ```
4. Write config with the remote endpoint and auth token

### 5. Offline Setup

If the user chose Offline:

Write config:
```json
{
  "endpoint": null,
  "auth_token": null,
  "api_version": "v1",
  "setup_complete": true
}
```

Inform the user that all data will be stored locally under `~/.something-wicked/wicked-garden/local/`. They can re-run `/wicked-garden:setup` to connect later.

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
