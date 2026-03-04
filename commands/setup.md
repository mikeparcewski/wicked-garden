---
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write", "Skill", "Agent"]
description: "Configure wicked-garden connection and onboard the current codebase"
argument-hint: "[--reconfigure]"
---

# /wicked-garden:setup

The single entry point for getting started with wicked-garden. Always runs interactively — detects current state and asks the user what they want to do.

## Arguments

- `--reconfigure`: Force connection reconfiguration even if already set up
- `--sync-to-cp`: Sync local wicked-garden data to the control plane. Pushes crew projects and memories that exist locally but not in CP. Useful after working offline or after connecting to a new CP instance.

## Question Mode

Detect whether AskUserQuestion is available:

```bash
python3 -c "
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState
state = SessionState.load()
print('PLAIN_TEXT' if state.dangerous_mode else 'INTERACTIVE')
"
```

- **INTERACTIVE**: Use AskUserQuestion as documented below.
- **PLAIN_TEXT**: AskUserQuestion is broken (dangerous mode auto-completes with empty answers). Present all questions as **numbered plain text lists**, then **STOP and wait** for the user to reply. Do NOT proceed until you receive their answer.

## Answer Verification (CRITICAL)

**If using AskUserQuestion (INTERACTIVE mode):**

After EVERY AskUserQuestion call, you MUST:

1. **Check the response** — verify the user's selection is clearly present in the tool result
2. **Echo it back** — say "You selected **[option]**. Proceeding with [action]..." before taking any action
3. **If ambiguous or empty** — do NOT assume an answer. Instead, tell the user: "I couldn't determine your selection. Could you tell me which option you'd like?" and wait for their response.

**If using plain text (PLAIN_TEXT mode):**

1. Present options as a numbered list
2. **STOP** — do not continue until the user replies
3. Parse their reply and echo back: "You selected **[option]**. Proceeding with [action]..."

Never proceed with a default or assumed answer. Wrong actions are worse than asking twice.

## Instructions

### 1. Detect Current State

Check config and CP health:

```bash
WG_CONFIG="$HOME/.something-wicked/wicked-garden/config.json"
if [ -f "$WG_CONFIG" ]; then
  cat "$WG_CONFIG"
else
  echo "NO_CONFIG"
fi
```

```bash
curl -s --connect-timeout 2 http://localhost:18889/health 2>/dev/null || echo "NOT_CONNECTED"
```

This determines which questions to ask in Step 2.

### 2. Ask the User (batched questions)

Ask questions upfront. The method depends on question mode detected above.

#### 2a. If connected (config exists AND health check passes)

**Questions to ask:**

- **Q1 — Connection**: "You're currently connected to {endpoint}. Would you like to keep this connection or update it?"
  - Options: **Keep current connection (Recommended)** | **Update connection**

- **Q2 — Onboarding**: "Would you like to run codebase onboarding?"
  - Options: **Full onboarding (Recommended)** | **Quick scout** | **Skip for now**

**INTERACTIVE mode**: Use a single AskUserQuestion call with both questions:
- Q1: header "Connection", options with descriptions (Keep = "Stay connected to {endpoint}. No changes needed.", Update = "Reconfigure the control plane connection.")
- Q2: header "Onboarding", options with descriptions (Full = "Index the codebase, explore architecture, trace flows, save discoveries as memories. Takes 1-2 minutes.", Quick scout = "Fast reconnaissance without indexing.", Skip = "Skip onboarding. Run /wicked-garden:setup later.")

**PLAIN_TEXT mode**: Present as numbered text and STOP:

```
Two questions before we start:

**1. Connection** — You're connected to {endpoint} and it's healthy.
   a) Keep current connection (recommended)
   b) Update connection

**2. Onboarding** — Would you like to run codebase onboarding?
   a) Full onboarding — index codebase, explore architecture, save discoveries (1-2 min)
   b) Quick scout — fast recon without indexing (seconds)
   c) Skip for now
```

Then STOP and wait for the user's reply.

**After receiving answers** (either mode): Verify BOTH selections are clear. Echo back: "You selected **[Q1 answer]** and **[Q2 answer]**." If either is ambiguous, ask the user to clarify before proceeding.

- If Q1 = "Keep current connection" → skip to Step 4 (onboarding) using Q2 answer
- If Q1 = "Update connection" → proceed to Step 3 (ask connection type, then onboard using Q2 answer)

#### 2b. If NOT connected (no config OR health check fails)

**Questions to ask:**

- **Q1 — Connection type**: "How would you like to connect wicked-garden?"
  - Options: **Local (Recommended)** | **Remote**

