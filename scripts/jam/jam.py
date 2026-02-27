#!/usr/bin/env python3
"""
wicked-jam query CLI -- exposes session data for cross-plugin access.

All data flows through StorageManager("wicked-jam") which routes to the
Control Plane when available and falls back to local JSON files.

Usage:
    jam.py list-sessions [--query Q] [--limit N] [--json] [--project P]
"""

import argparse
import json
import sys
from pathlib import Path

# Resolve _storage from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager

_sm = StorageManager("wicked-jam")


def list_sessions(query: str = None, limit: int = 10, project: str = None) -> dict:
    """List recent brainstorming sessions, optionally filtered by query."""
    params = {}
    if query:
        params["q"] = query
    if project:
        params["project"] = project

    records = _sm.list("sessions", **params)

    results = []
    query_lower = query.lower() if query else None

    for session in records:
        topic = session.get("topic", "")
        summary = session.get("synthesis", {}).get("summary", "")
        perspectives = session.get("perspectives", [])
        created = session.get("created", "")
        session_project = session.get("project", "")

        # Filter by project if specified (in case local fallback doesn't filter)
        if project and session_project and session_project != project:
            continue

        # Filter by query if specified (in case local fallback doesn't filter)
        if query_lower:
            text = f"{topic} {summary}".lower()
            if not any(word in text for word in query_lower.split() if len(word) > 2):
                continue

        results.append({
            "id": session.get("id", ""),
            "topic": topic,
            "summary": summary[:300] if summary else "",
            "perspectives_count": len(perspectives) if isinstance(perspectives, list) else 0,
            "created": created,
        })

        if len(results) >= limit:
            break

    return {"sessions": results}


def main():
    parser = argparse.ArgumentParser(description="wicked-jam query CLI")
    subparsers = parser.add_subparsers(dest="command")

    ls_parser = subparsers.add_parser("list-sessions", help="List brainstorming sessions")
    ls_parser.add_argument("--query", "-q", help="Filter by topic/summary text")
    ls_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    ls_parser.add_argument("--json", action="store_true", help="Output as JSON")
    ls_parser.add_argument("--project", "-p", help="Filter by project")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list-sessions":
        result = list_sessions(
            query=args.query,
            limit=args.limit,
            project=args.project,
        )
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            sessions = result["sessions"]
            if not sessions:
                print("No sessions found.")
                return
            for s in sessions:
                print(f"  {s['id']}: {s['topic']} ({s['perspectives_count']} perspectives)")


if __name__ == "__main__":
    main()
