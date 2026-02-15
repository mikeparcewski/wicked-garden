#!/usr/bin/env python3
"""Wicked Search Data API — standard Plugin Data API interface.

Reads from JSONL index files and SQLite graph DBs under ~/.something-wicked/wicked-search/.
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
    python3 api.py list graph [--limit N]
    python3 api.py get graph <id>
    python3 api.py search graph --query "ClassName" [--limit N]
    python3 api.py stats graph
    python3 api.py list lineage [--limit N]
    python3 api.py search lineage --query "source_id" [--limit N]
    python3 api.py list services [--limit N]
    python3 api.py stats services
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

INDEX_DIR = Path.home() / ".something-wicked" / "wicked-search"
VALID_SOURCES = {"symbols", "documents", "references", "graph", "lineage", "services"}


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


def _find_graph_dbs():
    """Find all *_graph.db files under INDEX_DIR."""
    if not INDEX_DIR.exists():
        return []
    return list(INDEX_DIR.glob("*_graph.db"))


def _query_graph_dbs(query, params=()):
    """Execute SQL query across all graph DBs and merge results."""
    dbs = _find_graph_dbs()
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


def _get_db_stats():
    """Get stats from SQLite graph DBs if available."""
    stats = {"db_files": 0, "total_symbols": 0, "total_refs": 0}
    try:
        for db_file in INDEX_DIR.glob("*_graph.db"):
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


def cmd_list(source, args):
    """List items from a source."""
    if source in ("graph", "lineage", "services"):
        # SQLite-based sources
        if source == "graph":
            query = """
            SELECT s.id, s.type, s.name, s.qualified_name, s.file_path, s.line_start
            FROM symbols s
            ORDER BY s.name
            LIMIT ? OFFSET ?
            """
            items = _query_graph_dbs(query, (args.limit, args.offset))

        elif source == "lineage":
            query = "SELECT * FROM lineage_paths ORDER BY id LIMIT ? OFFSET ?"
            items = _query_graph_dbs(query, (args.limit, args.offset))

        elif source == "services":
            query = "SELECT * FROM service_nodes ORDER BY name LIMIT ? OFFSET ?"
            items = _query_graph_dbs(query, (args.limit, args.offset))
            # Enrich each service with its connections
            for service in items:
                service_id = service.get("id")
                if service_id:
                    conn_query = "SELECT * FROM service_connections WHERE source_service_id = ?"
                    connections = _query_graph_dbs(conn_query, (service_id,))
                    service["connections"] = connections

        total = len(items)
        print(json.dumps({"data": items, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))
        return

    # JSONL-based sources
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
    if source == "graph":
        # Get symbol from graph DB
        symbol_query = "SELECT * FROM symbols WHERE id = ?"
        symbols = _query_graph_dbs(symbol_query, (item_id,))

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
                deps = _query_graph_dbs(query, (item_id,))
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
                dependents = _query_graph_dbs(query, (item_id,))
                if dependents:
                    break
            except Exception:
                continue

        symbol["dependencies"] = deps
        symbol["dependents"] = dependents

        print(json.dumps({"data": symbol, "meta": _meta(source, 1)}, indent=2))
        return

    # JSONL-based sources
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

    if source == "graph":
        # Search symbols in graph DBs
        query = """
        SELECT * FROM symbols
        WHERE name LIKE ? OR qualified_name LIKE ?
        LIMIT ? OFFSET ?
        """
        pattern = f"%{args.query}%"
        results = _query_graph_dbs(query, (pattern, pattern, args.limit, args.offset))
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
        results = _query_graph_dbs(query, (pattern, pattern, args.limit, args.offset))
        total = len(results)
        print(json.dumps({"data": results, "meta": _meta(source, total, args.limit, args.offset)}, indent=2))
        return

    # JSONL-based sources
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
    if source == "graph":
        # Graph DB statistics
        dbs = _find_graph_dbs()
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
        dbs = _find_graph_dbs()
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
        sub.add_argument("source", help="Data source (symbols, documents, references, graph, lineage, services)")
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