- **Q2 — Onboarding**: Same as 2a.

**INTERACTIVE mode**: Use a single AskUserQuestion call with both questions:
- Q1: header "Connection", options with descriptions (Local = "Run the control plane on your machine (localhost:18889). Auto-starts on session start. Falls back to local JSON files when CP is unavailable.", Remote = "Connect to a shared team server.")
- Q2: Same as 2a.

**PLAIN_TEXT mode**: Present as numbered text and STOP:

```
Two questions before we start:

**1. Connection** — How would you like to connect wicked-garden?
   a) Local (recommended) — auto-start CP on localhost, local JSON fallback
   b) Remote — connect to a shared team server

**2. Onboarding** — Would you like to run codebase onboarding?
   a) Full onboarding — index codebase, explore architecture, save discoveries (1-2 min)
   b) Quick scout — fast recon without indexing (seconds)
   c) Skip for now
```

Then STOP and wait for the user's reply.

**After receiving answers** (either mode): Verify BOTH selections are clear. Echo back: "You selected **[Q1 answer]** and **[Q2 answer]**." If either is ambiguous, ask the user to clarify before proceeding.

- Proceed to Step 3 with Q1 answer, then Step 4 with Q2 answer.

### 3. Configure Connection

Execute based on the connection answer from Step 2.

#### 3.1 Local Setup (Default)

1. Check if CP is already running:
   ```bash
   curl -s --connect-timeout 2 http://localhost:18889/health
   ```
2. If running, write config and proceed to Step 4.

3. If NOT running, check if CP source exists:
   ```bash
   ls ~/.claude/plugins/cache/wicked-control-plane/package.json 2>/dev/null
   ```

4. If source NOT found, clone it:
   ```bash
   git clone --depth 1 https://github.com/mikeparcewski/wicked-control-plane.git ~/.claude/plugins/cache/wicked-control-plane
   ```
   If clone fails (no network, no git), tell the user the clone failed and write config anyway — local JSON fallback will handle storage until CP is available.

5. Install dependencies if needed:
   ```bash
   CP_PATH=~/.claude/plugins/cache/wicked-control-plane
   if [ ! -d "${CP_PATH}/node_modules" ]; then
     cd "${CP_PATH}" && pnpm install
   fi
   ```

6. Start the control plane:
   ```bash
   cd ~/.claude/plugins/cache/wicked-control-plane && PORT=18889 pnpm run dev:backend &
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
   If not responding, tell the user: "CP didn't start yet. Local JSON fallback is active — all features work. CP will auto-start on next session."

9. Write config:
    ```bash
    mkdir -p "$HOME/.something-wicked/wicked-garden"
    cat > "$HOME/.something-wicked/wicked-garden/config.json" << 'CONF'
    {
      "endpoint": "http://localhost:18889",
      "auth_token": null,
      "api_version": "v1",
      "mode": "local",
      "viewer_path": "~/.claude/plugins/cache/wicked-control-plane",
      "health_check_interval_seconds": 60,
      "connect_timeout_seconds": 3,
      "request_timeout_seconds": 10,
      "setup_complete": true
    }
    CONF
    ```

After writing config, update session state for mid-session mode switches:
    ```bash
    python3 -c "
    import sys, os
    from pathlib import Path
    sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
    from _session import SessionState
    state = SessionState.load()
    state.update(cp_available=True, fallback_mode=False, setup_complete=True)
    print('Session state updated for local mode.')
    "
    ```

#### 3.2 Remote Setup

1. Ask for the endpoint URL (via AskUserQuestion "Other" in INTERACTIVE mode, or plain text prompt in PLAIN_TEXT mode). STOP and wait for the user's reply.
2. Ask if authentication is needed; if yes, ask for the auth token (same question mode pattern).
3. Verify: `curl -s --connect-timeout 3 -H "Authorization: Bearer {token}" {endpoint}/health`
4. Write config with `mode: "remote"`, the endpoint, and auth token
5. Update session state:
   ```bash
   python3 -c "
   import sys, os
   from pathlib import Path
   sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
   from _session import SessionState
   state = SessionState.load()
   state.update(cp_available=True, fallback_mode=False, setup_complete=True)
   print('Session state updated for remote mode.')
   "
   ```

#### 3.3 Keep Current Connection

No changes needed. Proceed to Step 4.

#### 3.4 Confirm Connection

Show:

```
Connection configured!
Mode: {Local | Remote | Kept}
Endpoint: {url or "http://localhost:18889"}
Status: {Connected | Local fallback}
```

### 4. Run Onboarding

Execute based on the onboarding answer from Step 2.

#### 4.1 Full Onboarding

First, ask which directories to onboard:

**INTERACTIVE mode**: Use AskUserQuestion with header "Directories", options: "Current directory (Recommended)" = "Onboard the project root: {cwd}", "Specify directories" = "Choose specific directories to index (enter paths via Other)".

**PLAIN_TEXT mode**: Ask in plain text:

```
Which directories should be onboarded?
   a) Current directory (recommended) — {cwd}
   b) Specify directories — tell me which paths to index
