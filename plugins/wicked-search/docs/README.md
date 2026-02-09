# Wicked-Search Documentation

Complete documentation for the wicked-search graph export cache system.

## Overview

The wicked-search graph export cache provides a high-performance, cross-plugin API for consuming code graph data. Instead of each plugin parsing JSONL files directly, they can use pre-computed, query-optimized views cached in wicked-cache.

**Key Benefits**:
- **50-100x faster** than direct JSONL parsing
- **Workspace-scoped** with automatic isolation
- **Versioned schema** for stability
- **Freshness tracking** to prevent stale data
- **Filter support** for custom queries

## Documentation Index

### Quick Start
- **[QUICKREF.md](QUICKREF.md)** - One-page API reference (start here!)

### Design & Specification
- **[cache-schema.md](cache-schema.md)** - Complete schema specification
  - Cache key naming convention
  - JSON schemas for all 4 query types
  - Freshness metadata format
  - Filter parameter schema
  - Versioning strategy
  - Python interface signatures

### Architecture
- **[cache-architecture.md](cache-architecture.md)** - System architecture diagrams
  - Data flow diagrams
  - Storage layout
  - Query type architecture
  - Filter architecture
  - Freshness validation flow
  - Invalidation strategies

### Usage & Examples
- **[cache-usage-examples.md](cache-usage-examples.md)** - Real-world usage scenarios
  - wicked-crew: Dependency analysis
  - wicked-product: PR impact review
  - wicked-kanban: Task blast radius
  - Custom plugin: Security audit
  - Error handling patterns
  - Cache management

### Implementation
- **[IMPLEMENTATION-SUMMARY.md](IMPLEMENTATION-SUMMARY.md)** - Implementation summary
  - Deliverables overview
  - Key design decisions
  - Integration points
  - Performance characteristics
  - Next steps

## Quick Examples

### Consumer (Read from Cache)

```python
from graph_client import GraphClient

# Initialize
client = GraphClient(workspace_path=".")

# Check freshness
if not client.is_fresh(max_age_seconds=3600):
    print("Warning: Cache may be stale")

# Query symbol dependencies
deps = client.get_symbol_dependencies(
    filter={"paths": ["src/auth/"]}
)

for symbol in deps.symbols:
    print(f"{symbol.name}: {len(symbol.dependencies)} deps")
```

### Producer (Export to Cache)

```python
from graph_export import GraphExporter
from cache import namespace

# After indexing
cache = namespace("wicked-search")
exporter = GraphExporter(cache)
result = exporter.export_all(graph, workspace_path)

print(f"Exported {result.stats['total_symbols']} symbols")
```

## Query Types

The cache provides 4 pre-computed query types:

| Query Type | Purpose | Key Format |
|------------|---------|------------|
| **symbol_deps** | Symbol dependencies & dependents | `symbol_deps:{workspace}` |
| **file_refs** | File-level symbol aggregation | `file_refs:{workspace}` |
| **def_lookup** | Fast symbol-to-location index | `def_lookup:{workspace}` |
| **call_chain** | Transitive dependency analysis | `call_chain:{workspace}` |

## Architecture Overview

```
┌──────────────────┐         ┌──────────────────┐
│  wicked-search   │────────▶│   wicked-cache   │
│   (Producer)     │         │  (Storage Layer) │
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

## Key Concepts

### Workspace Hash
- SHA256 hash of workspace path (truncated to 8 hex chars)
- Provides namespace isolation for multiple projects
- Automatically generated from workspace path

### Freshness Metadata
Every cached result includes:
```json
{
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1",
    "file_count": 1247,
    "node_count": 8934,
    "edge_count": 15672
  }
}
```

### Filter Hashing
- Filters are hashed (SHA256, truncated to 8 hex) for cache keys
- Same filter → same hash → cache hit
- Different filter → different hash → separate cache entry

### Manual Invalidation
- wicked-search controls invalidation (on re-index)
- Consumers can check freshness with `is_fresh()`
- No automatic TTL or file-based invalidation

## Performance

### Query Performance
| Query Type | Cold (no cache) | Warm (cached) | Speedup |
|------------|----------------|---------------|---------|
| symbol_deps | ~500ms | ~10ms | **50x** |
| file_refs | ~300ms | ~5ms | **60x** |
| def_lookup | ~200ms | ~2ms | **100x** |
| call_chain | ~1s | ~20ms | **50x** |

### Cache Size
| Project Size | Nodes | Edges | Cache Size |
|--------------|-------|-------|------------|
| Small (1K files) | ~5K | ~10K | ~2 MB |
| Medium (10K files) | ~50K | ~100K | ~20 MB |
| Large (100K files) | ~500K | ~1M | ~200 MB |

## Versioning

**Current Version**: 1.0.0

Semantic versioning:
- **Major** (1.x.x → 2.0.0): Breaking changes, consumer updates required
- **Minor** (1.0.x → 1.1.0): Additive changes, backward compatible
- **Patch** (1.0.0 → 1.0.1): Bug fixes, no schema changes

Consumers MUST check version compatibility:
```python
if not client._is_compatible(cached_version):
    raise VersionMismatchError("Update wicked-search plugin")
