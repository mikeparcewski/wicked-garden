---
name: basic-task-workflow
title: Basic Task Workflow
description: Claude creates a project and manages tasks through the full lifecycle
type: workflow
difficulty: basic
estimated_minutes: 5
---

# Basic Task Workflow

Test that Claude can create and manage tasks through the full lifecycle using kanban slash commands and native task tools.

## Setup

Ensure the kanban plugin is loaded and the session is active. No special configuration needed beyond a working wicked-garden installation.

## Steps

1. **Create a new task with a project**
   ```
   /wicked-garden:kanban:new-task "Design login flow" --project "Auth Feature" --priority P1
   ```
   Note the task and project confirmation from the output.

2. **Create additional tasks in the same project**
   ```
   /wicked-garden:kanban:new-task "Implement JWT tokens" --project "Auth Feature" --priority P1
   /wicked-garden:kanban:new-task "Add password reset" --project "Auth Feature" --priority P2
   ```

3. **View the board to see all tasks**
   ```
   /wicked-garden:kanban:board-status
   ```
   Verify all three tasks appear under the "Auth Feature" project.

4. **Move first task to "In Progress" using native task tools**
   Use `TaskUpdate` to set the first task to `in_progress`. The PostToolUse hook syncs this to the kanban board automatically.

5. **Add a comment documenting progress**
   ```
   /wicked-garden:kanban:comment AUTH_PROJECT_ID TASK_ID "Completed wireframes for login page"
   ```

6. **Complete the task**
   Use `TaskUpdate` to set the task status to `completed`. The hook syncs this to the kanban "done" swimlane.

7. **View final board state**
   ```
   /wicked-garden:kanban:board-status
   ```
   Verify the completed task appears in "Done" and remaining tasks are still in "To Do".

## Expected Outcomes

- Three tasks appear on the board under "Auth Feature" project
- New tasks start in "To Do" swimlane with correct priorities (P1, P1, P2)
- Task moves to "In Progress" when updated via TaskUpdate
- Comment is visible on the task
- Completed task appears in "Done" swimlane
- Board status shows task distribution across swimlanes
- Activity log captures task creation, status changes, and comments

## Success Criteria

- [ ] Project "Auth Feature" is created or reused automatically
- [ ] Tasks created with correct priorities via slash command
- [ ] TaskUpdate status changes sync to kanban swimlanes
- [ ] Comment added and visible on task
- [ ] Board status shows accurate swimlane counts
- [ ] All data persists across board-status calls

## Value Demonstrated

Claude can manage persistent tasks that survive across sessions. Unlike TodoWrite tasks that disappear when a session ends, kanban tasks persist via the Control Plane and can be accessed from any Claude Code session. This makes wicked-kanban ideal for managing ongoing work, tracking project progress, and maintaining visibility into what needs to be done.
