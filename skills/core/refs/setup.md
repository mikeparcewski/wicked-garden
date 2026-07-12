# Action: setup

Configure wicked-garden connection and onboard the current codebase. The single
entry point for getting started. Always interactive — detects current state and
asks the user what they want.

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

> **One required, three opt-in.** The evidence gate needs **wicked-vault** (§2.6) — it ships via wicked-testing and the internal loom engine is built into wicked-garden itself, so no separate loom install is needed. The other three (**wicked-testing**, **wicked-brain**, **wicked-bus**) are **opt-in toolkit layers** — install them for the acceptance-testing, memory, and audit-trail capabilities; skip any and the rest of the toolkit still works.

### 2.5 Verify wicked-testing (Recommended — acceptance-testing layer)

```bash
npx wicked-testing --version 2>/dev/null || echo "MISSING"
```

- `MISSING` → **recommended, not blocking.** Show "wicked-testing isn't installed — the evidence-gated acceptance-testing layer (author ≠ executor ≠ reviewer) will be unavailable. The produces-gate itself still works via vault + loom." **INTERACTIVE mode**: AskUserQuestion header "wicked-testing (optional layer)", options "Install now" = "Run: npx wicked-testing install" / "Skip" = "Continue without the acceptance-testing layer". **PLAIN_TEXT mode**: offer the choice and CONTINUE (do not stop). If install: run `npx wicked-testing install`, re-probe with `npx wicked-testing --version`, confirm the version. If skipped: continue setup — the layer can be added anytime.
- Version string (e.g. `0.3.0`) → check it satisfies `^0.3.0` (the pin from `plugin.json`). In range: show "wicked-testing {version} — ready." Out of range: warn "wicked-testing {version} is outside the supported range (^0.3.0). Update with: `npx wicked-testing install`" and ask whether to update now (same INTERACTIVE / PLAIN_TEXT pattern). Updating is strongly recommended but not a hard block — the SessionStart hook will warn each session.

### 2.5b Verify wicked-brain (Recommended — memory/context layer)

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

- `MISSING` → **recommended, not blocking.** wicked-brain is the memory/context layer (cross-session recall, cited search, `smaht:briefing`); the rest of the toolkit works without it. Show "wicked-brain isn't installed — you'll lose cross-session memory + brain-backed search until you add it." **INTERACTIVE mode**: AskUserQuestion header "wicked-brain (optional layer)", options "Install now" = "Run: /plugin install wicked-brain" / "Skip" = "Continue without the memory layer". **PLAIN_TEXT mode**: offer the choice and CONTINUE. If install: instruct the user to run `/plugin install wicked-brain` (a Claude Code slash command), then re-run the presence check and confirm `READY`. If skipped: continue setup.
- `READY` → show "wicked-brain — ready (plugin installed)."

### 2.5c Verify wicked-understanding (Recommended — repo-playbooks layer)

wicked-understanding installs as **`skills`-standard skills** (multi-CLI; no server). It analyzes the current repo at HEAD into task playbooks (`fix-bug`/`add-feature`/`verify`/`write-tests`) the agent loads on demand — the "how to work in THIS repo" layer that pairs with wicked-brain's "what". Per-repo, so verify by presence of its generated skills rather than a version probe.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PY' 2>/dev/null || python - <<'PY'
import os
from pathlib import Path
found = False
roots = [Path.home()/".claude"/"skills"]
cfg = os.environ.get("CLAUDE_CONFIG_DIR")
if cfg: roots.append(Path(cfg)/"skills")
for r in roots:
    try:
        if r.exists() and any(e.is_dir() and e.name.startswith(("repo-", "fix-bug", "add-feature")) for e in r.iterdir()):
            found = True; break
    except OSError: continue
