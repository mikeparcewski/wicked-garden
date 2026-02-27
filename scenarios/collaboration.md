---
name: collaboration
title: Human-Claude Collaboration
description: Human and Claude collaborate through shared kanban state
type: integration
difficulty: basic
estimated_minutes: 5
---

# Human-Claude Collaboration

Test that humans and Claude can collaborate on the same kanban board through shared file-based storage.

## Setup

Understand that wicked-kanban uses file-based storage at `~/.something-wicked/wicked-kanban/` which allows both humans (via external tools or wicked-workbench UI) and Claude (via CLI) to access the same data.

## Steps

1. **Claude creates a project**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Shared Work" -d "Human and Claude working together"
   # Note PROJECT_ID from output
   ```

2. **Claude adds tasks**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Implement feature A" -p P1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Write documentation" -p P2
   # Note TASK_ID_1 and TASK_ID_2
   ```

3. **Verify data is persisted to files**
   ```bash
   ls ~/.something-wicked/wicked-kanban/projects/
   cat ~/.something-wicked/wicked-kanban/projects/PROJECT_ID/project.json
   ```
   Should show the project and tasks in JSON format.

4. **Human can access same data via file system**
   The file-based storage means:
   - External tools can read/modify project.json
   - wicked-workbench can render the board
   - Version control can track changes
   - Backups are straightforward

5. **Claude adds a comment for human context**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID TASK_ID_1 "Started implementation, estimated 2 hours"
   ```

6. **Verify activity log contains comment**
   ```bash
   cat ~/.something-wicked/wicked-kanban/projects/PROJECT_ID/activity.jsonl | tail -5
   ```
   Should show the comment entry with Claude as author.

7. **Simulate human updating a task status**
   In a real scenario, a human would use wicked-workbench or edit the JSON directly.
   For this test, we can use the CLI as if we were the human:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID TASK_ID_1 --swimlane in_progress
   ```

8. **Claude sees the updated status**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-task PROJECT_ID TASK_ID_1
   ```
   The task should now show swimlane as "in_progress".

## Expected Outcome

- Both human and Claude can create, view, and modify the same data
- Changes made by either party are visible to the other
- No conflicts or data corruption when both access the board
- Comments show who made them (via author field)
- File-based storage enables integration with external tools

## Success Criteria

- [ ] Projects and tasks persist to file system
- [ ] Activity log captures all changes with timestamps
- [ ] Data can be read directly from JSON files
- [ ] Multiple parties can work on the board without conflicts
- [ ] Comments include author attribution

## Value Demonstrated

The file-based architecture allows humans and Claude to collaborate naturally. Humans can use wicked-workbench for visual interaction while Claude uses efficient scripts. Both see the same state because it's stored in shared files. This enables workflows where Claude does the heavy lifting while humans review and adjust priorities.
