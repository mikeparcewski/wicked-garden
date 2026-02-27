# Example: Feature Development Workflow

Complete example of managing a feature from start to finish.

## Scenario

Implement user authentication with OAuth support.

## Step 1: Create Project

```
User: "I need to implement user authentication"

Claude: Creating a project for the authentication feature.

mcp__wicked-kanban__save_project(
  name="User Authentication",
  description="JWT-based authentication with OAuth provider support"
)

Response:
{
  "id": "proj-auth-001",
  "name": "User Authentication",
  "swimlanes": [
    {"id": "swim-todo", "name": "To Do"},
    {"id": "swim-progress", "name": "In Progress"},
    {"id": "swim-done", "name": "Done"}
  ]
}
```

## Step 2: Break Down Tasks

```
Claude: Breaking down the feature into tasks with dependencies.

# Design task (no dependencies)
mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  name="Design authentication flow",
  description="Create sequence diagrams and select OAuth provider",
  swimlane_id="swim-todo",
  priority="P1"
)
# Returns: task-design

# Implementation tasks (depend on design)
mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  name="Implement JWT token service",
  swimlane_id="swim-todo",
  priority="P1",
  depends_on=["task-design"]
)
# Returns: task-jwt

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  name="Implement OAuth integration",
  swimlane_id="swim-todo",
  priority="P1",
  depends_on=["task-design"]
)
# Returns: task-oauth

# Login endpoint (depends on JWT and OAuth)
mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  name="Implement login endpoint",
  swimlane_id="swim-todo",
  priority="P1",
  depends_on=["task-jwt", "task-oauth"]
)
# Returns: task-login

# Testing (depends on login)
mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  name="Write authentication tests",
  swimlane_id="swim-todo",
  priority="P2",
  depends_on=["task-login"]
)
# Returns: task-tests
```

## Step 3: Start Design Work

```
User: "Let's start with the design"

Claude: Moving design task to In Progress.

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-design",
  swimlane_id="swim-progress"
)

Claude: [Works on design, creates sequence diagrams]

mcp__wicked-kanban__attach(
  project_id="proj-auth-001",
  target="task",
  attachment_type="comment",
  action="add",
  data={"content": "Selected Auth0 as OAuth provider. Sequence diagram attached to project."},
  target_id="task-design"
)
```

## Step 4: Complete Design

```
Claude: Design complete. Moving to Done.

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-design",
  swimlane_id="swim-done"
)

# task-jwt and task-oauth are now unblocked
```

## Step 5: Parallel Implementation

```
User: "Start on the JWT service"

Claude: Moving JWT task to In Progress.

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-jwt",
  swimlane_id="swim-progress"
)

Claude: [Implements JWT service]

mcp__wicked-kanban__attach(
  project_id="proj-auth-001",
  target="task",
  attachment_type="commit",
  action="add",
  data={"hash": "abc123"},
  target_id="task-jwt"
)

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-jwt",
  swimlane_id="swim-done"
)
```

## Step 6: Continue to Login Endpoint

After both JWT and OAuth tasks complete:

```
Claude: Both JWT and OAuth complete. Login endpoint is now unblocked.

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-login",
  swimlane_id="swim-progress"
)

# ... implementation ...

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-login",
  swimlane_id="swim-done"
)
```

## Step 7: Final Testing

```
Claude: Login endpoint complete. Starting on tests.

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-tests",
  swimlane_id="swim-progress"
)

# ... write and run tests ...

mcp__wicked-kanban__attach(
  project_id="proj-auth-001",
  target="task",
  attachment_type="comment",
  action="add",
  data={"content": "All 15 tests passing. Coverage: 92%"},
  target_id="task-tests"
)

mcp__wicked-kanban__save_task(
  project_id="proj-auth-001",
  task_id="task-tests",
  swimlane_id="swim-done"
)
```

## Result

All tasks complete. The kanban board shows:
- **To Do**: Empty
- **In Progress**: Empty
- **Done**: 5 tasks with linked commits and comments

Each task has:
- Documented progress via comments
- Linked git commits for traceability
- Clear dependency chain showing work order
