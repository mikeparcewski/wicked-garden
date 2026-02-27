---
description: Show current kanban board state with projects and tasks
---

# /wicked-garden:kanban-board-status

Display current kanban board state.

## Instructions

1. List all projects:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py list-projects
   ```

2. For the main project (or user-specified), get tasks by swimlane:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py list-tasks PROJECT_ID --swimlane todo
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py list-tasks PROJECT_ID --swimlane in_progress
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py list-tasks PROJECT_ID --swimlane done
   ```

3. Check recent activity:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py activity PROJECT_ID --limit 10
   ```

4. Summarize:
   - Number of projects
   - Tasks by swimlane (To Do, In Progress, Done)
   - Recent activity

## Output Format

Present a concise summary:

```
## Kanban Board Status

**Projects**: 2 active

### Project: User Authentication (abc12345)
- To Do: 3 tasks
- In Progress: 1 task (Implement JWT service)
- Done: 2 tasks

**Recent Activity**:
- Task created: "Add logout endpoint"
- Status change: "JWT service" → in_progress
- Commit linked: abc1234
```
