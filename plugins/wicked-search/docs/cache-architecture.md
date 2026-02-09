# Graph Cache Architecture

Visual reference for the wicked-search graph export cache system.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Wicked-Search Graph Cache                   │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  wicked-search   │         │   wicked-cache   │
│   (Producer)     │────────▶│  (Storage Layer) │
└──────────────────┘         └──────────────────┘
        │                             ▲
        │                             │
        │                             │
        ▼                             │
┌──────────────────┐         ┌──────────────────┐
│  GraphExporter   │         │   GraphClient    │
│  - export_all()  │         │  - get_*()       │
│  - invalidate()  │         │  - is_fresh()    │
└──────────────────┘         └──────────────────┘
                                      ▲
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
            ┌───────┴──────┐  ┌──────┴─────┐  ┌───────┴──────┐
            │ wicked-crew  │  │wicked-product │  │ wicked-kanban│
            │ (Consumer)   │  │(Consumer)  │  │  (Consumer)  │
            └──────────────┘  └────────────┘  └──────────────┘
```

## Data Flow

### 1. Indexing & Export

```
User runs /wicked-search:index

    │
    ▼
┌─────────────────┐
│   Parse Files   │  Parse code (tree-sitter) + docs (kreuzberg)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build Graph    │  Create SymbolGraph with nodes and references
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Export to      │  GraphExporter.export_all()
│  wicked-cache   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  wicked-cache namespace: "wicked-search"                │
│                                                          │
│  Keys written:                                           │
│  - symbol_deps:{workspace_hash}                          │
│  - file_refs:{workspace_hash}                            │
│  - def_lookup:{workspace_hash}                           │
│  - call_chain:{workspace_hash}                           │
└──────────────────────────────────────────────────────────┘
```

### 2. Consumer Query

```
Plugin needs graph data

    │
    ▼
┌─────────────────┐
│  GraphClient    │  Initialize with workspace_path
│  (client init)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Check          │  is_fresh(max_age_seconds=3600)
│  Freshness      │
└────────┬────────┘
         │
         ├─── Fresh ────▶ Continue
         │
         └─── Stale ────▶ Raise CacheStaleError
                          (user must re-index)
         │
         ▼
┌─────────────────┐
│  Query Cache    │  get_symbol_dependencies(filter={...})
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Parse Result   │  Deserialize JSON → Dataclasses
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Return to      │  SymbolDepsResult with typed data
│  Consumer       │
└─────────────────┘
```

## Cache Storage Layout

```
~/.something-wicked/
└── wicked-cache/
    ├── namespaces/
    │   └── wicked-search/
    │       ├── index.json                    # Metadata index
    │       └── data/
    │           ├── symbol_deps:{hash}.json   # Query type 1
    │           ├── file_refs:{hash}.json     # Query type 2
    │           ├── def_lookup:{hash}.json    # Query type 3
    │           └── call_chain:{hash}.json    # Query type 4
    │
    └── stats.json                            # Global cache stats
```

### Cache Entry Structure

```json
{
  "version": "1.0.0",
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1",
    "file_count": 1247,
    "node_count": 8934,
    "edge_count": 15672
  },
  "filter": { /* optional */ },
  "data": { /* query-specific data */ }
}
```

## Query Type Architecture

### 1. Symbol Dependencies

**Purpose**: Fast lookup of symbol relationships

```
Input:  symbol_id or filter
        ↓
Cache:  symbol_deps:{workspace_hash}[:{filter_hash}]
        ↓
Output: List[SymbolDepsEntry]
        ├─ id, name, type, file, line_start, line_end
        ├─ dependencies: List[SymbolDependency]
        │  └─ target_id, type, line
        └─ dependents: List[SymbolDependent]
           └─ source_id, type, line
```

**Example Query**:
```python
deps = client.get_symbol_dependencies(
    filter={"paths": ["src/auth/"]}
)

for symbol in deps.symbols:
    print(f"{symbol.name} calls {len(symbol.dependencies)} functions")
```

### 2. File References

**Purpose**: File-level aggregation of symbols

```
Input:  files list or filter
        ↓
Cache:  file_refs:{workspace_hash}[:{filter_hash}]
        ↓
Output: List[FileRef]
        ├─ path, mtime, size, domain
        ├─ symbols: List[FileSymbol]
        │  └─ id, name, type, line_start, line_end, calls_out, calls_in
        └─ imports: List[str]
