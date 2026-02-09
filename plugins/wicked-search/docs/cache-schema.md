# Wicked-Search Graph Export Cache Schema

**Version**: 1.0.0
**Target**: wicked-cache integration for cross-plugin graph consumption

## Overview

This schema defines how wicked-search exports graph data to wicked-cache for consumption by other plugins (wicked-crew, wicked-product, etc.). The design balances:

- **Namespace isolation**: Each workspace gets its own cache namespace
- **Query-optimized format**: Pre-computed views for common queries
- **Freshness tracking**: Workspace hash + timestamp for invalidation
- **Filter overrides**: Consumers can override default workspace scope

---

## Cache Key Naming Convention

All cache keys follow this pattern:

```
{namespace}:{query_type}:{scope}[:{filter_hash}]
```

### Components

| Component | Description | Example |
|-----------|-------------|---------|
| `namespace` | Plugin namespace (always `wicked-search`) | `wicked-search` |
| `query_type` | Type of query result | `symbol_deps`, `file_refs`, `def_lookup`, `call_chain` |
| `scope` | Workspace identifier (hash of root path) | `a3f5e2d1` |
| `filter_hash` | Optional: hash of filter params (for overrides) | `b7c9d4e1` |

### Examples

```
wicked-search:symbol_deps:a3f5e2d1                    # Default workspace scope
wicked-search:file_refs:a3f5e2d1:b7c9d4e1             # With path filter override
wicked-search:def_lookup:a3f5e2d1                     # Definition index
wicked-search:call_chain:a3f5e2d1:c8d2e5f3            # Filtered by depth
```

---

## Data Formats

### 1. Symbol Dependencies (`symbol_deps`)

**Purpose**: Get all dependencies (outgoing) and dependents (incoming) for symbols

**Cache Key**: `wicked-search:symbol_deps:{workspace_hash}[:{filter_hash}]`

**Schema**:
```json
{
  "version": "1.0.0",
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1b4c8e7f2",
    "file_count": 1247,
    "node_count": 8934
  },
  "filter": {
    "paths": ["src/", "lib/"],
    "node_types": ["function", "class", "method"],
    "domain": "code"
  },
  "symbols": [
    {
      "id": "src/auth.py::authenticate_user",
      "name": "authenticate_user",
      "type": "function",
      "file": "src/auth.py",
      "line_start": 42,
      "line_end": 67,
      "dependencies": [
        {
          "target_id": "src/db.py::User.get_by_email",
          "type": "calls",
          "line": 45
        },
        {
          "target_id": "src/crypto.py::verify_password",
          "type": "calls",
          "line": 52
        }
      ],
      "dependents": [
        {
          "source_id": "src/api/login.py::login_handler",
          "type": "calls",
          "line": 23
        }
      ]
    }
  ]
}
```

### 2. File References (`file_refs`)

**Purpose**: Get all symbols and references for specific files

**Cache Key**: `wicked-search:file_refs:{workspace_hash}[:{filter_hash}]`

**Schema**:
```json
{
  "version": "1.0.0",
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1b4c8e7f2",
    "file_count": 1247,
    "node_count": 8934
  },
  "filter": {
    "files": ["src/auth.py", "src/db.py"]
  },
  "files": [
    {
      "path": "src/auth.py",
      "mtime": 1706789234.567,
      "size": 12847,
      "domain": "code",
      "symbols": [
        {
          "id": "src/auth.py::authenticate_user",
          "name": "authenticate_user",
          "type": "function",
          "line_start": 42,
          "line_end": 67,
          "calls_out": 2,
          "calls_in": 1
        },
        {
          "id": "src/auth.py::AuthService",
          "name": "AuthService",
          "type": "class",
          "line_start": 70,
          "line_end": 150,
          "calls_out": 5,
          "calls_in": 8
        }
      ],
      "imports": [
        "hashlib",
        "jwt",
        "src.db"
      ]
    }
  ]
}
```

### 3. Definition Lookup (`def_lookup`)

**Purpose**: Fast symbol-to-location resolution (for jump-to-definition)

**Cache Key**: `wicked-search:def_lookup:{workspace_hash}[:{filter_hash}]`

