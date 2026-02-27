---
name: basic-task-workflow
title: Basic Task Workflow
description: Claude creates a project and manages tasks through the full lifecycle
type: workflow
difficulty: basic
estimated_minutes: 5
---

# Basic Task Workflow

Test that Claude can create and manage tasks through the full lifecycle using kanban.py.

## Setup

Ensure the kanban data directory exists and the kanban.py script is accessible.

```bash
# Verify script is available
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-projects
```

## Steps

1. **Create a new project**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-project "Auth Feature" -d "User authentication implementation"
   ```
   Note the project ID from the output.

2. **View the project details**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-project PROJECT_ID
   ```
   Shows swimlanes and any existing tasks.

3. **Create tasks**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Design login flow" -p P1 -d "Create wireframes and user flow for login process"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Implement JWT tokens" -p P1 -d "Add JWT generation and validation"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Add password reset" -p P2 -d "Email-based password reset flow"
   ```
   Note the task IDs for the next steps.

4. **Move first task to "In Progress"**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane in_progress
   ```

5. **Add a comment documenting progress**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT_ID TASK_ID "Completed wireframes for login page"
   ```

6. **Move task to "Done"**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane done
   ```

7. **View final project state**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-project PROJECT_ID
   ```

8. **View activity log**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py activity PROJECT_ID
   ```

## Expected Outcome

- Project created with default swimlanes (todo, in_progress, done)
- Tasks created and start in "todo" swimlane
- Task moves through swimlanes correctly
- Comments are attached to tasks
- Activity log captures all changes
- Final state shows completed task in "done" swimlane

## Success Criteria

- [ ] Project created with 3 default swimlanes
- [ ] Tasks created with correct priorities
- [ ] Task successfully moved through swimlanes
- [ ] Comment added and visible on task
- [ ] Activity log shows task_created, swimlane_changed, comment entries
- [ ] All data persists (visible in get-project)

## Value Demonstrated

Claude can manage persistent tasks that survive across sessions. Unlike TodoWrite tasks that disappear when a session ends, kanban tasks persist in file storage and can be accessed from any Claude Code session. This makes wicked-kanban ideal for managing ongoing work, tracking project progress, and maintaining visibility into what needs to be done. For visual dashboards, use wicked-workbench to render the kanban board.
