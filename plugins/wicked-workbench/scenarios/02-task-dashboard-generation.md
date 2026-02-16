---
name: task-dashboard-generation
title: End-to-End Task Dashboard Generation
description: Generate and render a task dashboard from natural language request
type: dashboard
difficulty: basic
estimated_minutes: 8
---

# End-to-End Task Dashboard Generation

Demonstrates the complete workflow from natural language request to rendered dashboard. Claude Code generates A2UI JSON, Workbench renders it, and live task data is fetched from the data gateway.

## Setup

Ensure wicked-kanban is installed and has some tasks. In Claude Code:

```
/wicked-kanban:new-task "Fix authentication bug"
/wicked-kanban:new-task "Update documentation"
/wicked-kanban:new-task "Refactor API layer"
```

Start Workbench:

```
/wicked-workbench:workbench start
```

Verify tasks are accessible via the data gateway:

```bash
curl -s http://localhost:18889/api/v1/data/wicked-kanban/tasks/list | jq '.items | length'
```

## Steps

### 1. Request Dashboard from Claude Code

In Claude Code conversation:

```
Show my high priority tasks in a dashboard
```

### 2. Claude Code Generates A2UI

Claude Code queries the data gateway for task data, generates A2UI with TaskList component, and sends to POST /api/render.

### 3. Verify Dashboard Rendered

Open http://localhost:18889 to see dashboard with task data.

### 4. Query Tasks Directly via Gateway

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list?limit=10" | jq '.items[] | {subject, status}'
```

## Expected Outcome

### Step 1: Claude Code Response
Generates and sends A2UI to Workbench.

### Step 2: Dashboard Rendered
POST /api/render processes the A2UI.

### Step 3: Browser View
Shows tasks with live data fetched via the plugin data gateway.

### Step 4: Direct Gateway Query
```json
[
  {"subject": "Fix authentication bug", "status": "pending"},
  {"subject": "Update documentation", "status": "pending"},
  {"subject": "Refactor API layer", "status": "pending"}
]
```

## Success Criteria

- [ ] Tasks are accessible via data gateway endpoint
- [ ] Claude Code generates A2UI with task components
- [ ] POST /api/render returns 200 OK
- [ ] Dashboard appears at http://localhost:18889
- [ ] Live task data is displayed from the data gateway
- [ ] Task filtering works (by status, priority, etc.)

## Value Demonstrated

**Natural language to dashboard**: Users describe what they want to see, Claude Code generates the appropriate dashboard structure.

**Unified data gateway**: Task data is fetched through the workbench data gateway, providing a single API surface for all plugin data.

**Real-world use**: Project managers can quickly visualize filtered task views without writing code. "Show blocked tasks", "Show tasks due this week" all work the same way.
