# Wicked Kanban Script Reference

Complete reference for the `kanban.py` CLI script.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py [command] [arguments]
```

## Command Overview

| Command | Purpose |
|---------|---------|
| `list-projects` | List all projects |
| `get-project PROJECT_ID` | Full board state: project + swimlanes + tasks |
| `create-project "Name"` | Create new project |
| `create-task PROJECT TASK SWIMLANE` | Create new task |
| `update-task PROJECT TASK [options]` | Update task fields |
| `add-comment PROJECT TASK "text"` | Add comment to task |
| `add-commit PROJECT TASK HASH` | Link commit to task |
| `search "query"` | Find tasks across projects |

For sprints, artifacts, and data model details, see `api-advanced.md`.

## Project Commands

### list-projects

List all projects in the kanban system.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py list-projects
```

**Output:**
```json
[
  {
    "id": "proj-123",
    "name": "User Auth",
    "description": "Authentication feature",
    "taskCount": 5,
    "createdAt": "2024-01-15T10:00:00Z",
    "archived": false
  }
]
```

### get-project

Get full project state including swimlanes and tasks.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID
```

**Output:**
```json
{
  "id": "proj-123",
  "name": "User Auth",
  "swimlanes": [
    {"id": "swim-1", "name": "To Do", "order": 0, "isComplete": false},
    {"id": "swim-2", "name": "In Progress", "order": 1, "isComplete": false},
    {"id": "swim-3", "name": "Done", "order": 2, "isComplete": true}
  ],
  "tasks": [
    {
      "id": "task-1",
      "name": "Implement login",
      "swimlaneId": "swim-1",
      "priority": "P1",
      "dependsOn": [],
      "isBlocked": false
    }
  ]
}
```

### create-project

Create a new project with default swimlanes (To Do, In Progress, Done).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Project Name" [-d "Description"]
```

## Task Commands

### create-task

Create a new task in a project.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Task Name" SWIMLANE_ID [-p PRIORITY] [-d "Description"]
```

**Arguments:**
- `project_id` (required): Project ID
- `name` (required): Task name
- `swimlane_id` (required): Swimlane ID from project
- `-p, --priority`: P0, P1, P2, P3 (default: P2)
- `-d, --description`: Task description

**Example:**
```bash
# First get swimlane ID from project
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project abc12345

# Then create task in the "To Do" swimlane
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task abc12345 "Implement auth" swim-todo-id -p P1
```

### update-task

Update an existing task.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID TASK_ID [--swimlane ID] [--priority P0-P3] [--name "New Name"] [--depends TASK_IDS] [--sprint SPRINT_ID]
```

**Arguments:**
- `--swimlane`: New swimlane ID (moves task)
- `--priority`: New priority level
- `--name`: New task name
- `--depends`: Comma-separated task IDs this task depends on
- `--sprint`: Sprint ID to assign task to

**Example - Move task to "In Progress":**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task abc12345 task-1 --swimlane swim-progress-id
```

**Example - Set dependencies:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task abc12345 task-2 --depends task-1,task-3
```

### add-comment

Add a comment to a task.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID TASK_ID "Comment text"
```

### add-commit

Link a git commit hash to a task.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID TASK_ID COMMIT_HASH
```

### add-project-comment

Add a comment to a project (not a specific task).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-project-comment PROJECT_ID "Comment text"
```

## Search

Search tasks across projects.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "query" [--project PROJECT_ID]
```

**Arguments:**
- `query` (required): Search text (matches name and description)
- `--project`: Limit search to specific project

**Output:**
```json
[
  {
    "taskId": "task-1",
    "taskName": "Implement auth",
    "projectId": "proj-1",
    "projectName": "User Auth",
    "priority": "P1",
    "swimlaneId": "swim-1"
  }
]
```
