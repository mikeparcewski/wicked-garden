---
name: task-dependencies
title: Task Dependencies
description: Claude manages tasks with dependencies and blocked status
type: workflow
difficulty: intermediate
estimated_minutes: 5
---

# Task Dependencies

Test that task dependencies work correctly, showing blocked status when dependencies are incomplete.

## Setup

Create a project with tasks that have dependencies.

## Steps

1. **Create a project**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-project "API Development" -d "REST API implementation"
   ```
   Note the project ID (e.g., PROJECT_ID).

2. **Create the foundation task**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Design API schema" -p P0
   ```
   Note this task's ID (e.g., SCHEMA_TASK_ID).

3. **Create dependent tasks with --depends**
   ```bash
   # Endpoints depend on schema
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Implement endpoints" -p P1 --depends SCHEMA_TASK_ID

   # Tests depend on endpoints (note the ENDPOINTS_TASK_ID from above)
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Write API tests" -p P1 --depends ENDPOINTS_TASK_ID
   ```

4. **Check blocking status**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-task PROJECT_ID ENDPOINTS_TASK_ID --with-status
   ```
   Should show `is_blocked: true` with `blocking_details` listing the schema task.

5. **Complete the schema task**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID SCHEMA_TASK_ID --swimlane done
   ```

6. **Verify endpoints task is now unblocked**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-task PROJECT_ID ENDPOINTS_TASK_ID --with-status
   ```
   Should show `is_blocked: false` and empty `blocking_details`.

7. **Modify dependencies on existing task**
   ```bash
   # Add another dependency
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TESTS_TASK_ID --add-depends SCHEMA_TASK_ID

   # Remove a dependency
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TESTS_TASK_ID --remove-depends SCHEMA_TASK_ID
   ```

## Expected Outcome

- Dependencies are set correctly on tasks via `--depends` flag
- Tasks with incomplete dependencies show `is_blocked: true`
- `blocking_details` shows which tasks are blocking and their status
- When a dependency is completed (moved to Done), dependent tasks become unblocked
- Dependencies can be added/removed with `--add-depends` and `--remove-depends`

## Success Criteria

- [ ] Dependencies can be set via `--depends` flag on create-task
- [ ] Dependencies can be modified via `--depends`, `--add-depends`, `--remove-depends` on update-task
- [ ] `get-task --with-status` shows is_blocked: true when dependencies are in non-complete swimlanes
- [ ] blocking_details contains information about blocking tasks
- [ ] Completing a dependency unblocks dependent tasks

## Value Demonstrated

Task dependencies help Claude understand what order work should be done. Blocked tasks can't be started until their dependencies are complete, preventing wasted effort on tasks that require prior work.
