---
name: dashboard-persistence
title: Dashboard Persistence and Retrieval
description: Save, list, and reload dashboards across sessions
type: dashboard
difficulty: intermediate
estimated_minutes: 8
---

# Dashboard Persistence and Retrieval

Demonstrates saving dashboards to the Workbench database so they can be reloaded in future sessions. This proves dashboards are not ephemeral - they're persistent artifacts that can be shared and revisited.

## Setup

Ensure Workbench is running with database enabled (default):

```bash
wicked-workbench
```

Create some test data:

```bash
# In Claude Code
/wicked-kanban:task create "Deploy to production" --priority high
/wicked-kanban:task create "Fix critical bug" --priority high
/wicked-kanban:task create "Update docs" --priority low
```

## Steps

### 1. Generate Initial Dashboard

In Claude Code:

```
Create a dashboard showing high priority tasks
```

Claude generates and sends A2UI to Workbench. Dashboard appears at http://localhost:18889.

### 2. Save the Dashboard

```bash
curl -X POST http://localhost:18889/api/dashboards \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Priority Tasks",
    "description": "Dashboard showing all high priority tasks from kanban",
    "tags": ["tasks", "priority", "kanban"]
  }'
```

This saves the currently displayed dashboard.

### 3. List Saved Dashboards

```bash
curl http://localhost:18889/api/dashboards | jq .
```

### 4. Generate a Different Dashboard

In Claude Code:

```
Show all tasks grouped by status
```

This replaces the current dashboard view.

### 5. Reload the Saved Dashboard

Get dashboard by ID and send its document to /api/render to restore the view.

### 6. Update Dashboard Metadata

Update name and tags via PUT /api/dashboards/{id}.

## Expected Outcome

### Step 1: Dashboard Generation
Dashboard appears showing high priority tasks.

### Step 2: Save Response
Returns dashboard ID with metadata (name, description, tags, timestamps).

### Step 3: List Dashboards
Shows saved dashboard with preview (component count, data sources).

### Step 4: Different Dashboard
Browser shows new dashboard (tasks by status).

### Step 5: Restored Dashboard
Original high priority dashboard is re-rendered.

### Step 6: Update Response
Returns updated metadata with new timestamp.

## Success Criteria

- [ ] Dashboard can be saved via POST /api/dashboards
- [ ] Save returns dashboard ID
- [ ] Saved dashboards appear in GET /api/dashboards list
- [ ] Dashboard metadata (name, description, tags) is persisted
- [ ] Dashboard A2UI document is persisted
- [ ] Saved dashboard can be retrieved by ID
- [ ] Retrieved dashboard can be re-rendered via /api/render
- [ ] Dashboard metadata can be updated via PUT /api/dashboards/{id}
- [ ] Dashboards persist across Workbench restarts

## Value Demonstrated

**Dashboard as artifact**: Dashboards aren't just transient views - they're saved configurations that can be revisited, shared, and version-controlled.

**Session independence**: Generate a dashboard once, reload it anytime. No need to regenerate A2UI from Claude Code each time.

**Dashboard library**: Build up a collection of useful dashboards over time. "Sprint Planning", "Production Metrics", "Data Quality Overview", etc.

**Collaboration**: Save a dashboard configuration and share the ID with teammates. Everyone sees the same view structure with their own live data.

**Real-world use**: Standard reporting dashboards that teams check daily, incident response dashboards pre-configured for common scenarios, executive dashboards showing key metrics, onboarding dashboards showing new team member relevant views.
