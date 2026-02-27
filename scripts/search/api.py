#!/usr/bin/env python3
"""Search API -- thin wrapper over Control Plane search endpoints.

All indexing, querying, and graph traversal is handled by the CP.
This module exposes a CLI and importable functions that delegate to
the CP's /api/v1/search/* and /api/v1/data/wicked-search/* endpoints.

Usage:
    python3 api.py list symbols [--limit N] [--offset N] [--project P]
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
from pathlib import Path

# Resolve _control_plane from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _control_plane import get_client

VALID_SOURCES = {
    "symbols", "documents", "references", "graph",
    "lineage", "services", "projects", "code",
}


# ---------------------------------------------------------------------------
# CP helper
# ---------------------------------------------------------------------------

def _cp():
    """Return a ControlPlaneClient instance."""
    return get_client()


def _search_request(source, params):
    """GET /api/v1/data/wicked-search/{source}/search with params."""
    return _cp().request("wicked-search", source, "search", params=params)


def _list_request(source, params):
    """GET /api/v1/data/wicked-search/{source}/list with params."""
    return _cp().request("wicked-search", source, "list", params=params)


def _get_request(source, item_id):
    """GET /api/v1/data/wicked-search/{source}/get/{id}."""
    return _cp().request("wicked-search", source, "get", id=item_id)


def _stats_request(source, params=None):
    """GET /api/v1/data/wicked-search/{source}/stats."""
    return _cp().request("wicked-search", source, "stats", params=params)


# ---------------------------------------------------------------------------
# Public async-compatible functions (importable by adapters)
# ---------------------------------------------------------------------------

def search(query, source="symbols", **kwargs):
    """Search symbols/documents/references/graph via CP."""
    params = {"q": query, **kwargs}
    return _search_request(source, params)


def symbols(query, **kwargs):
    """Search code symbols via CP."""
    return search(query, source="symbols", **kwargs)


def documents(query, **kwargs):
    """Search documents via CP."""
    return search(query, source="documents", **kwargs)


def graph_search(query, **kwargs):
    """Search graph nodes via CP."""
    return search(query, source="graph", **kwargs)


def graph_get(item_id):
    """Get a single graph node with dependencies/dependents."""
    return _get_request("graph", item_id)


def graph_traverse(item_id, depth=1, direction="both"):
    """Traverse graph from a symbol."""
    params = {"depth": depth, "direction": direction}
    return _cp().request("wicked-search", "graph", "traverse", id=item_id, params=params)


def graph_hotspots(**kwargs):
    """Find hotspot symbols with high connectivity."""
    return _cp().request("wicked-search", "graph", "hotspots", params=kwargs or None)


def graph_impact(column_id):
    """Reverse lineage from a database column to all UI fields it feeds."""
    return _cp().request("wicked-search", "graph", "impact", id=column_id)


def lineage_search(query, **kwargs):
    """Search lineage records via CP."""
    return search(query, source="lineage", **kwargs)


def categories(**kwargs):
    """Aggregate symbols by type and directory category."""
    return _cp().request("wicked-search", "symbols", "categories", params=kwargs or None)


def stats(source="symbols"):
    """Get statistics for a source."""
    return _stats_request(source)


def list_items(source, **kwargs):
    """List items from a source."""
    return _list_request(source, kwargs or None)


def content(file_path, line_start=None, line_end=None, project=None):
    """Read source file content for inline display."""
    params = {"path": file_path}
    if line_start is not None:
        params["line_start"] = line_start
    if line_end is not None:
        params["line_end"] = line_end
    if project:
        params["project"] = project
    return _cp().request("wicked-search", "code", "content", params=params)


def ide_url(file_path, line=1, ide="vscode", project=None):
    """Generate IDE deep link URL."""
    params = {"path": file_path, "line": line, "ide": ide}
    if project:
        params["project"] = project
    return _cp().request("wicked-search", "code", "ide-url", params=params)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _output(data):
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2))


def _error(message, code, **details):
    """Print error to stderr and exit."""
    err = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI verb handlers
# ---------------------------------------------------------------------------

def cmd_list(source, args):
    params = {"limit": args.limit, "offset": args.offset}
    if getattr(args, "project", None):
        params["project"] = args.project
    for attr in ("layer", "type", "category"):
        val = getattr(args, attr, None)
        if val:
            params[attr] = val
    result = _list_request(source, params)
    if result is None:
        _error("Control plane unreachable or returned no data", "CP_ERROR")
    _output(result)


def cmd_get(source, item_id, args):
    result = _get_request(source, item_id)
    if result is None:
        _error("Item not found or CP unreachable", "NOT_FOUND", source=source, id=item_id)
    _output(result)


def cmd_search(source, args):
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")
    params = {"q": args.query, "limit": args.limit, "offset": args.offset}
    if getattr(args, "project", None):
        params["project"] = args.project
    for attr in ("layer", "type", "category"):
        val = getattr(args, attr, None)
        if val:
            params[attr] = val
    result = _search_request(source, params)
    if result is None:
        _error("Control plane unreachable or returned no data", "CP_ERROR")
    _output(result)


def cmd_stats(source, args):
    params = {}
    if getattr(args, "project", None):
        params["project"] = args.project
    result = _stats_request(source, params or None)
    if result is None:
        _error("Control plane unreachable or returned no data", "CP_ERROR")
    _output(result)


def cmd_traverse(source, item_id, args):
    if source != "graph":
        _error("traverse only supported for graph source", "UNSUPPORTED_VERB")
    params = {"depth": args.depth, "direction": args.direction}
    if getattr(args, "project", None):
        params["project"] = args.project
    result = _cp().request("wicked-search", "graph", "traverse", id=item_id, params=params)
    if result is None:
        _error("Symbol not found or CP unreachable", "NOT_FOUND", id=item_id)
    _output(result)


def cmd_hotspots(source, args):
    if source != "graph":
        _error("hotspots only supported for graph source", "UNSUPPORTED_VERB")
    params = {"limit": args.limit, "offset": args.offset}
    if getattr(args, "project", None):
        params["project"] = args.project
    for attr in ("layer", "type", "category"):
        val = getattr(args, attr, None)
        if val:
            params[attr] = val
    result = _cp().request("wicked-search", "graph", "hotspots", params=params)
    if result is None:
        _error("Control plane unreachable or returned no data", "CP_ERROR")
    _output(result)


def cmd_categories(source, args):
    if source != "symbols":
        _error("categories only supported for symbols source", "UNSUPPORTED_VERB")
    params = {"limit": args.limit, "offset": args.offset}
    if getattr(args, "project", None):
        params["project"] = args.project
    result = _cp().request("wicked-search", "symbols", "categories", params=params)
    if result is None:
        _error("Control plane unreachable or returned no data", "CP_ERROR")
    _output(result)


def cmd_impact(source, item_id, args):
    if source != "graph":
        _error("impact only supported for graph source", "UNSUPPORTED_VERB")
    result = graph_impact(item_id)
    if result is None:
        _error("Column not found or CP unreachable", "NOT_FOUND", id=item_id)
    _output(result)


def cmd_content(source, item_id, args):
    if source != "code":
        _error("content only supported for code source", "UNSUPPORTED_VERB")
    result = content(
        item_id,
        line_start=getattr(args, "line_start", None),
        line_end=getattr(args, "line_end", None),
        project=getattr(args, "project", None),
    )
    if result is None:
        _error("File not found or CP unreachable", "NOT_FOUND", path=item_id)
    _output(result)


def cmd_ide_url(source, item_id, args):
    if source != "code":
        _error("ide-url only supported for code source", "UNSUPPORTED_VERB")
    result = ide_url(
        item_id,
        line=getattr(args, "line", 1),
        ide=getattr(args, "ide", "vscode"),
        project=getattr(args, "project", None),
    )
    if result is None:
        _error("File not found or CP unreachable", "NOT_FOUND", path=item_id)
    _output(result)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Wicked Search Data API (CP proxy)")
    subparsers = parser.add_subparsers(dest="verb")

    all_verbs = (
        "list", "get", "search", "stats", "traverse",
        "hotspots", "categories", "impact", "content", "ide-url",
    )
    for verb in all_verbs:
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source")
        if verb in ("get", "traverse", "impact", "content", "ide-url"):
            sub.add_argument("id", nargs="?", help="Item ID")
        if verb == "traverse":
            sub.add_argument("--depth", type=int, default=1)
            sub.add_argument("--direction", default="both")
        if verb == "content":
            sub.add_argument("--line-start", type=int, default=None, dest="line_start")
            sub.add_argument("--line-end", type=int, default=None, dest="line_end")
        if verb == "ide-url":
            sub.add_argument("--line", type=int, default=1)
            sub.add_argument("--ide", default="vscode")
        sub.add_argument("--limit", type=int, default=100 if verb != "hotspots" else 20)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument("--project", help="Filter by project")
        sub.add_argument("--query", help="Search query")
        if verb in ("list", "search", "hotspots"):
            sub.add_argument("--layer", help="Filter by architectural layer")
            sub.add_argument("--type", help="Filter by symbol type")
            sub.add_argument("--category", help="Filter by directory category")

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
