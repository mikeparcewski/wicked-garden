---
allowed-tools: ["Bash", "Read", "AskUserQuestion"]
description: "Reset wicked-garden to a clean state — choose which data to clear"
argument-hint: "[--all] [--only domain1,domain2] [--keep domain] [--force] [--list-projects] [--all-projects]"
---

# /wicked-garden:reset

Selectively clear wicked-garden local state. Shows what exists and lets the user choose what to reset.

## Arguments

- `--all`: Select all domains for clearing (can combine with `--keep`)
- `--only {domains}`: Comma-separated list of specific domains to clear
- `--keep {domains}`: Comma-separated domains to preserve when using `--all`
- `--force`: Skip confirmation prompt
- `--list-projects`: List all projects with stored state (each working directory is a separate project)
- `--all-projects`: Operate on all projects, not just the current one

## Project Scope

State is project-scoped — each working directory gets its own isolated storage. The reset command operates on the current project by default. Use `--list-projects` to see all projects, and `--all-projects` to clear data across all of them.

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

## Instructions

### 1. Scan Current State

Run a dry-run scan to see what exists:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reset.py" --json
```

Parse the JSON output. Extract the domains where `exists` is `true`.

The JSON output includes `project` (current project slug) and `project_root` (storage path).

If no domains have state, tell the user: "Nothing to reset — wicked-garden has no local state for project {project}." and stop.

**If `--list-projects` was passed**: Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reset.py" --list-projects --json` instead and display the project list. Stop after showing.

**If `--all-projects` was passed**: Add `--all-projects` to the reset command in Step 4.

### 2. Show State and Ask What to Clear

**If `--all` or `--only` was passed**: Skip the selection — targets are already known. Go to Step 3.

**Otherwise**: Present the found domains and let the user choose.

Show a numbered list of domains that have state, plus an "All" option:

```
## Current wicked-garden state (project: {project_slug})

Found {n} domain(s) with local data:

  1. config — Setup configuration (52 B)
  2. smaht — Session history and context cache (12 KB)
  3. crew — Crew project data (4 KB)
  4. mem — Memory store (8 KB)
  5. search — Search index (2.1 MB)
  a. All of the above

Which domains would you like to reset? (comma-separated numbers, or 'a' for all)
```

Only list domains where `exists` is `true`. Number them sequentially.

**INTERACTIVE mode**: Use AskUserQuestion. Since there may be more than 4 options, use plain text instead (AskUserQuestion only supports up to 4 options).

**In both modes**: Present as plain text and STOP. Wait for the user to reply.

Parse the user's reply:
- Single number → that domain only
- Comma-separated numbers (e.g., "1,3,5") → those domains
- "a" or "all" → all found domains
- Domain names (e.g., "smaht, crew") → those domains directly

Echo back: "You selected: **{domain list}**."

### 3. Confirm

**If `--force` was passed**: Skip to Step 4.

Present a confirmation:

```
This will permanently clear: {selected domains}

1. Yes, clear selected data
2. Cancel

Please reply with 1 or 2.
```

STOP and wait. If the user cancels, say "Reset cancelled." and stop.

### 4. Execute Reset

Build the `--only` list from the user's selection:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reset.py" --confirm --only {selected_domains_space_separated} --json
```

Or if `--all` with `--keep`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reset.py" --confirm --all --keep {kept_domains_space_separated} --json
```

### 5. Report Results

Parse the JSON output and show:

```
## Reset complete

Cleared: smaht, crew
Kept: config, mem, search, kanban, delivery, jam
Errors: none

Note: If you cleared 'config', the setup wizard will run on your next session.
Run /wicked-garden:setup to reconfigure now.
```

If there were errors, show them and suggest manual cleanup.
