---
name: task-dashboard-generation
title: Task Data Gateway Querying
description: Query task data from wicked-kanban via the data gateway with filtering, stats, and search
type: feature
difficulty: basic
estimated_minutes: 8
---

# Task Data Gateway Querying

Demonstrates querying task data from wicked-kanban through the Workbench data gateway. Claude uses the gateway endpoints to fetch, filter, and summarize tasks on request.

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

Verify the kanban data source is discovered:

```bash
curl -s http://localhost:18889/api/v1/data/plugins | python3 -m json.tool | grep wicked-kanban
```

## Steps

### 1. List Tasks via Data Gateway

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list" | python3 -m json.tool
```

**Expected**: JSON response with `items` array containing task objects and a `meta` block:
```json
{
  "items": [
    {"subject": "Fix authentication bug", "status": "pending", ...},
    {"subject": "Update documentation", "status": "pending", ...},
    {"subject": "Refactor API layer", "status": "pending", ...}
  ],
  "meta": {
    "plugin": "wicked-kanban",
    "source": "tasks",
    "verb": "list"
  }
}
```

### 2. Apply Limit and Offset Pagination

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list?limit=2&offset=0" | python3 -m json.tool
```

**Expected**: Only 2 items returned. Increase `offset=2` to get the next page.

### 3. Filter Tasks by Status

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list?filter=pending" | python3 -m json.tool
```

**Expected**: Only tasks with `status=pending` returned.

### 4. Get Task Stats

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/stats" | python3 -m json.tool
```

**Expected**: Aggregated counts by status showing the breakdown of pending, in_progress, and completed tasks.

### 5. Search Tasks by Keyword

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/search?query=auth" | python3 -m json.tool
```

**Expected**: Tasks matching "auth" in their subject or description.

### 6. Request a Task Summary from Claude Code

In Claude Code conversation:

```
Show me my pending tasks and give me a summary of what needs attention.
```

**Expected**: Claude queries the data gateway (`/api/v1/data/wicked-kanban/tasks/list?filter=pending`) and formats the results as a readable summary. No rendering endpoint is involved — Claude presents the data as markdown or prose.

### 7. Verify Gateway Metadata on All Responses

Every gateway response includes a `meta` block added by `_enrich_meta()`:

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('meta', {}))"
```

**Expected**: `{"plugin": "wicked-kanban", "source": "tasks"}` present in every response.

## Expected Outcome

- Data gateway discovers wicked-kanban as a data plugin
- Tasks are accessible via `/api/v1/data/wicked-kanban/tasks/list`
- Filtering, pagination (`limit`/`offset`), and search via `query` parameter all work
- Stats verb returns aggregated counts
- Claude can fetch and summarize task data when asked in natural language
- No `POST /api/render` endpoint exists — Claude formats data as text/markdown inline

## Valid Read Verbs for Task Data

| Verb | URL | Purpose |
|------|-----|---------|
| `list` | `/api/v1/data/wicked-kanban/tasks/list` | All tasks (paginated) |
| `get` | `/api/v1/data/wicked-kanban/tasks/get/{id}` | Single task by ID |
| `search` | `/api/v1/data/wicked-kanban/tasks/search?query=...` | Keyword search |
| `stats` | `/api/v1/data/wicked-kanban/tasks/stats` | Aggregated counts |

## Success Criteria

- [ ] `/api/v1/data/plugins` lists wicked-kanban as a data source
- [ ] Tasks are returned from the `list` verb
- [ ] `limit` and `offset` pagination parameters are respected
- [ ] `filter` parameter narrows results by status
- [ ] `search` verb returns keyword-matched tasks
- [ ] `stats` verb returns aggregated counts by status
- [ ] Every response includes a `meta` block with `plugin` and `source`
- [ ] Claude can describe task data from a natural language request

## Value Demonstrated

**Unified data gateway**: Task data is fetched through a single API surface (`/api/v1/data/{plugin}/{source}/{verb}`), providing consistent querying, filtering, and pagination across all plugins.

**Real-world use**: Project managers can ask Claude to summarize task state. "Show blocked tasks", "Show tasks updated today" — Claude queries the gateway and responds in natural language.
