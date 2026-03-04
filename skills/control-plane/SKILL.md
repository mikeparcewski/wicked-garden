---
name: control-plane
description: |
  Interface guide for the wicked-control-plane — an experimental team-shared persistence backend.
  wicked-garden defaults to local mode (auto-starts CP on localhost, falls back to local JSON files).
  Use this skill only when the user needs CP API access, endpoint discovery, or CP connectivity debugging.

  Use when: "control plane API", "CP endpoint", "CP connectivity", "team sync",
  "manifest discovery", "debug CP issue", "local mode", "remote mode"
---

# Control Plane Interface *(experimental)*

> **Note**: wicked-garden defaults to `local` mode — auto-starts CP on localhost with local JSON fallback. Use `remote` mode for team-shared persistence.

The control plane is a Fastify + SQLite backend that stores domain data — memories, tasks, crew projects, brainstorm sessions, delivery metrics, and more.

You don't need to know whether the CP is local or remote. The interface is the same.

## The Pattern: Discover → Understand → Request

### 1. Discover: What's available?

```
GET /api/v1/manifest
```

Returns every domain, source, and verb the CP supports:

```json
{
  "domains": {
    "memory":    { "sources": { "memories": ["list","get","search","create","update","delete",...] }},
    "kanban":    { "sources": { "tasks": ["list","get","create","update","delete","stats"], ... }},
    "crew":      { "sources": { "projects": ["list","get","create","update","archive",...] }},
    "jam":       { "sources": { "sessions": ["list","get","create","update","delete"] }},
    "knowledge": { "sources": { "graph": ["search","traverse","hotspots","impact",...] }},
    "delivery":  { "sources": { "velocity": ["list","capture"], "metrics": ["stats"] }},
    "events":    { "sources": { "events": ["list","stream","activity"] }},
    "agents":    { "sources": { "agents": ["list","get","register","heartbeat"] }},
    "indexing":  { "sources": { "jobs": ["list","get","create","delete"] }}
  }
}
```

### 2. Understand: What does an endpoint expect?

```
GET /api/v1/manifest/{domain}/{source}/{verb}
```

Returns method, path, parameters, request body schema, and response format:

```json
{
  "method": "POST",
  "path": "/api/v1/data/memory/memories/create",
  "description": "Create a new memory. Only title and content are required.",
  "request_body": {
    "properties": {
      "title":      { "type": "string", "required": true },
      "content":    { "type": "string", "required": true },
      "type":       { "type": "string", "enum": ["episodic","decision","procedural",...] },
      "importance": { "type": "integer", "default": 5 },
      "tags":       { "type": "array", "items": { "type": "string" } }
    }
  }
}
```

### 3. Request: Call the endpoint

```
{method} /api/v1/data/{domain}/{source}/{verb}[/{id}]
```

| Verb | Method | Body | Example |
|------|--------|------|---------|
| `list` | GET | — | `GET /api/v1/data/kanban/tasks/list?status=pending` |
| `get` | GET | — | `GET /api/v1/data/memory/memories/get/abc123` |
| `create` | POST | JSON | `POST /api/v1/data/crew/projects/create` |
| `update` | PUT | JSON | `PUT /api/v1/data/kanban/tasks/update/abc123` |
| `delete` | DELETE | — | `DELETE /api/v1/data/jam/sessions/delete/abc123` |

Domain-specific verbs (`archive`, `sweep`, `ingest`, `evaluate`, `advance`) are all POST.

## Quick Reference

**Health**: `GET /health` — returns `{"status":"ok","version":"...","domains":[...]}`

**Query**: `POST /api/v1/query` with `{"sql":"SELECT ..."}` — direct SQL (SELECT only)

**Domain aliases**: `wicked-mem` = `memory`, `wicked-kanban` = `kanban`, etc. Both work.

## From Python

```python
from _storage import StorageManager

sm = StorageManager("memory")
memories = sm.list("memories", project="my-project")
sm.create("memories", {"title": "...", "content": "..."})
```

StorageManager handles CP routing, offline fallback, and queue replay automatically. See [refs/usage.md](refs/usage.md) for details.

## Response Envelope

All responses wrap data in `{"data": ..., "meta": {...}}`. Lists return arrays, single records return objects.

## Further Reading

- [refs/usage.md](refs/usage.md) — StorageManager, direct client, hook timeouts
- [refs/modes.md](refs/modes.md) — Local, remote, offline mode behavior