**Schema**:
```json
{
  "version": "1.0.0",
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1b4c8e7f2",
    "file_count": 1247,
    "node_count": 8934
  },
  "filter": {
    "node_types": ["function", "class", "method"],
    "domain": "code"
  },
  "index": {
    "by_name": {
      "authenticate_user": [
        {
          "id": "src/auth.py::authenticate_user",
          "qualified_name": "auth.authenticate_user",
          "file": "src/auth.py",
          "line_start": 42,
          "type": "function"
        }
      ],
      "AuthService": [
        {
          "id": "src/auth.py::AuthService",
          "qualified_name": "auth.AuthService",
          "file": "src/auth.py",
          "line_start": 70,
          "type": "class"
        }
      ]
    },
    "by_qualified_name": {
      "auth.authenticate_user": {
        "id": "src/auth.py::authenticate_user",
        "file": "src/auth.py",
        "line_start": 42,
        "type": "function"
      },
      "auth.AuthService": {
        "id": "src/auth.py::AuthService",
        "file": "src/auth.py",
        "line_start": 70,
        "type": "class"
      }
    }
  }
}
```

### 4. Call Chain (`call_chain`)

**Purpose**: Transitive dependency analysis (blast radius)

**Cache Key**: `wicked-search:call_chain:{workspace_hash}[:{filter_hash}]`

**Schema**:
```json
{
  "version": "1.0.0",
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1b4c8e7f2",
    "file_count": 1247,
    "node_count": 8934
  },
  "filter": {
    "max_depth": 5,
    "ref_types": ["calls", "imports"]
  },
  "chains": [
    {
      "root_id": "src/api/login.py::login_handler",
      "root_name": "login_handler",
      "root_file": "src/api/login.py",
      "downstream": [
        {
          "id": "src/auth.py::authenticate_user",
          "name": "authenticate_user",
          "file": "src/auth.py",
          "depth": 1,
          "path": ["src/api/login.py::login_handler"]
        },
        {
          "id": "src/db.py::User.get_by_email",
          "name": "get_by_email",
          "file": "src/db.py",
          "depth": 2,
          "path": [
            "src/api/login.py::login_handler",
            "src/auth.py::authenticate_user"
          ]
        }
      ],
      "upstream": [
        {
          "id": "src/routes.py::setup_routes",
          "name": "setup_routes",
          "file": "src/routes.py",
          "depth": 1,
          "path": ["src/api/login.py::login_handler"]
        }
      ]
    }
  ]
}
```

---

## Freshness Metadata Schema

Every cached result includes freshness metadata for invalidation:

```json
{
  "freshness": {
    "indexed_at": "2026-02-01T12:34:56Z",
    "workspace_hash": "a3f5e2d1b4c8e7f2",
    "file_count": 1247,
    "node_count": 8934,
    "edge_count": 15672
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `indexed_at` | ISO8601 string | When the index was last updated |
| `workspace_hash` | hex string | Hash of workspace root path (for namespace isolation) |
| `file_count` | integer | Total files in index |
| `node_count` | integer | Total symbols in index |
| `edge_count` | integer | Total references in index |

### Invalidation Strategy

Consumers should invalidate cache when:

1. **Workspace change**: `workspace_hash` differs from current workspace
2. **Staleness**: `indexed_at` is too old (configurable TTL, default 1 hour)
3. **Index update**: wicked-search signals cache invalidation on re-index

---

## Filter Parameter Schema

Filters allow consumers to override the default workspace-wide scope:

```json
{
  "filter": {
    "paths": ["src/auth/", "lib/security/"],
    "exclude_paths": ["test/", "vendor/"],
    "node_types": ["function", "class"],
    "domain": "code",
    "max_depth": 5,
    "ref_types": ["calls", "imports"]
  }
}
```

### Filter Fields

| Field | Type | Applies To | Description |
|-------|------|------------|-------------|
| `paths` | string[] | All | Only include symbols from these paths |
| `exclude_paths` | string[] | All | Exclude symbols from these paths |
| `node_types` | NodeType[] | symbol_deps, def_lookup | Filter by symbol type |
| `domain` | "code" \| "doc" | All | Filter by domain |
| `files` | string[] | file_refs | Specific files to include |
| `max_depth` | integer | call_chain | Max traversal depth |
| `ref_types` | string[] | call_chain | Reference types to follow |

### Filter Hashing

Filters are hashed (SHA256, truncated to 8 hex chars) to generate cache keys:

```python
import hashlib
import json

