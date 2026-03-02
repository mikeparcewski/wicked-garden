---
name: task-dependencies
title: Task Dependencies
description: Claude manages tasks with dependencies and blocked status
type: workflow
difficulty: intermediate
estimated_minutes: 5
---

# Task Dependencies

Test that task dependencies work correctly using Claude's native task tools, showing blocked status when dependencies are incomplete.

## Setup

No special setup needed beyond an active wicked-garden session.

## Steps

1. **Create a foundation task**
   Use `TaskCreate` to create the first task:
   ```
   TaskCreate(subject="Design API schema", description="Define REST API schema for endpoints")
   ```
   Note the task ID (e.g., SCHEMA_TASK_ID).

2. **Create dependent tasks with blockedBy**
   Use `TaskCreate` for the dependent task, then set up the dependency:
   ```
   TaskCreate(subject="Implement endpoints", description="Build REST endpoints based on schema")
   ```
   Then use `TaskUpdate` to set the dependency:
   ```
   TaskUpdate(taskId=ENDPOINTS_TASK_ID, addBlockedBy=[SCHEMA_TASK_ID])
   ```

3. **Create a third task blocked by the second**
   ```
   TaskCreate(subject="Write API tests", description="Integration tests for all endpoints")
   TaskUpdate(taskId=TESTS_TASK_ID, addBlockedBy=[ENDPOINTS_TASK_ID])
   ```

4. **Verify the dependency chain**
   Use `TaskList` to see the full task list with blocked/blocking relationships. The endpoints task should show as blocked by the schema task.

5. **View the board to see the dependency context**
   ```
   /wicked-garden:kanban:board-status
   ```
   Tasks should appear on the board with their status reflecting the dependency chain.

6. **Complete the schema task to unblock the next**
   ```
   TaskUpdate(taskId=SCHEMA_TASK_ID, status="in_progress")
   ```
   Do the work, then:
   ```
   TaskUpdate(taskId=SCHEMA_TASK_ID, status="completed")
   ```

7. **Verify the endpoints task is now unblocked**
   Use `TaskList` or `TaskGet(taskId=ENDPOINTS_TASK_ID)` to confirm the blockedBy list is now empty (since the schema task is completed).

8. **Work through the dependency chain**
   ```
   TaskUpdate(taskId=ENDPOINTS_TASK_ID, status="in_progress")
   TaskUpdate(taskId=ENDPOINTS_TASK_ID, status="completed")
   ```
   Now the tests task should also be unblocked.

9. **Final board state**
   ```
   /wicked-garden:kanban:board-status
   ```
   Shows 2 tasks done, 1 task now available to start.

## Expected Outcomes

- Dependencies are set correctly using TaskUpdate addBlockedBy
- TaskList shows which tasks are blocked and what blocks them
- Completing a dependency unblocks dependent tasks
- Board status reflects the progression through the dependency chain
- Work proceeds in the correct order (schema -> endpoints -> tests)

## Success Criteria

- [ ] Dependencies set via TaskUpdate addBlockedBy
- [ ] TaskList/TaskGet shows blockedBy relationships
- [ ] Blocked tasks cannot start until dependencies complete
- [ ] Completing a dependency unblocks dependent tasks
- [ ] Board status reflects the dependency chain progression
- [ ] Full chain can be worked through in order

## Value Demonstrated

Task dependencies help Claude understand what order work should be done. Blocked tasks cannot be started until their dependencies are complete, preventing wasted effort on tasks that require prior work. This is essential for complex development workflows where implementation depends on design, and testing depends on implementation.
