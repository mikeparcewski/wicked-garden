# Workflow Patterns

> **Note**: Tool names below use short `kanban__` prefix. Actual MCP tool names depend on your server configuration.

Common workflows for task management with wicked-garden:kanban.

## Feature Development Workflow

### 1. Create Feature Project

```
kanban__save_project(
  name="User Authentication",
  description="Implement JWT-based authentication system"
)
```

### 2. Get Project Details

```
kanban__get_project(project_id="proj-123")
```

Extract swimlane IDs from response for task placement.

### 3. Create Initial Tasks

```
# Create design task
kanban__save_task(
  project_id="proj-123",
  name="Design auth flow",
  swimlane_id="todo-swimlane-id",
  priority="P1"
)

# Create implementation task with dependency
kanban__save_task(
  project_id="proj-123",
  name="Implement login endpoint",
  swimlane_id="todo-swimlane-id",
  priority="P1",
  depends_on=["design-task-id"]
)

# Create testing task
kanban__save_task(
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
kanban__save_task(
  project_id="proj-123",
  task_id="design-task-id",
  swimlane_id="in-progress-swimlane-id"
)
```

### 5. Document Progress

Add comments as work progresses:

```
kanban__attach(
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
kanban__attach(
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
kanban__save_task(
  project_id="proj-123",
  task_id="design-task-id",
  swimlane_id="done-swimlane-id"
)
```

Dependent tasks automatically become unblocked.

## Bug Fix Workflow

### 1. Create Bug Task

```
kanban__save_task(
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
kanban__attach(
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
kanban__attach(
  project_id="proj-123",
  target="task",
  attachment_type="commit",
  action="add",
  data={"hash": "fix123"},
  target_id="bug-task-id"
)

# Move to done
kanban__save_task(
  project_id="proj-123",
  task_id="bug-task-id",
  swimlane_id="done-swimlane-id"
)
```

## Session Resume Workflow

When starting a new Claude Code session:

### 1. Find Active Work

```
kanban__search(
  query="",
  scope="tasks",
  ready_only=true
)
```

### 2. Get Context on In-Progress Tasks

```
kanban__get_task(
  project_id="proj-123",
  task_id="in-progress-task"
)
```

Review comments and recent activity to understand context.

### 3. Continue Work

Update task with progress or complete it.