def hash_filter(filter_dict: dict) -> str:
    """Generate stable hash for filter parameters."""
    canonical = json.dumps(filter_dict, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:8]
```

---

## Versioning Strategy

### Schema Version

Each query result includes `"version": "1.0.0"` for backward compatibility.

**Versioning rules**:
- **Major**: Breaking changes (field removals, type changes)
- **Minor**: Additive changes (new optional fields)
- **Patch**: Bug fixes (no schema changes)

### Compatibility

Consumers MUST:
1. Check `version` field in cached results
2. Reject results with major version mismatch
3. Gracefully handle missing fields (forward compatibility)

Example version check:

```python
def is_compatible(cached_version: str, required_version: str) -> bool:
    """Check if cached version is compatible with required version."""
    cached_major = int(cached_version.split('.')[0])
    required_major = int(required_version.split('.')[0])
    return cached_major == required_major
```

---

## Python Interface

### High-Level API

```python
from wicked_search.graph_export import GraphExporter
from wicked_cache.cache import namespace

# Initialize
cache = namespace("wicked-search")
exporter = GraphExporter(cache=cache)

# Export to cache (called by wicked-search after indexing)
exporter.export_all(
    graph=symbol_graph,
    workspace_path="/path/to/project"
)

# Consumer API (used by other plugins)
from wicked_search.graph_client import GraphClient

client = GraphClient(workspace_path="/path/to/project")

# Get symbol dependencies
deps = client.get_symbol_dependencies(
    filter={"paths": ["src/"], "node_types": ["function"]}
)

# Get file references
refs = client.get_file_references(files=["src/auth.py"])

# Lookup definition
loc = client.lookup_definition(name="authenticate_user")

# Get call chain
chain = client.get_call_chain(
    symbol_id="src/auth.py::authenticate_user",
    max_depth=5
)

# Check freshness
fresh = client.is_fresh(max_age_seconds=3600)
```

### GraphExporter Interface

```python
class GraphExporter:
    """Exports wicked-search graph to wicked-cache."""

    def __init__(self, cache: NamespacedCache):
        """Initialize with wicked-cache namespace."""
        self.cache = cache

    def export_all(
        self,
        graph: SymbolGraph,
        workspace_path: str,
        force: bool = False
    ) -> ExportResult:
        """
        Export all query types to cache.

        Args:
            graph: SymbolGraph instance to export
            workspace_path: Root path of workspace (for hash generation)
            force: Force re-export even if cache is fresh

        Returns:
            ExportResult with statistics
        """

    def export_symbol_deps(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        filter: Optional[Dict] = None
    ) -> str:
        """
        Export symbol dependencies view.

        Returns:
            Cache key
        """

    def export_file_refs(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        filter: Optional[Dict] = None
    ) -> str:
        """
        Export file references view.

        Returns:
            Cache key
        """

    def export_def_lookup(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        filter: Optional[Dict] = None
    ) -> str:
        """
        Export definition lookup index.

        Returns:
            Cache key
        """

    def export_call_chain(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        filter: Optional[Dict] = None
    ) -> str:
        """
        Export call chain analysis.

        Returns:
            Cache key
        """

    def invalidate_all(self, workspace_hash: str) -> int:
        """
        Invalidate all cache entries for a workspace.

        Returns:
            Count of invalidated entries
        """
