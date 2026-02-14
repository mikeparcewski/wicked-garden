#!/usr/bin/env python3
"""Wicked Search Data API — standard Plugin Data API interface.

Reads from JSONL index files under ~/.something-wicked/wicked-search/.
Stdlib-only — no tree-sitter or other dependencies needed for queries.

Usage:
    python3 api.py list symbols [--limit N] [--offset N]
    python3 api.py search symbols --query "ClassName" [--limit N]
    python3 api.py get symbols <id>
    python3 api.py stats symbols
    python3 api.py list documents [--limit N]
    python3 api.py search documents --query "readme" [--limit N]
    python3 api.py list references [--limit N]
    python3 api.py search references --query "imports" [--limit N]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

INDEX_DIR = Path.home() / ".something-wicked" / "wicked-search"
VALID_SOURCES = {"symbols", "documents", "references"}


def _meta(source, total, limit=100, offset=0):
    """Build standard meta block."""
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _error(message, code, **details):
    """Print error to stderr and exit."""
    err = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


def _load_jsonl_index():
    """Load all JSONL index files and return nodes."""
    if not INDEX_DIR.exists():
        return []

    nodes = []
    for jsonl_file in INDEX_DIR.glob("*.jsonl"):
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


def _get_db_stats():
    """Get stats from SQLite graph DBs if available."""
    stats = {"db_files": 0, "total_symbols": 0, "total_refs": 0}
    try:
        import sqlite3
        for db_file in INDEX_DIR.glob("*_graph.db"):
            stats["db_files"] += 1
            try:
                conn = sqlite3.connect(str(db_file))
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


def cmd_list(source, args):
    """List items from a source."""
    nodes = _load_jsonl_index()

    if source == "symbols":
        items = [n for n in nodes if n.get("domain") == "code"]
    elif source == "documents":
        items = [n for n in nodes if n.get("domain") == "doc"]
    elif source == "references":
        # References are cross-reference entries
        items = [n for n in nodes if n.get("type") in ("import", "reference", "ref", "cross_ref")]
    else:
        items = nodes

    total = len(items)
    data = items[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))


def cmd_get(source, item_id, args):
    """Get a specific item by ID."""
    nodes = _load_jsonl_index()

    for node in nodes:
        nid = node.get("id") or node.get("name")
        if nid == item_id:
            print(json.dumps({"data": node, "meta": _meta(source, 1)}, indent=2))
            return

    _error("Item not found", "NOT_FOUND", resource=source, id=item_id)


def cmd_search(source, args):
    """Search items."""
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    nodes = _load_jsonl_index()

    if source == "symbols":
        nodes = [n for n in nodes if n.get("domain") == "code"]
    elif source == "documents":
        nodes = [n for n in nodes if n.get("domain") == "doc"]

    results = _search_nodes(nodes, args.query)
    total = len(results)
    data = results[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))


def cmd_stats(source, args):
    """Get statistics."""
    nodes = _load_jsonl_index()
    db_stats = _get_db_stats()

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
    jsonl_count = len(list(INDEX_DIR.glob("*.jsonl"))) if INDEX_DIR.exists() else 0

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

    for verb in ("list", "get", "search", "stats"):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (symbols, documents, references)")
        if verb == "get":
            sub.add_argument("id", nargs="?", help="Item ID")
        sub.add_argument("--limit", type=int, default=100)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument("--project", help="Filter by project")
        sub.add_argument("--query", help="Search query")
        sub.add_argument("--filter", help="Filter expression")

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


if __name__ == "__main__":
    main()
