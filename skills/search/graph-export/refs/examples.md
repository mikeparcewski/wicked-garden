# Graph Export Examples

Real-world usage patterns for cross-plugin graph access.

## Example 1: Impact Analysis Plugin

Find what's affected by changing a function:

```python
from graph_client import GraphClient, CacheStaleError

def analyze_impact(workspace: str, symbol_name: str) -> dict:
    """Analyze impact of changing a symbol."""
    client = GraphClient(workspace)

    # Find the symbol
    location = client.lookup_definition(name=symbol_name)
    if not location:
        return {"error": f"Symbol '{symbol_name}' not found"}

    # Get call chain (blast radius)
    try:
        chain = client.get_call_chain(location.id, max_depth=5)
    except CacheStaleError:
        return {"error": "Graph cache stale - run /wicked-garden:search:index"}

    if not chain.chains:
        return {"symbol": symbol_name, "upstream": [], "downstream": []}

    root = chain.chains[0]
    return {
        "symbol": symbol_name,
        "location": f"{location.file}:{location.line_start}",
        "upstream": [{"name": u.name, "file": u.file} for u in root.upstream],
        "downstream": [{"name": d.name, "file": d.file} for d in root.downstream],
        "total_affected": len(root.upstream) + len(root.downstream)
    }
```

## Example 2: Documentation Coverage

Find undocumented public functions:

```python
from graph_client import GraphClient

def find_undocumented(workspace: str) -> list:
    """Find public functions without documentation."""
    client = GraphClient(workspace)

    result = client.get_symbol_dependencies(filter={
        "node_types": ["FUNCTION", "METHOD"],
        "domain": "code"
    })

    undocumented = []
    for symbol in result.symbols:
        # Skip private/internal
        if symbol.name.startswith("_"):
            continue

        # Check if any doc references this symbol
        has_doc = any(
            dep.type == "DOCUMENTED_BY"
            for dep in symbol.dependents
        )

        if not has_doc:
            undocumented.append({
                "name": symbol.name,
                "file": symbol.file,
                "line": symbol.line_start
            })

    return undocumented
```

## Example 3: Dependency Graph for Visualization

Export data for graph visualization:

```python
from graph_client import GraphClient
import json

def export_for_viz(workspace: str, output_file: str):
    """Export graph data for D3/Cytoscape visualization."""
    client = GraphClient(workspace)

    result = client.get_symbol_dependencies()

    nodes = []
    edges = []

    for symbol in result.symbols:
        nodes.append({
            "id": symbol.id,
            "label": symbol.name,
            "type": symbol.type,
            "file": symbol.file
        })

        for dep in symbol.dependencies:
            edges.append({
                "source": symbol.id,
                "target": dep.target_id,
                "type": dep.type
            })

    graph_data = {"nodes": nodes, "edges": edges}

    with open(output_file, "w") as f:
        json.dump(graph_data, f, indent=2)

    return {"nodes": len(nodes), "edges": len(edges)}
```

## Example 4: File Coupling Analysis

Find tightly coupled file pairs:

```python
from graph_client import GraphClient
from collections import defaultdict

def find_coupled_files(workspace: str, threshold: int = 5) -> list:
    """Find file pairs with many cross-references."""
    client = GraphClient(workspace)

    result = client.get_symbol_dependencies()

    # Count references between file pairs
    coupling = defaultdict(int)

    for symbol in result.symbols:
        source_file = symbol.file
        for dep in symbol.dependencies:
            # Extract file from target_id
            target_file = dep.target_id.split("::")[0] if "::" in dep.target_id else dep.target_id
            if source_file != target_file:
                pair = tuple(sorted([source_file, target_file]))
                coupling[pair] += 1

    # Filter by threshold
    coupled = [
        {"files": list(pair), "references": count}
        for pair, count in coupling.items()
        if count >= threshold
    ]

    return sorted(coupled, key=lambda x: x["references"], reverse=True)
```

## Example 5: Graceful Degradation

Handle missing graph data gracefully:

```python
from graph_client import GraphClient, CacheStaleError, VersionMismatchError

def get_dependencies_safe(workspace: str, symbol: str) -> dict:
    """Get dependencies with graceful fallback."""
    try:
        client = GraphClient(workspace)

        # Check freshness first
        if not client.is_fresh():
            return {
                "status": "stale",
                "message": "Graph data is stale, results may be outdated",
                "dependencies": _fallback_grep(workspace, symbol)
            }

        location = client.lookup_definition(name=symbol)
        if not location:
            return {"status": "not_found", "message": f"Symbol '{symbol}' not found"}

        deps = client.get_symbol_dependencies(filter={"paths": [location.file]})

        return {
            "status": "ok",
            "symbol": symbol,
            "dependencies": [d.target_id for s in deps.symbols for d in s.dependencies if s.id == location.id]
        }

    except CacheStaleError:
        return {
            "status": "cache_miss",
            "message": "Run /wicked-garden:search:index first",
            "dependencies": _fallback_grep(workspace, symbol)
        }
    except VersionMismatchError as e:
        return {
            "status": "version_error",
            "message": str(e),
            "dependencies": []
        }

def _fallback_grep(workspace: str, symbol: str) -> list:
    """Fallback: grep for symbol usage."""
    import subprocess
    try:
        result = subprocess.run(
            ["grep", "-rn", symbol, workspace],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip().split("\n")[:10]
    except Exception:
        return []
```

## Integration Checklist

1. Import `GraphClient` from wicked-search scripts
2. Initialize with workspace path
3. Check `is_fresh()` before critical operations
4. Handle `CacheStaleError` and `VersionMismatchError`
5. Use filters to limit scope when possible
6. Provide fallback behavior for degraded mode
