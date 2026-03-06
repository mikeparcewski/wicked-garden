---
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write", "Skill", "Agent"]
description: "Configure wicked-garden connection and onboard the current codebase"
argument-hint: "[--reconfigure]"
---

# /wicked-garden:setup

The single entry point for getting started with wicked-garden. Always runs interactively — detects current state and asks the user what they want to do.

## Arguments

- `--reconfigure`: Force connection reconfiguration even if already set up

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
    state.update(setup_complete=True, setup_confirmed=True)
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
   state.update(setup_complete=True, setup_confirmed=True)
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

#### 4.0 Environment Scan (Full and Quick paths only)

Before running onboarding, scan the project environment. Skip this step if the user chose "Skip".

**Detect project type** (languages and frameworks):

```bash
python3 -c "
import json
from pathlib import Path
cwd = Path.cwd()
markers = {
    'Python': ['pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile'],
    'Node/TypeScript': ['package.json', 'tsconfig.json'],
    'Go': ['go.mod'],
    'Rust': ['Cargo.toml'],
    'Java/Kotlin': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
    'Ruby': ['Gemfile'],
    'PHP': ['composer.json'],
    'Swift': ['Package.swift'],
    'C/C++': ['CMakeLists.txt', 'Makefile'],
}
frameworks = {
    'FastAPI': ['app/main.py', 'main.py'],
    'Django': ['manage.py'],
    'Flask': ['app.py'],
    'Next.js': ['next.config.js', 'next.config.ts'],
    'React': ['src/App.tsx', 'src/App.jsx'],
    'Vue': ['vue.config.js'],
    'Rails': ['config/routes.rb'],
    'Claude Plugin': ['.claude-plugin/plugin.json'],
}
detected_langs = [l for l, fs in markers.items() if any((cwd / f).exists() for f in fs)]
detected_fws = [fw for fw, fs in frameworks.items() if any((cwd / f).exists() for f in fs)]
print(json.dumps({'languages': detected_langs, 'frameworks': detected_fws}))
"
```

**Detect available integrations**:

```bash
python3 -c "
import shutil, json
tools = {
    'gh': shutil.which('gh') is not None,
    'tree-sitter': shutil.which('tree-sitter') is not None,
    'duckdb': shutil.which('duckdb') is not None,
    'ollama': shutil.which('ollama') is not None,
    'docker': shutil.which('docker') is not None,
    'kubectl': shutil.which('kubectl') is not None,
}
print(json.dumps(tools))
"
```

Store the JSON output from both commands in variables: `DETECTED_LANGS`, `DETECTED_FWS`, `DETECTED_TOOLS`.

**Domain preferences** — ask which issue tracker is used:

**INTERACTIVE mode**: Use AskUserQuestion with header "Issue Tracking", options:
- "GitHub Issues" = "Use gh cli for issue tracking"
- "Linear" = "Use Linear API"
- "Jira" = "Use Jira API"
- "Local kanban only" = "Use wicked-kanban local board only (default)"

**PLAIN_TEXT mode**: Write default "local" without asking (dangerous mode sessions should not block on preferences).

Write the selection to config.json:

```bash
python3 -c "
import json
from pathlib import Path
config_path = Path.home() / '.something-wicked' / 'wicked-garden' / 'config.json'
config = json.loads(config_path.read_text()) if config_path.exists() else {}
config['domain_prefs'] = {'delivery': '{selection}'}
config_path.write_text(json.dumps(config, indent=2))
print('Domain preferences saved.')
"
```

Where `{selection}` is one of: `github`, `linear`, `jira`, `local`.

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

After onboarding completes, store an enriched onboarding memory with detected context from Step 4.0:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} fully onboarded on {date}. Languages: {DETECTED_LANGS}. Frameworks: {DETECTED_FWS}. Tools available: {DETECTED_TOOLS_SUMMARY}.\" --type procedural --tags onboarding,project-context,{project}")
```

Where `{DETECTED_TOOLS_SUMMARY}` lists only the tools where the value is `true` (e.g., "gh, docker").

#### 4.2 Quick Scout

Ask which directories to scout (same question mode pattern as 4.1 — use AskUserQuestion or plain text depending on mode).

Run a fast scout:

```
Skill(skill="wicked-garden:search:scout")
```

Then store an enriched onboarding memory with detected context from Step 4.0:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} quick-scouted on {date}. Languages: {DETECTED_LANGS}. Frameworks: {DETECTED_FWS}. Tools: {DETECTED_TOOLS_SUMMARY}. Full onboarding not yet run.\" --type procedural --tags onboarding,project-context,{project}")
```

#### 4.3 Skip

Store a skip memory so the bootstrap directive doesn't fire again:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} skipped by user on {date}. Run /wicked-garden:setup to onboard later.\" --type procedural --tags onboarding,{project}")
```

### 5. Clear Onboarding Gate

After onboarding (or skip), clear the enforcement gate so prompts are no longer blocked.

Set `{mode}` to `"full"`, `"quick"`, or `"skip"` based on the onboarding path taken.
Set `{complete}` to `True` for full/quick, `False` for skip.

```bash
python3 -c "
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState
state = SessionState.load()
state.update(
    needs_onboarding=False,
    setup_in_progress=False,
    setup_confirmed=True,
    onboarding_mode='{mode}',
    onboarding_complete={complete},
)
print('Onboarding gate cleared.')
"
```

### 6. Done

Show a summary with all detected information:

```
wicked-garden is ready!

Connection:   {mode} ({endpoint or "offline"})
Onboarding:   {Full | Quick scout | Skipped}
Directories:  {paths onboarded}
Project type: {DETECTED_LANGS} / {DETECTED_FWS} (or "Not detected" if scan was skipped)
Integrations: {list tools where detected=true, e.g. "gh, docker" or "None detected"}
Preferences:  Delivery → {selected issue tracker}

Quick start:
- /wicked-garden:help — see all domains and commands
- /wicked-garden:crew:start — start a project with crew workflow
- /wicked-garden:engineering:review — code review
- /wicked-garden:search:search "query" — search code and docs
```

## Graceful Degradation

- If connection setup fails, local JSON fallback handles storage automatically
- If onboarding indexing fails, fall back to quick scout
- If memory store fails, still complete (just won't suppress future directives)
- Never block the user from working — all failures offer alternatives
