---
description: Manage kanban initiatives for crew projects and issue tracking
argument-hint: "<lookup|create|ensure-issues> [name] [--board-type crew|jam|collaboration|issues]"
---

# /wicked-garden:kanban:initiative

Manage kanban initiatives — lookup, create, or ensure defaults exist.

## Usage

```
/kanban:initiative lookup {name}                          # Find initiative by crew project name
/kanban:initiative create {name}                          # Create crew initiative (default)
/kanban:initiative create {name} --board-type jam         # Create jam board initiative
/kanban:initiative create {name} --board-type collaboration  # Create collaboration board
/kanban:initiative ensure-issues                          # Ensure "Issues" default initiative exists
```

## Instructions

### Parse Arguments

- `lookup <name>` — Find an existing initiative by name
- `create <name> [--board-type TYPE]` — Create an initiative (idempotent — returns existing if found). Board type defaults to `"crew"`.
- `ensure-issues` — Ensure the default "Issues" initiative exists for this repo (always `board_type="issues"`)

**Board type choices:** `crew` (default), `jam`, `collaboration`, `issues`

### Execute

Run the appropriate subcommand:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/kanban/kanban_initiative.py {subcommand} {name}
```

For typed boards:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/kanban/kanban_initiative.py create "Sprint Retro" --board-type jam
```

### Output Format

All subcommands return JSON to stdout:

- **lookup**: `{"found": true, "initiative_id": "...", "project_id": "..."}` or `{"found": false}`
- **create**: `{"initiative_id": "...", "project_id": "...", "already_existed": true|false}`
- **ensure-issues**: `{"status": "exists|created|failed", "initiative_id": "..."}`

### Report

Display the JSON result. On error, report gracefully — kanban initiative tracking is optional and should never block callers.
