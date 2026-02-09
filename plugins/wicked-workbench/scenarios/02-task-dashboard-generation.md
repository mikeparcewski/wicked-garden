---
name: task-dashboard-generation
title: End-to-End Task Dashboard Generation
description: Generate and render a task dashboard from natural language request
type: dashboard
difficulty: basic
estimated_minutes: 8
---

# End-to-End Task Dashboard Generation

Demonstrates the complete workflow from natural language request to rendered dashboard. Claude Code generates A2UI JSON, Workbench renders it, and live task data is fetched from the kanban MCP server.

## Setup

Ensure wicked-kanban is installed and has some tasks:

```bash
# Install kanban if needed
pip install wicked-kanban

# In Claude Code, create test tasks
/wicked-kanban:task create "Fix authentication bug" --priority high
/wicked-kanban:task create "Update documentation" --priority medium
/wicked-kanban:task create "Refactor API layer" --priority high
```

Start Workbench:

```bash
wicked-workbench
```

## Steps

### 1. Request Dashboard from Claude Code

In Claude Code conversation:

```
Show my high priority tasks in a dashboard
```

### 2. Claude Code Generates A2UI

Claude Code reads kanban catalog, generates A2UI with TaskList component, and sends to POST /api/render.

### 3. Verify Dashboard Rendered

Open http://localhost:18889 to see dashboard with task data.

### 4. Check Current Document

```bash
curl http://localhost:18889/api/current
```

## Expected Outcome

### Step 1: Claude Code Response
Generates and sends A2UI to Workbench.

### Step 2: Dashboard Rendered
POST /api/render processes the A2UI.

### Step 3: Browser View
Shows high priority tasks with live data from kanban MCP server.

### Step 4: Current Document
Returns surfaceId, catalogId, components, and timestamp.

## Success Criteria

- [ ] Claude Code successfully reads kanban catalog
- [ ] A2UI JSON is generated with TaskList component
- [ ] POST /api/render returns 200 OK
- [ ] Dashboard appears at http://localhost:18889
- [ ] Live task data is displayed (from kanban MCP server)
- [ ] Only high priority tasks are shown (filter applied)
- [ ] /api/current returns the rendered document

## Value Demonstrated

**Natural language to dashboard**: Users describe what they want to see, Claude Code generates the appropriate dashboard structure, no manual JSON writing required.

**Component catalog system**: Claude Code knows which components are available (TaskList, Text, Column) by reading the catalog, ensuring it generates valid A2UI.

**Live data integration**: Dashboard shows current task data from the kanban MCP server, not static snapshots.

**Real-world use**: Project managers can quickly visualize filtered task views without writing code or SQL. "Show blocked tasks", "Show tasks due this week", "Show my team's tasks" all work the same way.