```

### GraphClient Interface

```python
class GraphClient:
    """Consumer API for reading cached graph data."""

    def __init__(
        self,
        workspace_path: str,
        cache: Optional[NamespacedCache] = None
    ):
        """
        Initialize client.

        Args:
            workspace_path: Root path of workspace
            cache: Optional wicked-cache namespace (auto-created if None)
        """
        self.workspace_hash = self._hash_workspace(workspace_path)
        self.cache = cache or namespace("wicked-search")

    def get_symbol_dependencies(
        self,
        filter: Optional[Dict] = None
    ) -> SymbolDepsResult:
        """
        Get symbol dependencies with optional filter.

        Args:
            filter: Optional filter parameters

        Returns:
            SymbolDepsResult with symbols and relationships

        Raises:
            CacheStaleError: If cache is stale or missing
        """

    def get_file_references(
        self,
        files: Optional[List[str]] = None
    ) -> FileRefsResult:
        """
        Get file references.

        Args:
            files: Optional list of file paths to include

        Returns:
            FileRefsResult with file-level symbol data

        Raises:
            CacheStaleError: If cache is stale or missing
        """

    def lookup_definition(
        self,
        name: Optional[str] = None,
        qualified_name: Optional[str] = None
    ) -> Optional[SymbolLocation]:
        """
        Lookup symbol definition location.

        Args:
            name: Simple name (may return multiple results)
            qualified_name: Fully qualified name (unique)

        Returns:
            SymbolLocation or None if not found

        Raises:
            CacheStaleError: If cache is stale or missing
        """

    def get_call_chain(
        self,
        symbol_id: str,
        max_depth: int = 5,
        ref_types: Optional[List[str]] = None
    ) -> CallChainResult:
        """
        Get transitive call chain.

        Args:
            symbol_id: Root symbol ID
            max_depth: Max traversal depth
            ref_types: Reference types to follow

        Returns:
            CallChainResult with upstream/downstream chains

        Raises:
            CacheStaleError: If cache is stale or missing
        """

    def is_fresh(self, max_age_seconds: int = 3600) -> bool:
        """
        Check if cache is fresh.

        Args:
            max_age_seconds: Max age in seconds (default 1 hour)

        Returns:
            True if cache is fresh
        """

    def get_freshness(self) -> Optional[FreshnessMetadata]:
        """
        Get freshness metadata.

        Returns:
            FreshnessMetadata or None if cache is empty
        """
```

### Result Types

```python
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class FreshnessMetadata:
    """Freshness metadata from cache."""
    indexed_at: str
    workspace_hash: str
    file_count: int
    node_count: int
    edge_count: int

@dataclass
class SymbolDependency:
    """A single dependency relationship."""
    target_id: str
    type: str
    line: int

@dataclass
class SymbolDependent:
    """A single dependent relationship."""
    source_id: str
    type: str
    line: int

@dataclass
class SymbolDepsEntry:
    """Symbol with dependencies and dependents."""
    id: str
    name: str
    type: str
    file: str
    line_start: int
    line_end: int
    dependencies: List[SymbolDependency]
    dependents: List[SymbolDependent]

@dataclass
class SymbolDepsResult:
    """Result for symbol dependencies query."""
    version: str
    freshness: FreshnessMetadata
    filter: Dict
    symbols: List[SymbolDepsEntry]

@dataclass
class FileSymbol:
    """Symbol summary for file references."""
    id: str
    name: str
    type: str
    line_start: int
    line_end: int
    calls_out: int
    calls_in: int

@dataclass
class FileRef:
    """File with symbols."""
    path: str
    mtime: float
    size: int
    domain: str
    symbols: List[FileSymbol]
    imports: List[str]

@dataclass
class FileRefsResult:
    """Result for file references query."""
    version: str
    freshness: FreshnessMetadata
    filter: Dict
    files: List[FileRef]

@dataclass
class SymbolLocation:
    """Symbol location for definition lookup."""
    id: str
    qualified_name: str
    file: str
    line_start: int
    type: str

@dataclass
class CallChainEntry:
    """Single entry in a call chain."""
    id: str
    name: str
    file: str
    depth: int
    path: List[str]

@dataclass
class CallChain:
    """Call chain for a symbol."""
    root_id: str
    root_name: str
    root_file: str
    downstream: List[CallChainEntry]
    upstream: List[CallChainEntry]

@dataclass
class CallChainResult:
    """Result for call chain query."""
    version: str
    freshness: FreshnessMetadata
    filter: Dict
    chains: List[CallChain]

@dataclass
class ExportResult:
    """Result from export operation."""
    workspace_hash: str
    exported_at: str
    keys_written: List[str]
    stats: Dict[str, int]
```

### Error Handling

```python
class CacheStaleError(Exception):
    """Raised when cache is stale or missing."""
    pass

class VersionMismatchError(Exception):
    """Raised when cache version is incompatible."""
    pass
```

---

## Cache Invalidation Strategy

### Automatic Invalidation

1. **On re-index**: wicked-search invalidates all cache keys after updating index
2. **File-based**: wicked-cache tracks `indexed_at` timestamp (via index metadata.json)
3. **TTL**: Optional TTL mode (default: manual invalidation)

### Manual Invalidation

Consumers can force refresh:

```python
# Invalidate all
exporter.invalidate_all(workspace_hash="a3f5e2d1")