```

**Example Query**:
```python
refs = client.get_file_references(
    files=["src/auth.py", "src/api/login.py"]
)

for file in refs.files:
    print(f"{file.path}: {len(file.symbols)} symbols")
```

### 3. Definition Lookup

**Purpose**: O(1) symbol-to-location resolution

```
Input:  name or qualified_name
        ↓
Cache:  def_lookup:{workspace_hash}
        ├─ by_name: Dict[str, List[SymbolLocation]]
        └─ by_qualified_name: Dict[str, SymbolLocation]
        ↓
Output: SymbolLocation
        └─ id, qualified_name, file, line_start, type
```

**Example Query**:
```python
# Unique lookup
loc = client.lookup_definition(
    qualified_name="auth.authenticate_user"
)
print(f"Found at {loc.file}:{loc.line_start}")

# May return multiple matches
loc = client.lookup_definition(name="User")
```

### 4. Call Chain

**Purpose**: Transitive dependency analysis (blast radius)

```
Input:  symbol_id, max_depth, ref_types
        ↓
Cache:  call_chain:{workspace_hash}:{filter_hash}
        ↓
Output: List[CallChain]
        ├─ root_id, root_name, root_file
        ├─ downstream: List[CallChainEntry]
        │  └─ id, name, file, depth, path
        └─ upstream: List[CallChainEntry]
           └─ id, name, file, depth, path
```

**Example Query**:
```python
chain = client.get_call_chain(
    symbol_id="src/auth.py::authenticate_user",
    max_depth=5
)

for entry in chain.chains[0].downstream:
    print(f"[{entry.depth}] {entry.name} ({entry.file})")
```

## Filter Architecture

### Filter Flow

```
┌──────────────────┐
│  Consumer Query  │  filter = {"paths": ["src/"], "node_types": ["function"]}
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Hash Filter     │  SHA256(json.dumps(filter, sort_keys=True))[:8]
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Build Cache Key │  "symbol_deps:{workspace}:{filter_hash}"
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Check Cache     │  cache.get(key)
└────────┬─────────┘
         │
         ├─── Hit ──────▶ Return cached result
         │
         └─── Miss ─────▶ Export with filter (or raise CacheStaleError)
```

### Filter Parameter Schema

```yaml
filter:
  # Path filtering
  paths: ["src/auth/", "lib/security/"]
  exclude_paths: ["test/", "vendor/"]

  # Symbol filtering
  node_types: ["function", "class", "method"]
  domain: "code"  # or "doc"

  # File filtering (for file_refs)
  files: ["src/auth.py", "src/db.py"]

  # Call chain filtering
  max_depth: 5
  ref_types: ["calls", "imports"]
```

## Freshness Architecture

### Freshness Validation Flow

```
┌──────────────────┐
│  Consumer Query  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Get Freshness   │  client.get_freshness()
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Check Conditions                         │
│                                           │
│  1. Workspace hash matches?               │
│  2. indexed_at within max_age_seconds?    │
│  3. Version compatible?                   │
└────────┬─────────────────────────────────┘
         │
         ├─── All Pass ──▶ Continue query
         │
         └─── Any Fail ──▶ Raise CacheStaleError
```

### Freshness Metadata

```json
{
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",    // ISO8601 timestamp
    "workspace_hash": "a3f5e2d1b4c8e7f2",    // SHA256(workspace_path)[:8]
    "file_count": 1247,                       // Total files indexed
    "node_count": 8934,                       // Total symbols
    "edge_count": 15672                       // Total references
  }
}
```

## Invalidation Architecture

### Manual Invalidation

```
┌──────────────────┐
│  Re-index Event  │  User runs /wicked-search:index
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Invalidate Old  │  exporter.invalidate_all(workspace_hash)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Delete Keys     │  cache.invalidate(key) for each query type
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Export New      │  exporter.export_all(graph, workspace_path)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Consumers Get   │  Fresh data on next query
│  Fresh Data      │
└──────────────────┘
```

### Invalidation Modes

wicked-cache supports 3 invalidation modes:

| Mode | Trigger | Use Case |
|------|---------|----------|
| **FILE** | Source file mtime/size change | Auto-invalidate on file changes |
| **TTL** | Time expiration | Auto-invalidate after N seconds |
| **MANUAL** | Explicit invalidate call | **Used by wicked-search** for controlled invalidation |

wicked-search uses **MANUAL** mode:
```python
cache.set(key, value, options={"mode": "manual"})
```

This gives wicked-search full control over when to invalidate (only on re-index).

## Versioning Architecture

### Version Compatibility Check

```
┌──────────────────┐
│  Cache Read      │  data = cache.get(key)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Extract Version │  cached_version = data["version"]
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Check Compatibility                      │
│                                           │
│  cached_major = int(cached_version[0])    │
│  required_major = int(REQUIRED[0])        │
│                                           │
│  if cached_major != required_major:       │
│      raise VersionMismatchError           │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│  Parse Data      │  Safe to parse, schema is compatible
└──────────────────┘
```

### Version Evolution

```
Version 1.0.0 (Current)
├─ Initial schema
├─ 4 query types
└─ Basic filter support

