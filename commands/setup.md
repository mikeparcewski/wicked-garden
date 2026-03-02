---
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write", "Skill", "Agent"]
description: "Configure wicked-garden connection and onboard the current codebase"
argument-hint: "[--reconfigure]"
---

# /wicked-garden:setup

The single entry point for getting started with wicked-garden. Auto-detects what's needed and walks through it interactively.

- **No config?** → asks about control plane (local/remote/offline), configures it, then onboards
- **Config exists but no onboarding?** → skips straight to onboarding
- **Everything done?** → reports status, offers to reconfigure

## Arguments

- `--reconfigure`: Force re-run of control plane configuration even if already set up

## Instructions

### 1. Detect Current State

Check what's already configured:

```bash
WG_CONFIG="$HOME/.something-wicked/wicked-garden/config.json"
if [ -f "$WG_CONFIG" ]; then
  cat "$WG_CONFIG"
else
  echo "NO_CONFIG"
fi
```

Determine which phases to run:

| State | Action |
|-------|--------|
| No config OR `--reconfigure` | Run Phase 1 (CP config) → Phase 2 (onboarding) |
| Config exists, `setup_complete: true`, no onboarding memories | Skip to Phase 2 (onboarding) |
| Config exists, onboarding memories exist | Report status. Ask: "Everything looks good. Want to reconfigure?" |

To check onboarding status, look for memories tagged `onboarding`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/memory.py" recall --tags onboarding --limit 1 2>/dev/null
```

### 2. Phase 1 — Control Plane Configuration

Use AskUserQuestion:

**Question**: "How would you like to connect wicked-garden?"

| Option | Description |
|--------|-------------|
| **Local (Recommended)** | Run the control plane on your machine (localhost:18889). Best for solo development. |
| **Remote** | Connect to a shared team server. Best for team collaboration. |
| **Offline** | Local file storage only. No control plane needed. Features work but data stays on this machine. |

#### 2.1 Local Setup

1. Check if CP is already running:
   ```bash
   curl -s --connect-timeout 2 http://localhost:18889/health
   ```
2. If running, write config and proceed to Phase 2

3. If NOT running, check if CP source exists in the plugin cache:
   ```bash
   ls ~/.claude/plugins/cache/wicked-control-plane/package.json 2>/dev/null
   ```

4. If source NOT found, clone it:
   ```bash
   git clone --depth 1 https://github.com/mikeparcewski/wicked-control-plane.git ~/.claude/plugins/cache/wicked-control-plane
   ```
   If clone fails (no network, no git), offer Offline mode as fallback via AskUserQuestion.

5. Install dependencies if needed:
   ```bash
   CP_PATH=~/.claude/plugins/cache/wicked-control-plane
   if [ ! -d "${CP_PATH}/node_modules" ]; then
     cd "${CP_PATH}" && pnpm install
   fi
   ```

6. Start the control plane:
   ```bash
   cd ~/.claude/plugins/cache/wicked-control-plane && PORT=18889 pnpm run dev &
   ```

7. Poll health (up to 15 seconds):
   ```bash
   for i in $(seq 1 15); do
     curl -s --connect-timeout 1 http://localhost:18889/health 2>/dev/null && break
     sleep 1
   done
   ```

8. Verify:
   ```bash
   curl -s --connect-timeout 2 http://localhost:18889/health
   ```
   If not responding, ask: "CP didn't start. Switch to offline mode or troubleshoot?"

9. Open dashboard: `open http://localhost:5173`

10. Write config:
    ```json
    {
      "endpoint": "http://localhost:18889",
      "auth_token": null,
      "api_version": "v1",
      "mode": "local-install",
      "viewer_path": "~/.claude/plugins/cache/wicked-control-plane",
      "health_check_interval_seconds": 60,
      "connect_timeout_seconds": 3,
      "request_timeout_seconds": 10,
      "setup_complete": true
    }
    ```

#### 2.2 Remote Setup

1. Ask for the endpoint URL
2. Ask if authentication is needed; if yes, ask for the auth token
3. Verify: `curl -s --connect-timeout 3 -H "Authorization: Bearer {token}" {endpoint}/health`
4. Write config with `mode: "remote"`, the endpoint, and auth token

#### 2.3 Offline Setup

1. Write config with `mode: "offline"`, `endpoint: null`
2. Show storage location:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-garden
   ```
3. Tell the user: "Run `/wicked-garden:setup` later to connect to a control plane. Queued writes will sync automatically."

#### 2.4 Confirm

```
Control plane configured!
Mode: {Local | Remote | Offline}
Endpoint: {url or "none (offline)"}
Status: {Connected | Offline}
```

### 3. Phase 2 — Codebase Onboarding

Use AskUserQuestion:

**Question**: "What kind of onboarding would you like for this codebase?"

| Option | Description |
|--------|-------------|
| **Full onboarding (Recommended)** | Index the codebase, explore architecture, trace flows, save discoveries as memories. Takes 1-2 minutes. |
| **Quick scout** | Fast reconnaissance without indexing. Gives you the lay of the land in seconds. |
| **Skip for now** | Skip onboarding. You can run `/wicked-garden:setup` later to onboard. |

#### 3.1 Full Onboarding

Invoke the onboarding engine:

```
Skill(skill="wicked-garden:smaht:onboard")
```

This handles indexing, exploration, memory storage, and validation.

#### 3.2 Quick Scout

Run a fast scout:

```
Skill(skill="wicked-garden:search:scout")
```

Then store a basic onboarding memory:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} quick-scouted on {date}. Full onboarding not yet run.\" --type procedural --tags onboarding,{project}")
```

#### 3.3 Skip

Store a skip memory so the bootstrap directive doesn't fire again:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} skipped by user on {date}. Run /wicked-garden:setup to onboard later.\" --type procedural --tags onboarding,{project}")
```

### 4. Clear Onboarding Gate

After onboarding (or skip), clear the enforcement gate so prompts are no longer blocked:

```bash
python3 -c "
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState
state = SessionState.load()
state.update(needs_onboarding=False)
print('Onboarding gate cleared.')
"
```

### 5. Done

Show a summary:

```
wicked-garden is ready!

Connection: {mode} ({endpoint or "offline"})
Onboarding: {Full | Quick scout | Skipped}

Quick start:
- /wicked-garden:help — see all domains and commands
- /wicked-garden:crew:start — start a project with crew workflow
- /wicked-garden:engineering:review — code review
- /wicked-garden:search:search "query" — search code and docs
```

## Graceful Degradation

- If CP setup fails, offer offline as fallback
- If onboarding indexing fails, fall back to quick scout
- If memory store fails, still complete (just won't suppress future directives)
- Never block the user from working — all failures offer alternatives
