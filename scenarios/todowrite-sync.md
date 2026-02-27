---
name: todowrite-sync
title: TaskCreate/TaskUpdate Auto-Sync
description: TaskCreate and TaskUpdate calls are automatically synced to the kanban board via hook
type: integration
difficulty: basic
estimated_minutes: 3
---

# TaskCreate/TaskUpdate Auto-Sync

Test that TaskCreate and TaskUpdate calls are automatically captured and synced to a project on the kanban board.

## Setup

The PostToolUse hook should be active (loaded at session start).

```bash
# Verify kanban CLI works
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py list-projects
```

Note any existing projects. New tasks will be synced to a project bound to the current repo.

## Steps

1. **Use TaskCreate to create tasks**
   Ask Claude to work on something that requires task tracking:
   ```
   User: "Help me refactor the authentication module. Break it down into steps."
   ```
   Claude should use TaskCreate to track the steps.

2. **Check the kanban board**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py list-projects
   ```
   Look for a project bound to the current repo (auto-created if needed).

3. **View the synced tasks**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID
   ```
   Tasks from TaskCreate should appear.

4. **Update task status via TaskUpdate**
   As Claude works, it marks tasks as in_progress and completed.
   Verify changes with:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py list-tasks PROJECT_ID
   ```

5. **Verify activity log**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py activity PROJECT_ID
   ```
   Should show task_created and swimlane_changed entries.

## Expected Outcome

- A project is auto-created or existing project is used (bound to repo)
- TaskCreate tasks appear as kanban tasks in "todo" swimlane
- When Claude marks tasks in_progress, they move to "in_progress"
- When Claude marks tasks completed, they move to "done"
- Activity log records all changes

## Success Criteria

- [ ] Project exists after TaskCreate is used
- [ ] Tasks from TaskCreate appear on the board
- [ ] Task status changes sync correctly (pending → todo, in_progress → in_progress, completed → done)
- [ ] Activity log shows sync events

## Value Demonstrated

No tasks are lost - even quick TaskCreate tasks get persistent tracking. Claude uses its familiar TaskCreate/TaskUpdate interface while wicked-kanban captures everything for long-term visibility. This bridge between Claude's native task tools and the persistent kanban means:

1. Claude doesn't need to change behavior - TaskCreate just works
2. Users get persistent tracking of all Claude's work
3. Quick session-based tasks are preserved for future reference
4. Teams can see Claude's task progress at any time

This approach combines the best of both worlds: Claude's efficient task workflow and persistent, searchable task management.
