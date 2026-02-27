#!/usr/bin/env python3
"""Wicked Smaht Data API — standard Plugin Data API interface.

Usage:
    python3 api.py list sessions [--limit N] [--offset N]
    python3 api.py get sessions <id>
    python3 api.py stats sessions
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_BASE = Path.home() / ".something-wicked" / "wicked-smaht" / "sessions"
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


def _load_session_summary(session_dir):
    """Load session summary from a session directory."""
    summary_path = session_dir / "summary.json"
    turns_path = session_dir / "turns.jsonl"

    result = {
        "id": session_dir.name,
        "turn_count": 0,
        "topics": [],
        "decisions": [],
        "current_task": "",
    }

    if summary_path.exists():
        try:
            with open(summary_path) as f:
                data = json.load(f)
            result["topics"] = data.get("topics", [])
            result["decisions"] = data.get("decisions", [])
            result["current_task"] = data.get("current_task", "")
            result["active_constraints"] = data.get("active_constraints", [])
            result["file_scope"] = data.get("file_scope", [])
        except (json.JSONDecodeError, OSError):
            pass

    if turns_path.exists():
        try:
            with open(turns_path) as f:
                result["turn_count"] = sum(1 for _ in f)
        except OSError:
            pass

    return result


def _all_sessions():
    """Get all sessions across all workspaces."""
    if not SESSIONS_BASE.exists():
        return []

    sessions = []
    for workspace in sorted(SESSIONS_BASE.iterdir()):
        if not workspace.is_dir():
            continue
        for session_dir in sorted(workspace.iterdir(), reverse=True):
            if not session_dir.is_dir():
                continue
            s = _load_session_summary(session_dir)
            s["workspace"] = workspace.name
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
    if not SESSIONS_BASE.exists():
        _error("Session not found", "NOT_FOUND", resource="sessions", id=session_id)

    # Search across workspaces
    for workspace in SESSIONS_BASE.iterdir():
        if not workspace.is_dir():
            continue
        session_dir = workspace / session_id
        if session_dir.exists() and session_dir.is_dir():
            data = _load_session_summary(session_dir)
            data["workspace"] = workspace.name
            print(json.dumps({"data": data, "meta": _meta("sessions", 1)}, indent=2))
            return

    _error("Session not found", "NOT_FOUND", resource="sessions", id=session_id)


def cmd_stats(args):
    """Get session statistics."""
    sessions = _all_sessions()
    total = len(sessions)
    total_turns = sum(s.get("turn_count", 0) for s in sessions)
    total_decisions = sum(len(s.get("decisions", [])) for s in sessions)
    workspaces = set(s.get("workspace", "") for s in sessions)

    data = {
        "total_sessions": total,
        "total_turns": total_turns,
        "total_decisions": total_decisions,
        "workspaces": sorted(workspaces),
    }
    print(json.dumps({"data": data, "meta": _meta("sessions", total)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Wicked Smaht Data API")
    subparsers = parser.add_subparsers(dest="verb")

    for verb in ("list", "get", "stats"):
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
    elif args.verb == "stats":
        cmd_stats(args)


if __name__ == "__main__":
    main()
