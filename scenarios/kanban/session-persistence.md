---
name: session-persistence
title: Session Persistence and Recovery
description: Verify tasks persist across Claude Code sessions
type: integration
difficulty: basic
estimated_minutes: 4
---

# Session Persistence and Recovery

Test that tasks persist across Claude Code sessions, demonstrating the core value proposition of wicked-kanban.

## Setup

Start with a baseline view of existing projects.

```
/wicked-garden:kanban:board-status
```

Note any existing projects so new work is clearly distinguishable.

## Steps

1. **Name the session and create tasks**
   ```
   /wicked-garden:kanban:name-session "Long-Running Work"
   ```
   Then create several tasks:
   ```
   /wicked-garden:kanban:new-task "Refactor authentication module" --project "Long-Running Work" --priority P1
   /wicked-garden:kanban:new-task "Update API documentation" --project "Long-Running Work" --priority P2
   /wicked-garden:kanban:new-task "Fix mobile responsive issues" --project "Long-Running Work" --priority P2
   ```

2. **Start work on first task**
   Use `TaskUpdate` to set the first task to `in_progress`, then add a comment:
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID "Started refactoring - extracted auth logic to separate module"
   ```

3. **Verify board shows current state**
   ```
   /wicked-garden:kanban:board-status
   ```
   Should show 1 task in progress, 2 tasks in To Do.

4. **Simulate session end and recovery**
   In a real scenario, the user would close Claude Code and start a new session.
   For this test, verify the data is still accessible by checking the board again:
   ```
   /wicked-garden:kanban:board-status
   ```
   All tasks, statuses, and comments should still be visible.

5. **Continue work in the "new session"**
   Complete the in-progress task using `TaskUpdate` (status: `completed`), then add a comment:
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID "Refactoring complete - all tests passing"
   ```
   Start the second task using `TaskUpdate` (status: `in_progress`).

6. **Verify full history is preserved**
   ```
   /wicked-garden:kanban:board-status
   ```
   Should show: 1 task done, 1 in progress, 1 in To Do. All comments and status history should be intact.

## Expected Outcomes

- Tasks created in one session are visible in subsequent sessions
- Task status, comments, and initiative assignment all persist
- Board status accurately reflects accumulated changes
- Work can seamlessly continue across sessions
- Session name (initiative) groups related tasks together
- No data loss between sessions

## Success Criteria

- [ ] Project and tasks visible after simulated "new session"
- [ ] Task swimlanes and priorities persist
- [ ] Comments added are still present
- [ ] Board status shows correct task distribution
- [ ] Initiative groups session work together
- [ ] No data loss

## Value Demonstrated

The core value of wicked-kanban is persistence. Unlike TodoWrite tasks that disappear when a Claude Code session ends, wicked-kanban tasks survive across:

1. **Claude Code sessions** - Close and reopen Claude Code, tasks remain
2. **Days/weeks of work** - Long-running projects stay organized
3. **Team coordination** - Tasks are always available via the Control Plane

This makes wicked-kanban essential for:
- Multi-day development efforts
- Team coordination (tasks are always available)
- Project continuity (no lost context between sessions)
- Onboarding (new team members see full work history)
