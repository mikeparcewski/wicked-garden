#!/usr/bin/env python3
"""
wicked-jam query CLI -- exposes session data for cross-plugin access.

All data flows through StorageManager("wicked-jam") which routes to the
Control Plane when available and falls back to local JSON files.

Usage:
    jam.py list-sessions [--query Q] [--limit N] [--json] [--project P]
    jam.py transcript [--session-id ID] [--json]
    jam.py persona <name> [--session-id ID] [--json]
    jam.py thinking [--session-id ID] [--json]

Transcript entry schema:
    {
        "session_id": "...",
        "round": 1,
        "persona_name": "Technical Architect",
        "persona_type": "technical",   # technical | user | business | process | council
        "raw_text": "...",
        "timestamp": "...",
        "entry_type": "perspective"    # perspective | synthesis | council_response
    }
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


def _resolve_session_id(session_id: str = None) -> str:
    """Return the given session_id or derive the most recent one from stored sessions."""
    if session_id:
        return session_id
    records = _sm.list("sessions")
    if not records:
        return None
    # Sessions are expected to be in insertion order; take the last one.
    latest = records[-1]
    return latest.get("id", "")


def get_transcript(session_id: str = None) -> dict:
    """Return the full transcript (all entries) for a session, in chronological order."""
    sid = _resolve_session_id(session_id)
    if not sid:
        return {"session_id": None, "entries": [], "error": "No sessions found."}

    data = _sm.get("transcripts", sid)
    if not data:
        return {
            "session_id": sid,
            "entries": [],
            "error": f"No transcript found for session: {sid}",
        }

    entries = data.get("entries", [])
    return {"session_id": sid, "entries": entries}


def get_persona(name: str, session_id: str = None) -> dict:
    """Return all transcript entries from a specific persona (case-insensitive match)."""
    sid = _resolve_session_id(session_id)
    if not sid:
        return {"session_id": None, "persona": name, "entries": [], "error": "No sessions found."}

    data = _sm.get("transcripts", sid)
    if not data:
        return {
            "session_id": sid,
            "persona": name,
            "entries": [],
            "error": f"No transcript found for session: {sid}",
        }

    name_lower = name.lower()
    entries = [
        e for e in data.get("entries", [])
        if e.get("persona_name", "").lower() == name_lower
    ]

    if not entries:
        return {
            "session_id": sid,
            "persona": name,
            "entries": [],
            "error": f"No contributions found for persona: {name}",
        }

    return {"session_id": sid, "persona": name, "entries": entries}


def get_thinking(session_id: str = None) -> dict:
    """Return all pre-synthesis perspective entries for a session."""
    sid = _resolve_session_id(session_id)
    if not sid:
        return {"session_id": None, "entries": [], "error": "No sessions found."}

    data = _sm.get("transcripts", sid)
    if not data:
        return {
            "session_id": sid,
            "entries": [],
            "error": f"No transcript found for session: {sid}",
        }

    entries = [
        e for e in data.get("entries", [])
        if e.get("entry_type") == "perspective"
    ]
    return {"session_id": sid, "entries": entries}


def _print_entry(entry: dict, index: int = None) -> None:
    """Pretty-print a single transcript entry."""
    prefix = f"[{index}] " if index is not None else ""
    round_num = entry.get("round", "?")
    persona = entry.get("persona_name", "Unknown")
    ptype = entry.get("persona_type", "")
    etype = entry.get("entry_type", "")
    timestamp = entry.get("timestamp", "")

    type_label = f"  ({etype})" if etype else ""
    ptype_label = f" [{ptype}]" if ptype else ""
    ts_label = f"  {timestamp}" if timestamp else ""

    print(f"\n{prefix}Round {round_num} — {persona}{ptype_label}{type_label}{ts_label}")
    print("-" * 60)
    print(entry.get("raw_text", "").strip())


def main():
    parser = argparse.ArgumentParser(description="wicked-jam query CLI")
    subparsers = parser.add_subparsers(dest="command")

    ls_parser = subparsers.add_parser("list-sessions", help="List brainstorming sessions")
    ls_parser.add_argument("--query", "-q", help="Filter by topic/summary text")
    ls_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    ls_parser.add_argument("--json", action="store_true", help="Output as JSON")
    ls_parser.add_argument("--project", "-p", help="Filter by project")

    tr_parser = subparsers.add_parser("transcript", help="Full conversation transcript")
    tr_parser.add_argument("--session-id", help="Session ID (defaults to most recent)")
    tr_parser.add_argument("--json", action="store_true", help="Output as JSON")

    pe_parser = subparsers.add_parser("persona", help="Specific persona's contributions")
    pe_parser.add_argument("name", help="Persona name (case-insensitive)")
    pe_parser.add_argument("--session-id", help="Session ID (defaults to most recent)")
    pe_parser.add_argument("--json", action="store_true", help="Output as JSON")

    th_parser = subparsers.add_parser("thinking", help="All pre-synthesis perspectives")
    th_parser.add_argument("--session-id", help="Session ID (defaults to most recent)")
    th_parser.add_argument("--json", action="store_true", help="Output as JSON")

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

    elif args.command == "transcript":
        result = get_transcript(session_id=getattr(args, "session_id", None))
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            error = result.get("error")
            if error and not result["entries"]:
                print(error)
                return
            sid = result.get("session_id", "")
            entries = result["entries"]
            print(f"Transcript — session: {sid}  ({len(entries)} entries)")
            for i, entry in enumerate(entries, start=1):
                _print_entry(entry, index=i)

    elif args.command == "persona":
        result = get_persona(name=args.name, session_id=getattr(args, "session_id", None))
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            error = result.get("error")
            if error and not result["entries"]:
                print(error)
                return
            sid = result.get("session_id", "")
            entries = result["entries"]
            persona = result.get("persona", args.name)
            print(f"Contributions from: {persona}  |  session: {sid}  ({len(entries)} entries)")
            for i, entry in enumerate(entries, start=1):
                _print_entry(entry, index=i)

    elif args.command == "thinking":
        result = get_thinking(session_id=getattr(args, "session_id", None))
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            error = result.get("error")
            if error and not result["entries"]:
                print(error)
                return
            sid = result.get("session_id", "")
            entries = result["entries"]
            print(f"Pre-synthesis perspectives — session: {sid}  ({len(entries)} entries)")
            for i, entry in enumerate(entries, start=1):
                _print_entry(entry, index=i)


if __name__ == "__main__":
    main()