Version 1.1.0 (Future - Minor)
├─ Add new optional fields to results
├─ New filter parameters
└─ Backward compatible with 1.0.0 consumers

Version 2.0.0 (Future - Major)
├─ Breaking changes (field removals, type changes)
├─ Requires consumer updates
└─ 6-month migration window
```

## Performance Characteristics

### Query Performance Comparison

```
Direct JSONL Parsing (No Cache):
┌──────────┐  ┌──────────┐  ┌──────────┐
│  Open    │→ │  Parse   │→ │  Filter  │  ~500ms
│  JSONL   │  │  Lines   │  │  Results │
└──────────┘  └──────────┘  └──────────┘

Cached Query:
┌──────────┐  ┌──────────┐
│  Cache   │→ │  Parse   │  ~10ms
│  Lookup  │  │  JSON    │
└──────────┘  └──────────┘

Speedup: ~50x faster
```

### Cache Size Scaling

```
Project Size vs Cache Size

200 MB │                                    ●
       │
150 MB │
       │
100 MB │                          ●
       │
 50 MB │              ●
       │
  0 MB │  ●
       └───────────────────────────────────
          1K     10K    100K   1M files

Small:  1K files   → ~5K symbols  → ~2 MB cache
Medium: 10K files  → ~50K symbols → ~20 MB cache
Large:  100K files → ~500K symbols → ~200 MB cache
```

## Error Handling Architecture

### Error Types

```
┌─────────────────────────────────────────────────────────┐
│                    Error Hierarchy                       │
├─────────────────────────────────────────────────────────┤
│  Exception                                               │
│  └─ CacheStaleError                                      │
│     ├─ Cache miss (no data)                              │
│     ├─ Workspace hash mismatch                           │
│     └─ Age exceeds max_age_seconds                       │
│                                                           │
│  └─ VersionMismatchError                                 │
│     └─ Major version incompatible                        │
└─────────────────────────────────────────────────────────┘
```

### Error Handling Flow

```
try:
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    # Option 1: Re-index
    print("Run: /wicked-search:index")

    # Option 2: Fallback to JSONL
    deps = parse_jsonl_directly()

except VersionMismatchError:
    # Update plugin
    print("Update wicked-search plugin")
```

## Integration Patterns

### Pattern 1: Fresh Check + Query

```python
client = GraphClient(workspace_path)

# Check before expensive operation
if not client.is_fresh(max_age_seconds=3600):
    raise CacheStaleError("Please re-index")

# Safe to query
deps = client.get_symbol_dependencies()
```

### Pattern 2: Graceful Degradation

```python
try:
    # Try cache first
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    # Fallback to slower method
    deps = parse_jsonl_fallback()
```

### Pattern 3: Batch Queries

```python
client = GraphClient(workspace_path)

# Single client, multiple queries (reuses workspace hash)
deps = client.get_symbol_dependencies()
refs = client.get_file_references()
loc = client.lookup_definition(name="User")
```

## Summary

This architecture provides:

✓ **Fast queries** - ~50x faster than JSONL parsing
✓ **Workspace isolation** - SHA256 hash prevents conflicts
✓ **Version safety** - Major version checks prevent schema errors
✓ **Freshness tracking** - Age validation prevents stale data
✓ **Filter support** - Optional overrides for custom queries
✓ **Graceful degradation** - Error handling with fallback options
✓ **Cross-plugin compatible** - Standardized interface for all consumers
