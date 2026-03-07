---
description: Add a comment to a task
argument-hint: "<project_id> <task_id> <comment_content>"
user_facing: true
allowed_tools:
  - Bash
---

# /wicked-garden:kanban:comment

Add a comment to an existing task on the kanban board.

## Arguments

- `project_id` (required): The project ID containing the task
- `task_id` (required): The task ID to comment on
- `comment_content` (required): The comment text to add

## Instructions

1. Parse the three required arguments from user input: project_id, task_id, and comment_content

2. Add the comment to the task via the local kanban store (primary):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" add-comment "${PROJECT_ID}" "${TASK_ID}" "${COMMENT_CONTENT}"
   ```

   Data is persisted via DomainStore (local JSON files).

3. If the command succeeds, confirm the comment was added. If it fails, report the error.

## Example Usage

```
/wicked-garden:kanban:comment my-project task-abc123 "Updated implementation approach after code review"
```

## Output

Confirm the comment was added with:
- Task ID
- Project ID
- Comment content summary
