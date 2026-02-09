---
name: multi-plugin-dashboard
title: Multi-Plugin Dashboard Composition
description: Combine components from multiple plugins in a single dashboard
type: integration
difficulty: intermediate
estimated_minutes: 12
---

# Multi-Plugin Dashboard Composition

Demonstrates composing a dashboard from components provided by multiple plugins. This proves Workbench can orchestrate data fetching from multiple MCP servers and render a unified view.

## Setup

Install multiple plugins with component catalogs:

```bash
pip install wicked-kanban wicked-mem
```

Create test data in both systems:

```bash
# Create tasks
/wicked-kanban:task create "Implement user auth" --priority high
/wicked-kanban:task create "Add logging" --priority medium --status blocked

# Store memories
/wicked-mem:store "Decided to use JWT for authentication" --type decision
/wicked-mem:store "Auth implementation should handle refresh tokens" --type requirement
```

Start Workbench:

```bash
wicked-workbench
```

## Steps

### 1. Verify Multiple Catalogs Available

```bash
curl http://localhost:18889/api/catalogs | jq '.[] | .catalogId'
```

Expected:
```
"workbench"
"kanban"
"memory"
```

### 2. Request Multi-Plugin Dashboard

In Claude Code:

```
Create a dashboard showing:
- High priority tasks from kanban
- Recent decisions from memory
Put them side by side
```

### 3. Claude Generates Composed A2UI

Claude generates A2UI with components from multiple catalogs:
- Row/Column layout (workbench catalog)
- TaskList component (kanban catalog)
- MemoryList component (memory catalog)

### 4. Verify Data from Both Sources

Check MCP connections:

```bash
curl http://localhost:18889/api/servers
```

### 5. View Rendered Dashboard

Open http://localhost:18889 to see both data sources rendered together.

## Expected Outcome

### Step 1: Multiple Catalogs
Returns: `"workbench"`, `"kanban"`, `"memory"`

### Step 2: Claude Response
Generates A2UI combining components from both plugins.

### Step 3: Multi-Source A2UI
- Layout: Row, Column, Text (workbench)
- Data: TaskList (kanban), MemoryList (memory)

### Step 4: MCP Server Status
Both kanban (port 18888) and memory (port 18890) show "connected".

### Step 5: Rendered Dashboard
Two columns: High Priority Tasks (left) + Recent Decisions (right)

## Success Criteria

- [ ] Multiple component catalogs are discovered
- [ ] Claude Code generates A2UI using components from 2+ catalogs
- [ ] Layout components (Row, Column) structure the dashboard
- [ ] TaskList fetches data from kanban MCP server
- [ ] MemoryList fetches data from memory MCP server
- [ ] Both data sources render in the same dashboard
- [ ] Dashboard shows current data from both sources

## Value Demonstrated

**Cross-plugin composition**: Users can create dashboards that combine data from multiple sources without worrying about API integration details.

**Unified data view**: Instead of switching between tools, see related information in one place. Example: tasks + relevant decisions, tasks + relevant documentation, tasks + data quality metrics.

**Catalog-driven design**: Adding new plugins with component catalogs automatically makes their components available for dashboard composition. No code changes to Workbench required.

**Real-world use**: Executive dashboards combining metrics from multiple systems, sprint planning views showing tasks + team velocity + recent decisions, incident response dashboards showing alerts + runbooks + recent changes.
