---
name: artifacts-and-commits
title: Linking Code and Documentation
description: Attach commits, files, and URLs to tasks for traceability
type: feature
difficulty: intermediate
estimated_minutes: 6
---

# Linking Code and Documentation

Test attaching artifacts and commit hashes to tasks to maintain traceability between work and implementation.

## Setup

Create a project with tasks that will have associated code changes and documentation.

```bash
# Create project
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "User Profile Feature" -d "Implement user profile management"
# Note PROJECT_ID from output

# Create tasks
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Add profile API endpoints" -p P1 -d "REST endpoints for profile CRUD"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Frontend profile component" -p P1
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Profile image upload" -p P2
# Note TASK_ID_1, TASK_ID_2, TASK_ID_3 from outputs
```

## Steps

1. **Move first task to In Progress**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID TASK_ID_1 --swimlane in_progress
   ```

2. **Link API documentation as artifact**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-artifact PROJECT_ID TASK_ID_1 "API Design Doc" --type url --url "https://docs.google.com/document/d/abc123"
   ```

3. **Simulate completing work and link commit**
   ```bash
   # Add commit hash (simulate a real commit)
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID TASK_ID_1 "a1b2c3d4"

   # Add comment about the implementation
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID TASK_ID_1 "Implemented GET/POST/PUT/DELETE endpoints with validation"

   # Move to Done
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID TASK_ID_1 --swimlane done
   ```

4. **Work on frontend task with multiple commits and artifacts**
   ```bash
   # Move to In Progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID TASK_ID_2 --swimlane in_progress

   # Link design mockup as file artifact
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-artifact PROJECT_ID TASK_ID_2 "Profile Mockup" --type image --path "/path/to/mockup.png"

   # Add multiple commits as work progresses
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID TASK_ID_2 "e5f6g7h8"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID TASK_ID_2 "Initial component structure"

   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID TASK_ID_2 "i9j0k1l2"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID TASK_ID_2 "Added form validation and API integration"

   # Move to Done
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID TASK_ID_2 --swimlane done
   ```

5. **View task with artifacts and commits**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-task PROJECT_ID TASK_ID_1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-task PROJECT_ID TASK_ID_2
   ```
   Verify the `commits` and `artifacts` arrays contain the linked items.

6. **View activity log showing all changes**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py activity PROJECT_ID
   ```
   Should show artifact_added and commit_linked entries.

## Expected Outcome

- Artifacts (URLs, files, images) are attached to tasks
- Commit hashes are linked to tasks showing what code implemented them
- Multiple artifacts and commits can be attached to a single task
- Activity log tracks all artifact and commit additions
- Full traceability from task to implementation

## Success Criteria

- [ ] Artifacts can be added to tasks with different types (url, file, image, document)
- [ ] Commit hashes are stored and displayed on tasks
- [ ] Multiple commits can be linked to a single task
- [ ] Multiple artifacts can be attached to a single task
- [ ] Activity log records artifact and commit additions
- [ ] Comments provide narrative context for commits

## Value Demonstrated

Maintaining traceability between tasks and code is essential for understanding why changes were made. Claude can automatically link commits to tasks during development, and attach relevant documentation, making it easy to understand the full context of any work item. This is especially valuable during code reviews, debugging, or onboarding new team members.
