#!/usr/bin/env python3
"""Cheatsheet store — CLI wrapper for StorageManager cheatsheet operations.

Usage:
    python3 cheatsheet_store.py store --library react --data '{"key_apis": [...], ...}'
    python3 cheatsheet_store.py list [--search query]
    python3 cheatsheet_store.py get --library react
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager

_sm = StorageManager("wicked-smaht")


def cmd_store(args):
    """Store a cheatsheet."""
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("library", args.library)
    data.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    if args.version_hint:
        data.setdefault("version_hint", args.version_hint)

    result = _sm.create("cheatsheets", data)
    if result is None:
        print(json.dumps({"id": data["id"], "success": False, "error": "StorageManager returned None (offline queue)"}))
    else:
        print(json.dumps({"id": data["id"], "success": True}))


def cmd_list(args):
    """List stored cheatsheets."""
    records = _sm.list("cheatsheets") or []
    if args.search:
        q = args.search.lower()
        records = [
            r for r in records
            if q in r.get("library", "").lower()
        ]
    print(json.dumps(records, indent=2))


def cmd_get(args):
    """Get cheatsheet by library name (most recent)."""
    records = _sm.list("cheatsheets") or []
    matches = [
        r for r in records
        if r.get("library", "").lower() == args.library.lower()
    ]
    if matches:
        matches.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        print(json.dumps(matches[0]))
    else:
        print(json.dumps({"found": False}))


def main():
    parser = argparse.ArgumentParser(
        description="Cheatsheet store — CRUD operations via StorageManager"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # store subcommand
    store_p = subparsers.add_parser("store", help="Store a cheatsheet")
    store_p.add_argument("--library", required=True, help="Library name (e.g. react, fastapi)")
    store_p.add_argument("--data", required=True, help="JSON cheatsheet payload")
    store_p.add_argument("--version-hint", dest="version_hint", default=None,
                         help="Optional version string (e.g. 18.x)")
    store_p.set_defaults(func=cmd_store)

    # list subcommand
    list_p = subparsers.add_parser("list", help="List stored cheatsheets")
    list_p.add_argument("--search", default=None, help="Filter by library name substring")
    list_p.set_defaults(func=cmd_list)

    # get subcommand
    get_p = subparsers.add_parser("get", help="Get most recent cheatsheet for a library")
    get_p.add_argument("--library", required=True, help="Library name")
    get_p.set_defaults(func=cmd_get)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