print("READY" if found else "ABSENT")
PY
```

- `ABSENT` → **recommended, not blocking.** Show "wicked-understanding isn't set up — without it the agent re-derives *how to work in this repo* each task. Add the repo-playbooks layer: `npx skills add mikeparcewski/wicked-understanding --all`, then run its `repo-analyst` to generate this repo's playbooks." **INTERACTIVE mode**: AskUserQuestion header "wicked-understanding (optional layer)", options "Install now" = "Run: npx skills add mikeparcewski/wicked-understanding --all" / "Skip" = "Continue without repo playbooks". **PLAIN_TEXT mode**: offer the choice and CONTINUE. If skipped: continue setup.
- `READY` → show "wicked-understanding — ready (repo playbooks installed)." Suggest re-running `repo-analyst` after large changes so the playbooks track HEAD.

### 2.6 Verify wicked-vault (Required — the evidence gate)

```bash
npx wicked-vault --version 2>/dev/null || echo "MISSING"
```

- `MISSING` → blocking. wicked-vault is the evidence backend every archetype gate re-derives against — without it, "done" can only be self-asserted. Show "wicked-vault is not installed. wicked-garden requires it as a peer (sibling to wicked-bus / wicked-brain / wicked-testing)." **INTERACTIVE mode**: AskUserQuestion header "wicked-vault Required", options "Install now (Required)" = "Run: npx wicked-testing install" / "Exit setup" = "Cancel — I'll install manually and re-run". **PLAIN_TEXT mode**: present numbered options and STOP. If install: run `npx wicked-testing install` (installs the cross-CLI skills) and confirm the CLI resolves with `npx wicked-vault --version`. On failure, show stderr and exit with manual instructions (`npm i -g wicked-vault`). If exit: "Run `npx wicked-testing install` then restart by invoking the wicked-garden-core skill's `setup` action."
- Version string (e.g. `0.3.0`) → show "wicked-vault {version} — ready." Then verify the garden can resolve it for gating: `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/qe/vault_gate.py" resolve` should report `resolvable: true`. If `installed: false` (resolving only via npx), suggest `npm i -g wicked-vault` for faster gate latency — recommended, not a hard block.

### 2.7 Verify wicked-bus (Recommended — audit-trail layer)

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

- `MISSING` → **recommended, not blocking.** wicked-bus is the audit-trail layer; event emission is already fire-and-forget / fail-open, so the toolkit runs fine without it (events just aren't recorded). Show "wicked-bus isn't installed — the cross-session audit trail will be empty until you add it." **INTERACTIVE mode**: AskUserQuestion header "wicked-bus (optional layer)", options "Install now" = "Run: /plugin install wicked-bus" / "Skip" = "Continue without the audit trail". **PLAIN_TEXT mode**: offer the choice and CONTINUE. If install: instruct the user to run `/plugin install wicked-bus` (a Claude Code slash command), then re-run the presence check and confirm `READY`. If skipped: continue setup.
- `READY` → show "wicked-bus — ready (plugin installed)."

### 2.7b Verify loom peer-resolution engine (internal — no external install needed)

After Phase B of the ecosystem rationalization, the loom peer-resolution engine is absorbed
directly into wicked-garden as `scripts/loom/`. No external `wicked-loom` npm package is
required. Check that the internal module is importable:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'scripts'))
try:
    from loom import resolve, compose, gate, manifest
    print('READY')
except ImportError as e:
    print('MISSING: ' + str(e))
"
```

- `READY` → show "Loom peer-resolution — ready (internal module available). Peer resolution, vault gating, and peer-health checks are fully operational."
- `MISSING: ...` → this indicates a wicked-garden installation problem. Show "The loom internal module could not be imported from `scripts/loom/`. This is a garden install error — reinstall wicked-garden via the marketplace." This is blocking; do not proceed until resolved. **Note**: `WICKED_LOOM_BIN` overrides to an external loom binary (debugging escape hatch); `WICKED_LOOM_CUTOVER=off` is an emergency kill-switch that disables the gate entirely and causes it to FAIL CLOSED — there is no fallback/graceful-degradation path when the kill-switch is active. It is not a rollback mode; it is an emergency stop. Do NOT set it except under explicit incident direction.

### 2.8 v6→v11 Project State Migration (optional)

If the user has v6-v10 crew projects on disk, advise them to run the v11 migration script:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/migrate_v6_projects.py"
```

`CLEAN` → no v6-state found, skip silently. `MIGRATABLE_FOUND` → list affected projects and ask whether to translate them to v11 archetype-mode shape. The legacy qe-evaluator naming sweep that lived here in v6 was removed when the universal pipeline was deleted in v11.0.0.