# Or specific query type
cache.invalidate(f"wicked-search:symbol_deps:{workspace_hash}")
```

---

## Usage Examples

### Example 1: wicked-crew needs symbol dependencies

```python
from wicked_search.graph_client import GraphClient

client = GraphClient(workspace_path="/path/to/project")

# Get dependencies for security-related functions
result = client.get_symbol_dependencies(
    filter={
        "paths": ["src/auth/", "src/security/"],
        "node_types": ["function", "method"]
    }
)

# Check freshness
if not client.is_fresh(max_age_seconds=1800):  # 30 min
    print("Warning: Graph cache is stale, consider re-indexing")

# Process results
for symbol in result.symbols:
    print(f"{symbol.name} calls {len(symbol.dependencies)} functions")
    print(f"{symbol.name} is called by {len(symbol.dependents)} functions")
```

### Example 2: wicked-product needs file references for PR review

```python
from wicked_search.graph_client import GraphClient

client = GraphClient(workspace_path="/path/to/project")

# Get references for changed files
changed_files = ["src/auth.py", "src/db.py"]
result = client.get_file_references(files=changed_files)

for file in result.files:
    print(f"\n{file.path}:")
    print(f"  Symbols: {len(file.symbols)}")
    print(f"  Imports: {', '.join(file.imports)}")

    for sym in file.symbols:
        print(f"  - {sym.name} ({sym.type}): "
              f"{sym.calls_out} calls out, {sym.calls_in} calls in")
```

### Example 3: wicked-crew needs blast radius analysis

```python
from wicked_search.graph_client import GraphClient

client = GraphClient(workspace_path="/path/to/project")

# Analyze impact of changing a function
result = client.get_call_chain(
    symbol_id="src/auth.py::authenticate_user",
    max_depth=5,
    ref_types=["calls", "imports"]
)

for chain in result.chains:
    print(f"\nBlast Radius for {chain.root_name}:")
    print(f"  Downstream: {len(chain.downstream)} symbols")
    print(f"  Upstream: {len(chain.upstream)} symbols")

    # Show first few downstream dependencies
    for entry in chain.downstream[:5]:
        print(f"  - [{entry.depth}] {entry.name} ({entry.file})")
```

---

## Migration Path

### Phase 1: Export Implementation (wicked-search)
1. Implement `GraphExporter` class
2. Add export hook to indexing pipeline
3. Add `/wicked-search:export` command for manual export

### Phase 2: Client Implementation (wicked-search)
1. Implement `GraphClient` class
2. Add result type dataclasses
3. Document consumer API

### Phase 3: Consumer Adoption (wicked-crew, wicked-product, etc.)
1. Replace direct JSONL parsing with `GraphClient`
2. Add freshness checks to workflows
3. Update documentation

---

## Performance Considerations

### Cache Size

Estimated cache size for typical projects:

| Project Size | Nodes | Edges | Cache Size (uncompressed) |
|--------------|-------|-------|---------------------------|
| Small (1K files) | ~5K | ~10K | ~2 MB |
| Medium (10K files) | ~50K | ~100K | ~20 MB |
| Large (100K files) | ~500K | ~1M | ~200 MB |

### Query Performance

| Query Type | Cold (no cache) | Warm (cached) |
|------------|----------------|---------------|
| symbol_deps | ~500ms | ~10ms |
| file_refs | ~300ms | ~5ms |
| def_lookup | ~200ms | ~2ms |
| call_chain | ~1s | ~20ms |

### Cache Warming

For CI/CD environments, pre-warm cache:

```python
# After indexing, export all views
exporter.export_all(graph=symbol_graph, workspace_path=".")

# Consumers get instant results
client = GraphClient(workspace_path=".")
deps = client.get_symbol_dependencies()  # Fast!
```

---

## Future Enhancements

### Incremental Updates

Track deltas between index updates to minimize cache writes:

```python
exporter.export_incremental(
    graph=symbol_graph,
    changed_files=["src/auth.py"],
    workspace_hash="a3f5e2d1"
)
```

### Compression

For large graphs, add optional gzip compression:

```python
cache.set(
    key,
    value,
    options={"compress": True, "mode": "manual"}
)
```

### Multi-Workspace Support

Support multiple workspace roots in a single cache:

```python
client = GraphClient(workspace_paths=[
    "/path/to/monorepo/pkg1",
    "/path/to/monorepo/pkg2"
])
```
