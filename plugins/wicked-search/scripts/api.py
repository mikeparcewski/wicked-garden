#!/usr/bin/env python3
"""Wicked Search Data API — standard Plugin Data API interface.

Reads from unified.db SQLite database under ~/.something-wicked/wicked-search/.
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
import sys
from datetime import datetime, timezone
from pathlib import Path

from query_builder import UnifiedQueryEngine

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


def _find_unified_db(project: str = None) -> Path:
    """Find unified.db for a project or default."""
    index_dir = _get_index_dir(project)
    return index_dir / "unified.db"


def _get_unified_engine(project: str = None):
    """Get UnifiedQueryEngine for current project."""
    db_path = _find_unified_db(project)
    if not db_path.exists():
        return None

    try:
        return UnifiedQueryEngine(str(db_path))
    except Exception:
        return None


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




def cmd_list_projects(args):
    """List all projects with stats."""
    projects_dir = INDEX_DIR / "projects"

    if not projects_dir.exists():
        # No projects directory - check for default unified.db
        default_db = _find_unified_db(None)
        if default_db.exists():
            # Get mtime
            last_indexed = datetime.fromtimestamp(default_db.stat().st_mtime, timezone.utc).isoformat()
            # Get stats
            engine = _get_unified_engine(None)
            if engine:
                stats = engine.get_stats()
                data = [{
                    "name": "default",
                    "symbol_count": stats.get('total_symbols', 0),
                    "file_count": 1,
                    "last_indexed": last_indexed
                }]
                print(json.dumps({"data": data, "meta": _meta("projects", 1)}, indent=2))
                return

        print(json.dumps({"data": [], "meta": _meta("projects", 0)}, indent=2))
        return

    projects = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_name = project_dir.name
        if not _validate_project_name(project_name):
            continue

        # Get unified.db for this project
        db_path = _find_unified_db(project_name)
        if not db_path.exists():
            continue

        # Get mtime
        last_indexed = datetime.fromtimestamp(db_path.stat().st_mtime, timezone.utc).isoformat()

        # Get stats
        engine = _get_unified_engine(project_name)
        if engine:
            stats = engine.get_stats()
            projects.append({
                "name": project_name,
                "symbol_count": stats.get('total_symbols', 0),
                "file_count": 1,
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

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    if source == "graph":
        type_filter = getattr(args, 'type', None)
        layer_filter = getattr(args, 'layer', None)
        category_filter = getattr(args, 'category', None)

        items = engine.list_symbols(
            limit=args.limit,
            offset=args.offset,
            type_filter=type_filter,
            layer_filter=layer_filter,
            category_filter=category_filter,
            domain_filter='code'
        )

        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "lineage":
        items = engine.list_lineage(limit=args.limit, offset=args.offset)
        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "services":
        items = engine.list_services(limit=args.limit, offset=args.offset)
        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "symbols":
        layer_filter = getattr(args, 'layer', None)
        type_filter = getattr(args, 'type', None)
        category_filter = getattr(args, 'category', None)

        items = engine.list_symbols(
            limit=args.limit,
            offset=args.offset,
            domain_filter='code',
            layer_filter=layer_filter,
            type_filter=type_filter,
            category_filter=category_filter
        )

        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "documents":
        items = engine.list_symbols(
            limit=args.limit,
            offset=args.offset,
            domain_filter='doc'
        )

        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "references":
        items = engine.list_refs(limit=args.limit, offset=args.offset)
        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    else:
        _error(f"Unsupported source: {source}", "UNSUPPORTED_SOURCE", source=source)


def cmd_get(source, item_id, args):
    """Get a specific item by ID."""
    project = getattr(args, 'project', None)

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    if source == "graph":
        symbol = engine.get_symbol_with_refs(item_id)
        if not symbol:
            _error("Item not found", "NOT_FOUND", resource=source, id=item_id)

        # Convert dependencies/dependents to legacy format
        deps = []
        for dep in symbol.get('dependencies', []):
            deps.append({
                'target_id': dep['symbol']['id'],
                'ref_type': dep['ref_type'],
                'confidence': None
            })

        dependents = []
        for dep in symbol.get('dependents', []):
            dependents.append({
                'source_id': dep['symbol']['id'],
                'ref_type': dep['ref_type'],
                'confidence': None
            })

        symbol['dependencies'] = deps
        symbol['dependents'] = dependents

        print(json.dumps({"data": symbol, "meta": _meta(source, 1)}, indent=2))

    else:
        # Direct ID lookup first, then fallback to search
        result = engine.get_symbol(item_id)
        if result:
            print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))
            return

        # Fallback: search by name
        results = engine.search_all(item_id, limit=10)
        for node in results:
            if node.get("id") == item_id or node.get("name") == item_id:
                print(json.dumps({"data": node, "meta": _meta(source, 1)}, indent=2))
                return

        _error("Item not found", "NOT_FOUND", resource=source, id=item_id)


def cmd_search(source, args):
    """Search items."""
    project = getattr(args, 'project', None)

    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    if source == "graph":
        # Use search_code() to stay consistent with list graph (domain='code')
        fetch_limit = args.limit + args.offset
        results = engine.search_code(args.query, limit=fetch_limit)

        # Apply additional filters if needed
        type_filter = getattr(args, 'type', None)
        layer_filter = getattr(args, 'layer', None)
        category_filter = getattr(args, 'category', None)

        if type_filter:
            results = [r for r in results if r.get('type', '').upper() == type_filter.upper()]
        if layer_filter:
            results = [r for r in results if r.get('layer', '').lower() == layer_filter.lower()]
        if category_filter:
            results = [r for r in results if r.get('category', '') == category_filter]

        results = results[args.offset:args.offset + args.limit]
        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "lineage":
        results = engine.search_lineage(args.query, limit=args.limit, offset=args.offset)
        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "symbols":
        # Over-fetch to support offset + Python-side filters
        fetch_limit = args.limit + args.offset
        results = engine.search_code(args.query, limit=fetch_limit)

        # Apply additional filters
        layer_filter = getattr(args, 'layer', None)
        type_filter = getattr(args, 'type', None)
        category_filter = getattr(args, 'category', None)

        if type_filter:
            results = [r for r in results if r.get('type', '').upper() == type_filter.upper()]
        if layer_filter:
            results = [r for r in results if r.get('layer', '').lower() == layer_filter.lower()]
        if category_filter:
            results = [r for r in results if r.get('category', '') == category_filter]

        # Apply offset
        results = results[args.offset:args.offset + args.limit]

        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "documents":
        fetch_limit = args.limit + args.offset
        results = engine.search_docs(args.query, limit=fetch_limit)

        # Apply offset
        results = results[args.offset:args.offset + args.limit]

        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    elif source == "references":
        results = engine.search_refs(args.query, limit=args.limit, offset=args.offset)
        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))

    else:
        _error(f"Unsupported source: {source}", "UNSUPPORTED_SOURCE", source=source)


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

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    # Map 'in'/'out' to 'incoming'/'outgoing'
    engine_direction = direction
    if direction == 'in':
        engine_direction = 'incoming'
    elif direction == 'out':
        engine_direction = 'outgoing'

    result = engine.traverse(item_id, depth=depth, direction=engine_direction)

    if not result.get('root'):
        _error("Symbol not found", "NOT_FOUND", id=item_id)

    root = result['root']
    nodes = result['nodes']
    edges = result['edges']

    # Add line field to edges for legacy format compatibility
    for edge in edges:
        edge['line'] = 0

    output = {
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

    print(json.dumps(output, indent=2))


def cmd_hotspots(source, args):
    """Find hotspot symbols with high connectivity."""
    project = getattr(args, 'project', None)

    if source != "graph":
        _error("hotspots verb only supported for graph source", "UNSUPPORTED_VERB",
               source=source, verb="hotspots")

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    limit = getattr(args, 'limit', 20)
    offset = getattr(args, 'offset', 0)
    layer_filter = getattr(args, 'layer', None)
    type_filter = getattr(args, 'type', None)
    category_filter = getattr(args, 'category', None)

    items = engine.hotspots(
        limit=limit,
        offset=offset,
        layer_filter=layer_filter,
        type_filter=type_filter,
        category_filter=category_filter
    )

    total = len(items)

    result = {
        "data": items,
        "meta": _meta("graph", total, limit, offset)
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

    # Try DB lookup using unified engine
    engine = _get_unified_engine(project)
    if engine:
        try:
            results = engine.search_code(relative_path, limit=1)
            if results and Path(results[0].get('file_path', '')).exists():
                return results[0]['file_path']
        except Exception:
            pass

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
    """Aggregate symbols by type and directory category with cross-category relationships."""
    project = getattr(args, 'project', None)

    if source != "symbols":
        _error("categories verb only supported for symbols source", "UNSUPPORTED_VERB",
               source=source, verb="categories")

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    categories = engine.get_categories()

    # Convert to legacy format
    by_directory = categories.get('categories', [])
    for cat in by_directory:
        cat['category'] = cat.pop('name')
        cat['symbol_count'] = cat.pop('count')
        cat.pop('layers', None)

    relationships_dir = []
    for rel in categories.get('relationships', []):
        relationships_dir.append({
            'source': rel['from'],
            'target': rel['to'],
            'ref_type': 'cross_ref',
            'count': rel['count']
        })

    # Get stats for by_type and by_layer
    stats = engine.get_stats()

    type_rows = []
    for type_name, count in stats.get('by_type', {}).items():
        type_rows.append({'type': type_name, 'count': count})
    type_rows.sort(key=lambda x: -x['count'])

    layer_rows = []
    for layer_name, count in stats.get('by_layer', {}).items():
        layer_rows.append({'layer': layer_name, 'symbol_count': count})
    layer_rows.sort(key=lambda x: -x['symbol_count'])

    data = {
        "by_type": type_rows,
        "by_layer": layer_rows,
        "by_directory": by_directory[:args.limit],
        "relationships": {
            "by_directory": relationships_dir[:args.limit],
            "by_layer": [],
        },
    }

    total = len(type_rows) + len(layer_rows) + len(by_directory)
    print(json.dumps({"data": data, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))


def cmd_impact(source, item_id, args):
    """Reverse lineage from a database column to all UI fields it feeds."""
    project = getattr(args, 'project', None)

    if source != "graph":
        _error("impact verb only supported for graph source", "UNSUPPORTED_VERB",
               source=source, verb="impact")

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    # Parse table.column from item_id
    if "." in item_id:
        parts = item_id.split(".", 1)
        table = parts[0]
        column = parts[1]
    else:
        table = ""
        column = item_id

    # Try both ID formats
    column_ids = [f"db::{item_id}", item_id]

    # Try each ID format
    impact_result = None
    for col_id in column_ids:
        try:
            impact_result = engine.impact_analysis(col_id)
            if impact_result and impact_result.get('root'):
                break
        except Exception:
            continue

    if not impact_result or not impact_result.get('root'):
        # Return empty result
        result = {
            "table": table,
            "column": column,
            "total_affected": 0,
            "affected_fields": [],
        }
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))
        return

    # Convert to legacy format
    affected_fields = []
    for layer_group in impact_result.get('layers', []):
        for symbol in layer_group.get('symbols', []):
            # Only include UI layer symbols
            if symbol.get('layer') in ('view', 'frontend'):
                affected_fields.append({
                    "ui_field_id": symbol['id'],
                    "field_path": symbol.get('qualified_name', symbol['name']),
                    "jsp_file": symbol.get('file_path', '')
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

    engine = _get_unified_engine(project)
    if not engine:
        _error("No unified database found. Run /wicked-search:index first.", "NO_DATABASE")

    stats = engine.get_stats()

    if source == "graph":
        output_stats = {
            "total_symbols": stats.get('total_symbols', 0),
            "total_refs": stats.get('total_refs', 0),
            "by_type": stats.get('by_type', {}),
            "by_ref_type": stats.get('by_ref_type', {}),
            "db_files": 1
        }
        print(json.dumps({"data": output_stats, "meta": _meta(source, 1)}, indent=2))

    elif source == "services":
        output_stats = {
            "total_services": stats.get('services', 0),
            "total_connections": 0,
            "by_type": {},
            "by_technology": {}
        }
        print(json.dumps({"data": output_stats, "meta": _meta(source, 1)}, indent=2))

    elif source == "symbols":
        output_stats = {
            "total_symbols": stats.get('total_symbols', 0),
            "by_type": stats.get('by_type', {}),
            "by_layer": stats.get('by_layer', {})
        }
        print(json.dumps({"data": output_stats, "meta": _meta(source, 1)}, indent=2))

    elif source == "documents":
        # Count doc domain symbols
        doc_count = stats.get('by_domain', {}).get('doc', 0)
        output_stats = {
            "total_documents": doc_count
        }
        print(json.dumps({"data": output_stats, "meta": _meta(source, 1)}, indent=2))

    else:
        _error(f"Unsupported source for stats: {source}", "UNSUPPORTED_SOURCE", source=source)


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
            sub.add_argument("--category", help="Filter by directory category (e.g., portlets, api, service)")

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
