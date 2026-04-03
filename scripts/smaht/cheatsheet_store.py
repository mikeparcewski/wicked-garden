#!/usr/bin/env python3
"""Cheatsheet store — CLI wrapper for DomainStore cheatsheet operations.

Usage:
    python3 cheatsheet_store.py store --library react --data '{"key_apis": [...], ...}'
    python3 cheatsheet_store.py list [--search query]
    python3 cheatsheet_store.py get --library react
    python3 cheatsheet_store.py remove --library react
    python3 cheatsheet_store.py update-all
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _domain_store import DomainStore

_sm = DomainStore("wicked-smaht")


def _find_existing(library):
    """Find the most recent cheatsheet for a library. Returns (record, all_matches)."""
    records = _sm.list("cheatsheets") or []
    matches = [
        r for r in records
        if r.get("library", "").lower() == library.lower()
    ]
    if matches:
        matches.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return matches[0], matches
    return None, []


def _diff_cheatsheets(old, new):
    """Compute a human-readable diff between two cheatsheet records.

    Returns a dict with changed sections and a boolean indicating whether
    anything meaningful changed.
    """
    changes = {}

    # Compare key_apis by name
    old_apis = {a["name"]: a for a in old.get("key_apis", [])}
    new_apis = {a["name"]: a for a in new.get("key_apis", [])}
    added_apis = sorted(set(new_apis) - set(old_apis))
    removed_apis = sorted(set(old_apis) - set(new_apis))
    if added_apis or removed_apis:
        changes["key_apis"] = {}
        if added_apis:
            changes["key_apis"]["added"] = added_apis
        if removed_apis:
            changes["key_apis"]["removed"] = removed_apis

    # Compare common_patterns by name
    old_pats = {p["name"]: p for p in old.get("common_patterns", [])}
    new_pats = {p["name"]: p for p in new.get("common_patterns", [])}
    added_pats = sorted(set(new_pats) - set(old_pats))
    removed_pats = sorted(set(old_pats) - set(new_pats))
    if added_pats or removed_pats:
        changes["common_patterns"] = {}
        if added_pats:
            changes["common_patterns"]["added"] = added_pats
        if removed_pats:
            changes["common_patterns"]["removed"] = removed_pats

    # Compare gotchas
    old_gotchas = set(old.get("gotchas", []))
    new_gotchas = set(new.get("gotchas", []))
    added_g = sorted(new_gotchas - old_gotchas)
    removed_g = sorted(old_gotchas - new_gotchas)
    if added_g or removed_g:
        changes["gotchas"] = {}
        if added_g:
            changes["gotchas"]["added"] = added_g
        if removed_g:
            changes["gotchas"]["removed"] = removed_g

    has_changes = len(changes) > 0
    return changes, has_changes


def cmd_store(args):
    """Store a cheatsheet. Detects updates to existing entries and reports diffs."""
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    existing, all_matches = _find_existing(args.library)

    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("library", args.library)
    data.setdefault("timestamp", now)
    data["fetched_at"] = now
    if existing:
        data["last_updated"] = now
        data["previous_fetched_at"] = existing.get("fetched_at", existing.get("timestamp"))
    if args.version_hint:
        data.setdefault("version_hint", args.version_hint)

    # Compute diff if updating an existing cheatsheet
    diff_result = None
    if existing:
        changes, has_changes = _diff_cheatsheets(existing, data)
        diff_result = {"has_changes": has_changes, "changes": changes}
        # Remove old entries for this library so we don't accumulate duplicates
        for old_rec in all_matches:
            old_id = old_rec.get("id")
            if old_id:
                try:
                    _sm.delete("cheatsheets", old_id)
                except Exception:
                    pass  # best-effort cleanup

    result = _sm.create("cheatsheets", data)
    output = {"id": data["id"], "success": result is not None}
    if result is None:
        output["error"] = "DomainStore returned None"
    if existing:
        output["updated"] = True
        output["diff"] = diff_result
    else:
        output["updated"] = False

    print(json.dumps(output))


def cmd_list(args):
    """List stored cheatsheets."""
    records = _sm.list("cheatsheets") or []
    if args.search:
        q = args.search.lower()
        records = [
            r for r in records
            if q in r.get("library", "").lower()
        ]
    # Deduplicate: keep only the most recent per library
    seen = {}
    for r in sorted(records, key=lambda x: x.get("timestamp", ""), reverse=True):
        lib = r.get("library", "").lower()
        if lib not in seen:
            seen[lib] = r
    deduped = sorted(seen.values(), key=lambda x: x.get("timestamp", ""), reverse=True)
    print(json.dumps(deduped, indent=2))


def cmd_get(args):
    """Get cheatsheet by library name (most recent)."""
    existing, _ = _find_existing(args.library)
    if existing:
        print(json.dumps(existing))
    else:
        print(json.dumps({"found": False}))


def cmd_remove(args):
    """Remove all cheatsheet entries for a library."""
    existing, all_matches = _find_existing(args.library)
    if not existing:
        print(json.dumps({"success": False, "error": f"No cheatsheet found for '{args.library}'"}))
        sys.exit(1)

    removed = 0
    for rec in all_matches:
        rec_id = rec.get("id")
        if rec_id:
            try:
                _sm.delete("cheatsheets", rec_id)
                removed += 1
            except Exception:
                pass
    print(json.dumps({"success": True, "library": args.library, "removed": removed}))


def cmd_update_all(args):
    """List all unique libraries that have cached cheatsheets (for re-fetch orchestration)."""
    records = _sm.list("cheatsheets") or []
    seen = {}
    for r in sorted(records, key=lambda x: x.get("timestamp", ""), reverse=True):
        lib = r.get("library", "").lower()
        if lib not in seen:
            seen[lib] = {
                "library": r.get("library"),
                "version_hint": r.get("version_hint"),
                "fetched_at": r.get("fetched_at", r.get("timestamp")),
            }
    libraries = sorted(seen.values(), key=lambda x: x.get("fetched_at", ""))
    print(json.dumps({"libraries": libraries, "count": len(libraries)}))


def main():
    parser = argparse.ArgumentParser(
        description="Cheatsheet store — CRUD operations via DomainStore"
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

    # remove subcommand
    remove_p = subparsers.add_parser("remove", help="Remove cheatsheet for a library")
    remove_p.add_argument("--library", required=True, help="Library name to remove")
    remove_p.set_defaults(func=cmd_remove)

    # update-all subcommand
    update_all_p = subparsers.add_parser("update-all",
                                          help="List all cached libraries for re-fetch")
    update_all_p.set_defaults(func=cmd_update_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
