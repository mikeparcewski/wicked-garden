---
description: Quick task creation with optional project and priority
argument-hint: <task_name> [--project name] [--priority P0|P1|P2|P3]
---

# /wicked-garden:kanban:new-task

Create a task on the kanban board.

## Arguments

- `task_name` (required): The task name/description
- `project` (optional): Project to add task to (default: most recent or "Claude Tasks")
- `priority` (optional): P0 (Critical), P1 (High), P2 (Normal), P3 (Low)

## Instructions

1. Parse arguments from user input

2. List existing projects to find or create target:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban/kanban.py list-projects
   ```

3. If project specified and doesn't exist, create it:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban/kanban.py create-project "PROJECT_NAME"
   ```

4. If no project specified, use the most recent project or create "Claude Tasks"

5. Create the task:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban/kanban.py create-task PROJECT_ID "TASK_NAME" --priority P2
   ```

## Example Usage

```
/wicked-garden:kanban:new-task "Implement login endpoint" --project "Auth Feature" --priority P1
```

## Default Behavior

- Priority defaults to P2 (Normal)
- New tasks go to "todo" swimlane
- If no project specified, uses most recent project or creates "Claude Tasks"

## Output

Confirm task creation with:
- Task ID
- Task name
- Project name
- Swimlane (todo)
- Priority
