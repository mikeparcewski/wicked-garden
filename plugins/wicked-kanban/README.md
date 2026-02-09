# wicked-kanban

Persistent task board that survives across sessions. Claude Code's built-in tasks reset every time you start a new conversation -- kanban auto-syncs via PostToolUse hooks, links commits to tasks, and maintains sprint grouping and activity audit trails that persist forever. Every TaskCreate and TaskUpdate flows to a durable board with full history.

## Quick Start

```bash
# Install
claude plugin install wicked-kanban@wicked-garden

# That's it - tasks sync automatically via hooks
# Just use TaskCreate as normal, kanban tracks everything
```

After install, every task you create is automatically synced to a persistent kanban board with activity tracking.

### Three Ways to Use

**1. Automatic (Recommended)** - Tasks sync via hooks, zero effort:
```bash
# Use Claude's built-in task tools as normal
# Kanban syncs automatically in the background
```

**2. Slash Commands** - Quick board access:
```bash
/wicked-kanban:board-status      # See current board state
/wicked-kanban:new-task          # Create a task interactively
/wicked-kanban:name-session      # Name this work session
/wicked-kanban:start-api         # Start data API for workbench dashboards
```

**3. CLI** - Direct access for scripting:
```bash
python scripts/kanban.py list-projects
python scripts/kanban.py list-tasks PROJECT_ID
python scripts/kanban.py search "authentication"
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-kanban:board-status` | Show board with all tasks by status | `/wicked-kanban:board-status` |
| `/wicked-kanban:new-task` | Create a task interactively | `/wicked-kanban:new-task` |
| `/wicked-kanban:name-session` | Name the current session/initiative | `/wicked-kanban:name-session "Sprint 3"` |
| `/wicked-kanban:start-api` | Start data API for wicked-workbench | `/wicked-kanban:start-api` |
| `/wicked-kanban:help` | Setup instructions and usage guide | `/wicked-kanban:help` |

## How Automatic Sync Works

When you use TaskCreate or TaskUpdate, kanban's PostToolUse hook automatically:

1. Detects the tool call
2. Maps your repo to a kanban project (creates one on first use)
3. Syncs the task to persistent storage
4. Logs the activity with timestamp

The hook also tracks git commits and links them to active tasks.

## Key Concepts

| Concept | What It Is |
|---------|-----------|
| **Project** | All work for a repository, auto-created on first task |
| **Swimlanes** | Board columns: `todo`, `in_progress`, `done` |
| **Priorities** | P0 (critical), P1 (high), P2 (normal), P3 (low) |
| **Initiatives** | Time-boxed work periods (sprints, sessions) |
| **Dependencies** | Tasks can block other tasks |

## Storage

Folder-based storage for fast, concurrent access:

```
~/.something-wicked/wicked-kanban/
├── config.json              # Repo-to-project mappings
├── active_context.json      # Current task/session state
└── projects/{id}/
    ├── project.json         # Project metadata
    ├── tasks/{id}.json      # Individual tasks
    ├── initiatives/{id}.json
    └── activity/{date}.jsonl # Daily audit log
```

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Tasks auto-grouped by crew project initiative | Manual task organization |
| wicked-workbench | Visual kanban board dashboard | Text-only board status |
| wicked-mem | Auto-capture learnings from completed tasks | Manual memory storage |
| wicked-smaht | Active tasks injected into context | Manual board checks |

## License

MIT