### 3. Ask the User (batched questions)

Method depends on Question Mode.

#### 3a. If config exists (setup_complete: true)

**Q1 — Onboarding**: "Would you like to run codebase onboarding?" Options: "Full onboarding (Recommended)" | "Quick scout" | "Skip for now". **INTERACTIVE mode**: Use AskUserQuestion with header "Onboarding" (Full = "Index the codebase, explore architecture, trace flows, save discoveries as memories. Takes 1-2 minutes.", Quick scout = "Fast reconnaissance without indexing.", Skip = "Skip onboarding. Run the wicked-garden-core `setup` action later."). **PLAIN_TEXT mode**: present numbered text (a/b/c with same descriptions) and STOP. Verify, echo back. Skip to Step 5 with the answer.

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

**Step A — Brain init** (if brain doesn't exist). Probe the brain (resolve its port dynamically): `PORT="$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_brain_port.py" 2>/dev/null || echo 4242)"; curl -s -X POST "http://localhost:${PORT}/api" -H "Content-Type: application/json" -d '{"action":"health","params":{}}' 2>/dev/null`. If connection refused or no brain directory at `~/.wicked-brain`, run `Skill(skill="wicked-brain-init")`.
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
Skill(skill="wicked-brain:memory", args="\"Onboarding: {project} skipped by user on {date}. Invoke the wicked-garden-core skill's setup action to onboard later.\" --type procedural --tags onboarding,{project}")
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

Before implementing manually, check if wicked-garden has a skill for it:
- Code review: invoke the `wicked-garden-engineering` skill (`review` action)
- Brainstorm/decide: invoke the `wicked-garden-jam` skill (`quick "your question"`)
- Security/compliance: invoke the `wicked-garden-platform` skill (`security` action)
- Any task: describe it (the hook routes to a work-shape archetype) or invoke
  the `wicked-garden-archetype` skill directly, e.g. `build "description"`

Invoke the `wicked-garden-core` skill for help with all available skills.
```

### 6.6 Enable the work-mode status line (optional)

Offer to surface the detected archetype on screen. **INTERACTIVE mode**: AskUserQuestion header "Status line", options "Enable (Recommended)" = "Show the live work mode at the bottom of the screen" / "Skip" = "Don't change my status line". **PLAIN_TEXT mode**: ask in plain text and STOP.

If enabled, add (non-destructively — skip if a `statusLine` key already exists) to the user's `settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "sh \"$CLAUDE_PLUGIN_ROOT/scripts/_python.sh\" \"$CLAUDE_PLUGIN_ROOT/scripts/statusline.py\""
}
```

The bar then shows `🌱 wg │ <archetypes> │ intent · phase · gate verdict`. It reads session state only, is fail-soft, and never blocks a render. If a `statusLine` is already set, show the snippet and let the user merge it manually rather than overwriting.

### 7. Done

Show:

```
wicked-garden is ready!

Storage:         Local (DomainStore)
wicked-brain:    {"ready (plugin installed)" or "MISSING — install required"}
wicked-bus:      {"ready (plugin installed)" or "MISSING — install required"}
wicked-testing:  {version e.g. "0.1.2 — ready" or "MISSING — install required"}
wicked-vault:    {version e.g. "0.3.0 — ready" or "MISSING — install required"}
loom engine:     {"ready (internal — scripts/loom/)" or "MISSING — garden installation problem"}
Onboarding:      {Full | Quick scout | Skipped}
Directories:     {paths onboarded}
Project type:    {DETECTED_LANGS} / {DETECTED_FWS} (or "Not detected")
Integrations:    {available tools, or "None detected"}
Preferences:     Delivery → {selected issue tracker}

Quick start: wicked-garden-core (help) · wicked-garden-archetype (build) ·
wicked-garden-prove (compile) · wicked-garden-engineering (review) ·
wicked-brain:search "query"
```

## Graceful Degradation

- Connection setup fails → local JSON fallback handles storage automatically.
- Onboarding indexing fails → fall back to quick scout.
- Memory store fails → still complete (just won't suppress future directives).
- Never block the user from working — all failures offer alternatives.
