# Graph Cache Quick Reference

One-page reference for wicked-search graph cache API.

## Basic Setup

```python
from graph_client import GraphClient

client = GraphClient(workspace_path=".")
```

## Query Types

### 1. Symbol Dependencies
```python
deps = client.get_symbol_dependencies(
    filter={
        "paths": ["src/auth/"],
        "node_types": ["function", "class"]
    }
)

for symbol in deps.symbols:
    print(f"{symbol.name}: {len(symbol.dependencies)} deps, {len(symbol.dependents)} dependents")
```

### 2. File References
```python
refs = client.get_file_references(
    files=["src/auth.py", "src/db.py"]
)

for file in refs.files:
    print(f"{file.path}: {len(file.symbols)} symbols")
```

### 3. Definition Lookup
```python
# By qualified name (unique)
loc = client.lookup_definition(qualified_name="auth.authenticate_user")

# By name (may have multiple matches)
loc = client.lookup_definition(name="authenticate_user")

print(f"Found at {loc.file}:{loc.line_start}")
```

### 4. Call Chain (Blast Radius)
```python
chain_result = client.get_call_chain(
    symbol_id="src/auth.py::authenticate_user",
    max_depth=5,
    ref_types=["calls"]
)

chain = chain_result.chains[0]
print(f"Downstream: {len(chain.downstream)}")
print(f"Upstream: {len(chain.upstream)}")
```

## Filter Parameters

```python
filter = {
    # Path filtering
    "paths": ["src/auth/", "lib/security/"],
    "exclude_paths": ["test/", "vendor/"],

    # Symbol filtering
    "node_types": ["function", "class", "method"],
    "domain": "code",  # or "doc"

    # Call chain filtering
    "max_depth": 5,
    "ref_types": ["calls", "imports"]
}
```

## Freshness Checks

```python
# Check if fresh (default: 1 hour)
if client.is_fresh(max_age_seconds=3600):
    print("Cache is fresh")

# Get metadata
freshness = client.get_freshness()
print(f"Indexed at: {freshness.indexed_at}")
print(f"Symbols: {freshness.node_count}")
```

## Error Handling

```python
from graph_client import CacheStaleError, VersionMismatchError

try:
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    print("Cache miss - run /wicked-search:index")
except VersionMismatchError:
    print("Version incompatible - update wicked-search")
```

## Result Types

### SymbolDepsResult
```python
result.version           # "1.0.0"
result.freshness         # FreshnessMetadata
result.filter            # Applied filter
result.symbols           # List[SymbolDepsEntry]
  ├─ .id
  ├─ .name
  ├─ .type
  ├─ .file
  ├─ .line_start
  ├─ .line_end
  ├─ .dependencies       # List[SymbolDependency]
  │   ├─ .target_id
  │   ├─ .type
  │   └─ .line
  └─ .dependents         # List[SymbolDependent]
      ├─ .source_id
      ├─ .type
      └─ .line
```

### FileRefsResult
```python
result.files             # List[FileRef]
  ├─ .path
  ├─ .mtime
  ├─ .size
  ├─ .domain
  ├─ .symbols            # List[FileSymbol]
  │   ├─ .id
  │   ├─ .name
  │   ├─ .type
  │   ├─ .line_start
  │   ├─ .line_end
  │   ├─ .calls_out
  │   └─ .calls_in
  └─ .imports            # List[str]
```

### SymbolLocation
```python
loc.id
loc.qualified_name
loc.file
loc.line_start
loc.type
```

### CallChainResult
```python
result.chains            # List[CallChain]
  ├─ .root_id
  ├─ .root_name
  ├─ .root_file
  ├─ .downstream         # List[CallChainEntry]
  │   ├─ .id
  │   ├─ .name
  │   ├─ .file
  │   ├─ .depth
  │   └─ .path
  └─ .upstream           # List[CallChainEntry]
```

## Cache Keys

```
Format: {query_type}:{workspace_hash}[:{filter_hash}]

Examples:
  symbol_deps:a3f5e2d1
  file_refs:a3f5e2d1:b7c9d4e1
  def_lookup:a3f5e2d1
  call_chain:a3f5e2d1:c8d2e5f3
```

## Common Patterns

### Pattern 1: Fresh Check Before Query
```python
if not client.is_fresh(max_age_seconds=1800):
    raise CacheStaleError("Please re-index")
deps = client.get_symbol_dependencies()
```

### Pattern 2: Graceful Degradation
```python
try:
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    deps = fallback_to_jsonl_parsing()
```

### Pattern 3: Batch Queries
```python
# Reuse client for multiple queries
deps = client.get_symbol_dependencies()
refs = client.get_file_references()
loc = client.lookup_definition(name="User")
```

### Pattern 4: Filter for Performance
```python
# Good: Filter at cache level
deps = client.get_symbol_dependencies(
    filter={"paths": ["src/auth/"]}
)

# Bad: Load all then filter
deps = client.get_symbol_dependencies()
auth_symbols = [s for s in deps.symbols if "auth" in s.file]
```

## Producer API (wicked-search only)

```python
from graph_export import GraphExporter
from cache import namespace

# Export after indexing
cache = namespace("wicked-search")
exporter = GraphExporter(cache)
result = exporter.export_all(graph, workspace_path)

# Invalidate on re-index
exporter.invalidate_all(workspace_hash)
```

## Performance

| Query Type | Cold | Warm | Speedup |
|------------|------|------|---------|
| symbol_deps | 500ms | 10ms | 50x |
| file_refs | 300ms | 5ms | 60x |
| def_lookup | 200ms | 2ms | 100x |
| call_chain | 1s | 20ms | 50x |

## Cache Size

| Project | Files | Symbols | Cache Size |
|---------|-------|---------|------------|
| Small | 1K | 5K | 2 MB |
| Medium | 10K | 50K | 20 MB |
| Large | 100K | 500K | 200 MB |

## Versioning

Current: **1.0.0**

- Major version change = breaking (update required)
- Minor version change = additive (backward compatible)
- Patch version change = bug fix (no schema change)

## Documentation

- Full Schema: `docs/cache-schema.md`
- Usage Examples: `docs/cache-usage-examples.md`
- Architecture: `docs/cache-architecture.md`
- Implementation: `docs/IMPLEMENTATION-SUMMARY.md`

## Support

Issues? See:
1. Check cache status: `client.get_freshness()`
2. Re-index: `/wicked-search:index <path>`
3. Check version: `result.version`
4. Clear cache: `/wicked-cache:clear --namespace wicked-search`
