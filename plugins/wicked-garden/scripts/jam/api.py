#!/usr/bin/env python3
"""Wicked Jam Data API — standard Plugin Data API interface.

Usage:
    python3 api.py list sessions [--limit N] [--offset N] [--query Q]
    python3 api.py get sessions <id>
    python3 api.py search sessions --query Q [--limit N]
    python3 api.py stats sessions
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".something-wicked" / "wicked-jam" / "sessions"
VALID_SOURCES = {"sessions"}


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


def _load_session(path):
    """Load a session file and return normalized data."""
    try:
        with open(path) as f:
            data = json.load(f)
        return {
            "id": path.stem,
            "topic": data.get("topic", ""),
            "summary": ((data.get("synthesis") or {}).get("summary", "") or "")[:500],
            "perspectives_count": len(data.get("perspectives", [])),
            "created": data.get("created", ""),
            "project": data.get("project", ""),
        }
    except (json.JSONDecodeError, OSError):
        return None


def _load_session_full(path):
    """Load full session data."""
    try:
        with open(path) as f:
            data = json.load(f)
        perspectives = data.get("perspectives", [])
        return {
            "id": path.stem,
            "topic": data.get("topic", ""),
            "synthesis": data.get("synthesis") or {},
            "perspectives": [
                {
                    "persona": p.get("persona", ""),
                    "role": p.get("role", ""),
                    "response": (p.get("response", "") or "")[:1000],
                    "position": p.get("position", ""),
                    "key_concern": p.get("key_concern", ""),
                    "would_change_mind": p.get("would_change_mind", ""),
                }
                for p in perspectives
            ],
            "created": data.get("created", ""),
            "project": data.get("project", ""),
        }
    except (json.JSONDecodeError, OSError):
        return None


def _all_sessions():
    """Get all sessions sorted by modification time (newest first)."""
    if not SESSIONS_DIR.exists():
        return []
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    sessions = []
    for f in files:
        s = _load_session(f)
        if s:
            sessions.append(s)
    return sessions


def cmd_list(args):
    """List sessions."""
    sessions = _all_sessions()
    total = len(sessions)
    data = sessions[args.offset:args.offset + args.limit]
    print(json.dumps({"data": data, "meta": _meta("sessions", total, args.limit, args.offset)}, indent=2))


def cmd_get(session_id, args):
    """Get a specific session."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        _error("Session not found", "NOT_FOUND", resource="sessions", id=session_id)

    data = _load_session_full(path)
    if not data:
        _error("Could not read session", "READ_ERROR", resource="sessions", id=session_id)

    print(json.dumps({"data": data, "meta": _meta("sessions", 1)}, indent=2))


def cmd_search(args):
    """Search sessions by topic/summary."""
    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    query_lower = args.query.lower()
    sessions = _all_sessions()

    results = []
    for s in sessions:
        text = f"{s['topic']} {s['summary']}".lower()
        if any(word in text for word in query_lower.split() if len(word) > 2):
            results.append(s)
        if len(results) >= args.limit:
            break

    print(json.dumps({"data": results, "meta": _meta("sessions", len(results), args.limit, args.offset)}, indent=2))


def cmd_stats(args):
    """Get session statistics."""
    sessions = _all_sessions()
    total = len(sessions)
    total_perspectives = sum(s.get("perspectives_count", 0) for s in sessions)
    projects = set(s.get("project", "") for s in sessions if s.get("project"))

    data = {
        "total_sessions": total,
        "total_perspectives": total_perspectives,
        "unique_projects": len(projects),
        "projects": sorted(projects),
    }
    print(json.dumps({"data": data, "meta": _meta("sessions", total)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Wicked Jam Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in ("list", "get", "search", "stats"):
        sub = subparsers.add_parser(verb)
        sub.add_argument("source", help="Data source (sessions)")
        if verb == "get":
            sub.add_argument("id", nargs="?", help="Session ID")
        sub.add_argument("--limit", type=int, default=100)
        sub.add_argument("--offset", type=int, default=0)
        sub.add_argument("--query", help="Search query")
        sub.add_argument("--project", help="Filter by project")
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
