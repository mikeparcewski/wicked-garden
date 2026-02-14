#!/usr/bin/env python3
"""Wicked Mem Data API — standard Plugin Data API interface.

Usage:
    python3 api.py list memories [--type TYPE] [--limit N] [--offset N]
    python3 api.py get memories <id>
    python3 api.py search memories --query "text" [--limit N]
    python3 api.py stats memories
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))
from memory import MemoryStore, MemoryType, get_store

VALID_SOURCES = {"memories"}


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


def _memory_to_dict(m):
    """Convert a Memory object to a serializable dict."""
    return {
        "id": m.id,
        "title": m.title,
        "content": m.content,
        "type": m.type,
        "status": getattr(m, "status", "active"),
        "importance": getattr(m, "importance", "medium"),
        "tags": getattr(m, "tags", []),
        "created": getattr(m, "created", ""),
        "accessed": getattr(m, "accessed", ""),
        "access_count": getattr(m, "access_count", 0),
    }


def cmd_list(args):
    """List memories with optional type filter."""
    store = get_store(project=args.project)

    all_memories = []
    # Walk the file tree to get all memories
    for md_file in store.base_path.rglob("*.md"):
        memory = store._from_markdown(md_file)
        if memory and memory.status == "active":
            if args.type and memory.type != args.type:
                continue
            all_memories.append(_memory_to_dict(memory))

    # Sort by updated date descending
    all_memories.sort(key=lambda m: m.get("updated", ""), reverse=True)

    total = len(all_memories)
    data = all_memories[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("memories", total, args.limit, args.offset)}, indent=2))


def cmd_get(item_id, args):
    """Get a specific memory by ID."""
    store = get_store(project=args.project)

    # Search for the memory by ID
    for md_file in store.base_path.rglob("*.md"):
        memory = store._from_markdown(md_file)
        if memory and memory.id == item_id:
            print(json.dumps({"data": _memory_to_dict(memory), "meta": _meta("memories", 1)}, indent=2))
            return

    _error("Memory not found", "NOT_FOUND", resource="memories", id=item_id)


def cmd_search(args):
    """Search memories by query string."""
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    store = get_store(project=args.project)
    query_lower = args.query.lower()

    results = []
    for md_file in store.base_path.rglob("*.md"):
        memory = store._from_markdown(md_file)
        if not memory or memory.status != "active":
            continue
        # Search in title, content, and tags
        searchable = f"{memory.title} {memory.content} {' '.join(memory.tags)}".lower()
        if query_lower in searchable:
            results.append(_memory_to_dict(memory))

    results.sort(key=lambda m: m.get("updated", ""), reverse=True)
    total = len(results)
    data = results[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("memories", total, args.limit, args.offset)}, indent=2))


def cmd_stats(args):
    """Get memory statistics."""
    store = get_store(project=args.project)
    raw_stats = store.stats()
    print(json.dumps({"data": raw_stats, "meta": _meta("memories", 1)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Wicked Mem Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in ("list", "get", "search", "stats"):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (memories)")
        if verb == "get":
            sub.add_argument("id", nargs="?", help="Memory ID")
        sub.add_argument("--limit", type=int, default=100)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument("--project", help="Filter by project")
        sub.add_argument("--query", help="Search query")
        sub.add_argument("--type", help="Filter by memory type")
        sub.add_argument("--filter", help="Filter expression")

    args = parser.parse_args()

    if not args.verb:
        parser.print_help()
        sys.exit(1)

    if args.source not in VALID_SOURCES:
        _error(f"Unknown source: {args.source}", "INVALID_SOURCE",
               source=args.source, valid=list(VALID_SOURCES))

    if args.verb == "list":
        cmd_list(args)
    elif args.verb == "get":
        if not args.id:
            _error("ID required for get verb", "MISSING_ID")
        cmd_get(args.id, args)
    elif args.verb == "search":
        cmd_search(args)
    elif args.verb == "stats":
        cmd_stats(args)


if __name__ == "__main__":
    main()
