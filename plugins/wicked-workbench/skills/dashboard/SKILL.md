---
name: dashboard
description: |
  Generate and render A2UI dashboards from wicked-garden plugins.
  Claude Code generates the dashboard layout, workbench renders it with live MCP data.
---

# Dashboard Skill

Generate visual dashboards combining data from multiple wicked-garden plugins.

## When to Use

- User wants a custom view of tasks, memories, or plugin data
- "Show me blocked tasks with context"
- "Create a dashboard for sprint planning"
- "Visualize my project status"

## Instructions

### 1. Check Server Status

```bash
curl -s http://localhost:18889/health
```

If not running, start it:

```bash
uvx wicked-workbench-server &
```

### 2. Get Available Components

Fetch the catalog to see what components are available:

```bash
curl -s http://localhost:18889/api/catalogs
```

### 3. Generate A2UI Document

Based on the user's request, generate an A2UI document. Example structure:

```json
[
  {"createSurface": {"surfaceId": "dashboard", "catalogId": "workbench"}},
  {"updateComponents": {"surfaceId": "dashboard", "components": [
    {"id": "root", "component": "Row", "children": ["tasks", "context"]},
    {"id": "tasks", "component": "TaskList", "title": "Blocked Tasks", "children": ["task-1"]},
    {"id": "task-1", "component": "TaskCard", "title": "Fix auth", "status": "blocked"}
  ]}}
]
```

### 4. Send to Workbench

```bash
curl -X POST http://localhost:18889/api/render \
  -H "Content-Type: application/json" \
  -d '{"document": <your A2UI JSON>, "fetch_data": true}'
```

### 5. Present Results

- Dashboard URL: http://localhost:18889
- Components rendered
- Data fetched from MCP servers

## Component Mapping

| User Request | Components |
|--------------|------------|
| "blocked tasks" | TaskList + TaskCard (status=blocked) |
| "high priority" | TaskList + TaskCard (priority=high) |
| "with context" | Add MemoryPanel + MemoryItem |
| "kanban board" | KanbanBoard + TaskCard |
| "decisions" | MemoryPanel + MemoryItem (type=decision) |

## Integration

Works standalone. Enhanced with:

| Plugin | Data Source |
|--------|-------------|
| wicked-kanban | Tasks via MCP (port 18888) |
| wicked-mem | Memories via MCP (port 18890) |
