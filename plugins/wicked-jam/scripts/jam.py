#!/usr/bin/env python3
"""
wicked-jam query CLI — exposes session data for cross-plugin access.

Usage:
    jam.py list-sessions [--query Q] [--limit N] [--json] [--project P]
"""

import argparse
import json
import sys
from pathlib import Path


def get_sessions_dir() -> Path:
    """Get the sessions storage directory."""
    return Path.home() / ".something-wicked" / "wicked-jam" / "sessions"


def list_sessions(query: str = None, limit: int = 10, project: str = None) -> dict:
    """List recent brainstorming sessions, optionally filtered by query."""
    sessions_dir = get_sessions_dir()
    if not sessions_dir.exists():
        return {"sessions": []}

    results = []
    session_files = sorted(
        sessions_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    query_lower = query.lower() if query else None

    for session_file in session_files:
        try:
            with open(session_file) as f:
                session = json.load(f)

            topic = session.get("topic", "")
            summary = session.get("synthesis", {}).get("summary", "")
            perspectives = session.get("perspectives", [])
            created = session.get("created", "")
            session_project = session.get("project", "")

            # Filter by project if specified
            if project and session_project and session_project != project:
                continue

            # Filter by query if specified
            if query_lower:
                text = f"{topic} {summary}".lower()
                if not any(word in text for word in query_lower.split() if len(word) > 2):
                    continue

            results.append({
                "id": session_file.stem,
                "topic": topic,
                "summary": summary[:300] if summary else "",
                "perspectives_count": len(perspectives),
                "created": created,
            })

            if len(results) >= limit:
                break

        except (json.JSONDecodeError, OSError):
            continue

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
