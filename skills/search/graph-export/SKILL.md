---
name: graph-export
description: |
  This skill should be used by plugin authors who need to access wicked-search
  graph data for symbol dependencies, file references, definitions, or call chains.
  Triggered by queries about "graph data", "symbol dependencies", "cross-plugin search",
  "file references", "call chain", "blast radius from cache", or "cached graph".

  Enables other plugins to query the code graph without direct wicked-search coupling,
  using wicked-cache for efficient data sharing.
---

# Graph Export Skill

Seamless access to wicked-search graph data for other plugins.

## Quick Start

```python
from graph_client import GraphClient

# Initialize with workspace path (auto-connects to wicked-cache)
client = GraphClient("/path/to/workspace")

# Check freshness before querying
if not client.is_fresh(max_age_seconds=3600):
    print("Graph data may be stale - consider re-indexing")

# Query symbol dependencies
result = client.get_symbol_dependencies()
for symbol in result.symbols:
    print(f"{symbol.name}: {len(symbol.dependencies)} deps, {len(symbol.dependents)} dependents")

# Lookup definition by name
location = client.lookup_definition(name="UserService")
if location:
    print(f"Found at {location.file}:{location.line_start}")

# Get call chain (blast radius)
chain = client.get_call_chain("src/auth.py::login", max_depth=3)
```

## Available Query Types

| Method | Returns | Use Case |
|--------|---------|----------|
| `get_symbol_dependencies()` | All symbols with deps/dependents | Dependency analysis |
| `get_file_references(files)` | File-level symbol summaries | File impact analysis |
| `lookup_definition(name)` | Symbol location | Jump-to-definition |
| `get_call_chain(id, depth)` | Upstream/downstream chains | Blast radius |

## Filter Support

All queries support optional filters (workspace-scoped by default):

```python
# Filter by paths
deps = client.get_symbol_dependencies(filter={
    "paths": ["src/auth/"],
    "exclude_paths": ["src/auth/tests/"],
    "node_types": ["FUNCTION", "METHOD"],
    "domain": "code"
})

# Filter file references
refs = client.get_file_references(files=["src/api.py", "src/models.py"])
```

## Freshness & Versioning

```python
# Check if data is fresh (default: 1 hour)
is_ok = client.is_fresh(max_age_seconds=3600)

# Get detailed freshness info
meta = client.get_freshness()
print(f"Indexed at: {meta.indexed_at}")
print(f"Files: {meta.file_count}, Nodes: {meta.node_count}")
```

## Error Handling

```python
from graph_client import GraphClient, CacheStaleError, VersionMismatchError

try:
    result = client.get_symbol_dependencies()
except CacheStaleError:
    print("Cache miss - run /wicked-garden:search:index first")
except VersionMismatchError as e:
    print(f"Schema changed: {e}")
```

## Integration Patterns

### For Plugin Authors

Add this to your plugin's requirements:
```
wicked-search  # Provides graph-export skill
wicked-cache   # Cache infrastructure
```

In your skill/agent, use the client:
```python
import sys
sys.path.insert(0, "${WICKED_SEARCH_SCRIPTS}")
from graph_client import GraphClient
```

### Triggering Cache Export

To populate the cache, run indexing with `--export-cache`:
```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py index /path/to/project --export-graph --export-cache
```

This will:
1. Build the JSONL index (fast, parallel)
2. Build the Symbol Graph (JSP/HTML support)
3. Export to wicked-cache for cross-plugin access

For manual export (advanced):

```python
from graph_export import GraphExporter
from symbol_graph import SymbolGraph

exporter = GraphExporter(cache)
result = exporter.export_all(graph, workspace_path)
print(f"Exported {len(result.keys_written)} cache entries")
```

## References

- [Cache Schema](refs/cache-schema.md) - Full schema specification
- [Usage Examples](refs/examples.md) - Real-world patterns
