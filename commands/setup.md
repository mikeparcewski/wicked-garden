---
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write", "Skill", "Agent"]
description: "Configure wicked-garden connection and onboard the current codebase"
argument-hint: "[--reconfigure]"
phase_relevance: ["bootstrap"]
archetype_relevance: ["*"]
---

# /wicked-garden:setup

The single entry point for getting started. Always interactive — detects current state and asks the user what they want.

## Arguments

- `--reconfigure`: Force connection reconfiguration even if already set up

## Question Mode

Detect once, branch every interactive call site below:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/detect_state.py" question-mode
```

- **INTERACTIVE**: Use AskUserQuestion as documented in each step.
- **PLAIN_TEXT**: AskUserQuestion is broken (dangerous mode auto-completes with empty answers). Present every question as a **numbered plain text list**, then **STOP and wait** for the user. Do NOT proceed until you receive a reply.

## Answer Verification (CRITICAL)

**INTERACTIVE (AskUserQuestion) mode**: after EVERY AskUserQuestion call you MUST (1) verify the selection is clearly present in the response, (2) echo it back — "You selected **[option]**. Proceeding with [action]..." — before any action, (3) if ambiguous or empty, do NOT assume — ask "I couldn't determine your selection. Could you tell me which option you'd like?" and wait.

**PLAIN_TEXT mode**: present options as a numbered list, **STOP**, parse the reply, echo back the same way. Never proceed with a default. Wrong actions are worse than asking twice.

## Instructions

### 1. Detect Current State

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/detect_state.py" config
```

Returns `{"present": false, "path": ...}` if no config, otherwise `{"present": true, "path": ..., "config": {...}}`. This determines which questions to ask in Step 3.

### 2. Install Prerequisites

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check-all
```

Parse the JSON. Only `core` tools are required during setup. For each `core` tool: `status: "available"` → checkmark; `status: "missing"` → show "{name} is not installed. Install with: `{install_cmd}`?" then **INTERACTIVE mode**: AskUserQuestion header "{name}", options "Install now" = "Run: {install_cmd}" / "Skip" = "Continue without {name}"; **PLAIN_TEXT mode**: ask in plain text and STOP. If approved, run `install_cmd` (and `post_install` if present), then re-check with `prereq_doctor.py check {tool}`. If declined, warn dependent features will be unavailable and continue. **Skip `optional` tools** — the PostToolUseFailure hook detects them at runtime.

After core tools, if `uv` is available, sync Python deps: `{uv_path} sync --quiet`. If sync fails, warn that search indexing will be unavailable but continue.

### 2.5 Verify wicked-testing (Required)

```bash
npx wicked-testing --version 2>/dev/null || echo "MISSING"
```

- `MISSING` → blocking. Show "wicked-testing is not installed. wicked-garden v7.0+ requires wicked-testing >= 0.1 as a peer plugin. Upgrading from v6.x? See `docs/MIGRATION-v7.md`." **INTERACTIVE mode**: AskUserQuestion header "wicked-testing Required", options "Install now (Required)" = "Run: npx wicked-testing install" / "Exit setup" = "Cancel — I'll install manually and re-run". **PLAIN_TEXT mode**: present numbered options and STOP. If install: run `npx wicked-testing install`, re-probe with `npx wicked-testing --version`, confirm the version. On failure, show stderr and exit with manual instructions. If exit: "Run `npx wicked-testing install` then restart with `/wicked-garden:setup`."
- Version string (e.g. `0.3.0`) → check it satisfies `^0.3.0` (the pin from `plugin.json`). In range: show "wicked-testing {version} — ready." Out of range: warn "wicked-testing {version} is outside the supported range (^0.3.0). Update with: `npx wicked-testing install`" and ask whether to update now (same INTERACTIVE / PLAIN_TEXT pattern). Updating is strongly recommended but not a hard block — the SessionStart hook will warn each session.

### 2.5b Verify wicked-brain (Required)

wicked-brain installs as a **Claude Code plugin** (not an npx CLI), so verify by presence rather than a version probe.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PY' 2>/dev/null || python - <<'PY'
import json, os
from pathlib import Path
installed = False
candidates = [Path.home()/".claude"/"settings.json", Path(".claude")/"settings.json"]
cfg = os.environ.get("CLAUDE_CONFIG_DIR")
if cfg: candidates.append(Path(cfg)/"settings.json")
for p in candidates:
    try:
        if not p.exists(): continue
        enabled = json.loads(p.read_text(encoding="utf-8")).get("enabledPlugins", {})
        if "wicked-brain" in (enabled if isinstance(enabled, (dict, list)) else {}):
            installed = True; break
    except Exception: continue
if not installed:
    roots = [Path.home()/".claude"/"skills"]
    if cfg: roots.append(Path(cfg)/"skills")
    for r in roots:
        try:
            if r.exists() and any(e.is_dir() and e.name.startswith("wicked-brain") for e in r.iterdir()):
                installed = True; break
        except OSError: continue
print("READY" if installed else "MISSING")
PY
```

