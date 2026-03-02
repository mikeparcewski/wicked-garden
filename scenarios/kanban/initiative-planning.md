---
name: initiative-planning
title: Initiative Planning
description: Claude helps plan and execute a time-boxed initiative
type: workflow
difficulty: intermediate
estimated_minutes: 7
---

# Initiative Planning

Test initiative creation and management for time-boxed work using kanban slash commands.

## Setup

No special setup needed beyond an active wicked-garden session.

## Steps

1. **Name a session to create an initiative**
   ```
   /wicked-garden:kanban:name-session "Q1 Dashboard Sprint"
   ```
   This creates an initiative that groups related tasks together.

2. **Add several tasks to the backlog**
   ```
   /wicked-garden:kanban:new-task "User dashboard" --project "Q1 Features" --priority P1
   /wicked-garden:kanban:new-task "API rate limiting" --project "Q1 Features" --priority P1
   /wicked-garden:kanban:new-task "Email notifications" --project "Q1 Features" --priority P2
   /wicked-garden:kanban:new-task "Analytics dashboard" --project "Q1 Features" --priority P2
   /wicked-garden:kanban:new-task "Mobile responsive" --project "Q1 Features" --priority P3
   ```

3. **View the board to see the initiative's backlog**
   ```
   /wicked-garden:kanban:board-status
   ```
   All tasks should appear under the "Q1 Features" project, grouped by the initiative.

4. **Work through the initiative tasks**
   Start the first P1 task using `TaskUpdate` (status: `in_progress`).
   Add a progress comment:
   ```
   /wicked-garden:kanban:comment PROJECT_ID DASHBOARD_TASK_ID "Implementing chart components for user metrics"
   ```
   Complete the task using `TaskUpdate` (status: `completed`).

5. **Continue with the second P1 task**
   Use `TaskUpdate` to start the rate limiting task (`in_progress`), then complete it (`completed`).

6. **Check board progress mid-initiative**
   ```
   /wicked-garden:kanban:board-status
   ```
   Should show 2 tasks done, 3 remaining in To Do. P1 tasks are completed first.

7. **Add a summary comment about initiative progress**
   ```
   /wicked-garden:kanban:comment PROJECT_ID ANY_TASK_ID "Initiative progress: 2/5 tasks complete. Core dashboard features delivered. Remaining: notifications, analytics, mobile."
   ```

8. **View final board state**
   ```
   /wicked-garden:kanban:board-status
   ```
   Board shows the initiative's progress: completed P1 items and remaining P2/P3 backlog.

## Expected Outcomes

- Initiative created via name-session groups related tasks
- Tasks are created with appropriate priorities (P1 for core, P2/P3 for nice-to-haves)
- Work proceeds in priority order (P1 first, then P2, then P3)
- Board status shows progress through the initiative
- Comments document progress and decisions
- Initiative provides a focused view of time-boxed work

## Success Criteria

- [ ] Initiative created via name-session command
- [ ] Tasks grouped under the initiative's project
- [ ] P1 tasks worked first, reflecting priority-based planning
- [ ] Board status shows accurate progress (done vs remaining)
- [ ] Comments provide narrative of initiative progress
- [ ] Initiative history preserved for retrospectives

## Value Demonstrated

Time-boxed initiatives help organize work into focused iterations with clear goals. Claude can help plan initiatives, create prioritized tasks, and track progress against initiative goals. The session-naming feature connects Claude Code sessions to kanban initiatives, making it easy to see what was accomplished in each work session.
