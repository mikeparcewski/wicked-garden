---
name: multi-plugin-dashboard
title: Multi-Plugin Dashboard Composition
description: Combine data from multiple plugins in a single dashboard via the data gateway
type: integration
difficulty: intermediate
estimated_minutes: 12
---

# Multi-Plugin Dashboard Composition

Demonstrates composing a dashboard using data from multiple plugins via the data gateway. This proves Workbench can orchestrate data fetching from multiple sources and render a unified view.

## Setup

Ensure multiple plugins with data sources are installed. Verify with:

```bash
curl -s http://localhost:18889/api/v1/data/plugins | jq '.plugins[] | .name'
```

Create test data in both systems. In Claude Code:

```
/wicked-kanban:new-task "Implement user auth"
/wicked-kanban:new-task "Add logging"
/wicked-mem:store "Decided to use JWT for authentication" --type decision
/wicked-mem:store "Auth implementation should handle refresh tokens" --type requirement
```

Start Workbench:

```
/wicked-workbench:workbench start
```

## Steps

### 1. Verify Multiple Data Sources Available

```bash
curl -s http://localhost:18889/api/v1/data/plugins | jq '.plugins[] | {name, sources: [.sources[].name]}'
```

Expected: Multiple plugins with their data sources listed.

### 2. Query Data from Multiple Plugins

```bash
# Tasks from kanban
curl -s http://localhost:18889/api/v1/data/wicked-kanban/tasks/list | jq '.items | length'

# Memories from mem
curl -s http://localhost:18889/api/v1/data/wicked-mem/memories/list | jq '.items | length'
```

### 3. Request Multi-Plugin Dashboard

In Claude Code:

```
Create a dashboard showing:
- Tasks from kanban
- Recent decisions from memory
Put them side by side
```

### 4. Verify Dashboard Uses Multiple Sources

Claude generates A2UI referencing data from both kanban and memory data sources.

### 5. View Rendered Dashboard

Open http://localhost:18889 to see both data sources rendered together.

## Expected Outcome

### Step 1: Multiple Data Sources
```json
[
  {"name": "wicked-kanban", "sources": ["projects", "tasks", "initiatives", "activity", "comments"]},
  {"name": "wicked-mem", "sources": ["memories", "sessions"]},
  {"name": "wicked-crew", "sources": ["projects", "phases", "specialists", "artifacts", "signals"]}
]
```

### Step 2: Data from Both Sources
Tasks and memories are both accessible via the gateway.

### Step 3: Multi-Source Dashboard
Claude generates A2UI combining task and memory data.

### Step 5: Rendered Dashboard
Two sections: Tasks (left) + Decisions (right)

## Success Criteria

- [ ] Data gateway discovers multiple plugins with data sources
- [ ] Tasks are queryable via `/api/v1/data/wicked-kanban/tasks/list`
- [ ] Memories are queryable via `/api/v1/data/wicked-mem/memories/list`
- [ ] Claude Code generates A2UI using data from 2+ plugins
- [ ] Both data sources render in the same dashboard
- [ ] Dashboard shows current data from both sources

## Value Demonstrated

**Cross-plugin composition**: Users can create dashboards that combine data from multiple sources without worrying about API integration details.

**Unified data gateway**: A single API surface (`/api/v1/data/{plugin}/{source}/{verb}`) provides access to all plugin data, simplifying dashboard data fetching.

**Real-world use**: Executive dashboards combining metrics from multiple systems, sprint planning views showing tasks + recent decisions, incident response dashboards showing alerts + runbooks.
