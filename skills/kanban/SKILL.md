---
name: task-management
description: |
  Persistent task management through kanban boards with cross-session tracking.
  Provides guidance for using wicked-garden:kanban for CRUD operations, dependencies,
  priorities, and sprint management.

  Use when: "track tasks", "create a task", "add a todo", "manage tasks",
  "show my tasks", "what should I work on", "move task to done", "update task status",
  "kanban board", "project management"
disable-model-invocation: true
---

# Task Management with Wicked Kanban

Persistent task management through Python scripts and a web UI, providing visual kanban boards and cross-session task tracking.

## Overview

Wicked Kanban provides AI-native task management that persists across Claude Code sessions. Use the `kanban.py` script via Bash for CRUD operations, and the web UI for visual management.

**Key benefit:** Tasks created with TodoWrite are automatically synced to the kanban board via PostToolUse hook, but using the kanban script directly provides richer features (dependencies, priorities, sprints).

## Using the Kanban Script

The script is located at `${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py`. Execute commands via Bash.

### Viewing Tasks

**List all projects:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" list-projects
```

**Get full project state (swimlanes + tasks):**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" get-project PROJECT_ID
```

### Creating Tasks

**Create a project first:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" create-project "Project Name" -d "Description"
```

**Create a task (need swimlane_id from project):**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" create-task PROJECT_ID "Task Name" SWIMLANE_ID -p P1 -d "Description"
```

Priority levels: P0 (Critical), P1 (High), P2 (Normal), P3 (Low)

### Updating Tasks

**Update task status (move to different swimlane):**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" update-task PROJECT_ID TASK_ID --swimlane NEW_SWIMLANE_ID
```

**Update task priority:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" update-task PROJECT_ID TASK_ID --priority P0
```

### Comments and Commits

**Add comment to task:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" add-comment PROJECT_ID TASK_ID "Comment text"
```

**Link commit to task:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" add-commit PROJECT_ID TASK_ID abc123
```

### Searching

**Search tasks across projects:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" search "search query"
```

**Search within a specific project:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" search "search query" --project PROJECT_ID
```

## Scoped Boards

Four board types with purpose-built column schemas:

| Board Type | Terminal Column | Best For |
|------------|----------------|----------|
| `crew` (default) | `done` (Done) | Software development, crew phases |
| `jam` | `jam:decision_made` (Decision Made) | Brainstorming, design decisions |
| `collaboration` | `collab:complete` (Complete) | Cross-team workflows |
| `issues` | `done` (Done) | Bug tracking, general issues |

Create a typed initiative with `--board-type`:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" create-initiative PROJECT_ID "API Design" --board-type jam
# or: /wicked-garden:kanban:initiative create "API Design" --board-type jam
```

Filter board-status: `/wicked-garden:kanban:board-status --board-type jam`

Reaching a terminal column on jam or collaboration boards auto-writes a wicked-garden:mem record (`decision` or `finding`). Crew and issues boards do not trigger mem writes.

See `refs/scoped-boards.md` for full column schemas, provisioning rules, and CLI examples.

## When to Use Script vs TodoWrite

### Prefer Kanban Script For

- Tasks that should persist across sessions
- Work items requiring priorities or organization
- Tasks the user wants to track visually on the board
- Project-level task management

### TodoWrite Still Works

TodoWrite calls are automatically synced to a "Claude Tasks" project on the kanban board via the PostToolUse hook. Tasks are organized into **session-based sprints** for better organization.

Use `/wicked-garden:kanban:name-session "Feature Name"` to name the session sprint. Each session gets its own sprint for easy filtering.

## Web UI

Access the visual kanban board at `http://localhost:18888`. The web UI provides:

- Drag-and-drop task management
- Visual dependency graphs
- Sprint planning views
- Search across all projects

The server auto-starts with the Claude Code session. To start manually:
```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run wicked-garden:kanban
```

## Workflow Example

See `refs/workflow-patterns.md` for complete workflow examples (feature dev, bug fix, session resume).

## Quick Reference

| Action | Command |
|--------|---------|
| List projects | `list-projects` |
| Get project | `get-project PROJECT_ID` |
| Create project | `create-project "Name" -d "Desc"` |
| Create task | `create-task PROJECT_ID "Name" SWIMLANE_ID` |
| Update task | `update-task PROJECT_ID TASK_ID --swimlane ID` |
| Add comment | `add-comment PROJECT_ID TASK_ID "Text"` |
| Link commit | `add-commit PROJECT_ID TASK_ID HASH` |
| Add artifact | `add-artifact PROJECT_ID TASK_ID "Name" --type file` |
| Project comment | `add-project-comment PROJECT_ID "Text"` |
| Search | `search "query"` |
| Create initiative | `create-initiative PROJECT_ID "Name" --board-type jam` |
| List initiatives | `list-initiatives PROJECT_ID --board-type jam` |

## Additional Resources

- **`refs/api-reference.md`** — Core script commands (projects, tasks, initiatives, search)
- **`refs/api-advanced.md`** — Advanced features (sprints, artifacts, data model)
- **`refs/scoped-boards.md`** — Full column schemas, provisioning, wicked-garden:mem triggers
- **`refs/workflow-patterns.md`** — Common workflow examples (feature dev, bug fix, session resume)
- **`refs/advanced-patterns.md`** — Sprint planning, dependency graphs, priority filtering
- **`examples/feature-workflow.md`** — End-to-end feature development workflow example