- `MISSING` → blocking. wicked-brain is the memory, search, and context-assembly layer wicked-garden depends on — it cannot function without it. Show "wicked-brain is not installed. wicked-garden requires it as a peer (sibling to wicked-bus / wicked-vault / wicked-testing)." **INTERACTIVE mode**: AskUserQuestion header "wicked-brain Required", options "Install now (Required)" = "Run: /plugin install wicked-brain" / "Exit setup" = "Cancel — I'll install manually and re-run". **PLAIN_TEXT mode**: present numbered options and STOP. If install: instruct the user to run `/plugin install wicked-brain` (a Claude Code slash command, not a shell command), then re-run the presence check above and confirm `READY`. On failure, exit with manual instructions (`/plugin install wicked-brain`). If exit: "Run `/plugin install wicked-brain` then restart with `/wicked-garden:setup`."
- `READY` → show "wicked-brain — ready (plugin installed)."

### 2.6 Verify wicked-vault (Required)

```bash
npx wicked-vault --version 2>/dev/null || echo "MISSING"
```

- `MISSING` → blocking. wicked-vault is the evidence backend every archetype gate re-derives against — without it, "done" can only be self-asserted. Show "wicked-vault is not installed. wicked-garden requires it as a peer (sibling to wicked-bus / wicked-brain / wicked-testing)." **INTERACTIVE mode**: AskUserQuestion header "wicked-vault Required", options "Install now (Required)" = "Run: npx wicked-vault-install" / "Exit setup" = "Cancel — I'll install manually and re-run". **PLAIN_TEXT mode**: present numbered options and STOP. If install: run `npx wicked-vault-install` (installs the cross-CLI skills) and confirm the CLI resolves with `npx wicked-vault --version`. On failure, show stderr and exit with manual instructions (`npm i -g wicked-vault`). If exit: "Run `npx wicked-vault-install` then restart with `/wicked-garden:setup`."
- Version string (e.g. `0.3.0`) → show "wicked-vault {version} — ready." Then verify the garden can resolve it for gating: `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/qe/vault_gate.py" resolve` should report `resolvable: true`. If `installed: false` (resolving only via npx), suggest `npm i -g wicked-vault` for faster gate latency — recommended, not a hard block.

### 2.7 Verify wicked-bus (Required)

wicked-bus installs as a **Claude Code plugin** (not an npx CLI), so verify by presence rather than a version probe.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PY' 2>/dev/null || python - <<'PY'
import json, os
from pathlib import Path
installed = False
candidates = [Path.home()/".claude"/"settings.json", Path(".claude")/"settings.json"]
cfg = os.environ.get("CLAUDE_CONFIG_DIR")
if cfg: candidates.append(Path(cfg)/"settings.json")
for p in candidates:
    try:
        if not p.exists(): continue
        enabled = json.loads(p.read_text(encoding="utf-8")).get("enabledPlugins", {})
        if "wicked-bus" in (enabled if isinstance(enabled, (dict, list)) else {}):
            installed = True; break
    except Exception: continue
if not installed:
    roots = [Path.home()/".claude"/"skills"]
    if cfg: roots.append(Path(cfg)/"skills")
    for r in roots:
        try:
            if r.exists() and any(e.is_dir() and e.name.startswith("wicked-bus") for e in r.iterdir()):
                installed = True; break
        except OSError: continue
print("READY" if installed else "MISSING")
PY
```

- `MISSING` → blocking. wicked-bus is the event backbone the garden's archetype events flow through — without it, cross-plugin event wiring is silently dropped. Show "wicked-bus is not installed. wicked-garden requires it as a peer (sibling to wicked-brain / wicked-vault / wicked-testing)." **INTERACTIVE mode**: AskUserQuestion header "wicked-bus Required", options "Install now (Required)" = "Run: /plugin install wicked-bus" / "Exit setup" = "Cancel — I'll install manually and re-run". **PLAIN_TEXT mode**: present numbered options and STOP. If install: instruct the user to run `/plugin install wicked-bus` (a Claude Code slash command, not a shell command), then re-run the presence check above and confirm `READY`. On failure, exit with manual instructions (`/plugin install wicked-bus`). If exit: "Run `/plugin install wicked-bus` then restart with `/wicked-garden:setup`."
- `READY` → show "wicked-bus — ready (plugin installed)."

### 2.8 v6→v11 Project State Migration (optional)

If the user has v6-v10 crew projects on disk, advise them to run the v11 migration script:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/migrate_v6_projects.py"
```

