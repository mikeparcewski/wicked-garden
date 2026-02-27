#!/usr/bin/env python3
"""Wicked Mem Data API — standard Plugin Data API interface.

Usage:
    python3 api.py list memories [--type TYPE] [--limit N] [--offset N]
    python3 api.py get memories <id>
    python3 api.py search memories --query "text" [--limit N]
    python3 api.py stats memories
    python3 api.py create memories < payload.json
    python3 api.py update memories <id> < payload.json
    python3 api.py delete memories <id>
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))
from memory import MemoryStore, MemoryType, Importance, get_store

VALID_SOURCES = {"memories", "projects"}


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


def _read_input():
    """Read JSON input from stdin for write operations."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        _error("Invalid JSON input", "INVALID_INPUT")


def _validate_required(data, *fields):
    """Validate required fields are present."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        _error("Validation failed", "VALIDATION_ERROR",
               fields={f: "required field missing" for f in missing})


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


# ==================== Read Handlers ====================


def cmd_list_projects(args):
    """List all projects that have stored memories."""
    store = get_store()
    projects = store.list_projects()
    data = [{"name": p} for p in projects]
    total = len(data)
    page = data[args.offset:args.offset + args.limit]
    print(json.dumps({"data": page, "meta": _meta("projects", total, args.limit, args.offset)}, indent=2))


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


# ==================== Write Handlers ====================


def cmd_create(args):
    """Create a new memory — reads JSON from stdin."""
    data = _read_input()
    _validate_required(data, "title", "content")

    store = get_store(project=args.project)

    # Map type string to MemoryType enum
    mem_type = MemoryType.EPISODIC  # default
    type_str = data.get("type", "episodic").upper()
    try:
        mem_type = MemoryType[type_str]
    except KeyError:
        valid_types = [t.name.lower() for t in MemoryType]
        _error(f"Invalid memory type: {data.get('type')}",
               "VALIDATION_ERROR",
               fields={"type": f"must be one of: {', '.join(valid_types)}"})

    # Map importance string to Importance enum
    importance = Importance.MEDIUM  # default
    imp_str = data.get("importance", "medium").upper()
    try:
        importance = Importance[imp_str]
    except KeyError:
        valid_imps = [i.name.lower() for i in Importance]
        _error(f"Invalid importance: {data.get('importance')}",
               "VALIDATION_ERROR",
               fields={"importance": f"must be one of: {', '.join(valid_imps)}"})

    # Tags can be a list or comma-separated string
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    memory = store.store(
        title=data["title"],
        content=data["content"],
        type=mem_type,
        tags=tags,
        importance=importance,
        summary=data.get("summary"),
    )

    if not memory:
        _error("Failed to create memory", "CREATE_FAILED", resource="memories")

    print(json.dumps({"data": _memory_to_dict(memory), "meta": _meta("memories", 1)}, indent=2))


def cmd_update(item_id, args):
    """Update an existing memory — reads JSON from stdin."""
    data = _read_input()

    store = get_store(project=args.project)

    # Verify memory exists
    found = None
    for md_file in store.base_path.rglob("*.md"):
        memory = store._from_markdown(md_file)
        if memory and memory.id == item_id:
            found = memory
            break

    if not found:
        _error("Memory not found", "NOT_FOUND", resource="memories", id=item_id)

    # Apply updates to the found memory object
    allowed_fields = {"title", "content", "summary", "tags", "importance", "context", "outcome", "status"}
    for key, val in data.items():
        if key in allowed_fields and val is not None:
            if key == "tags" and isinstance(val, str):
                val = [t.strip() for t in val.split(",") if t.strip()]
            if key == "importance":
                imp_str = val.upper()
                try:
                    val = Importance[imp_str].value
                except KeyError:
                    valid_imps = [i.name.lower() for i in Importance]
                    _error(f"Invalid importance: {val}",
                           "VALIDATION_ERROR",
                           fields={"importance": f"must be one of: {', '.join(valid_imps)}"})
            setattr(found, key, val)

    # Re-save to disk
    path = store._get_path(found)
    path.write_text(store._to_markdown(found), encoding="utf-8")

    print(json.dumps({"data": _memory_to_dict(found), "meta": _meta("memories", 1)}, indent=2))


def cmd_delete(item_id, args):
    """Delete (soft) a memory."""
    store = get_store(project=args.project)

    result = store.forget(item_id, hard=False)
    if not result:
        _error("Memory not found", "NOT_FOUND", resource="memories", id=item_id)

    print(json.dumps({"data": {"deleted": True, "id": item_id}, "meta": _meta("memories", 1)}, indent=2))


# ==================== Main ====================


def main():
    parser = argparse.ArgumentParser(description="Wicked Mem Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in ("list", "get", "search", "stats", "create", "update", "delete"):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (memories)")
        if verb in ("get", "update", "delete"):
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
        if args.source == "projects":
            cmd_list_projects(args)
        else:
            cmd_list(args)
    elif args.verb == "get":
        if not args.id:
            _error("ID required for get verb", "MISSING_ID")
        cmd_get(args.id, args)
    elif args.verb == "search":
        cmd_search(args)
    elif args.verb == "stats":
        cmd_stats(args)
    elif args.verb == "create":
        cmd_create(args)
    elif args.verb == "update":
        if not args.id:
            _error("ID required for update verb", "MISSING_ID")
        cmd_update(args.id, args)
    elif args.verb == "delete":
        if not args.id:
            _error("ID required for delete verb", "MISSING_ID")
        cmd_delete(args.id, args)


if __name__ == "__main__":
    main()
