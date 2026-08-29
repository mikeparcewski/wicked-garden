# Action: install

First-run installer for the wicked-* ecosystem. Ensures wicked-garden is
current, installs the required evidence floor (wicked-vault automatically — no
question asked), then prompts for optional layers and solo beds via a
multi-select picker. The loom peer-resolution engine is absorbed into
wicked-garden itself (scripts/loom/) — no separate wicked-loom install is
needed.

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

No prompt — wicked-vault is the mandatory evidence backend for every gate. The loom
peer-resolution engine is built into wicked-garden (scripts/loom/) — nothing to install
for loom. Run vault install and show a progress line:

```bash
npm i -g wicked-vault
```

On failure: display the raw error and note "you can install wicked-vault manually via `npm i -g wicked-vault` and re-run the wicked-garden-core skill's `install` action to retry." Continue to step 3 regardless — step 5 will surface what's still missing.

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
- label: "wicked-estate", description: "Memory/context layer — cross-session memory, cited knowledge recall, code graph (Rust binaries)"
- label: "wicked-understanding", description: "Repo playbooks from HEAD — the repo's 'how,' always current"
- label: "wicked-bus", description: "Local event bus — one SQLite file, no broker, no daemon, no ports"

Q2 — single-select, header "Solo bed":

"Add wicked-interactive — the live HTML presentation builder?"

Options:
- label: "Yes — add it", description: "Great for decks, landing pages, and demos at 11pm. Standalone — no garden required."
- label: "Skip for now", description: "Add it later by re-running the wicked-garden-core skill's install action"

Echo back the full selection list before installing: "Installing: [comma-joined list]. Proceeding..."

---

**PLAIN_TEXT mode (dangerous — AskUserQuestion broken)**

Present both questions as numbered plain-text lists. STOP and wait for the user's reply before proceeding. Parse the reply, echo it back, then continue.

### 4. Install selected tools

Run in the order listed. Show a ✓ or ✗ line per tool as each completes.

| Tool | Method |
|---|---|
| wicked-estate | Install the `wicked-estate` + `wicked-estate-mcp` binaries onto PATH or `~/.local/bin` (see the wicked-estate README — cargo install or a release download), then verify with the §2.5b presence probe in refs/setup.md |
| wicked-understanding | `npx skills add mikeparcewski/wicked-understanding --all` |
| wicked-bus | `npm i -g wicked-bus && npx wicked-bus-install` (the installer copies the bus skills into detected AI CLIs), then verify skills under `~/.claude/skills/wicked-bus-*` |
| wicked-interactive | `claude plugins marketplace add mikeparcewski/wicked-interactive && claude plugins install wicked-interactive` |

For any tool where the user must run a command themselves, clearly display the command, pause, and wait for confirmation before marking it done.

### 5. Verify peer health

Run the internal loom doctor (no external wicked-loom needed):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, json
sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'scripts'))
from loom import compose
rows = compose.check_all()
print(json.dumps(rows, indent=2))
"
```

Parse JSON output. Show a summary table — peer name, version/status (`ok`/`drift`/`present`/`missing`/`error`), and a next-step hint for anything `missing` or `drift`. A `present` row (peer responds but version unreadable) is a warning, not blocking.

### 6. Done

Display:
- A clean installed-tools summary with versions
- Quick start hint: invoke the wicked-garden-core skill's `setup` action — full onboarding (indexes your codebase into the wicked-estate knowledge layer, writes project memory, configures the status line)
- Or just start: describe a task and wicked-garden routes it to the right work-shape archetype automatically
