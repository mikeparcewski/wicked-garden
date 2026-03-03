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
  - Options: **Standalone / local-only (Recommended)** | **Local CP (experimental)** | **Remote (experimental)** | **Offline (experimental)**

- **Q2 — Onboarding**: Same as 2a.

**INTERACTIVE mode**: Use a single AskUserQuestion call with both questions:
- Q1: header "Connection", options with descriptions (Standalone = "Local SQLite storage. No server required. All features work out of the box.", Local CP = "Run the control plane on your machine (localhost:18889). Experimental — requires Node.js + pnpm.", Remote = "Connect to a shared team server. Experimental.", Offline = "Local file storage with CP sync queue. Experimental.")
- Q2: Same as 2a.

**PLAIN_TEXT mode**: Present as numbered text and STOP:

```
Two questions before we start:

**1. Connection** — How would you like to connect wicked-garden?
   a) Standalone / local-only (recommended) — local SQLite, no server required
   b) Local CP (experimental) — run control plane on your machine (localhost:18889)
   c) Remote (experimental) — connect to a shared team server
   d) Offline (experimental) — local file storage with CP sync queue

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

#### 3.0 Standalone / Local-Only Setup

This is the default and recommended path. No external process required.

1. Write config:
   ```bash
   mkdir -p "$HOME/.something-wicked/wicked-garden"
   cat > "$HOME/.something-wicked/wicked-garden/config.json" << 'CONF'
   {
     "mode": "local-only",
     "setup_complete": true
   }
   CONF
   ```

2. Show storage location:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-garden
   ```

3. Update session state to match new mode (critical for mid-session switches):
   ```bash
   python3 -c "
   import sys, os
   from pathlib import Path
   sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
   from _session import SessionState
   state = SessionState.load()
   state.update(cp_available=False, fallback_mode=False, setup_complete=True)
   print('Session state updated for local-only mode.')
   "
   ```

4. Tell the user: "All data is stored locally in SQLite at the path above. Full search, lineage, and all domain features are available with no external process needed."

#### 3.1 Local CP Setup *(experimental)*

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
   If clone fails (no network, no git), offer Offline mode as fallback (use AskUserQuestion or plain text depending on question mode).

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
    ```bash
    mkdir -p "$HOME/.something-wicked/wicked-garden"
    cat > "$HOME/.something-wicked/wicked-garden/config.json" << 'CONF'
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
    print('Session state updated for local-install mode.')
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

#### 3.3 Offline Setup

1. Write config with `mode: "offline"`, `endpoint: null`
2. Show storage location:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-garden
   ```
3. Update session state:
   ```bash
   python3 -c "
   import sys, os
   from pathlib import Path
   sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
   from _session import SessionState
   state = SessionState.load()
   state.update(cp_available=False, fallback_mode=True, setup_complete=True)
   print('Session state updated for offline mode.')
   "
   ```
4. Tell the user: "Run `/wicked-garden:setup` later to connect to a control plane. Queued writes will sync automatically."

#### 3.4 Keep Current Connection

No changes needed. Proceed to Step 4.

#### 3.5 Confirm Connection

Show:

```
Connection configured!
Mode: {Standalone | Local CP | Remote | Offline | Kept}
Endpoint: {url or "none (local-only/offline)"}
Status: {Connected | Local SQLite | Offline}
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

1. **Check CP availability**:

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
from _storage import StorageManager
r1 = StorageManager('wicked-crew').sync_to_cp('projects')
r2 = StorageManager('wicked-mem').sync_to_cp('memories')
print(json.dumps({'crew_projects': r1, 'memories': r2}))
"
```

2. **Report results** to the user:
   - If `CP_UNAVAILABLE`: "The control plane is not reachable. Connect to CP first with `/wicked-garden:setup`."
   - Otherwise: display the sync counts — "Synced N crew projects (M skipped, K failed), P memories (Q skipped, R failed)."

3. **If any records failed**, advise: "Check stderr for details. Failed records remain in local storage and will sync automatically when CP is next available."

## Graceful Degradation

- If CP setup fails, offer offline as fallback
- If onboarding indexing fails, fall back to quick scout
- If memory store fails, still complete (just won't suppress future directives)
- Never block the user from working — all failures offer alternatives
