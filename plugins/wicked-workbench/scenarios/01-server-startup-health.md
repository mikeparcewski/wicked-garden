---
name: server-startup-health
title: Server Startup and Health Check
description: Verify Workbench server starts and discovers plugin ecosystem
type: setup
difficulty: basic
estimated_minutes: 5
---

# Server Startup and Health Check

Verifies that Workbench starts successfully, exposes its API, and discovers the plugin ecosystem. This proves the foundation for all dashboard rendering workflows.

## Setup

No additional setup required. Ensure you have wicked-workbench installed:

```bash
pip install wicked-workbench
```

Optionally install plugins with component catalogs:

```bash
pip install wicked-kanban wicked-mem
```

## Steps

### 1. Start Workbench Server

In Claude Code:

```
/wicked-workbench:workbench
```

Or directly from terminal:

```bash
wicked-workbench
```

### 2. Verify Health Endpoint

```bash
curl http://localhost:18889/health
```

### 3. Check Component Catalogs

```bash
curl http://localhost:18889/api/catalogs
```

### 4. Check MCP Server Status

```bash
curl http://localhost:18889/api/servers
```

### 5. Verify Server is Ready

```bash
curl http://localhost:18889/api/prompt
```

## Expected Outcome

### Step 1: Server Startup
```
Starting Wicked Workbench on http://127.0.0.1:18889
Plugin directory: ~/.claude/plugins
Database: ~/.wicked-workbench/workbench.db
```

### Step 2: Health Check
```json
{
  "status": "ok",
  "version": "0.2.0",
  "uptime": 5
}
```

### Step 3: Component Catalogs
```json
[
  {
    "catalogId": "workbench",
    "version": "1.0.0",
    "description": "Built-in demo components",
    "componentCount": 8
  },
  {
    "catalogId": "kanban",
    "version": "1.0.0",
    "description": "Task management components",
    "componentCount": 5
  },
  {
    "catalogId": "memory",
    "version": "1.0.0",
    "description": "Memory and context components",
    "componentCount": 3
  }
]
```

Note: If no plugins are installed, you'll only see the `workbench` built-in catalog.

### Step 4: MCP Server Status
```json
{
  "kanban": {
    "status": "connected",
    "port": 18888,
    "lastPing": "2026-02-05T10:30:00Z"
  },
  "memory": {
    "status": "connected",
    "port": 18890,
    "lastPing": "2026-02-05T10:30:00Z"
  }
}
```

### Step 5: A2UI Prompt
Should return a detailed system prompt explaining how to generate A2UI JSON from component catalogs.

## Success Criteria

- [ ] Server starts without errors
- [ ] Health endpoint returns `{"status": "ok"}`
- [ ] At least one catalog is discovered (built-in `workbench` catalog)
- [ ] MCP server status endpoint responds (may show no servers if none running)
- [ ] A2UI prompt endpoint returns generation instructions
- [ ] Server is accessible at http://localhost:18889

## Value Demonstrated

**Zero-configuration startup**: Workbench starts with no configuration required and automatically discovers installed plugins and their component catalogs.

**Plugin ecosystem awareness**: The `/api/catalogs` endpoint shows Workbench has successfully scanned the plugin directory and loaded component definitions that Claude Code can use.

**MCP integration readiness**: The `/api/servers` endpoint shows which data sources are available for live dashboard data.

**Real-world use**: Before generating dashboards, you can verify what components and data sources are available, ensuring Claude Code has the building blocks it needs.
