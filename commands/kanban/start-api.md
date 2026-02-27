---
description: Start the data API for wicked-workbench integration
---

# /wicked-garden:kanban:start-api

Start the minimal data API server for wicked-workbench integration.

## Instructions

Start the API server in the background:

```bash
cd ${CLAUDE_PLUGIN_ROOT} && nohup uv run python scripts/api.py --port 18888 > /tmp/wicked-kanban-api.log 2>&1 &
echo "API started on http://localhost:18888"
```

## Verification

Check that the API is running:

```bash
curl -s http://localhost:18888/health | head -20
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/projects` | GET | List all projects |
| `/api/projects/{id}` | GET | Get project details |
| `/api/projects/{id}/tasks` | GET | List tasks (filter: ?swimlane=&initiative=) |
| `/api/projects/{id}/tasks/{tid}` | GET | Get task details |
| `/api/projects/{id}/initiatives` | GET | List initiatives |
| `/api/projects/{id}/swimlanes` | GET | List swimlanes |
| `/api/projects/{id}/activity` | GET | Activity log (?date=&limit=) |
| `/api/projects/{id}/stats` | GET | Task statistics |
| `/api/search` | GET | Search tasks (?q=query&project=) |
| `/api/context` | GET | Active context |
| `/api/mcp/call` | POST | MCP-style tool call |

## Notes

- The API runs on port 18888 by default (configurable via `WICKED_KANBAN_PORT`)
- This is a lightweight data-only API for workbench integration
- No frontend is served - workbench renders the UI