`CLEAN` → no v6-state found, skip silently. `MIGRATABLE_FOUND` → list affected projects and ask whether to translate them to v11 archetype-mode shape. The legacy qe-evaluator naming sweep that lived here in v6 was removed when the universal pipeline was deleted in v11.0.0.

### 3. Ask the User (batched questions)

Method depends on Question Mode.

#### 3a. If config exists (setup_complete: true)

**Q1 — Onboarding**: "Would you like to run codebase onboarding?" Options: "Full onboarding (Recommended)" | "Quick scout" | "Skip for now". **INTERACTIVE mode**: Use AskUserQuestion with header "Onboarding" (Full = "Index the codebase, explore architecture, trace flows, save discoveries as memories. Takes 1-2 minutes.", Quick scout = "Fast reconnaissance without indexing.", Skip = "Skip onboarding. Run /wicked-garden:setup later."). **PLAIN_TEXT mode**: present numbered text (a/b/c with same descriptions) and STOP. Verify, echo back. Skip to Step 5 with the answer.

#### 3b. If NO config

**Q1 — Onboarding**: same as 3a. Storage is always local (DomainStore writes local JSON) — no connection setup needed. After answer: Step 4 (write config) → Step 5.

### 4. Write Config (if needed)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/onboarding.py" write-local-config
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/onboarding.py" mark-setup-complete
```

Show: "Storage configured! Mode: Local (DomainStore — local JSON files). Status: Ready."

### 5. Run Onboarding

Execute based on the onboarding answer from Step 3.

#### 5.0 Environment Scan (Full and Quick paths only)

Skip this step if the user chose "Skip".

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/detect_state.py" project-env
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check-all
```

Store as `DETECTED_LANGS`, `DETECTED_FWS`. Build `DETECTED_TOOLS` from combined `core` + `optional` where `status` is `"available"`.

**Domain preferences** — which issue tracker? **INTERACTIVE mode**: Use AskUserQuestion header "Issue Tracking" with the 4 most common (AskUserQuestion supports max 4): "GitHub Issues" = "Use gh cli" / "Jira" = "Use Jira API" / "Azure DevOps" = "Use Azure DevOps work items" / "Local tasks only" = "Use Claude Code's native tasks only (default)". Let the user select "Other" for Linear or Rally. **PLAIN_TEXT mode**: write default `local` without asking (dangerous-mode sessions should not block on preferences).

**Validate the selected tool is reachable** (skip for `local`):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check "{selection}"
```

- `available` + `via: "mcp"` → show "**{name}** connected via MCP server `{mcp_server}`."
- `available` + `via: "cli"` → show "**{cli}** CLI found at {cli_path}."
- `missing` → "**{name}** is not installed. Install with: `{install_cmd}`?". **INTERACTIVE mode**: AskUserQuestion header "{name}", options "Install now (Recommended)" = "Run: {install_cmd}" / "Skip" = "Use local native tasks instead". **PLAIN_TEXT mode**: ask in plain text and STOP. If approved, run `install_cmd` (and `post_install` if present), re-check with `prereq_doctor.py check {selection}`. If declined, override to `local`.

Persist the selection (one of `github` | `linear` | `jira` | `ado` | `rally` | `local`):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/onboarding.py" save-domain-pref {selection}
```

#### 5.1 Full Onboarding

Runs the **brain pipeline** — init knowledge layer, index codebase, improve search quality, store onboarding context. Show progress as each step completes. If any step fails, log it and continue — each step is independently valuable.

First, ask which directories to onboard. **INTERACTIVE mode**: Use AskUserQuestion with header "Directories", options "Current directory (Recommended)" = "Onboard the project root: {cwd}" / "Specify directories" = "Choose specific directories to index (enter paths via Other)". **PLAIN_TEXT mode**: ask in plain text (a = current directory `{cwd}`, b = specify paths), STOP, wait, verify, echo back.

##### Brain Pipeline (in order)

