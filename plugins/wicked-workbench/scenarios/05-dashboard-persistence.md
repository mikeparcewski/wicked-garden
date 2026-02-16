---
name: dashboard-persistence
title: Dashboard Data Refresh and Multi-Source Queries
description: Refresh plugin discovery and query multiple data sources
type: dashboard
difficulty: intermediate
estimated_minutes: 8
---

# Dashboard Data Refresh and Multi-Source Queries

Demonstrates the data gateway's refresh mechanism and complex multi-source queries. This proves the gateway maintains an up-to-date view of the plugin ecosystem and supports rich data access patterns.

## Setup

Ensure Workbench is running:

```
/wicked-workbench:workbench start
```

Create some test data. In Claude Code:

```
/wicked-kanban:new-task "Deploy to production"
/wicked-kanban:new-task "Fix critical bug"
/wicked-kanban:new-task "Update docs"
```

## Steps

### 1. Check Current Data Sources

```bash
curl -s http://localhost:18889/api/v1/data/plugins | jq '.meta'
```

### 2. Query with Filters

```bash
# Search tasks
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/search?query=bug" | jq '.items'

# Get task stats
curl -s http://localhost:18889/api/v1/data/wicked-kanban/tasks/stats | jq .
```

### 3. Refresh Plugin Discovery

```bash
curl -X POST http://localhost:18889/api/v1/data/refresh | jq .
```

### 4. Query with Pagination

```bash
# First page
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list?limit=2&offset=0" | jq '.items | length'

# Second page
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list?limit=2&offset=2" | jq '.items | length'
```

### 5. Cross-Plugin Data Assembly

Query multiple sources to build a composite view:

```bash
# Tasks
curl -s http://localhost:18889/api/v1/data/wicked-kanban/tasks/list?limit=5

# Related memories
curl -s "http://localhost:18889/api/v1/data/wicked-mem/memories/search?query=deploy"

# Project context
curl -s http://localhost:18889/api/v1/data/wicked-crew/projects/list
```

## Expected Outcome

### Step 1: Current Sources
```json
{
  "total_plugins": 7,
  "total_sources": 24,
  "schema_version": "1.0.0"
}
```

### Step 2: Filtered Results
Search returns matching tasks; stats returns aggregated counts.

### Step 3: Refresh
```json
{
  "status": "refreshed",
  "plugins": 7
}
```

### Step 4: Pagination
First page returns 2 items, second page returns remaining items.

### Step 5: Cross-Plugin Data
Multiple API calls return data from different plugins, ready for dashboard composition.

## Success Criteria

- [ ] Data source count matches installed plugins with wicked.json
- [ ] Search verb filters results by query string
- [ ] Stats verb returns aggregated data
- [ ] POST /refresh re-discovers plugins without restart
- [ ] Pagination (limit/offset) works correctly
- [ ] Multiple data sources can be queried independently

## Value Demonstrated

**Live data gateway**: The refresh endpoint ensures new plugins are discovered without restarting the server.

**Rich query patterns**: Search, stats, pagination, and filtering provide flexible data access for dashboard generation.

**Cross-plugin assembly**: Claude Code can query multiple sources in parallel to build comprehensive dashboards from diverse plugin data.
