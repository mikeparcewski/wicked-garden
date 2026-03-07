#!/usr/bin/env python3
"""
reset.py — Clear wicked-garden local state for a fresh start.

Usage:
    python3 scripts/reset.py --json                          # scan what exists
    python3 scripts/reset.py --confirm --all --json          # clear everything
    python3 scripts/reset.py --confirm --only smaht crew --json  # clear specific domains
    python3 scripts/reset.py --confirm --all --keep mem --json   # clear all except memories

Outputs JSON with domains found, sizes, and actions taken.
Always stdlib-only (runs from hook/command context).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

_WICKED_ROOT = Path.home() / ".something-wicked"
_WG_ROOT = _WICKED_ROOT / "wicked-garden"
_LOCAL_ROOT = _WG_ROOT / "local"

# All known domain state locations
_DOMAINS = {
    "config": {
        "description": "Setup configuration",
        "paths": [_WG_ROOT / "config.json"],
    },
    "smaht": {
        "description": "Session history and context cache",
        "paths": [_LOCAL_ROOT / "wicked-smaht"],
    },
    "crew": {
        "description": "Crew project data",
        "paths": [_LOCAL_ROOT / "wicked-crew"],
    },
    "kanban": {
        "description": "Kanban board and tasks",
        "paths": [_LOCAL_ROOT / "wicked-kanban"],
    },
    "mem": {
        "description": "Memory store",
        "paths": [_LOCAL_ROOT / "wicked-mem"],
    },
    "search": {
        "description": "Search index (SQLite)",
        "paths": [_LOCAL_ROOT / "wicked-search"],
    },
    "delivery": {
        "description": "Delivery metrics and config",
        "paths": [_LOCAL_ROOT / "wicked-delivery"],
    },
    "jam": {
        "description": "Brainstorm session history",
        "paths": [_LOCAL_ROOT / "wicked-jam"],
    },
}


def _dir_size(path: Path) -> int:
    """Total size in bytes of a file or directory tree."""
    if path.is_file():
        return path.stat().st_size
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _scan():
    """Scan for existing state. Returns list of {domain, description, paths, size_bytes, exists}."""
    results = []
    for domain, info in _DOMAINS.items():
        existing = [p for p in info["paths"] if p.exists()]
        size = sum(_dir_size(p) for p in existing)
        results.append({
            "domain": domain,
            "description": info["description"],
            "paths": [str(p) for p in info["paths"]],
            "exists": len(existing) > 0,
            "size_bytes": size,
        })
    return results


def _clear(targets: list[str]) -> dict:
    """Clear specified domains. Returns summary."""
    cleared = []
    skipped = []
    errors = []

    for domain, info in _DOMAINS.items():
        if domain not in targets:
            skipped.append(domain)
            continue
        for path in info["paths"]:
            if not path.exists():
                continue
            try:
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                cleared.append(domain)
            except Exception as e:
                errors.append({"domain": domain, "path": str(path), "error": str(e)})

    return {"cleared": cleared, "skipped": skipped, "errors": errors}


def _resolve_targets(only: list[str], keep: list[str], clear_all: bool) -> list[str]:
    """Resolve which domains to clear based on flags."""
    all_domains = list(_DOMAINS.keys())
    if only:
        return [d for d in only if d in all_domains]
    if clear_all:
        return [d for d in all_domains if d not in keep]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (without this, dry-run only)")
    parser.add_argument("--only", nargs="*", default=[], help="Specific domains to clear (e.g., --only smaht crew)")
    parser.add_argument("--keep", nargs="*", default=[], help="Domains to preserve when using --all (e.g., --keep mem)")
    parser.add_argument("--all", dest="clear_all", action="store_true", help="Clear all domains (use --keep to exclude)")
    args = parser.parse_args()

    scan = _scan()
    found = [s for s in scan if s["exists"]]
    targets = _resolve_targets(args.only, args.keep, args.clear_all)

    if not args.confirm:
        output = {
            "mode": "dry_run",
            "domains": scan,
            "found_count": len(found),
            "total_size_bytes": sum(s["size_bytes"] for s in found),
            "targets": targets,
            "would_clear": [d for d in targets if any(s["exists"] for s in scan if s["domain"] == d)],
            "would_keep": [s["domain"] for s in scan if s["domain"] not in targets],
        }
    else:
        if not targets:
            output = {"mode": "cleared", "cleared": [], "skipped": list(_DOMAINS.keys()), "errors": [],
                       "message": "No domains specified. Use --only or --all."}
        else:
            result = _clear(targets)
            output = {"mode": "cleared", **result}

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        if not args.confirm:
            print(f"Scan: {len(found)} domain(s) with state found")
            for s in found:
                tag = " [CLEAR]" if s["domain"] in targets else ""
                print(f"  {s['domain']}: {s['description']} ({s['size_bytes']} bytes){tag}")
            if targets:
                print(f"\nWould clear: {', '.join(targets)}")
            print("\nRun with --confirm to clear.")
        else:
            if not targets:
                print("No domains specified. Use --only or --all.")
            else:
                print(f"Cleared: {', '.join(result['cleared']) or 'nothing'}")
                if result["skipped"]:
                    print(f"Kept: {', '.join(result['skipped'])}")
                if result["errors"]:
                    for e in result["errors"]:
                        print(f"Error: {e['domain']} — {e['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
