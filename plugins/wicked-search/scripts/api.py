#!/usr/bin/env python3
"""Wicked Search Data API — standard Plugin Data API interface.

Reads from JSONL index files and SQLite graph DBs under ~/.something-wicked/wicked-search/.
Stdlib-only — no tree-sitter or other dependencies needed for queries.

Usage:
    python3 api.py list symbols [--limit N] [--offset N]
    python3 api.py search symbols --query "ClassName" [--limit N]
    python3 api.py get symbols <id>
    python3 api.py stats symbols
    python3 api.py categories symbols [--limit N]
    python3 api.py list documents [--limit N]
    python3 api.py search documents --query "readme" [--limit N]
    python3 api.py list references [--limit N]
    python3 api.py search references --query "imports" [--limit N]
    python3 api.py list graph [--limit N]
    python3 api.py get graph <id>
    python3 api.py search graph --query "ClassName" [--limit N]
    python3 api.py stats graph
    python3 api.py traverse graph <id> [--depth N] [--direction both|in|out]
    python3 api.py hotspots graph [--limit N] [--layer LAYER] [--type TYPE]
    python3 api.py impact graph <column_id>
    python3 api.py list lineage [--limit N]
    python3 api.py search lineage --query "source_id" [--limit N]
    python3 api.py list services [--limit N]
    python3 api.py stats services
    python3 api.py content code <file_path> [--line-start N] [--line-end N]
    python3 api.py ide-url code <file_path> [--line N] [--ide vscode|idea|cursor]
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

INDEX_DIR = Path.home() / ".something-wicked" / "wicked-search"
VALID_SOURCES = {"symbols", "documents", "references", "graph", "lineage", "services", "projects", "code"}


def _validate_project_name(name: str) -> bool:
    """Validate project name: alphanumeric + hyphens, max 64 chars."""
    if not name or len(name) > 64:
        return False
    return all(c.isalnum() or c == '-' for c in name)


def _get_index_dir(project: str = None) -> Path:
    """
    Get index directory for a project or default.

    If project is specified, returns ~/.something-wicked/wicked-search/projects/{project}/
    Otherwise, returns ~/.something-wicked/wicked-search/ (backward compatible)
    """
    if project:
        if not _validate_project_name(project):
            _error("Invalid project name", "INVALID_PROJECT_NAME",
                   project=project, rule="alphanumeric + hyphens, max 64 chars")
        return INDEX_DIR / "projects" / project
    return INDEX_DIR


def _meta(source, total, limit=100, offset=0, **extra):
    """Build standard meta block."""
    meta = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Add extra fields like warning, project
    meta.update(extra)
    return meta


def _error(message, code, **details):
    """Print error to stderr and exit."""
    err = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


def _load_jsonl_index(project: str = None):
    """Load all JSONL index files and return nodes."""
    index_dir = _get_index_dir(project)
    if not index_dir.exists():
        return []

    nodes = []
    for jsonl_file in index_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        node = json.loads(line)
                        nodes.append(node)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return nodes


def _filter_by_domain(nodes, domain):
    """Filter nodes by domain (code/doc)."""
    return [n for n in nodes if n.get("domain") == domain]


def _get_layer_for_type(node_type):
    """Get architectural layer for a node type."""
    node_type_lower = str(node_type).lower()

    # Map node types to layers (similar to SymbolGraph.get_layer())
    layer_map = {
        # Backend types
        'class': 'backend',
        'function': 'backend',
        'method': 'backend',
        'interface': 'backend',
        'struct': 'backend',
        'enum': 'backend',
        'enum_type': 'backend',
        'type': 'backend',
        'trait': 'backend',
        'entity': 'backend',
        'entity_field': 'backend',
        'controller': 'backend',
        'controller_method': 'backend',
        'service': 'backend',
        'dao': 'backend',
        # Database types
        'table': 'database',
        'column': 'database',
        # Frontend types
        'import': 'frontend',
        'component': 'frontend',
        'component_prop': 'frontend',
        'route': 'frontend',
        'form_field': 'frontend',
        'event_handler': 'frontend',
        'data_binding': 'frontend',
        # View types
        'jsp_page': 'view',
        'html_page': 'view',
        'el_expression': 'view',
        'form_binding': 'view',
        'jstl_variable': 'view',
        'taglib': 'view',
        'doc_section': 'view',
        'doc_page': 'view',
    }
    return layer_map.get(node_type_lower, 'unknown')


def _apply_filters(items, args):
    """Apply --layer and --type filters to items."""
    if hasattr(args, 'layer') and args.layer:
        filtered = []
        for item in items:
            # Get layer from item or calculate it
            item_layer = item.get('layer')
            if not item_layer:
                item_type = item.get('type') or item.get('node_type')
                if item_type:
                    item_layer = _get_layer_for_type(item_type)
                    item['layer'] = item_layer  # Add layer to output
            if item_layer and item_layer.lower() == args.layer.lower():
                filtered.append(item)
        items = filtered

    if hasattr(args, 'type') and args.type:
        items = [item for item in items
                if (item.get('type') or item.get('node_type', '')).upper() == args.type.upper()]

    return items


def _search_nodes(nodes, query):
    """Simple text search across node names and metadata."""
    query_lower = query.lower()
    results = []
    for node in nodes:
        name = (node.get("name") or "").lower()
        node_type = (node.get("type") or node.get("node_type") or "").lower()
        file_path = (node.get("file") or node.get("file_path") or "").lower()
        # Score: exact match > starts with > contains
        if query_lower == name:
            results.append((0, node))
        elif name.startswith(query_lower):
            results.append((1, node))
        elif query_lower in name or query_lower in file_path or query_lower in node_type:
            results.append((2, node))
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]


def _find_graph_dbs(project: str = None):
    """Find all *_graph.db files under index directory."""
    index_dir = _get_index_dir(project)
    if not index_dir.exists():
        return []
    return list(index_dir.glob("*_graph.db"))


def _query_graph_dbs(query, params=(), project: str = None):
    """Execute SQL query across all graph DBs and merge results."""
    dbs = _find_graph_dbs(project)
    if not dbs:
        return []

    all_results = []
    for db_file in dbs:
        try:
            conn = sqlite3.connect(str(db_file), timeout=5.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            # Convert Row objects to dicts
            for row in rows:
                all_results.append(dict(row))
            conn.close()
        except sqlite3.OperationalError:
            # Table doesn't exist in this DB, skip
            continue
        except Exception:
            # Other errors, skip this DB
            continue

    return all_results


def _enrich_with_layer(items):
    """Compute layer from type for each item (always works regardless of DB schema)."""
    for item in items:
        if not item.get('layer'):
            item['layer'] = _get_layer_for_type(item.get('type', ''))
    return items


def _get_db_stats(project: str = None):
    """Get stats from SQLite graph DBs if available."""
    stats = {"db_files": 0, "total_symbols": 0, "total_refs": 0}
    index_dir = _get_index_dir(project)
    try:
        for db_file in index_dir.glob("*_graph.db"):
            stats["db_files"] += 1
            try:
                conn = sqlite3.connect(str(db_file), timeout=5.0)
                cursor = conn.execute("SELECT COUNT(*) FROM symbols")
                stats["total_symbols"] += cursor.fetchone()[0]
                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM symbol_references")
                    stats["total_refs"] += cursor.fetchone()[0]
                except Exception:
                    try:
                        cursor = conn.execute("SELECT COUNT(*) FROM refs")
                        stats["total_refs"] += cursor.fetchone()[0]
                    except Exception:
                        pass
                conn.close()
            except Exception:
                continue
    except ImportError:
        pass
    return stats


def cmd_list_projects(args):
    """List all projects with stats."""
    projects_dir = INDEX_DIR / "projects"

    if not projects_dir.exists():
        # No projects directory - return empty or check for default index
        default_stats = _get_db_stats(None)
        if default_stats["total_symbols"] > 0:
            # There's a default/legacy index
            data = [{
                "name": "default",
                "symbol_count": default_stats["total_symbols"],
                "file_count": default_stats["db_files"],
                "last_indexed": None  # Not tracked in legacy
            }]
            print(json.dumps({"data": data, "meta": _meta("projects", 1)}, indent=2))
        else:
            print(json.dumps({"data": [], "meta": _meta("projects", 0)}, indent=2))
        return

    projects = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_name = project_dir.name
        if not _validate_project_name(project_name):
            continue

        # Get stats for this project
        db_stats = _get_db_stats(project_name)

        # Try to get last indexed time from DB files
        last_indexed = None
        dbs = _find_graph_dbs(project_name)
        if dbs:
            # Get most recent mtime
            mtimes = [db.stat().st_mtime for db in dbs]
            if mtimes:
                last_indexed = datetime.fromtimestamp(max(mtimes), timezone.utc).isoformat()

        projects.append({
            "name": project_name,
            "symbol_count": db_stats["total_symbols"],
            "file_count": db_stats["db_files"],
            "last_indexed": last_indexed
        })

    # Sort by name
    projects.sort(key=lambda p: p["name"])

    print(json.dumps({"data": projects, "meta": _meta("projects", len(projects))}, indent=2))


def cmd_list(source, args):
    """List items from a source."""
    project = getattr(args, 'project', None)

    # Handle projects source separately
    if source == "projects":
        cmd_list_projects(args)
        return

    if source in ("graph", "lineage", "services"):
        # SQLite-based sources
        if source == "graph":
            # Build SQL query — never reference 'layer' column (may not exist in older DBs)
            where_clauses = []
            params = []

            if hasattr(args, 'type') and args.type:
                where_clauses.append("UPPER(s.type) = UPPER(?)")
                params.append(args.type)

            where_str = ""
            if where_clauses:
                where_str = "WHERE " + " AND ".join(where_clauses)

            layer_filter = hasattr(args, 'layer') and args.layer

            if layer_filter:
                # Layer filtering done in Python (column may not exist in older DBs).
                # Over-fetch with a capped limit to balance correctness vs performance.
                sql_limit = min((args.offset + args.limit) * 10, 10000)
                sql_offset = 0
            else:
                sql_limit = args.limit
                sql_offset = args.offset

            query = f"""
            SELECT s.id, s.type, s.name, s.qualified_name, s.file_path, s.line_start
            FROM symbols s
            {where_str}
            ORDER BY s.name
            LIMIT ? OFFSET ?
            """
            params.extend([sql_limit, sql_offset])
            items = _query_graph_dbs(query, tuple(params), project)

            # Always compute layer from type in Python (works with any DB schema)
            _enrich_with_layer(items)

            # Apply layer filter and pagination in Python
            if layer_filter:
                items = [i for i in items if i.get('layer', '').lower() == args.layer.lower()]
                items = items[args.offset:args.offset + args.limit]

        elif source == "lineage":
            query = "SELECT * FROM lineage_paths ORDER BY id LIMIT ? OFFSET ?"
            items = _query_graph_dbs(query, (args.limit, args.offset), project)

        elif source == "services":
            query = "SELECT * FROM service_nodes ORDER BY name LIMIT ? OFFSET ?"
            items = _query_graph_dbs(query, (args.limit, args.offset), project)
            # Enrich each service with its connections
            for service in items:
                service_id = service.get("id")
                if service_id:
                    conn_query = "SELECT * FROM service_connections WHERE source_service_id = ?"
                    connections = _query_graph_dbs(conn_query, (service_id,), project)
                    service["connections"] = connections

        # Add warning if project specified but doesn't exist
        meta_extra = {}
        if project:
            index_dir = _get_index_dir(project)
            if not index_dir.exists() or not list(index_dir.glob("*_graph.db")):
                meta_extra["warning"] = f"Project '{project}' not found or has no indexes"

        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset, **meta_extra)}, indent=2))
        return

    # JSONL-based sources
    nodes = _load_jsonl_index(project)

    if source == "symbols":
        items = [n for n in nodes if n.get("domain") == "code"]
    elif source == "documents":
        items = [n for n in nodes if n.get("domain") == "doc"]
    elif source == "references":
        # References are cross-reference entries
        items = [n for n in nodes if n.get("type") in ("import", "reference", "ref", "cross_ref")]
    else:
        items = nodes

    # Apply filters
    items = _apply_filters(items, args)

    total = len(items)
    data = items[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))


def cmd_get(source, item_id, args):
    """Get a specific item by ID."""
    project = getattr(args, 'project', None)

    if source == "graph":
        # Get symbol from graph DB
        symbol_query = "SELECT * FROM symbols WHERE id = ?"
        symbols = _query_graph_dbs(symbol_query, (item_id,), project)

        if not symbols:
            _error("Item not found", "NOT_FOUND", resource=source, id=item_id)

        symbol = symbols[0]

        # Get dependencies (outgoing refs)
        dep_queries = [
            "SELECT target_id, ref_type, confidence FROM symbol_references WHERE source_id = ?",
            "SELECT target_id, ref_type, confidence FROM refs WHERE source_id = ?"
        ]
        deps = []
        for query in dep_queries:
            try:
                deps = _query_graph_dbs(query, (item_id,), project)
                if deps:
                    break
            except Exception:
                continue

        # Get dependents (incoming refs)
        dependent_queries = [
            "SELECT source_id, ref_type, confidence FROM symbol_references WHERE target_id = ?",
            "SELECT source_id, ref_type, confidence FROM refs WHERE target_id = ?"
        ]
        dependents = []
        for query in dependent_queries:
            try:
                dependents = _query_graph_dbs(query, (item_id,), project)
                if dependents:
                    break
            except Exception:
                continue

        symbol["dependencies"] = deps
        symbol["dependents"] = dependents

        print(json.dumps({"data": symbol, "meta": _meta(source, 1)}, indent=2))
        return

    # JSONL-based sources
    nodes = _load_jsonl_index(project)

    for node in nodes:
        nid = node.get("id") or node.get("name")
        if nid == item_id:
            print(json.dumps({"data": node, "meta": _meta(source, 1)}, indent=2))
            return

    _error("Item not found", "NOT_FOUND", resource=source, id=item_id)


def cmd_search(source, args):
    """Search items."""
    project = getattr(args, 'project', None)

    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    if source == "graph":
        # Search symbols in graph DBs — never reference 'layer' column in SQL
        where_clauses = ["(name LIKE ? OR qualified_name LIKE ?)"]
        params = [f"%{args.query}%", f"%{args.query}%"]

        if hasattr(args, 'type') and args.type:
            where_clauses.append("UPPER(type) = UPPER(?)")
            params.append(args.type)

        where_str = " AND ".join(where_clauses)

        layer_filter = hasattr(args, 'layer') and args.layer

        if layer_filter:
            # Layer filtering done in Python (column may not exist in older DBs).
            # Over-fetch with a capped limit to balance correctness vs performance.
            sql_limit = min((args.offset + args.limit) * 10, 10000)
            sql_offset = 0
        else:
            sql_limit = args.limit
            sql_offset = args.offset

        query = f"""
        SELECT * FROM symbols
        WHERE {where_str}
        LIMIT ? OFFSET ?
        """
        params.extend([sql_limit, sql_offset])
        results = _query_graph_dbs(query, tuple(params), project)

        # Always compute layer from type in Python (works with any DB schema)
        _enrich_with_layer(results)

        # Apply layer filter and pagination in Python
        if layer_filter:
            results = [r for r in results if r.get('layer', '').lower() == args.layer.lower()]
            results = results[args.offset:args.offset + args.limit]

        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))
        return

    if source == "lineage":
        # Search lineage paths
        query = """
        SELECT * FROM lineage_paths
        WHERE source_id LIKE ? OR sink_id LIKE ?
        LIMIT ? OFFSET ?
        """
        pattern = f"%{args.query}%"
        results = _query_graph_dbs(query, (pattern, pattern, args.limit, args.offset), project)
        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))
        return

    # JSONL-based sources
    nodes = _load_jsonl_index(project)

    if source == "symbols":
        nodes = [n for n in nodes if n.get("domain") == "code"]
    elif source == "documents":
        nodes = [n for n in nodes if n.get("domain") == "doc"]

    results = _search_nodes(nodes, args.query)

    # Apply filters
    results = _apply_filters(results, args)

    total = len(results)
    data = results[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))


def cmd_traverse(source, item_id, args):
    """Traverse graph from a symbol."""
    project = getattr(args, 'project', None)

    if source != "graph":
        _error("traverse verb only supported for graph source", "UNSUPPORTED_VERB",
               source=source, verb="traverse")

    # Validate depth
    depth = getattr(args, 'depth', 1)
    if depth < 1 or depth > 3:
        _error("Depth must be between 1 and 3", "INVALID_DEPTH", depth=depth)

    direction = getattr(args, 'direction', 'both')
    if direction not in ('both', 'in', 'out'):
        _error("Direction must be 'both', 'in', or 'out'", "INVALID_DIRECTION", direction=direction)

    # Find the root symbol first
    symbol_query = "SELECT * FROM symbols WHERE id = ?"
    symbols = _query_graph_dbs(symbol_query, (item_id,), project)

    if not symbols:
        _error("Symbol not found", "NOT_FOUND", id=item_id)

    root = symbols[0]

    # BFS traversal - collect all symbol IDs that should be in the result
    visited_nodes = {item_id}  # Start with root
    visited_edges = set()
    queue = [(item_id, 0)]

    # Get all graph DBs for querying
    dbs = _find_graph_dbs(project)
    if not dbs:
        _error("No graph databases found", "NO_GRAPH_DB")

    while queue:
        current_id, current_depth = queue.pop(0)

        if current_depth >= depth:
            continue

        # Query outgoing refs (refs table only — symbol_references is a view over refs)
        if direction in ('out', 'both'):
            refs = _query_graph_dbs(
                "SELECT target_id, ref_type FROM refs WHERE source_id = ?",
                (current_id,), project)
            for ref in refs:
                target_id = ref['target_id']
                edge_key = (current_id, target_id, ref['ref_type'])
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                    if target_id not in visited_nodes:
                        visited_nodes.add(target_id)
                        queue.append((target_id, current_depth + 1))

        # Query incoming refs
        if direction in ('in', 'both'):
            refs = _query_graph_dbs(
                "SELECT source_id, ref_type FROM refs WHERE target_id = ?",
                (current_id,), project)
            for ref in refs:
                source_id = ref['source_id']
                edge_key = (source_id, current_id, ref['ref_type'])
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                    if source_id not in visited_nodes:
                        visited_nodes.add(source_id)
                        queue.append((source_id, current_depth + 1))

    # Batch fetch full symbol objects for all visited nodes (except root)
    visited_nodes.discard(item_id)  # Don't include root in nodes list
    nodes = []
    if visited_nodes:
        sorted_ids = sorted(visited_nodes)
        placeholders = ",".join("?" for _ in sorted_ids)
        node_query = f"SELECT id, name, type, qualified_name, file_path, line_start, line_end FROM symbols WHERE id IN ({placeholders})"
        nodes = _query_graph_dbs(node_query, tuple(sorted_ids), project)
        nodes.sort(key=lambda n: n.get("id", ""))

    # Build edge list (refs table does not store line numbers, so line=0)
    edges = []
    for source_id, target_id, ref_type in sorted(visited_edges):
        edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "ref_type": ref_type,
            "line": 0
        })

    result = {
        "data": {
            "root": root,
            "nodes": nodes,
            "edges": edges
        },
        "meta": {
            "source": "graph",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "depth": depth,
            "direction": direction
        }
    }

    print(json.dumps(result, indent=2))


def cmd_hotspots(source, args):
    """Find hotspot symbols with high connectivity."""
    project = getattr(args, 'project', None)

    if source != "graph":
        _error("hotspots verb only supported for graph source", "UNSUPPORTED_VERB",
               source=source, verb="hotspots")

    # Build query using refs table only (symbol_references is a view over refs,
    # so UNION ALL would double-count)
    query = """
    SELECT
        s.id,
        s.type,
        s.name,
        s.file_path,
        COALESCE(in_refs.cnt, 0) as in_count,
        COALESCE(out_refs.cnt, 0) as out_count,
        COALESCE(in_refs.cnt, 0) + COALESCE(out_refs.cnt, 0) as total_count
    FROM symbols s
    LEFT JOIN (
        SELECT source_id, COUNT(*) as cnt
        FROM refs
        GROUP BY source_id
    ) out_refs ON s.id = out_refs.source_id
    LEFT JOIN (
        SELECT target_id, COUNT(*) as cnt
        FROM refs
        GROUP BY target_id
    ) in_refs ON s.id = in_refs.target_id
    WHERE COALESCE(in_refs.cnt, 0) + COALESCE(out_refs.cnt, 0) > 0
    ORDER BY total_count DESC, id
    """

    items = _query_graph_dbs(query, (), project)

    # Re-sort after cross-DB merge (SQL ORDER BY applies per-DB only)
    items.sort(key=lambda x: (-x.get('total_count', 0), x.get('id', '')))

    # Enrich with layer
    _enrich_with_layer(items)

    # Apply filters
    items = _apply_filters(items, args)

    # Apply pagination
    total = len(items)
    limit = getattr(args, 'limit', 20)
    offset = getattr(args, 'offset', 0)
    data = items[offset:offset + limit]

    result = {
        "data": data,
        "meta": {
            "source": "graph",
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }

    print(json.dumps(result, indent=2))


def _get_project_root(project=None):
    """Get project root path from index metadata files."""
    index_dir = _get_index_dir(project)
    if not index_dir.exists():
        return None
    for meta_file in index_dir.glob("*_meta.json"):
        try:
            with open(meta_file) as f:
                meta = json.loads(f.read())
            root = meta.get("root_path")
            if root:
                return root
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _resolve_file_path(relative_path, project=None):
    """Resolve a relative file path to absolute using project root or DB lookup."""
    # Already absolute
    if relative_path.startswith("/") and Path(relative_path).exists():
        return relative_path

    # Try project root from metadata
    root = _get_project_root(project)
    if root:
        candidate = Path(root) / relative_path
        if candidate.exists():
            return str(candidate)

    # Try DB lookup — find a symbol whose file_path ends with this relative path
    dbs = _find_graph_dbs(project)
    for db_file in dbs:
        try:
            conn = sqlite3.connect(str(db_file), timeout=5.0)
            cursor = conn.execute(
                "SELECT file_path FROM symbols WHERE file_path LIKE ? LIMIT 1",
                (f"%{relative_path}",))
            row = cursor.fetchone()
            conn.close()
            if row and Path(row[0]).exists():
                return row[0]
        except Exception:
            continue

    return None


def _infer_language(file_path):
    """Infer programming language from file extension."""
    ext_map = {
        ".java": "java", ".jsp": "jsp", ".xml": "xml", ".sql": "sql",
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "tsx", ".jsx": "jsx", ".html": "html", ".htm": "html",
        ".css": "css", ".scss": "scss", ".json": "json", ".yaml": "yaml",
        ".yml": "yaml", ".md": "markdown", ".properties": "properties",
        ".sh": "bash", ".rb": "ruby", ".go": "go", ".rs": "rust",
        ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
    }
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, "text")


def cmd_categories(source, args):
    """Aggregate symbols (pages) by category with counts."""
    project = getattr(args, 'project', None)

    if source != "symbols":
        _error("categories verb only supported for symbols source", "UNSUPPORTED_VERB",
               source=source, verb="categories")

    # Query: get all jsp_page symbols grouped by directory category
    # Also count fields (el_expression + form_binding) per page via refs
    dbs = _find_graph_dbs(project)

    if not dbs:
        print(json.dumps({"data": [], "meta": _meta(source, 0)}, indent=2))
        return

    # Step 1: Get all JSP pages
    pages = _query_graph_dbs(
        "SELECT id, file_path FROM symbols WHERE type = 'jsp_page'",
        (), project)

    # Step 2: Count fields (el_expression + form_binding) per page
    field_counts = _query_graph_dbs(
        """SELECT s2.file_path, COUNT(*) as cnt
           FROM symbols s2
           WHERE s2.type IN ('el_expression', 'form_binding')
           GROUP BY s2.file_path""",
        (), project)
    fields_by_file = {r["file_path"]: r["cnt"] for r in field_counts}

    # Step 3: Derive category from file path
    # Pattern: extract first meaningful directory after WEB-INF/pages/ or WEB-INF/jsp/ or webapp/
    categories = {}
    for page in pages:
        fp = page.get("file_path", "")
        parts = fp.replace("\\", "/").split("/")

        # Find category: first dir after known markers
        cat = "other"
        for i, part in enumerate(parts):
            if part in ("pages", "jsp", "jsp-client", "views"):
                remaining = parts[i + 1:]
                if len(remaining) > 1:
                    cat = remaining[0]
                elif len(remaining) == 1:
                    cat = "root"
                break
            if part == "webapp":
                remaining = parts[i + 1:]
                # Skip WEB-INF if present
                if remaining and remaining[0] == "WEB-INF":
                    remaining = remaining[1:]
                # Skip pages/jsp/views if present
                if remaining and remaining[0] in ("pages", "jsp", "jsp-client", "views"):
                    remaining = remaining[1:]
                if len(remaining) > 1:
                    cat = remaining[0]
                elif len(remaining) == 1:
                    cat = "root"
                break

        if cat not in categories:
            categories[cat] = {"category": cat, "page_count": 0, "total_fields": 0}
        categories[cat]["page_count"] += 1
        categories[cat]["total_fields"] += fields_by_file.get(fp, 0)

    data = sorted(categories.values(), key=lambda c: -c["page_count"])

    # Apply pagination
    total = len(data)
    data = data[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))


def cmd_impact(source, item_id, args):
    """Reverse lineage from a database column to all UI fields it feeds."""
    project = getattr(args, 'project', None)

    if source != "graph":
        _error("impact verb only supported for graph source", "UNSUPPORTED_VERB",
               source=source, verb="impact")

    # Parse table.column from item_id
    # Frontend sends "TABLE.COLUMN", DB stores "db::TABLE.COLUMN"
    if "." in item_id:
        parts = item_id.split(".", 1)
        table = parts[0]
        column = parts[1]
    else:
        table = ""
        column = item_id

    # Try both ID formats
    column_ids = [f"db::{item_id}", item_id]

    # Step 1: Find entity_fields that maps_to this column (reverse: entity_field -> column)
    entity_fields = []
    for col_id in column_ids:
        ef = _query_graph_dbs(
            "SELECT source_id FROM refs WHERE target_id = ? AND ref_type = 'maps_to'",
            (col_id,), project)
        entity_fields.extend(ef)
        if entity_fields:
            break

    # Step 2: For each entity_field, find UI fields that binds_to it
    affected_fields = []
    seen_ids = set()
    for ef in entity_fields:
        ef_id = ef["source_id"]
        # Get the field path from entity_field name (e.g., "Entity.fieldName")
        ef_info = _query_graph_dbs(
            "SELECT name, qualified_name FROM symbols WHERE id = ?",
            (ef_id,), project)
        field_path = ef_info[0]["qualified_name"] if ef_info and ef_info[0].get("qualified_name") else (
            ef_info[0]["name"] if ef_info else ef_id)

        # Find binds_to refs pointing at this entity_field
        bindings = _query_graph_dbs(
            "SELECT source_id FROM refs WHERE target_id = ? AND ref_type = 'binds_to'",
            (ef_id,), project)

        for binding in bindings:
            ui_id = binding["source_id"]
            if ui_id in seen_ids:
                continue
            seen_ids.add(ui_id)

            # Get symbol info for this UI field
            sym = _query_graph_dbs(
                "SELECT id, name, file_path FROM symbols WHERE id = ?",
                (ui_id,), project)
            if sym:
                affected_fields.append({
                    "ui_field_id": sym[0]["id"],
                    "field_path": field_path,
                    "jsp_file": sym[0]["file_path"],
                })

    result = {
        "table": table,
        "column": column,
        "total_affected": len(affected_fields),
        "affected_fields": affected_fields,
    }
    print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))


def cmd_content(source, item_id, args):
    """Read source file content for inline display."""
    project = getattr(args, 'project', None)

    if source != "code":
        _error("content verb only supported for code source", "UNSUPPORTED_VERB",
               source=source, verb="content")

    # Resolve to absolute path
    abs_path = _resolve_file_path(item_id, project)
    if not abs_path or not Path(abs_path).exists():
        _error("File not found", "NOT_FOUND", path=item_id)

    line_start = getattr(args, 'line_start', None)
    line_end = getattr(args, 'line_end', None)

    try:
        with open(abs_path, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        _error(f"Cannot read file: {e}", "READ_ERROR", path=abs_path)

    total_lines = len(lines)

    if line_start is not None:
        ls = max(1, line_start)
        le = min(total_lines, line_end) if line_end else total_lines
    else:
        ls = 1
        le = total_lines

    content = "".join(lines[ls - 1:le])
    language = _infer_language(abs_path)

    result = {
        "path": item_id,
        "content": content,
        "line_start": ls,
        "line_end": le,
        "language": language,
    }
    print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))


def cmd_ide_url(source, item_id, args):
    """Generate IDE deep link URL."""
    project = getattr(args, 'project', None)

    if source != "code":
        _error("ide-url verb only supported for code source", "UNSUPPORTED_VERB",
               source=source, verb="ide-url")

    line = getattr(args, 'line', 1)
    ide = getattr(args, 'ide', 'vscode') or 'vscode'

    # Resolve to absolute path
    abs_path = _resolve_file_path(item_id, project)
    if not abs_path:
        _error("File not found", "NOT_FOUND", path=item_id)

    if ide == "vscode":
        url = f"vscode://file{abs_path}:{line}"
    elif ide == "idea":
        url = f"idea://open?file={abs_path}&line={line}"
    elif ide == "cursor":
        url = f"cursor://file{abs_path}:{line}"
    else:
        _error(f"Unsupported IDE: {ide}", "INVALID_IDE",
               ide=ide, supported=["vscode", "idea", "cursor"])

    print(json.dumps({"data": {"url": url}, "meta": _meta(source, 1)}, indent=2))


def cmd_stats(source, args):
    """Get statistics."""
    project = getattr(args, 'project', None)

    if source == "graph":
        # Graph DB statistics
        dbs = _find_graph_dbs(project)
        if not dbs:
            stats = {
                "total_symbols": 0,
                "total_refs": 0,
                "by_type": {},
                "by_ref_type": {},
                "db_files": 0
            }
            print(json.dumps({"data": stats, "meta": _meta(source, 1)}, indent=2))
            return

        total_symbols = 0
        total_refs = 0
        by_type = {}
        by_ref_type = {}

        for db_file in dbs:
            try:
                conn = sqlite3.connect(str(db_file), timeout=5.0)
                conn.row_factory = sqlite3.Row

                # Count symbols
                cursor = conn.execute("SELECT COUNT(*) as cnt FROM symbols")
                total_symbols += cursor.fetchone()["cnt"]

                # Count by symbol type
                cursor = conn.execute("SELECT type, COUNT(*) as cnt FROM symbols GROUP BY type")
                for row in cursor.fetchall():
                    t = row["type"]
                    by_type[t] = by_type.get(t, 0) + row["cnt"]

                # Count refs (try both table names)
                ref_table = None
                for table_name in ("symbol_references", "refs"):
                    try:
                        cursor = conn.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
                        total_refs += cursor.fetchone()["cnt"]
                        ref_table = table_name
                        break
                    except sqlite3.OperationalError:
                        continue

                # Count by ref type
                if ref_table:
                    cursor = conn.execute(f"SELECT ref_type, COUNT(*) as cnt FROM {ref_table} GROUP BY ref_type")
                    for row in cursor.fetchall():
                        rt = row["ref_type"]
                        by_ref_type[rt] = by_ref_type.get(rt, 0) + row["cnt"]

                conn.close()
            except Exception:
                continue

        stats = {
            "total_symbols": total_symbols,
            "total_refs": total_refs,
            "by_type": by_type,
            "by_ref_type": by_ref_type,
            "db_files": len(dbs)
        }
        print(json.dumps({"data": stats, "meta": _meta(source, 1)}, indent=2))
        return

    if source == "services":
        # Services statistics
        dbs = _find_graph_dbs(project)
        if not dbs:
            stats = {
                "total_services": 0,
                "total_connections": 0,
                "by_type": {},
                "by_technology": {}
            }
            print(json.dumps({"data": stats, "meta": _meta(source, 1)}, indent=2))
            return

        total_services = 0
        total_connections = 0
        by_type = {}
        by_technology = {}

        for db_file in dbs:
            try:
                conn = sqlite3.connect(str(db_file), timeout=5.0)
                conn.row_factory = sqlite3.Row

                # Count services
                try:
                    cursor = conn.execute("SELECT COUNT(*) as cnt FROM service_nodes")
                    total_services += cursor.fetchone()["cnt"]

                    # Count by type
                    cursor = conn.execute("SELECT type, COUNT(*) as cnt FROM service_nodes GROUP BY type")
                    for row in cursor.fetchall():
                        t = row["type"]
                        by_type[t] = by_type.get(t, 0) + row["cnt"]

                    # Count by technology
                    cursor = conn.execute("SELECT technology, COUNT(*) as cnt FROM service_nodes WHERE technology IS NOT NULL GROUP BY technology")
                    for row in cursor.fetchall():
                        tech = row["technology"]
                        by_technology[tech] = by_technology.get(tech, 0) + row["cnt"]
                except sqlite3.OperationalError:
                    pass

                # Count connections
                try:
                    cursor = conn.execute("SELECT COUNT(*) as cnt FROM service_connections")
                    total_connections += cursor.fetchone()["cnt"]
                except sqlite3.OperationalError:
                    pass

                conn.close()
            except Exception:
                continue

        stats = {
            "total_services": total_services,
            "total_connections": total_connections,
            "by_type": by_type,
            "by_technology": by_technology
        }
        print(json.dumps({"data": stats, "meta": _meta(source, 1)}, indent=2))
        return

    # JSONL-based sources
    nodes = _load_jsonl_index(project)
    db_stats = _get_db_stats(project)

    code_nodes = [n for n in nodes if n.get("domain") == "code"]
    doc_nodes = [n for n in nodes if n.get("domain") == "doc"]

    # Count by type
    by_type = {}
    for n in nodes:
        t = n.get("type") or n.get("node_type") or "unknown"
        if hasattr(t, "value"):
            t = t.value
        by_type[str(t)] = by_type.get(str(t), 0) + 1

    # Count index files
    index_dir = _get_index_dir(project)
    jsonl_count = len(list(index_dir.glob("*.jsonl"))) if index_dir.exists() else 0

    stats = {
        "total_nodes": len(nodes),
        "code_symbols": len(code_nodes),
        "documents": len(doc_nodes),
        "by_type": by_type,
        "index_files": jsonl_count,
        "graph_dbs": db_stats["db_files"],
        "graph_symbols": db_stats["total_symbols"],
        "graph_refs": db_stats["total_refs"],
    }
    print(json.dumps({"data": stats, "meta": _meta(source, 1)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Wicked Search Data API")
    subparsers = parser.add_subparsers(dest="verb")

    all_verbs = ("list", "get", "search", "stats", "traverse", "hotspots",
                  "categories", "impact", "content", "ide-url")
    for verb in all_verbs:
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (symbols, documents, references, graph, lineage, services, projects, code)")
        if verb in ("get", "traverse", "impact", "content", "ide-url"):
            sub.add_argument("id", nargs="?", help="Item ID")
        if verb == "traverse":
            sub.add_argument("--depth", type=int, default=1, help="Traversal depth (1-3)")
            sub.add_argument("--direction", default="both", help="Direction: both, in, out")
        if verb == "content":
            sub.add_argument("--line-start", type=int, default=None, dest="line_start", help="First line to return")
            sub.add_argument("--line-end", type=int, default=None, dest="line_end", help="Last line to return")
        if verb == "ide-url":
            sub.add_argument("--line", type=int, default=1, help="Line number")
            sub.add_argument("--ide", default="vscode", help="Target IDE (vscode, idea, cursor)")
        sub.add_argument("--limit", type=int, default=100 if verb != "hotspots" else 20)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument("--project", help="Filter by project")
        sub.add_argument("--query", help="Search query")
        sub.add_argument("--filter", help="Filter expression")
        if verb in ("list", "search", "hotspots"):
            sub.add_argument("--layer", help="Filter by architectural layer (backend, frontend, database, view)")
            sub.add_argument("--type", help="Filter by symbol type (e.g., CLASS, FUNCTION, METHOD, TABLE)")

    args = parser.parse_args()

    if not args.verb:
        parser.print_help()
        sys.exit(1)

    if args.source not in VALID_SOURCES:
        _error(f"Unknown source: {args.source}", "INVALID_SOURCE",
               source=args.source, valid=list(VALID_SOURCES))

    if args.verb == "list":
        cmd_list(args.source, args)
    elif args.verb == "get":
        if not args.id:
            _error("ID required for get verb", "MISSING_ID")
        cmd_get(args.source, args.id, args)
    elif args.verb == "search":
        cmd_search(args.source, args)
    elif args.verb == "stats":
        cmd_stats(args.source, args)
    elif args.verb == "traverse":
        if not args.id:
            _error("ID required for traverse verb", "MISSING_ID")
        cmd_traverse(args.source, args.id, args)
    elif args.verb == "hotspots":
        cmd_hotspots(args.source, args)
    elif args.verb == "categories":
        cmd_categories(args.source, args)
    elif args.verb == "impact":
        if not args.id:
            _error("ID required for impact verb", "MISSING_ID")
        cmd_impact(args.source, args.id, args)
    elif args.verb == "content":
        if not args.id:
            _error("ID required for content verb", "MISSING_ID")
        cmd_content(args.source, args.id, args)
    elif args.verb == "ide-url":
        if not args.id:
            _error("ID required for ide-url verb", "MISSING_ID")
        cmd_ide_url(args.source, args.id, args)


if __name__ == "__main__":
    main()
