# Advanced Patterns

> **Note**: Tool names below use short `kanban__` prefix. Actual MCP tool names depend on your server configuration.

Advanced task management patterns for sprints, dependencies, and project documentation.

## Sprint Planning Workflow

### 1. Create Sprint

```
kanban__save_sprint(
  project_id="proj-123",
  name="Sprint 1",
  start_date="2024-01-15",
  end_date="2024-01-29",
  goal="Complete core authentication flow"
)
```

### 2. Assign Tasks to Sprint

```
kanban__save_task(
  project_id="proj-123",
  task_id="task-1",
  sprint_id="sprint-1"
)

kanban__save_task(
  project_id="proj-123",
  task_id="task-2",
  sprint_id="sprint-1"
)
```

### 3. Track Sprint Progress

```
kanban__get_sprint(
  project_id="proj-123",
  sprint_id="sprint-1"
)
```

## Dependency Graph Pattern

Create a complex task dependency graph:

```
# Foundation task
kanban__save_task(
  project_id="proj-123",
  name="Set up database schema",
  swimlane_id="todo-id",
  priority="P1"
)  # Returns task-db

# Parallel tasks depending on foundation
kanban__save_task(
  project_id="proj-123",
  name="Implement user model",
  swimlane_id="todo-id",
  depends_on=["task-db"]
)  # Returns task-user

kanban__save_task(
  project_id="proj-123",
  name="Implement session model",
  swimlane_id="todo-id",
  depends_on=["task-db"]
)  # Returns task-session

# Final task depending on both
kanban__save_task(
  project_id="proj-123",
  name="Integrate auth with sessions",
  swimlane_id="todo-id",
  depends_on=["task-user", "task-session"]
)
```

Result: `task-db` must complete first, then `task-user` and `task-session` can proceed in parallel, then the integration task becomes unblocked.

## Project Documentation Pattern

Attach artifacts to project for reference:

```
# Add PRD
kanban__attach(
  project_id="proj-123",
  target="project",
  attachment_type="artifact",
  action="add",
  data={
    "name": "Product Requirements Document",
    "type": "document",
    "content": "## Overview\n\nThis feature enables..."
  }
)

# Add design doc
kanban__attach(
  project_id="proj-123",
  target="project",
  attachment_type="artifact",
  action="add",
  data={
    "name": "Technical Design",
    "type": "document",
    "content": "## Architecture\n\n..."
  }
)
```

## Priority Filtering Pattern

Find high-priority unblocked work:

```
kanban__search(
  query="",
  scope="tasks",
  min_priority="P0",
  max_priority="P1",
  ready_only=true
)
```

This returns only P0 and P1 tasks that have no blocking dependencies.
