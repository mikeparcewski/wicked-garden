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

Check config:

```bash
WG_CONFIG="$HOME/.something-wicked/wicked-garden/config.json"
if [ -f "$WG_CONFIG" ]; then
  cat "$WG_CONFIG"
else
  echo "NO_CONFIG"
fi
```

This determines which questions to ask in Step 3.

### 2. Install Prerequisites

Use the prereq-doctor to check and install dependencies. This is required for search indexing and context assembly.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" check-all
```

**Evaluate the result:**

Parse the JSON output. For each tool in `core` and `optional`:

- If `status` is `"available"`: Tool is ready. Show a checkmark.
- If `status` is `"missing"`: **Ask the user** if you can install it:
  - Show: "{name} is not installed. Install with: `{install_cmd}`?"
  - **INTERACTIVE mode**: Use AskUserQuestion with header "{name}", options: "Install now" = "Run: {install_cmd}", "Skip" = "Continue without {name}".
  - **PLAIN_TEXT mode**: Ask in plain text and STOP.
  - If user approves: Run the `install_cmd` via Bash. If the tool has `post_install`, run that too. Then re-check with `prereq_doctor.py check {tool}` to verify.
  - If user declines: Warn that features depending on this tool will be unavailable. Continue.

After all core tools are installed, if `uv` is available, sync Python dependencies:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" check uv
```

If uv is available, sync deps:

```bash
# Use the path from the check result
{uv_path} sync --quiet
```

If `uv sync` fails, warn that search indexing will be unavailable but setup can continue.

**Note**: The PostToolUseFailure hook also detects missing tools at runtime. If a tool is skipped here, the hook will catch the failure later and suggest installing via the prereq-doctor skill. So it's safe to skip.

### 3. Ask the User (batched questions)

Ask questions upfront. The method depends on question mode detected above.

#### 3a. If config exists (setup_complete: true)

**Questions to ask:**

- **Q1 — Onboarding**: "Would you like to run codebase onboarding?"
  - Options: **Full onboarding (Recommended)** | **Quick scout** | **Skip for now**

**INTERACTIVE mode**: Use AskUserQuestion:
- Q1: header "Onboarding", options with descriptions (Full = "Index the codebase, explore architecture, trace flows, save discoveries as memories. Takes 1-2 minutes.", Quick scout = "Fast reconnaissance without indexing.", Skip = "Skip onboarding. Run /wicked-garden:setup later.")

**PLAIN_TEXT mode**: Present as numbered text and STOP:

```
**Onboarding** — Would you like to run codebase onboarding?
   a) Full onboarding — index codebase, explore architecture, save discoveries (1-2 min)
   b) Quick scout — fast recon without indexing (seconds)
   c) Skip for now
```

Then STOP and wait for the user's reply.

**After receiving answer**: Verify selection is clear. Echo back: "You selected **[answer]**." If ambiguous, ask the user to clarify.

- Skip to Step 5 (onboarding) using answer.

#### 3b. If NO config

**Questions to ask:**

- **Q1 — Onboarding**: Same as 3a.

Storage is always local (DomainStore writes local JSON files). No connection setup needed.

**After receiving answer**: Skip to Step 4 (write config), then Step 5 with onboarding answer.

### 4. Write Config (if needed)

If no config exists, write the default local config:

```bash
mkdir -p "$HOME/.something-wicked/wicked-garden"
cat > "$HOME/.something-wicked/wicked-garden/config.json" << 'CONF'
{
  "mode": "local",
  "setup_complete": true
}
CONF
```

Update session state:
```bash
python3 -c "
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState
state = SessionState.load()
state.update(setup_complete=True, setup_confirmed=True)
print('Session state updated.')
"
```

Show:
```
Storage configured!
Mode: Local (DomainStore — local JSON files)
Status: Ready
```

### 5. Run Onboarding

Execute based on the onboarding answer from Step 3.

