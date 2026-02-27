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

Start with a clean slate to demonstrate persistence clearly.

```bash
# List existing projects to see baseline
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-projects
```

## Steps

1. **Create a project and tasks in the current session**
   ```bash
   # Create project
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-project "Long-Running Work" -d "Work that spans multiple sessions"
   # Note PROJECT_ID from output

   # Create several tasks
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Refactor authentication module" -p P1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Update API documentation" -p P2
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Fix mobile responsive issues" -p P2
   # Note TASK_1_ID, TASK_2_ID, TASK_3_ID from outputs

   # Start work on first task
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_1_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT_ID TASK_1_ID "Started refactoring - extracted auth logic to separate module"
   ```

2. **Verify data is stored on disk**
   ```bash
   # Check the project file exists
   ls ~/.something-wicked/wicked-kanban/projects/

   # Verify project data
   cat ~/.something-wicked/wicked-kanban/projects/PROJECT_ID/project.json | head -50
   ```
   Should show the project with all three tasks.

3. **Simulate session end by closing and reopening terminal**
   In a real scenario, this would be:
   - Closing Claude Code
   - Restarting your computer
   - Starting a new session the next day

   For this test, we simply verify the data persists by reading from disk:
   ```bash
   # Data is still there
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-projects
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-project PROJECT_ID
   ```

4. **Continue work in the "new session"**
   ```bash
   # Complete the in-progress task
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-commit PROJECT_ID TASK_1_ID "refactor-auth-abc123"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT_ID TASK_1_ID "Refactoring complete - all tests passing"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_1_ID --swimlane done

   # Start second task
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_2_ID --swimlane in_progress
   ```

5. **Verify all history is preserved**
   ```bash
   # Check activity log for full history
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py activity PROJECT_ID
   ```
   Should show task_created, swimlane_changed, comment, commit_linked entries across the "session break".

6. **Verify task details show accumulated work**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-task PROJECT_ID TASK_1_ID
   ```
   Should show commits array with the linked commit hash and multiple comments.

## Expected Outcome

- Tasks created in one session are visible in subsequent sessions
- Task status, comments, and commits all persist
- Activity log preserves complete history
- Work can seamlessly continue across sessions
- No data loss between sessions

## Success Criteria

- [ ] Project and tasks visible after simulated "new session"
- [ ] Task swimlanes, priorities, and descriptions persist
- [ ] Comments added are still present
- [ ] Commits linked are preserved
- [ ] Activity log shows full history
- [ ] No data loss

## Value Demonstrated

The core value of wicked-kanban is persistence. Unlike TodoWrite tasks that disappear when a Claude Code session ends, wicked-kanban tasks survive across:

1. **Claude Code sessions** - Close and reopen Claude Code, tasks remain
2. **Days/weeks of work** - Long-running projects stay organized
3. **Team coordination** - Tasks are always available via shared files

This makes wicked-kanban essential for:
- Multi-day development efforts
- Team coordination (tasks are always available)
- Project continuity (no lost context between sessions)
- Onboarding (new team members see full work history)

The file-based storage (~/.something-wicked/wicked-kanban/projects/) ensures data is durable and can even be version-controlled or backed up.