**Step A — Brain init** (if brain doesn't exist). Probe `curl -s -X POST http://localhost:4242/api -H "Content-Type: application/json" -d '{"action":"health","params":{}}' 2>/dev/null`. If connection refused or no brain directory at `~/.wicked-brain`, run `Skill(skill="wicked-brain-init")`.
Then start the server with `Skill(skill="wicked-brain-server")`.

**Step B — Ingest codebase**. Show "Indexing codebase into brain..." then `Skill(skill="wicked-brain-ingest", args="{selected_directory}")`.

**Step C — Retag** (semantic tag expansion). Show "Improving search tags..." then `Skill(skill="wicked-brain-retag")`.

**Step D — Compile** (synthesize wiki articles). Show "Generating knowledge articles..." then `Skill(skill="wicked-brain-compile")`.

**Step E — Configure brain instructions** (write source_type guidance + wiki stats into CLAUDE.md). Must run AFTER compile so the wiki count is accurate. Show "Configuring brain instructions..." then `Skill(skill="wicked-brain-configure")`.

**Step F — Store onboarding memory** as a brain chunk. `{DETECTED_TOOLS_SUMMARY}` lists only available tools (e.g. "gh, docker"):
```
Skill(skill="wicked-brain:memory", args="\"Onboarding: {project} fully onboarded on {date}. Languages: {DETECTED_LANGS}. Frameworks: {DETECTED_FWS}. Tools available: {DETECTED_TOOLS_SUMMARY}.\" --type procedural --tags onboarding,project-context,{project}")
```

Show: "Onboarding complete — brain has {N} chunks, {M} wiki articles."

#### 5.2 Quick Scout

Ask which directories to scout (same question mode pattern as 5.1 — AskUserQuestion or plain text depending on mode). Then run `Skill(skill="wicked-brain:search")` and store an enriched onboarding memory with detected context from Step 5.0:

```
Skill(skill="wicked-brain:memory", args="\"Onboarding: {project} quick-scouted on {date}. Languages: {DETECTED_LANGS}. Frameworks: {DETECTED_FWS}. Tools: {DETECTED_TOOLS_SUMMARY}. Full onboarding not yet run.\" --type procedural --tags onboarding,project-context,{project}")
```

#### 5.3 Skip

Store a skip memory so the bootstrap directive doesn't fire again:
```
Skill(skill="wicked-brain:memory", args="\"Onboarding: {project} skipped by user on {date}. Run /wicked-garden:setup to onboard later.\" --type procedural --tags onboarding,{project}")
```

### 6. Clear Onboarding Gate

Set `{mode}` to `full` / `quick` / `skip`. Pass `--complete` for full/quick (omit for skip):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/onboarding.py" clear-gate --mode {mode} [--complete]
```

### 6.5 Inject CLAUDE.md Hints

Inject a minimal wicked-garden hint block into `.claude/CLAUDE.md` so Claude discovers the plugin in future sessions. Rules: target `.claude/CLAUDE.md` in the working directory (create the directory if needed); idempotent — if a `## Wicked Garden` section already exists, skip entirely; non-destructive — append to end; ultra-condensed (~80 tokens). If the file is created new, prepend `# Project Instructions\n\n` before the section. **Skip mode still injects** — the user should know the plugin is available even if onboarding was skipped.

Append (or prepend with header for a new file):

```markdown

## Wicked Garden

This project uses the [wicked-garden](https://github.com/mikeparcewski/wicked-garden) plugin.

Before implementing manually, check if wicked-garden has a domain for it:
- Code review: `/wicked-garden:engineering:review`
- Brainstorm/decide: `/wicked-garden:jam:quick "your question"`
- Security/compliance: `/wicked-garden:platform:security`
- Full workflow: `/wicked-garden:crew:start "description"`

Run `/wicked-garden:help` for all commands across 16 domains.
```

### 7. Done

Show:

```
wicked-garden is ready!

Storage:         Local (DomainStore)
wicked-brain:    {"ready (plugin installed)" or "MISSING — install required"}
wicked-bus:      {"ready (plugin installed)" or "MISSING — install required"}
wicked-testing:  {version e.g. "0.1.2 — ready" or "MISSING — install required"}
wicked-vault:    {version e.g. "0.3.0 — ready" or "MISSING — install required"}
Onboarding:      {Full | Quick scout | Skipped}
Directories:     {paths onboarded}
Project type:    {DETECTED_LANGS} / {DETECTED_FWS} (or "Not detected")
Integrations:    {available tools, or "None detected"}
Preferences:     Delivery → {selected issue tracker}

Quick start: /wicked-garden:help · /wicked-garden:crew:start · /wicked-garden:engineering:review · wicked-brain:search "query"
```

## Graceful Degradation

- Connection setup fails → local JSON fallback handles storage automatically.
- Onboarding indexing fails → fall back to quick scout.
- Memory store fails → still complete (just won't suppress future directives).
- Never block the user from working — all failures offer alternatives.