```

Then STOP and wait for the user's reply.

**After receiving the answer**: Verify the selection. Echo it back.

Then invoke the onboarding engine:

```
Skill(skill="wicked-garden:smaht:onboard")
```

If the user specified custom directories, pass them as context to the onboarding skill.

This handles indexing, exploration, memory storage, and validation.

#### 4.2 Quick Scout

Ask which directories to scout (same question mode pattern as 4.1 — use AskUserQuestion or plain text depending on mode).

Run a fast scout:

```
Skill(skill="wicked-garden:search:scout")
```

Then store a basic onboarding memory:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} quick-scouted on {date}. Full onboarding not yet run.\" --type procedural --tags onboarding,{project}")
```

#### 4.3 Skip

Store a skip memory so the bootstrap directive doesn't fire again:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} skipped by user on {date}. Run /wicked-garden:setup to onboard later.\" --type procedural --tags onboarding,{project}")
```

### 5. Clear Onboarding Gate

After onboarding (or skip), clear the enforcement gate so prompts are no longer blocked:

```bash
python3 -c "
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState
state = SessionState.load()
state.update(needs_onboarding=False, setup_in_progress=False)
print('Onboarding gate cleared.')
"
```

### 6. Done

Show a summary:

```
wicked-garden is ready!

Connection: {mode} ({endpoint or "offline"})
Onboarding: {Full | Quick scout | Skipped}
Directories: {paths onboarded}

Quick start:
- /wicked-garden:help — see all domains and commands
- /wicked-garden:crew:start — start a project with crew workflow
- /wicked-garden:engineering:review — code review
- /wicked-garden:search:search "query" — search code and docs
```

### sync-to-cp Flow

When `--sync-to-cp` is passed:

1. **Confirm with user before syncing**:

**INTERACTIVE mode**: Use AskUserQuestion with header "Sync", question "This will push local wicked-garden data to the control plane. Existing CP records will not be overwritten. Proceed?", options: "Yes, sync now (Recommended)" = "Push local records to CP. Safe — uses dedup, won't overwrite.", "Cancel" = "Abort sync. No changes will be made."

**PLAIN_TEXT mode**: Ask in plain text:

```
--sync-to-cp will push local wicked-garden data to the control plane.
Existing CP records will NOT be overwritten (dedup is enforced).

   a) Yes, sync now (recommended)
   b) Cancel
```

Then STOP and wait for the user's reply.

If the user cancels, say "Sync cancelled. No changes were made." and stop.

2. **Check CP availability and sync all domains** (in dependency order):

```bash
python3 -c "
import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState
state = SessionState.load()
if not state.cp_available:
    print('CP_UNAVAILABLE')
    sys.exit(0)
from _storage import sync_all_to_cp
results = sync_all_to_cp()
print(json.dumps(results, indent=2))
"
```

This syncs all domains in dependency order:
1. `wicked-crew/projects` (first, to establish CP UUIDs)
2. `wicked-mem/memories`
3. `wicked-kanban/initiatives`
4. `wicked-kanban/tasks`
5. `wicked-jam/sessions`

3. **Report results** to the user per domain:
   - If `CP_UNAVAILABLE`: "The control plane is not reachable. Connect to CP first with `/wicked-garden:setup`."
   - If results contain an `error` key: display the error note.
   - Otherwise: display the sync counts per domain, e.g.:
     ```
     Sync results:
       wicked-crew/projects:     2 synced, 1 skipped, 0 failed
       wicked-mem/memories:      5 synced, 3 skipped, 0 failed
       wicked-kanban/initiatives: 1 synced, 0 skipped, 0 failed
       wicked-kanban/tasks:      4 synced, 2 skipped, 0 failed
       wicked-jam/sessions:      0 synced, 0 skipped, 0 failed
     ```

4. **If any records failed**, advise: "Check stderr for details. Failed records remain in local storage and will sync automatically when CP is next available."

## Graceful Degradation

- If CP setup fails, local JSON fallback handles storage automatically
- If onboarding indexing fails, fall back to quick scout
- If memory store fails, still complete (just won't suppress future directives)
- Never block the user from working — all failures offer alternatives
