---
description: Check the Control Plane status for workbench integration
---

# /wicked-garden:kanban:start-api

The kanban data API is now served by the **wicked-control-plane** (CP) at `http://localhost:18889`. A separate server is no longer needed.

## Instructions

Check that the CP is running:

```bash
curl -s http://localhost:18889/health
```

If not running, start it:

```bash
cd ~/Projects/wicked-viewer && npm start &
```

## Kanban API Endpoints (via CP)

All kanban data is available at `/api/v1/data/kanban/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/data/kanban/projects/list` | GET | List all projects |
| `/api/v1/data/kanban/projects/get/:id` | GET | Get project details |
| `/api/v1/data/kanban/tasks/list` | GET | List tasks (filter: ?project_id=) |
| `/api/v1/data/kanban/tasks/get/:id` | GET | Get task details |
| `/api/v1/data/kanban/tasks/search` | GET | Search tasks (?q=query) |
| `/api/v1/data/kanban/tasks/stats` | GET | Task statistics |
| `/api/v1/data/kanban/initiatives/list` | GET | List initiatives |
| `/api/v1/data/kanban/comments/list/:taskId` | GET | List task comments |
| `/api/v1/data/kanban/activity/list` | GET | Activity log |
| `/api/v1/data/kanban/board/:projectId` | GET | Board state |

## CLI Access

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" kanban tasks list --project_id my-project
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" kanban tasks search --q "bug"
```

## Notes

- The CP runs on port 18889 (configurable via config.json)
- Workbench connects to the CP directly
- Use `python3 scripts/cp.py manifest` to see all available endpoints
