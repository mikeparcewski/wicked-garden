---
allowed-tools: ["AskUserQuestion", "Bash"]
description: "Install wicked-* peer tools — version-checks garden first, then picks layers and solo beds via multi-select"
argument-hint: ""
phase_relevance: ["bootstrap"]
archetype_relevance: ["*"]
---

# /wicked-garden:install

First-run installer for the wicked-* ecosystem. Ensures wicked-garden is current, installs the required evidence floor (vault + loom automatically — no question asked), then prompts for optional layers and solo beds via a multi-select picker.

## Instructions

### 1. Check wicked-garden is current

Get the installed version from its package.json (typically `~/.claude/plugins/wicked-garden/package.json` or the path Claude Code reports for `CLAUDE_PLUGIN_ROOT`):

```bash
node -e "try{const p=require('path'),os=require('os');const v=require(p.join(os.homedir(),'.claude','plugins','wicked-garden','package.json')).version;console.log(v)}catch(e){console.log('UNKNOWN')}" 2>/dev/null || echo "UNKNOWN"
```

Get the npm latest:

```bash
npm view wicked-garden version 2>/dev/null || echo "UNKNOWN"
```

If installed < latest: show "wicked-garden {installed} is installed — latest is {latest}. Consider updating via the marketplace (`claude plugins marketplace update wicked-garden`)." Then continue — don't block on this.

If UNKNOWN: note it and continue.

### 2. Install the required evidence floor

No prompt — vault and loom are mandatory for every evidence gate. Run in order, show a progress line for each.

```bash
npx wicked-vault-install
```

```bash
npm i -g wicked-loom
```

On any failure: display the raw error and note "you can install this manually and re-run `/wicked-garden:install` to retry." Continue to step 3 regardless — `wicked-loom doctor` (step 5) will surface what's still missing.

### 3. Pick optional layers and solo beds

Detect question mode:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/detect_state.py" question-mode 2>/dev/null || echo "INTERACTIVE"
```

---

**INTERACTIVE mode (AskUserQuestion)**

Q1 — multi-select, header "Layers":

"Which optional layers do you want to add?"

Options (multiSelect: true):
- label: "wicked-testing", description: "QE pipeline — verdicts your agent can't fake · author ≠ executor ≠ reviewer"
- label: "wicked-brain", description: "Persistent memory — cross-session recall, cited search, code graph"
- label: "wicked-understanding", description: "Repo playbooks from HEAD — the repo's 'how,' always current"
- label: "wicked-bus", description: "Local event bus — one SQLite file, no broker, no daemon, no ports"

Q2 — single-select, header "Solo bed":

"Add wicked-interactive — the live HTML presentation builder?"

Options:
- label: "Yes — add it", description: "Great for decks, landing pages, and demos at 11pm. Standalone — no garden required."
- label: "Skip for now", description: "Add it later by re-running /wicked-garden:install"

Echo back the full selection list before installing: "Installing: [comma-joined list]. Proceeding..."

---

**PLAIN_TEXT mode (dangerous — AskUserQuestion broken)**

Present both questions as numbered plain-text lists. STOP and wait for the user's reply before proceeding. Parse the reply, echo it back, then continue.

### 4. Install selected tools

Run in the order listed. Show a ✓ or ✗ line per tool as each completes.

| Tool | Method |
|---|---|
| wicked-testing | `npx wicked-testing install` |
| wicked-brain | Claude Code slash command — display `/plugin install wicked-brain`, ask user to run it, then verify by checking if the plugin dir exists under `~/.claude/plugins/wicked-brain` |
| wicked-understanding | `npx skills add mikeparcewski/wicked-understanding --all` |
| wicked-bus | Claude Code slash command — display `/plugin install wicked-bus`, ask user to run it, then verify under `~/.claude/plugins/wicked-bus` |
| wicked-interactive | `claude plugins marketplace add mikeparcewski/wicked-interactive && claude plugins install wicked-interactive` |

For any tool where the user must run a slash command, clearly display the command, pause, and wait for confirmation before marking it done.

### 5. Verify with loom doctor

```bash
npx wicked-loom doctor
```

Parse JSON output. Show a summary table — tool name, version/status, and a next-step hint for anything MISSING.

### 6. Done

Display:
- A clean installed-tools summary with versions
- Quick start hint: `/wicked-garden:setup` — full onboarding (indexes your codebase into wicked-brain, writes project memory, configures the status line)
- Or just start: describe a task and wicked-garden routes it to the right work-shape archetype automatically
