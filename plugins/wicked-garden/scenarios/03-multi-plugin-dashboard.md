---
name: multi-plugin-dashboard
title: Multi-Plugin Data Assembly
description: Query and combine data from multiple plugins via the data gateway in a single session
type: integration
difficulty: intermediate
estimated_minutes: 12
---

# Multi-Plugin Data Assembly

Demonstrates querying data from multiple plugins via the Workbench data gateway. Claude assembles a combined view from different plugin data sources and presents it as a unified summary.

## Setup

Ensure multiple plugins with data sources are installed. Verify with:

```bash
curl -s http://localhost:18889/api/v1/data/plugins | python3 -c "import json,sys; [print(p['name']) for p in json.load(sys.stdin)['plugins']]"
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

### 1. Verify Multiple Data Sources Are Available

```bash
curl -s http://localhost:18889/api/v1/data/plugins | python3 -c "
import json, sys
d = json.load(sys.stdin)
for p in d['plugins']:
    print(p['name'], ':', [s['name'] for s in p['sources']])
"
```

**Expected**: Multiple plugins listed with their data sources. Example:
```
wicked-kanban : ['projects', 'tasks', 'initiatives', 'activity']
wicked-mem : ['memories', 'sessions']
wicked-crew : ['projects', 'phases', 'specialists', 'artifacts', 'signals']
```

### 2. Query Tasks from wicked-kanban

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"Tasks ({len(d.get('items', []))}):\")
for t in d.get('items', []):
    print(' -', t.get('subject', t.get('title', '?')), '|', t.get('status', '?'))
"
```

**Expected**: Task subjects and statuses printed from the kanban data source.

### 3. Query Memories from wicked-mem

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-mem/memories/list" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"Memories ({len(d.get('items', []))}):\")
for m in d.get('items', []):
    print(' -', m.get('content', '?')[:60])
"
```

**Expected**: Memory entries including the JWT decision and refresh token requirement.

### 4. Compare Plugin Stats Side by Side

```bash
echo "=== Kanban Stats ===" && \
  curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/stats" | python3 -m json.tool && \
  echo "=== Mem Stats ===" && \
  curl -s "http://localhost:18889/api/v1/data/wicked-mem/memories/stats" | python3 -m json.tool
```

**Expected**: Both plugins return aggregated stats. Each response includes the `meta` block identifying the plugin and source.

### 5. Search Across a Single Plugin

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-mem/memories/search?query=authentication" | python3 -m json.tool
```

**Expected**: Memories related to "authentication" are returned. The data gateway does not federate search across multiple plugins — each plugin is queried independently.

### 6. Request a Multi-Source Summary from Claude Code

In Claude Code conversation:

```
Give me a combined view: what tasks are pending and what decisions have we made recently?
```

**Expected**: Claude makes two gateway calls (one to `wicked-kanban/tasks/list` and one to `wicked-mem/memories/list`) and assembles a combined markdown summary. The data gateway provides the raw data; Claude formats the unified view as prose or a table.

### 7. Verify Gateway Metadata Distinguishes Sources

```bash
curl -s "http://localhost:18889/api/v1/data/wicked-kanban/tasks/list" | python3 -c "import json,sys; print(json.load(sys.stdin)['meta'])"
curl -s "http://localhost:18889/api/v1/data/wicked-mem/memories/list" | python3 -c "import json,sys; print(json.load(sys.stdin)['meta'])"
```

**Expected**: Each response's `meta.plugin` and `meta.source` correctly identify which plugin and source served the data.

### 8. Refresh Plugin Discovery

After installing a new plugin with data sources, refresh the gateway without restarting:

```bash
curl -s -X POST http://localhost:18889/api/v1/data/refresh | python3 -m json.tool
```

**Expected**: `{"status": "refreshed", "plugins": N}` with the updated plugin count.

## Expected Outcome

- Data gateway discovers multiple plugins with data sources
- Each plugin is queried independently via its own `/api/v1/data/{plugin}/{source}/{verb}` path
- `list`, `search`, and `stats` verbs work consistently across plugins
- Every response includes `meta.plugin` and `meta.source` for source attribution
- Claude assembles multi-source summaries from sequential or parallel gateway calls
- No `POST /api/render` endpoint exists — Claude formats the combined data as text inline

## Cross-Plugin Query Pattern

Claude assembles multi-plugin views by issuing separate gateway requests:

```
GET /api/v1/data/wicked-kanban/tasks/list    → tasks array
GET /api/v1/data/wicked-mem/memories/list    → memories array
→ Claude merges and formats both as a unified response
```

There is no server-side data federation — each plugin exposes its own data via its `api.py` subprocess and the gateway proxies requests independently.

## Success Criteria

- [ ] `/api/v1/data/plugins` lists 2+ plugins with data sources
- [ ] Tasks are queryable via `/api/v1/data/wicked-kanban/tasks/list`
- [ ] Memories are queryable via `/api/v1/data/wicked-mem/memories/list`
- [ ] Both plugins return responses with `meta.plugin` correctly set
- [ ] `stats` verb returns aggregated counts for both plugins
- [ ] `search` returns filtered results within a single plugin
- [ ] Claude can produce a combined summary from a natural language multi-source request
- [ ] Refresh endpoint updates the registry without server restart

## Value Demonstrated

**Cross-plugin data assembly**: Users can ask Claude to combine data from multiple sources. Claude issues independent gateway queries and formats the merged result.

**Unified API surface**: A single endpoint pattern (`/api/v1/data/{plugin}/{source}/{verb}`) provides consistent access to all plugin data, eliminating the need for custom integration code per plugin.

**Real-world use**: Sprint planning views combining tasks and recent decisions; incident response combining alerts with runbook memories; executive summaries pulling from multiple data domains.
