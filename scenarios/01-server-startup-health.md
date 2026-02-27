---
name: server-startup-health
title: Server Startup and Health Check
description: Verify Workbench server starts and discovers plugin data sources
type: setup
difficulty: basic
estimated_minutes: 5
---

# Server Startup and Health Check

Verifies that Workbench starts successfully, exposes its API, and discovers plugin data sources via the data gateway.

## Setup

No additional setup required. Ensure you have the workbench server available:

```bash
uvx --from wicked-workbench-server wicked-workbench --help
```

## Steps

### 1. Start Workbench Server

In Claude Code:

```
/wicked-workbench:workbench start
```

Or directly from terminal:

```bash
uvx --from wicked-workbench-server wicked-workbench
```

### 2. Verify Health Endpoint

```bash
curl http://localhost:18889/health
```

### 3. Check Data Sources

```bash
curl http://localhost:18889/api/v1/data/plugins
```

### 4. Check Legacy Plugin Discovery

```bash
curl http://localhost:18889/api/plugins
```

### 5. Check MCP Server Status

```bash
curl http://localhost:18889/api/servers
```

## Expected Outcome

### Step 1: Server Startup
```
Starting Wicked Workbench at http://127.0.0.1:18889
Dashboard UI: http://127.0.0.1:18889/
API docs: http://127.0.0.1:18889/docs
```

### Step 2: Health Check
```json
{
  "status": "healthy",
  "service": "wicked-workbench"
}
```

### Step 3: Data Sources
```json
{
  "plugins": [
    {
      "name": "wicked-kanban",
      "schema_version": "1.0.0",
      "sources": [
        {"name": "projects", "description": "...", "capabilities": ["list", "get", "create", "update", "delete"]},
        {"name": "tasks", "description": "...", "capabilities": ["list", "get", "search", "stats", "create", "update", "delete"]}
      ]
    }
  ],
  "meta": {
    "total_plugins": 7,
    "total_sources": 24,
    "schema_version": "1.0.0"
  }
}
```

Note: Actual plugin count depends on which plugins are installed and have `wicked.json` with data sources.

### Step 4: Legacy Plugin Discovery
Returns list of all installed wicked-garden plugins with metadata from their `plugin.json`.

### Step 5: MCP Server Status
Returns status of configured MCP server connections (may be empty if none configured).

## Success Criteria

- [ ] Server starts without errors
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] Data gateway discovers at least one plugin with data sources
- [ ] MCP server status endpoint responds
- [ ] Server is accessible at http://localhost:18889
- [ ] Dashboard UI loads in browser

## Value Demonstrated

**Zero-configuration startup**: Workbench starts with no configuration required and automatically discovers installed plugins and their data sources.

**Plugin data gateway**: The `/api/v1/data/plugins` endpoint shows all plugins that expose data via `wicked.json`, enabling unified data access across the ecosystem.

**Real-world use**: Before generating dashboards, verify what data sources are available, ensuring Claude Code has the building blocks it needs.
