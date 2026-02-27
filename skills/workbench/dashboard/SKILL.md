---
name: dashboard
description: |
  Generate and render A2UI dashboards from wicked-garden plugins.
  Claude Code generates the dashboard layout, workbench renders it with live plugin data.
---

# Dashboard Skill

Generate visual dashboards combining data from multiple wicked-garden plugins.

## When to Use

- User wants a custom view of tasks, memories, or plugin data
- "Show me blocked tasks with context"
- "Create a dashboard for sprint planning"
- "Visualize my project status"

## References

- [Installation & Setup](refs/installation.md) — where the code lives, install methods, configuration, troubleshooting

## Instructions

### 1. Check Server Status

```bash
curl -s http://localhost:18889/health
```

If not running, start it:

```bash
uvx --from wicked-workbench-server wicked-workbench &
```

### 2. Get Available Data Sources

Fetch discovered plugins and their data sources:

```bash
curl -s http://localhost:18889/api/v1/data/plugins
```

### 3. Query Plugin Data

Use the data gateway to fetch live data for your dashboard:

```bash
# List tasks
curl -s http://localhost:18889/api/v1/data/wicked-kanban/tasks/list

# Search memories
curl -s "http://localhost:18889/api/v1/data/wicked-mem/memories/search?query=decisions"

# Get project phases
curl -s http://localhost:18889/api/v1/data/wicked-crew/phases/list
```

### 4. Generate A2UI Document

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

### 5. Send to Workbench

```bash
curl -X POST http://localhost:18889/api/render \
  -H "Content-Type: application/json" \
  -d '{"document": <your A2UI JSON>, "fetch_data": true}'
```

### 6. Present Results

- Dashboard URL: http://localhost:18889
- Components rendered
- Data fetched via the plugin data gateway

## Component Mapping

| User Request | Components |
|--------------|------------|
| "blocked tasks" | TaskList + TaskCard (status=blocked) |
| "high priority" | TaskList + TaskCard (priority=high) |
| "with context" | Add MemoryPanel + MemoryItem |
| "kanban board" | KanbanBoard + TaskCard |
| "decisions" | MemoryPanel + MemoryItem (type=decision) |

## Integration

Works standalone. Enhanced with any plugin that declares data sources in `wicked.json`:

| Plugin | Data Source |
|--------|-------------|
| wicked-kanban | Tasks, projects, initiatives, activity, comments |
| wicked-mem | Memories, sessions |
| wicked-crew | Projects, phases, specialists, artifacts, signals |
| wicked-search | Symbols, documents, graph, lineage, coverage, layers, hotspots |
| wicked-delivery | Sprints, metrics |
| wicked-smaht | Context assembly |
| wicked-jam | Decisions |