#### 5.0 Environment Scan (Full and Quick paths only)

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

**Detect available integrations** (reuses prereq-doctor from Step 2):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" check-all
```

Parse the JSON result. Build `DETECTED_TOOLS` from the combined `core` + `optional` results — include tool name where `status` is `"available"`.

Store the language/framework output as `DETECTED_LANGS` and `DETECTED_FWS`.

**Domain preferences** — ask which issue tracker is used:

**INTERACTIVE mode**: Use AskUserQuestion with header "Issue Tracking", options:
- "GitHub Issues" = "Use gh cli for issue tracking"
- "Linear" = "Use Linear API"
- "Jira" = "Use Jira API"
- "Azure DevOps" = "Use Azure DevOps work items"
- "Rally" = "Use Rally (Broadcom) for agile project management"
- "Local kanban only" = "Use wicked-kanban local board only (default)"

Note: AskUserQuestion supports max 4 options. Present the first 4 most common choices (GitHub Issues, Jira, Azure DevOps, Local kanban only) and let the user select "Other" for Linear or Rally.

**PLAIN_TEXT mode**: Write default "local" without asking (dangerous mode sessions should not block on preferences).

**Validate the selected tool is reachable** (skip for "local"):

Use the prereq-doctor to check MCP + CLI availability:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" check "{selection}"
```

**Evaluate the result:**

- If `status` is `"available"` and `via` is `"mcp"`: Show "**{name}** connected via MCP server `{mcp_server}`." and continue.
- If `status` is `"available"` and `via` is `"cli"`: Show "**{cli}** CLI found at {cli_path}." and continue.
- If `status` is `"missing"`: Ask the user if you can install it:
  - Show: "**{name}** is not installed. Install with: `{install_cmd}`?"
  - **INTERACTIVE mode**: Use AskUserQuestion with header "{name}", options: "Install now (Recommended)" = "Run: {install_cmd}", "Skip" = "Use local kanban instead".
  - **PLAIN_TEXT mode**: Ask in plain text and STOP.
  - If user approves: Run `{install_cmd}` via Bash. If the result has `post_install`, run that too. Then re-check with `prereq_doctor.py check {selection}` to verify.
  - If user declines: Override selection to `local` and continue.

**Write the selection to config.json:**

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

Where `{selection}` is one of: `github`, `linear`, `jira`, `ado`, `rally`, `local`.

#### 5.1 Full Onboarding

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

After onboarding completes, store an enriched onboarding memory with detected context from Step 5.0:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} fully onboarded on {date}. Languages: {DETECTED_LANGS}. Frameworks: {DETECTED_FWS}. Tools available: {DETECTED_TOOLS_SUMMARY}.\" --type procedural --tags onboarding,project-context,{project}")
```

Where `{DETECTED_TOOLS_SUMMARY}` lists only the tools where the value is `true` (e.g., "gh, docker").

#### 5.2 Quick Scout

Ask which directories to scout (same question mode pattern as 5.1 — use AskUserQuestion or plain text depending on mode).

Run a fast scout:

```
Skill(skill="wicked-garden:search:scout")
```

Then store an enriched onboarding memory with detected context from Step 5.0:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} quick-scouted on {date}. Languages: {DETECTED_LANGS}. Frameworks: {DETECTED_FWS}. Tools: {DETECTED_TOOLS_SUMMARY}. Full onboarding not yet run.\" --type procedural --tags onboarding,project-context,{project}")
```

#### 5.3 Skip

Store a skip memory so the bootstrap directive doesn't fire again:

```
Skill(skill="wicked-garden:mem:store", args="\"Onboarding: {project} skipped by user on {date}. Run /wicked-garden:setup to onboard later.\" --type procedural --tags onboarding,{project}")
```

### 6. Clear Onboarding Gate

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

### 7. Done

Show a summary with all detected information:

```
wicked-garden is ready!

Storage:      Local (DomainStore)
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
