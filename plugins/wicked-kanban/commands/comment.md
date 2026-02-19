---
description: Add a comment to a task
argument-hint: <project_id> <task_id> <comment_content>
user_facing: true
allowed_tools:
  - Bash
---

# /wicked-kanban:comment

Add a comment to an existing task on the kanban board.

## Arguments

- `project_id` (required): The project ID containing the task
- `task_id` (required): The task ID to comment on
- `comment_content` (required): The comment text to add

## Instructions

1. Parse the three required arguments from user input: project_id, task_id, and comment_content

2. Add the comment to the task:
   ```bash
   python3 -c "import json,sys; print(json.dumps({'task_id':sys.argv[1],'project_id':sys.argv[2],'text':sys.argv[3]}))" "${TASK_ID}" "${PROJECT_ID}" "${COMMENT_CONTENT}" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/api.py" create comments
   ```

   Note: The api.py create verb reads a JSON payload from stdin with task_id, project_id, and text fields.

3. If the command succeeds, confirm the comment was added. If it fails, report the error.

## Example Usage

```
/wicked-kanban:comment my-project task-abc123 "Updated implementation approach after code review"
```

## Output

Confirm the comment was added with:
- Task ID
- Project ID
- Comment content summary
