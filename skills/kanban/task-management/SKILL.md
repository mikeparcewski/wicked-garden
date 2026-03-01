---
name: task-management
description: This skill should be used when the user asks to "track tasks", "create a task", "add a todo", "manage tasks", "show my tasks", "what should I work on", "move task to done", "update task status", or mentions persistent task tracking, kanban boards, or project management. Provides guidance for using wicked-kanban for persistent task management.
version: 1.0.0
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
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-projects
```

**Get full project state (swimlanes + tasks):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-project PROJECT_ID
```

### Creating Tasks

**Create a project first:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-project "Project Name" -d "Description"
```

**Create a task (need swimlane_id from project):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Task Name" SWIMLANE_ID -p P1 -d "Description"
```

Priority levels: P0 (Critical), P1 (High), P2 (Normal), P3 (Low)

### Updating Tasks

**Update task status (move to different swimlane):**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane NEW_SWIMLANE_ID
```

**Update task priority:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --priority P0
```

### Comments and Commits

**Add comment to task:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT_ID TASK_ID "Comment text"
```

**Link commit to task:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-commit PROJECT_ID TASK_ID abc123
```

### Searching

**Search tasks across projects:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py search "search query"
```

**Search within a specific project:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py search "search query" --project PROJECT_ID
```

## When to Use Script vs TodoWrite

### Prefer Kanban Script For

- Tasks that should persist across sessions
- Work items requiring priorities or organization
- Tasks the user wants to track visually on the board
- Project-level task management

### TodoWrite Still Works

TodoWrite calls are automatically synced to a "Claude Tasks" project on the kanban board via the PostToolUse hook. Tasks are organized into **session-based sprints** for better organization.

**Session Naming:** Use `/wicked-garden:kanban:name-session "Feature Name"` to give the current session a descriptive name. This creates sprints like "Session: Feature Name - a1b2c3d4" instead of generic date-based names.

**Sprint Organization:** Each Claude Code session gets its own sprint, so you can filter the board by session to see what was worked on.

## Web UI

Access the visual kanban board at `http://localhost:18888`. The web UI provides:

- Drag-and-drop task management
- Visual dependency graphs
- Sprint planning views
- Search across all projects

The server auto-starts with the Claude Code session. To start manually:
```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run wicked-kanban
```

## Workflow Example

### Starting Work on a Feature

1. Create a project:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-project "Auth Feature"
```

2. Get the project to see swimlane IDs:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-project PROJECT_ID
```

3. Create tasks in "To Do" swimlane:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Design auth flow" SWIMLANE_ID
```

4. Move tasks to "In Progress" when starting:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane IN_PROGRESS_ID
```

5. Add comments documenting progress:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT_ID TASK_ID "Implemented JWT validation"
```

6. Move to "Done" when complete:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane DONE_ID
```

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
| Project artifact | `add-project-artifact PROJECT_ID "Name" --url URL` |
| Search | `search "query"` |
| List sprints | `list-sprints PROJECT_ID` |
| Create sprint | `create-sprint PROJECT_ID "Name" --start DATE` |
| Update sprint | `update-sprint PROJECT_ID SPRINT_ID --status active` |
| Delete sprint | `delete-sprint PROJECT_ID SPRINT_ID` |

## Data Storage

Tasks are stored as JSON files in `~/.something-wicked/wicked-garden/local/wicked-kanban/projects/`. Each project has its own file containing swimlanes, tasks, sprints, and metadata.

## Additional Resources

### Reference Files

For detailed patterns and workflows:

- **`references/api-reference.md`** - Core script commands (projects, tasks, search)
- **`references/api-advanced.md`** - Advanced features (sprints, artifacts, data model)
- **`references/workflow-patterns.md`** - Common workflow examples
