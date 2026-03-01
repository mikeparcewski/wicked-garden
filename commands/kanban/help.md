---
description: Setup instructions and usage for wicked-kanban
---

# /wicked-garden:kanban:help

AI-native kanban that serves as the **source of truth** for task management.

## How It Works

wicked-kanban automatically captures all task activity:

- **TaskCreate/TaskUpdate** → Synced to kanban via hooks
- **Git commits** → Linked to active task
- **Agent work** → Logged as comments
- **Repo binding** → Each repo maps to a project

## Available Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:kanban:help` | This help |
| `/wicked-garden:kanban:board-status` | Show current board state |
| `/wicked-garden:kanban:new-task` | Quick task creation |
| `/wicked-garden:kanban:name-session` | Name the current session |
| `/wicked-garden:kanban:start-api` | Start data API for dashboard |

## CLI Usage

```bash
cd ${CLAUDE_PLUGIN_ROOT}

# List projects
uv run python scripts/kanban/kanban.py list-projects

# List tasks
uv run python scripts/kanban/kanban.py list-tasks PROJECT_ID --swimlane todo

# Create task
uv run python scripts/kanban/kanban.py create-task PROJECT_ID "Task name" --priority P1

# Update task
uv run python scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane in_progress

# Add comment
uv run python scripts/kanban/kanban.py add-comment PROJECT_ID TASK_ID "Comment text"

# Link commit
uv run python scripts/kanban/kanban.py add-commit PROJECT_ID TASK_ID abc1234

# View activity
uv run python scripts/kanban/kanban.py activity PROJECT_ID --limit 20

# Search
uv run python scripts/kanban/kanban.py search "query"
```

## Data Structure

```
~/.something-wicked/wicked-garden/local/wicked-kanban/
├── config.json              # Repo → project mappings
├── active_context.json      # Current task/session
└── projects/
    └── {id}/
        ├── project.json     # Metadata
        ├── swimlanes.json   # Board columns
        ├── tasks/           # One file per task
        ├── initiatives/     # Sessions/sprints
        └── activity/        # Daily logs (JSONL)
```

## Configuration

| Setting | Default | Environment Variable |
|---------|---------|---------------------|
| Data Dir | ~/.something-wicked/wicked-garden/local/wicked-kanban | `WICKED_KANBAN_DATA_DIR` |

## Rendering

The board is rendered via the **Control Plane** (CP) data API.

To access kanban data:
1. Ensure the CP is running at `http://localhost:18889`
2. Query via: `python3 scripts/cp.py kanban tasks list`
3. Or directly: `curl http://localhost:18889/api/v1/data/kanban/tasks/list`

### Available Components

See `.claude-plugin/catalog.json` for full component definitions:
- `KanbanBoard`, `Swimlane`, `TaskCard` - Board views
- `TaskList`, `TaskDetailPanel` - Task displays
- `InitiativeCard`, `InitiativeList` - Initiative views
- `DependencyGraph`, `TraceabilityLinks` - Relationships
- `CommentsPanel`, `ArtifactsPanel`, `CommitsList` - Details
