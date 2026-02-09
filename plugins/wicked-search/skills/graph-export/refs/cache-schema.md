# Cache Schema Reference

Full specification for wicked-search graph cache.

## Cache Key Patterns

```
{query_type}:{workspace_hash}[:{filter_hash}]
```

| Query Type | Key Example | Description |
|------------|-------------|-------------|
| `symbol_deps` | `symbol_deps:a1b2c3d4` | Symbol dependencies |
| `file_refs` | `file_refs:a1b2c3d4` | File-level references |
| `def_lookup` | `def_lookup:a1b2c3d4` | Definition index |
| `call_chain` | `call_chain:a1b2c3d4:f5e6d7c8` | Call chains (with filter) |

## Response Schema

All responses include:

```json
{
  "version": "1.0.0",
  "freshness": {
    "indexed_at": "2026-02-01T12:00:00Z",
    "workspace_hash": "a1b2c3d4",
    "file_count": 150,
    "node_count": 2500,
    "edge_count": 8000
  },
  "filter": {},
  "data": "..."
}
```

## Query Type Schemas

### symbol_deps

```json
{
  "symbols": [
    {
      "id": "src/auth.py::UserService.login",
      "name": "login",
      "type": "METHOD",
      "file": "src/auth.py",
      "line_start": 45,
      "line_end": 62,
      "dependencies": [
        {"target_id": "src/db.py::get_user", "type": "CALLS", "line": 48}
      ],
      "dependents": [
        {"source_id": "src/api.py::handle_login", "type": "CALLS", "line": 23}
      ]
    }
  ]
}
```

### file_refs

```json
{
  "files": [
    {
      "path": "src/auth.py",
      "mtime": 1706792400,
      "size": 2048,
      "domain": "code",
      "symbols": [
        {"id": "...", "name": "login", "type": "METHOD", "calls_out": 5, "calls_in": 3}
      ],
      "imports": ["hashlib", "jwt", "db"]
    }
  ]
}
```

### def_lookup

```json
{
  "index": {
    "by_name": {
      "login": [
        {"id": "src/auth.py::UserService.login", "qualified_name": "UserService.login", "file": "src/auth.py", "line_start": 45, "type": "METHOD"}
      ]
    },
    "by_qualified_name": {
      "userservice.login": {"id": "...", "file": "...", "line_start": 45, "type": "METHOD"}
    }
  }
}
```

### call_chain

```json
{
  "chains": [
    {
      "root_id": "src/auth.py::login",
      "root_name": "login",
      "root_file": "src/auth.py",
      "downstream": [
        {"id": "src/db.py::get_user", "name": "get_user", "file": "src/db.py", "depth": 1, "path": ["src/auth.py::login"]}
      ],
      "upstream": [
        {"id": "src/api.py::handle_login", "name": "handle_login", "file": "src/api.py", "depth": 1, "path": ["src/auth.py::login"]}
      ]
    }
  ]
}
```

## Filter Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `paths` | `List[str]` | Include only symbols in these paths |
| `exclude_paths` | `List[str]` | Exclude symbols in these paths |
| `node_types` | `List[str]` | Filter by node type (FUNCTION, CLASS, etc.) |
| `domain` | `str` | Filter by domain ("code" or "doc") |
| `files` | `List[str]` | For file_refs: specific files only |
| `max_depth` | `int` | For call_chain: traversal depth (default 5) |
| `ref_types` | `List[str]` | For call_chain: reference types to follow |

## Versioning

- Schema version: `1.0.0`
- Major version changes = breaking (requires re-export)
- Minor/patch = backward compatible
- Client checks major version compatibility