```

## Integration Points

### For Plugin Authors (Consumers)

1. **Add dependency**:
   ```python
   from graph_client import GraphClient
   ```

2. **Initialize client**:
   ```python
   client = GraphClient(workspace_path=".")
   ```

3. **Check freshness** (recommended):
   ```python
   if not client.is_fresh(max_age_seconds=3600):
       raise CacheStaleError("Please re-index")
   ```

4. **Query data**:
   ```python
   deps = client.get_symbol_dependencies()
   refs = client.get_file_references()
   loc = client.lookup_definition(name="User")
   chain = client.get_call_chain(symbol_id="...")
   ```

### For wicked-search (Producer)

1. **Export after indexing**:
   ```python
   exporter = GraphExporter(cache)
   result = exporter.export_all(graph, workspace_path)
   ```

2. **Invalidate on re-index**:
   ```python
   exporter.invalidate_all(workspace_hash)
   ```

## Error Handling

### CacheStaleError
Raised when:
- Cache miss (no data)
- Workspace hash mismatch
- Age exceeds `max_age_seconds`

**Solution**: Re-run `/wicked-search:index <path>`

### VersionMismatchError
Raised when:
- Major version incompatible

**Solution**: Update wicked-search plugin

### Example
```python
from graph_client import CacheStaleError, VersionMismatchError

try:
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    print("Run: /wicked-search:index")
except VersionMismatchError:
    print("Update wicked-search plugin")
```

## Common Patterns

### 1. Fresh Check + Query
```python
if not client.is_fresh(max_age_seconds=1800):
    raise CacheStaleError("Please re-index")
deps = client.get_symbol_dependencies()
```

### 2. Graceful Degradation
```python
try:
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    deps = fallback_to_jsonl_parsing()
```

### 3. Batch Queries
```python
# Reuse client for multiple queries
deps = client.get_symbol_dependencies()
refs = client.get_file_references()
loc = client.lookup_definition(name="User")
```

### 4. Filter for Performance
```python
# Good: Filter at cache level
deps = client.get_symbol_dependencies(
    filter={"paths": ["src/auth/"]}
)

# Bad: Load all then filter in Python
deps = client.get_symbol_dependencies()
auth_symbols = [s for s in deps.symbols if "auth" in s.file]
```

## Testing

Run the test suite:
```bash
cd plugins/wicked-search/scripts
python test_graph_cache.py
```

Tests cover:
- ✓ Symbol deps export
- ✓ File refs export
- ✓ Def lookup export
- ✓ Call chain export
- ✓ Export all query types
- ✓ Client symbol deps query
- ✓ Client definition lookup
- ✓ Freshness validation
- ✓ Filter parameter hashing
- ✓ Cache invalidation

## Files

### Implementation
- `scripts/graph_export.py` - GraphExporter (producer API)
- `scripts/graph_client.py` - GraphClient (consumer API)
- `scripts/test_graph_cache.py` - Test suite

### Documentation
- `docs/README.md` - This file
- `docs/QUICKREF.md` - One-page quick reference
- `docs/cache-schema.md` - Complete schema specification
- `docs/cache-architecture.md` - Architecture diagrams
- `docs/cache-usage-examples.md` - Real-world examples
- `docs/IMPLEMENTATION-SUMMARY.md` - Implementation summary

## Next Steps

### Phase 1: Core Integration (wicked-search)
- [ ] Add export call to indexing pipeline
- [ ] Add `/wicked-search:export` command
- [ ] Auto-export on `/wicked-search:index` completion
- [ ] Cache invalidation on re-index

### Phase 2: Consumer Adoption (wicked-crew)
- [ ] Replace JSONL parsing with GraphClient
- [ ] Add freshness checks to workflow gates
- [ ] Update quality-checker agent
- [ ] Add blast radius analysis

### Phase 3: Consumer Adoption (wicked-product)
- [ ] Integrate GraphClient for PR impact
- [ ] Use file_refs for changed file queries
- [ ] Add call_chain for "what breaks"
- [ ] Update code review agents

### Phase 4: Optimization
- [ ] Implement incremental updates
- [ ] Add compression for large graphs
- [ ] Multi-workspace support
- [ ] Cache warming for CI/CD

## Support & Feedback

**Issues**: Report via GitHub issues
**Questions**: See [cache-usage-examples.md](cache-usage-examples.md)
**Design Questions**: See [cache-schema.md](cache-schema.md)

## License

MIT
