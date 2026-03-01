# Advanced Features Reference

Extended commands for sprints, artifacts, and data model details.

## Sprint Commands

### list-sprints

List all sprints in a project.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-sprints PROJECT_ID
```

**Output:**
```json
[
  {
    "id": "sprint-1",
    "name": "Sprint 1",
    "projectId": "proj-1",
    "startDate": "2024-01-15",
    "endDate": "2024-01-29",
    "goal": "MVP features",
    "status": "active",
    "createdAt": "2024-01-10T10:00:00Z"
  }
]
```

### create-sprint

Create a new sprint in a project.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-sprint PROJECT_ID "Sprint Name" [--start DATE] [--end DATE] [--goal "Goal"] [--status STATUS]
```

**Arguments:**
- `project_id` (required): Project ID
- `name` (required): Sprint name
- `--start`: Start date (YYYY-MM-DD)
- `--end`: End date (YYYY-MM-DD)
- `--goal`: Sprint goal description
- `--status`: Status (planning, active, completed). Default: planning

**Example:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-sprint abc12345 "Sprint 1" --start 2024-01-15 --end 2024-01-29 --goal "Complete auth feature"
```

### update-sprint

Update an existing sprint.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-sprint PROJECT_ID SPRINT_ID [--name "Name"] [--start DATE] [--end DATE] [--goal "Goal"] [--status STATUS]
```

**Example - Activate a sprint:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-sprint abc12345 sprint-1 --status active
```

### delete-sprint

Delete a sprint. Tasks assigned to this sprint will have their sprintId cleared.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py delete-sprint PROJECT_ID SPRINT_ID
```

## Artifact Commands

### add-artifact

Add an artifact (file, URL, image, document) to a task.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-artifact PROJECT_ID TASK_ID "Artifact Name" [--type TYPE] [--path PATH] [--url URL]
```

**Arguments:**
- `--type`: Artifact type (file, url, image, document). Default: file
- `--path`: Local file path
- `--url`: URL reference

**Example - Link a file:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-artifact abc12345 task-1 "Error log" --type file --path "/tmp/error.log"
```

**Example - Link a URL:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-artifact abc12345 task-1 "API Docs" --type url --url "https://docs.example.com/api"
```

### add-project-artifact

Add an artifact to a project (not a specific task).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-project-artifact PROJECT_ID "Artifact Name" [--type TYPE] [--path PATH] [--url URL]
```

## Data Model

### Project

```json
{
  "id": "abc12345",
  "name": "Project Name",
  "description": "Optional description",
  "swimlanes": [...],
  "tasks": [...],
  "sprints": [...],
  "artifacts": [],
  "comments": [],
  "createdAt": "2024-01-15T10:00:00Z",
  "archived": false
}
```

### Task

```json
{
  "id": "def67890",
  "name": "Task Name",
  "description": "Task description",
  "swimlaneId": "swimlane-id",
  "order": 0,
  "priority": "P2",
  "dependsOn": ["other-task-id"],
  "sprintId": null,
  "assignedTo": null,
  "commitHashes": ["abc123"],
  "comments": [],
  "artifacts": [],
  "isBlocked": false,
  "blockingDetails": []
}
```

### Swimlane

Default swimlanes created with each project:

```json
[
  {"id": "...", "name": "To Do", "order": 0, "isComplete": false},
  {"id": "...", "name": "In Progress", "order": 1, "isComplete": false},
  {"id": "...", "name": "Done", "order": 2, "isComplete": true}
]
```

## Priority Levels

| Level | Name | Use Case |
|-------|------|----------|
| P0 | Critical | Blockers, security issues, production down |
| P1 | High | Important features, significant bugs |
| P2 | Normal | Standard work items (default) |
| P3 | Low | Nice-to-haves, minor improvements |

## Blocking Logic

Tasks with `dependsOn` IDs pointing to tasks not in "complete" swimlanes are marked as blocked:
- `isBlocked: true`
- `blockingDetails: [{taskId, taskName, swimlaneName}]`

When all dependencies are in a complete swimlane, the task is automatically unblocked.

## Storage

Data stored in: `~/.something-wicked/wicked-garden/local/wicked-kanban/projects/`

Each project is a separate JSON file: `{project-id}.json`

Environment variable `WICKED_KANBAN_DATA_DIR` can override the data directory.

## Error Handling

Errors are written to stderr with exit code 1. Common errors:
- "Project not found: {id}"
- "Task not found"
- "Failed to create task" (usually invalid swimlane ID)

## Web UI

The REST API server provides a web UI at `http://localhost:18888` (default port).

Port can be configured via `WICKED_KANBAN_PORT` environment variable.
