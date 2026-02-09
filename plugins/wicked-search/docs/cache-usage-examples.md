# Graph Cache Usage Examples

Real-world scenarios demonstrating how to use the wicked-search graph cache API.

## Table of Contents
1. [Basic Setup](#basic-setup)
2. [wicked-crew: Dependency Analysis](#wicked-crew-dependency-analysis)
3. [wicked-product: PR Impact Review](#wicked-product-pr-impact-review)
4. [wicked-kanban: Task Blast Radius](#wicked-kanban-task-blast-radius)
5. [Custom Plugin: Security Audit](#custom-plugin-security-audit)
6. [Error Handling](#error-handling)
7. [Cache Management](#cache-management)

---

## Basic Setup

### Producer (wicked-search)

After indexing, export graph to cache:

```python
from graph_export import GraphExporter
from cache import namespace

def index_and_export(workspace_path: str):
    # 1. Build graph (existing wicked-search indexing)
    from symbol_graph import SymbolGraph
    from indexer import build_graph

    graph = build_graph(workspace_path)

    # 2. Export to cache
    cache = namespace("wicked-search")
    exporter = GraphExporter(cache)
    result = exporter.export_all(graph, workspace_path)

    print(f"✓ Exported {result.stats['total_symbols']} symbols")
    print(f"✓ Cache keys: {', '.join(result.keys_written)}")

    return result
```

### Consumer (any plugin)

Read from cache:

```python
from graph_client import GraphClient, CacheStaleError

def get_cached_graph(workspace_path: str):
    client = GraphClient(workspace_path)

    # Check freshness
    if not client.is_fresh(max_age_seconds=3600):  # 1 hour
        raise CacheStaleError("Graph cache is stale, please re-index")

    # Query symbol dependencies
    deps = client.get_symbol_dependencies()
    print(f"✓ Loaded {len(deps.symbols)} symbols from cache")

    return deps
```

---

## wicked-crew: Dependency Analysis

**Scenario**: Analyze dependencies for a feature development task

```python
from graph_client import GraphClient

def analyze_feature_dependencies(workspace_path: str, feature_paths: list):
    """
    Analyze dependencies for files touched by a feature.

    Args:
        workspace_path: Project root
        feature_paths: List of paths involved in feature

    Returns:
        Analysis report with dependency counts
    """
    client = GraphClient(workspace_path)

    # Get dependencies for feature paths only
    deps_result = client.get_symbol_dependencies(
        filter={
            "paths": feature_paths,
            "node_types": ["function", "class", "method"]
        }
    )

    # Analyze
    total_symbols = len(deps_result.symbols)
    total_deps = sum(len(s.dependencies) for s in deps_result.symbols)
    total_dependents = sum(len(s.dependents) for s in deps_result.symbols)

    # Find symbols with high coupling
    high_coupling = [
        s for s in deps_result.symbols
        if len(s.dependencies) + len(s.dependents) > 10
    ]

    # Find symbols with no tests (heuristic: no dependents in test/)
    untested = [
        s for s in deps_result.symbols
        if not any("test" in d.source_id for d in s.dependents)
    ]

    report = {
        "total_symbols": total_symbols,
        "total_dependencies": total_deps,
        "total_dependents": total_dependents,
        "high_coupling_symbols": [
            {"name": s.name, "file": s.file, "coupling": len(s.dependencies) + len(s.dependents)}
            for s in high_coupling
        ],
        "potentially_untested": [
            {"name": s.name, "file": s.file}
            for s in untested
        ]
    }

    return report


# Usage
report = analyze_feature_dependencies(
    workspace_path=".",
    feature_paths=["src/auth/", "src/api/auth/"]
)

print(f"Feature involves {report['total_symbols']} symbols")
print(f"High coupling concerns: {len(report['high_coupling_symbols'])}")
print(f"Potentially untested: {len(report['potentially_untested'])}")
```

---

## wicked-product: PR Impact Review

**Scenario**: Analyze blast radius for changed files in a PR

```python
from graph_client import GraphClient

def analyze_pr_impact(workspace_path: str, changed_files: list):
    """
    Analyze impact of PR changes.

    Args:
        workspace_path: Project root
        changed_files: List of modified file paths

    Returns:
        Impact analysis with affected symbols
    """
    client = GraphClient(workspace_path)

    # Get file references for changed files
    file_refs = client.get_file_references(files=changed_files)

    # Collect all symbols in changed files
    changed_symbols = []
    for file_ref in file_refs.files:
        for symbol in file_ref.symbols:
            changed_symbols.append({
                "id": symbol.id,
                "name": symbol.name,
                "file": file_ref.path,
                "calls_in": symbol.calls_in,
                "calls_out": symbol.calls_out
            })

    # Analyze blast radius for each changed symbol
    impact_chains = []
    for symbol in changed_symbols:
        try:
            chain_result = client.get_call_chain(
                symbol_id=symbol["id"],
                max_depth=3,
                ref_types=["calls"]
            )

            if chain_result.chains:
                chain = chain_result.chains[0]
                impact_chains.append({
                    "symbol": symbol["name"],
                    "file": symbol["file"],
                    "downstream_count": len(chain.downstream),
                    "upstream_count": len(chain.upstream),
                    "blast_radius": len(chain.downstream) + len(chain.upstream)
                })
        except Exception as e:
            print(f"Warning: Could not analyze {symbol['name']}: {e}")

    # Sort by blast radius
    impact_chains.sort(key=lambda x: x["blast_radius"], reverse=True)

    return {
        "changed_files": len(changed_files),
        "changed_symbols": len(changed_symbols),
        "impact_analysis": impact_chains[:10],  # Top 10
        "total_affected": sum(c["blast_radius"] for c in impact_chains)
    }


# Usage in PR review
import subprocess

# Get changed files from git
result = subprocess.run(
    ["git", "diff", "--name-only", "main...HEAD"],
    capture_output=True,
    text=True
)
changed_files = result.stdout.strip().split("\n")

impact = analyze_pr_impact(workspace_path=".", changed_files=changed_files)

print(f"PR Impact Analysis:")
print(f"  Changed files: {impact['changed_files']}")
print(f"  Changed symbols: {impact['changed_symbols']}")
print(f"  Total affected: {impact['total_affected']}")
print(f"\nTop impact symbols:")
for item in impact['impact_analysis'][:5]:
    print(f"  - {item['symbol']} ({item['file']}): {item['blast_radius']} affected")
```

---

## wicked-kanban: Task Blast Radius

**Scenario**: Show blast radius for a task's affected files

```python
from graph_client import GraphClient

def get_task_blast_radius(workspace_path: str, task_files: list):
    """
    Calculate blast radius for task files.

    Args:
        workspace_path: Project root
        task_files: Files associated with task

    Returns:
        Blast radius data for visualization
    """
    client = GraphClient(workspace_path)

    # Get all symbols in task files
    file_refs = client.get_file_references(files=task_files)

    all_affected = set()
    symbol_details = []

    for file_ref in file_refs.files:
        for symbol in file_ref.symbols:
            # Get dependencies for this symbol
            try:
                deps_result = client.get_symbol_dependencies(
                    filter={"paths": [file_ref.path]}
                )

                # Find this symbol's deps
                sym_data = next(
                    (s for s in deps_result.symbols if s.id == symbol.id),
                    None
                )

                if sym_data:
                    # Collect all affected files
                    for dep in sym_data.dependencies:
                        # Extract file from target_id (format: "path/file.py::symbol")
                        file = dep.target_id.split("::")[0]
                        all_affected.add(file)

                    for dep in sym_data.dependents:
                        file = dep.source_id.split("::")[0]
                        all_affected.add(file)

                    symbol_details.append({
                        "name": symbol.name,
                        "file": file_ref.path,
                        "deps_count": len(sym_data.dependencies),
                        "dependents_count": len(sym_data.dependents)
                    })
            except Exception as e:
                print(f"Warning: Could not analyze {symbol.name}: {e}")

    return {
        "task_files": task_files,
        "task_file_count": len(task_files),
        "symbol_count": len(symbol_details),
        "affected_files": sorted(all_affected),
        "affected_file_count": len(all_affected),
        "symbols": symbol_details
    }


# Usage in kanban board
blast_radius = get_task_blast_radius(
    workspace_path=".",
    task_files=["src/auth.py", "src/api/login.py"]
)

print(f"Task Blast Radius:")
print(f"  Task files: {blast_radius['task_file_count']}")
print(f"  Symbols: {blast_radius['symbol_count']}")
print(f"  Affected files: {blast_radius['affected_file_count']}")
print(f"  Affected: {', '.join(blast_radius['affected_files'][:5])}...")
```

---

## Custom Plugin: Security Audit

**Scenario**: Find all authentication-related symbols and their callers

```python
from graph_client import GraphClient

def security_audit(workspace_path: str):
    """
    Audit security-related code paths.

    Args:
        workspace_path: Project root

    Returns:
        Security audit report
    """
    client = GraphClient(workspace_path)

    # Get all symbols in security-related paths
    deps_result = client.get_symbol_dependencies(
        filter={
            "paths": ["src/auth/", "src/security/", "src/crypto/"],
            "node_types": ["function", "class", "method"]
        }
    )

    # Classify symbols
    auth_entry_points = []
    crypto_functions = []
    password_handlers = []

    for symbol in deps_result.symbols:
        name_lower = symbol.name.lower()

        # Entry points (externally called)
        if len(symbol.dependents) > 0:
            # Check if called from outside security paths
            external_callers = [
                d for d in symbol.dependents
                if not any(d.source_id.startswith(p) for p in ["src/auth/", "src/security/"])
            ]
            if external_callers:
                auth_entry_points.append({
                    "name": symbol.name,
                    "file": symbol.file,
                    "external_callers": len(external_callers)
                })

        # Crypto functions
        if "encrypt" in name_lower or "decrypt" in name_lower or "hash" in name_lower:
            crypto_functions.append({
                "name": symbol.name,
                "file": symbol.file,
                "usage_count": len(symbol.dependents)
            })

        # Password handlers
        if "password" in name_lower:
            password_handlers.append({
                "name": symbol.name,
                "file": symbol.file,
                "dependents": len(symbol.dependents)
            })

    # Find definition locations for jump-to-definition
    critical_symbols = ["authenticate", "verify_password", "hash_password"]
    definitions = {}
    for sym_name in critical_symbols:
        loc = client.lookup_definition(name=sym_name)
        if loc:
            definitions[sym_name] = {
                "file": loc.file,
                "line": loc.line_start
            }

    return {
        "total_security_symbols": len(deps_result.symbols),
        "entry_points": auth_entry_points,
        "crypto_functions": crypto_functions,
        "password_handlers": password_handlers,
        "critical_definitions": definitions
    }


# Usage
audit = security_audit(workspace_path=".")

print(f"Security Audit Report:")
print(f"  Total security symbols: {audit['total_security_symbols']}")
print(f"\nEntry Points ({len(audit['entry_points'])}):")
for ep in audit['entry_points']:
    print(f"  - {ep['name']} ({ep['file']}): {ep['external_callers']} external callers")

print(f"\nCrypto Functions ({len(audit['crypto_functions'])}):")
for cf in audit['crypto_functions']:
    print(f"  - {cf['name']} ({cf['file']}): {cf['usage_count']} usages")

print(f"\nPassword Handlers ({len(audit['password_handlers'])}):")
for ph in audit['password_handlers']:
    print(f"  - {ph['name']} ({ph['file']})")
```

---

## Error Handling

### Handle stale cache

```python
from graph_client import GraphClient, CacheStaleError

def robust_query(workspace_path: str):
    client = GraphClient(workspace_path)

    try:
        # Check freshness first
        if not client.is_fresh(max_age_seconds=3600):
            print("Warning: Cache is older than 1 hour, consider re-indexing")

        # Query
        deps = client.get_symbol_dependencies()
        return deps

    except CacheStaleError as e:
        print(f"Cache miss: {e}")
        print("Please run: /wicked-search:index <path>")
        return None
```

### Handle version mismatch

```python
from graph_client import GraphClient, VersionMismatchError

def version_safe_query(workspace_path: str):
    client = GraphClient(workspace_path)

    try:
        deps = client.get_symbol_dependencies()
        return deps

    except VersionMismatchError as e:
        print(f"Version incompatibility: {e}")
        print("Please update wicked-search plugin")
        return None
```

### Graceful degradation

```python
from graph_client import GraphClient, CacheStaleError

def get_dependencies_with_fallback(workspace_path: str, symbol_id: str):
    """
    Get dependencies with fallback to direct JSONL parsing.
    """
    client = GraphClient(workspace_path)

    try:
        # Try cache first
        chain = client.get_call_chain(symbol_id=symbol_id)
        return chain.chains[0] if chain.chains else None

    except CacheStaleError:
        print("Cache miss, falling back to JSONL parsing...")

        # Fallback: parse JSONL directly (slower)
        from pathlib import Path
        import json

        index_path = Path.home() / ".something-wicked" / "wicked-search" / "graph.jsonl"
        if not index_path.exists():
            print("No index found, please run /wicked-search:index")
            return None

        # Parse JSONL (this is slower but works)
        with open(index_path) as f:
            for line in f:
                node = json.loads(line)
                if node["id"] == symbol_id:
                    return node

        return None
```

---

## Cache Management

### Force refresh

```python
from graph_export import GraphExporter
from graph_client import GraphClient
from cache import namespace

def force_refresh(workspace_path: str):
    """
    Force cache refresh even if fresh.
    """
    # Build graph
    from symbol_graph import SymbolGraph
    from indexer import build_graph

    graph = build_graph(workspace_path)

    # Invalidate old cache
    cache = namespace("wicked-search")
    exporter = GraphExporter(cache)
    client = GraphClient(workspace_path, cache)

    workspace_hash = client.workspace_hash
    count = exporter.invalidate_all(workspace_hash)
    print(f"✓ Invalidated {count} cache entries")

    # Export fresh data
    result = exporter.export_all(graph, workspace_path)
    print(f"✓ Exported {len(result.keys_written)} query types")

    return result
```

### Check cache status

```python
from graph_client import GraphClient

def cache_status(workspace_path: str):
    """
    Get cache status and statistics.
    """
    client = GraphClient(workspace_path)

    freshness = client.get_freshness()
    if freshness is None:
        return {
            "exists": False,
            "message": "No cache found"
        }

    from datetime import datetime, timezone

    indexed_at = datetime.fromisoformat(
        freshness.indexed_at.replace("Z", "+00:00")
    )
    age_seconds = (datetime.now(timezone.utc) - indexed_at).total_seconds()
    age_minutes = age_seconds / 60
    age_hours = age_minutes / 60

    return {
        "exists": True,
        "workspace_hash": freshness.workspace_hash,
        "indexed_at": freshness.indexed_at,
        "age_seconds": int(age_seconds),
        "age_display": f"{age_hours:.1f}h" if age_hours > 1 else f"{age_minutes:.0f}m",
        "file_count": freshness.file_count,
        "node_count": freshness.node_count,
        "edge_count": freshness.edge_count,
        "is_fresh": age_seconds < 3600  # 1 hour
    }


# Usage
status = cache_status(workspace_path=".")
if status["exists"]:
    print(f"Cache Status:")
    print(f"  Age: {status['age_display']}")
    print(f"  Files: {status['file_count']}")
    print(f"  Symbols: {status['node_count']}")
    print(f"  References: {status['edge_count']}")
    print(f"  Fresh: {'✓' if status['is_fresh'] else '✗'}")
else:
    print("No cache found, please run /wicked-search:index")
```

### Multi-project cache

```python
def compare_projects(project_paths: list):
    """
    Compare symbol counts across multiple projects.
    """
    from graph_client import GraphClient

    results = []
    for path in project_paths:
        client = GraphClient(path)
        freshness = client.get_freshness()

        if freshness:
            results.append({
                "path": path,
                "node_count": freshness.node_count,
                "edge_count": freshness.edge_count
            })
        else:
            results.append({
                "path": path,
                "node_count": 0,
                "edge_count": 0,
                "error": "No cache"
            })

    return results


# Usage
projects = ["~/project1", "~/project2", "~/project3"]
comparison = compare_projects(projects)

for proj in comparison:
    print(f"{proj['path']}: {proj['node_count']} symbols, {proj['edge_count']} refs")
```

---

## Tips and Best Practices

### 1. Check Freshness Before Critical Operations
```python
client = GraphClient(workspace_path)
if not client.is_fresh(max_age_seconds=1800):  # 30 min
    print("Warning: Cache may be stale")
    # Optionally re-index or warn user
```

### 2. Use Filters for Performance
```python
# Bad: Load all symbols then filter
deps = client.get_symbol_dependencies()
auth_symbols = [s for s in deps.symbols if "auth" in s.file]

# Good: Filter at cache level
deps = client.get_symbol_dependencies(
    filter={"paths": ["src/auth/"]}
)
```

### 3. Cache Workspace Hash for Reuse
```python
# Good: Reuse client instance
client = GraphClient(workspace_path)
deps1 = client.get_symbol_dependencies()
deps2 = client.get_file_references()

# Bad: Create new client each time (re-hashes workspace)
deps1 = GraphClient(workspace_path).get_symbol_dependencies()
deps2 = GraphClient(workspace_path).get_file_references()
```

### 4. Handle Missing Cache Gracefully
```python
from graph_client import CacheStaleError

try:
    deps = client.get_symbol_dependencies()
except CacheStaleError:
    # Provide helpful message
    print("Graph cache not found. Please run:")
    print("  /wicked-search:index <workspace_path>")
    return None
```

### 5. Use Qualified Names for Unique Lookups
```python
# Ambiguous: may return multiple results
loc = client.lookup_definition(name="User")

# Unique: returns exact match
loc = client.lookup_definition(qualified_name="auth.models.User")
```
