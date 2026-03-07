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
uv run python scripts/_run.py scripts/kanban/kanban.py list-projects

# List tasks
uv run python scripts/_run.py scripts/kanban/kanban.py list-tasks PROJECT_ID --swimlane todo

# Create task
uv run python scripts/_run.py scripts/kanban/kanban.py create-task PROJECT_ID "Task name" --priority P1

# Update task
uv run python scripts/_run.py scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane in_progress

# Add comment
uv run python scripts/_run.py scripts/kanban/kanban.py add-comment PROJECT_ID TASK_ID "Comment text"

# Link commit
uv run python scripts/_run.py scripts/kanban/kanban.py add-commit PROJECT_ID TASK_ID abc1234

# View activity
uv run python scripts/_run.py scripts/kanban/kanban.py activity PROJECT_ID --limit 20

# Search
uv run python scripts/_run.py scripts/kanban/kanban.py search "query"
```

## Data Structure

```
{SM_LOCAL_ROOT}/wicked-kanban/
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

Data paths are resolved dynamically by DomainStore. To find the local root:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-kanban
```

## Configuration

| Setting | Default | Environment Variable |
|---------|---------|---------------------|
| Data Dir | Resolved by DomainStore | `WICKED_KANBAN_DATA_DIR` |

## Data Access

Kanban data is stored as local JSON files via DomainStore.

To access kanban data:
1. Use the kanban CLI: `uv run python scripts/_run.py scripts/kanban/kanban.py list-tasks PROJECT_ID`
2. Or the board command: `/wicked-garden:kanban:board-status`
3. Integration-discovery can route to Linear/Jira MCP when configured

### Available Components

See `.claude-plugin/catalog.json` for full component definitions:
- `KanbanBoard`, `Swimlane`, `TaskCard` - Board views
- `TaskList`, `TaskDetailPanel` - Task displays
- `InitiativeCard`, `InitiativeList` - Initiative views
- `DependencyGraph`, `TraceabilityLinks` - Relationships
- `CommentsPanel`, `ArtifactsPanel`, `CommitsList` - Details
