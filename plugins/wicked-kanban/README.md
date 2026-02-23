# wicked-kanban

Claude Code's built-in tasks reset every session — wicked-kanban auto-syncs every TaskCreate and TaskUpdate to a persistent board with git commit linking, sprint grouping, and a full activity audit trail that survives across every conversation.

## Quick Start

```bash
# Install — tasks start syncing automatically
claude plugin install wicked-kanban@wicked-garden

# Check your board right now
/wicked-kanban:board-status

# Name the current session as a sprint or initiative
/wicked-kanban:name-session "Sprint 14"
```

After install, zero configuration is required. Every `TaskCreate` and `TaskUpdate` you or any agent makes is automatically captured.

## Workflows

### Zero-Effort Persistence

The most common workflow is doing nothing differently. Just use Claude's native task tools, and kanban captures everything:

```
You: "Build the authentication module"

Claude creates tasks:
  TaskCreate("Design: auth-module - JWT token structure")
  TaskCreate("Build: auth-module - Login endpoint")
  TaskCreate("Build: auth-module - Token refresh logic")
  TaskCreate("Test: auth-module - Auth integration tests")
```

Those tasks now exist in persistent storage. Start a new session tomorrow:

```bash
/wicked-kanban:board-status
```

Output:
```
Project: my-app (linked to /Users/you/projects/my-app)

IN PROGRESS (1)
  [P1] Build: auth-module - Login endpoint

TO DO (2)
  [P1] Build: auth-module - Token refresh logic
  [P2] Test: auth-module - Auth integration tests

DONE (1)
  [P1] Design: auth-module - JWT token structure
      Completed 2026-02-22 · commit a3f91b2

Recent activity: 4 tasks created, 1 completed, 1 git commit linked
```

### Sprint Tracking Across Sessions

Group related work into a named initiative, then track it over days or weeks:

```bash
# Name the current work period
/wicked-kanban:name-session "Sprint 14 - Auth Hardening"

# Create tasks — they're automatically grouped under this initiative
TaskCreate("Build: auth-sprint - Rate limiting on login")
TaskCreate("Build: auth-sprint - Account lockout policy")
TaskCreate("Review: auth-sprint - Security audit")

# Check sprint status anytime, any session
/wicked-kanban:board-status
```

### Linking Commits to Work

When you commit code, kanban hooks detect it and link the commit hash to the active task. This creates a traceable connection from requirement to code change to deployment — visible in the audit log and accessible via the Data API.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-kanban:board-status` | Show board with all tasks by status | `/wicked-kanban:board-status` |
| `/wicked-kanban:new-task` | Create a task interactively | `/wicked-kanban:new-task "Fix login timeout" --priority P1` |
| `/wicked-kanban:name-session` | Name the current session or initiative | `/wicked-kanban:name-session "Sprint 14"` |
| `/wicked-kanban:start-api` | Start data API for wicked-workbench | `/wicked-kanban:start-api` |
| `/wicked-kanban:help` | Setup instructions and usage guide | `/wicked-kanban:help` |

## How It Works

When you or an agent calls `TaskCreate` or `TaskUpdate`, kanban's PostToolUse hook fires automatically:

1. Maps your current repo path to a kanban project (creates one on first use)
2. Syncs the task to folder-based persistent storage
3. Logs the event with a timestamp to the daily activity log
4. If a git commit just happened, links the commit hash to the active task

The hook also watches for session naming via `name-session` to group tasks into initiatives (sprints). No polling, no background daemons — purely event-driven.

## Storage

```
~/.something-wicked/wicked-kanban/
├── config.json              # Repo-to-project mappings
├── active_context.json      # Current task/session state
└── projects/{id}/
    ├── project.json         # Project metadata
    ├── tasks/{id}.json      # Individual task files
    ├── initiatives/{id}.json
    └── activity/{date}.jsonl # Daily audit log
```

## Skills

| Skill | What It Does |
|-------|-------------|
| `task-management` | Guidance for persistent task management and kanban CLI operations |

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| projects | list, get | Kanban projects with metadata and configuration |
| tasks | list, get, search, stats | Tasks with status, priority, and metadata |
| initiatives | list, get | Project initiatives for grouping tasks |
| activity | list | Recent task activity and changes |
| comments | list, create | Task comments and annotations (requires `--task-id` and `--project`) |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-kanban/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Tasks auto-grouped into crew project initiatives | Manual task organization |
| wicked-workbench | Visual kanban board dashboard | Text-only board status |
| wicked-mem | Auto-capture learnings from completed tasks | Manual memory storage |
| wicked-smaht | Active tasks injected into context automatically | Manual board checks |

## License

MIT
