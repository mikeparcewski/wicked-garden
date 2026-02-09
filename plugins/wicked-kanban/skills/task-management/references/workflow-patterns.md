# Workflow Patterns

Common workflows for task management with wicked-kanban.

## Feature Development Workflow

### 1. Create Feature Project

```
mcp__wicked-kanban__save_project(
  name="User Authentication",
  description="Implement JWT-based authentication system"
)
```

### 2. Get Project Details

```
mcp__wicked-kanban__get_project(project_id="proj-123")
```

Extract swimlane IDs from response for task placement.

### 3. Create Initial Tasks

```
# Create design task
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Design auth flow",
  swimlane_id="todo-swimlane-id",
  priority="P1"
)

# Create implementation task with dependency
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Implement login endpoint",
  swimlane_id="todo-swimlane-id",
  priority="P1",
  depends_on=["design-task-id"]
)

# Create testing task
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Write auth tests",
  swimlane_id="todo-swimlane-id",
  priority="P2",
  depends_on=["implement-task-id"]
)
```

### 4. Start Work

Move task to "In Progress":

```
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  task_id="design-task-id",
  swimlane_id="in-progress-swimlane-id"
)
```

### 5. Document Progress

Add comments as work progresses:

```
mcp__wicked-kanban__attach(
  project_id="proj-123",
  target="task",
  attachment_type="comment",
  action="add",
  data={"content": "Completed OAuth provider research. Going with Auth0."},
  target_id="design-task-id"
)
```

### 6. Link Commits

When code is committed:

```
mcp__wicked-kanban__attach(
  project_id="proj-123",
  target="task",
  attachment_type="commit",
  action="add",
  data={"hash": "abc123def456"},
  target_id="implement-task-id"
)
```

### 7. Complete Task

Move to "Done":

```
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  task_id="design-task-id",
  swimlane_id="done-swimlane-id"
)
```

Dependent tasks automatically become unblocked.

## Bug Fix Workflow

### 1. Create Bug Task

```
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Fix: Login timeout on slow connections",
  description="Users report timeout errors when logging in on 3G connections",
  swimlane_id="todo-swimlane-id",
  priority="P0",
  traceability=[
    {"type": "issue", "ref": "GH-456", "label": "GitHub Issue"}
  ]
)
```

### 2. Investigate and Document

```
mcp__wicked-kanban__attach(
  project_id="proj-123",
  target="task",
  attachment_type="comment",
  action="add",
  data={"content": "Root cause: API timeout is 5s, needs to be 30s for slow connections"},
  target_id="bug-task-id"
)
```

### 3. Fix and Close

```
# Link fix commit
mcp__wicked-kanban__attach(
  project_id="proj-123",
  target="task",
  attachment_type="commit",
  action="add",
  data={"hash": "fix123"},
  target_id="bug-task-id"
)

# Move to done
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  task_id="bug-task-id",
  swimlane_id="done-swimlane-id"
)
```

## Sprint Planning Workflow

### 1. Create Sprint

```
mcp__wicked-kanban__save_sprint(
  project_id="proj-123",
  name="Sprint 1",
  start_date="2024-01-15",
  end_date="2024-01-29",
  goal="Complete core authentication flow"
)
```

### 2. Assign Tasks to Sprint

```
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  task_id="task-1",
  sprint_id="sprint-1"
)

mcp__wicked-kanban__save_task(
  project_id="proj-123",
  task_id="task-2",
  sprint_id="sprint-1"
)
```

### 3. Track Sprint Progress

```
mcp__wicked-kanban__get_sprint(
  project_id="proj-123",
  sprint_id="sprint-1"
)
```

## Session Resume Workflow

When starting a new Claude Code session:

### 1. Find Active Work

```
mcp__wicked-kanban__search(
  query="",
  scope="tasks",
  ready_only=true
)
```

### 2. Get Context on In-Progress Tasks

```
mcp__wicked-kanban__get_task(
  project_id="proj-123",
  task_id="in-progress-task"
)
```

Review comments and recent activity to understand context.

### 3. Continue Work

Update task with progress or complete it.

## Dependency Graph Pattern

Create a complex task dependency graph:

```
# Foundation task
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Set up database schema",
  swimlane_id="todo-id",
  priority="P1"
)  # Returns task-db

# Parallel tasks depending on foundation
mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Implement user model",
  swimlane_id="todo-id",
  depends_on=["task-db"]
)  # Returns task-user

mcp__wicked-kanban__save_task(
  project_id="proj-123",
  name="Implement session model",
  swimlane_id="todo-id",
  depends_on=["task-db"]
)  # Returns task-session

# Final task depending on both
mcp__wicked-kanban__save_task(
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
mcp__wicked-kanban__attach(
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
mcp__wicked-kanban__attach(
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
mcp__wicked-kanban__search(
  query="",
  scope="tasks",
  min_priority="P0",
  max_priority="P1",
  ready_only=true
)
```

This returns only P0 and P1 tasks that have no blocking dependencies.
