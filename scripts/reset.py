#!/usr/bin/env python3
"""
reset.py — Clear wicked-garden local state for a fresh start.

Project-scoped: operates on the current project's data by default.
Use --all-projects to see/clear data across all projects.

Usage:
    python3 scripts/reset.py --json                          # scan current project
    python3 scripts/reset.py --confirm --all --json          # clear everything (current project)
    python3 scripts/reset.py --confirm --only smaht crew     # clear specific domains
    python3 scripts/reset.py --confirm --all --keep mem      # clear all except memories
    python3 scripts/reset.py --list-projects --json          # list all projects
    python3 scripts/reset.py --confirm --all --all-projects  # clear ALL projects

Always stdlib-only (runs from hook/command context).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import get_project_root, get_project_slug, list_projects

_WG_ROOT = Path.home() / ".something-wicked" / "wicked-garden"

# All known domain state locations (relative to project root)
_DOMAIN_NAMES = {
    "config": "Setup configuration",
    "smaht": "Session history and context cache",
    "crew": "Crew project data",
    "kanban": "Kanban board and tasks",
    "mem": "Memory store",
    "search": "Search index (SQLite)",
    "delivery": "Delivery metrics and config",
    "jam": "Brainstorm session history",
}

# Map domain names to their directory names under the project root
_DOMAIN_DIRS = {
    "config": None,  # special: global config.json
    "smaht": "wicked-smaht",
    "crew": "wicked-crew",
    "kanban": "wicked-kanban",
    "mem": "wicked-garden:mem",
    "search": "wicked-garden:search",
    "delivery": "wicked-delivery",
    "jam": "wicked-jam",
}


def _dir_size(path: Path) -> int:
    """Total size in bytes of a file or directory tree."""
    if path.is_file():
        return path.stat().st_size
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _get_domain_path(domain: str, project_root: Path) -> Path:
    """Get the storage path for a domain within a project root."""
    if domain == "config":
        return _WG_ROOT / "config.json"
    return project_root / _DOMAIN_DIRS[domain]


def _scan(project_root: Path):
    """Scan for existing state in a project root."""
    results = []
    for domain, description in _DOMAIN_NAMES.items():
        path = _get_domain_path(domain, project_root)
        exists = path.exists()
        size = _dir_size(path) if exists else 0
        results.append({
            "domain": domain,
            "description": description,
            "paths": [str(path)],
            "exists": exists,
            "size_bytes": size,
        })
    return results


def _clear(targets: list[str], project_root: Path) -> dict:
    """Clear specified domains in a project root."""
    cleared = []
    skipped = []
    errors = []

    for domain in _DOMAIN_NAMES:
        if domain not in targets:
            skipped.append(domain)
            continue
        path = _get_domain_path(domain, project_root)
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
    all_domains = list(_DOMAIN_NAMES.keys())
    if only:
        return [d for d in only if d in all_domains]
    if clear_all:
        return [d for d in all_domains if d not in keep]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (without this, dry-run only)")
    parser.add_argument("--only", nargs="*", default=[], help="Specific domains to clear")
    parser.add_argument("--keep", nargs="*", default=[], help="Domains to preserve when using --all")
    parser.add_argument("--all", dest="clear_all", action="store_true", help="Clear all domains")
    parser.add_argument("--list-projects", action="store_true", help="List all projects with state")
    parser.add_argument("--all-projects", action="store_true", help="Operate on all projects, not just current")
    args = parser.parse_args()

    project_root = get_project_root()
    project_slug = get_project_slug()

    if args.list_projects:
        projects = list_projects()
        if args.json:
            print(json.dumps({"projects": projects, "current": project_slug}, indent=2))
        else:
            if not projects:
                print("No projects found.")
            else:
                for p in projects:
                    marker = " (current)" if p["is_current"] else ""
                    size_kb = p["size_bytes"] / 1024
                    print(f"  {p['slug']}{marker}: {len(p['domains'])} domains, {size_kb:.1f} KB")
        return

    if args.all_projects and args.confirm:
        # Clear all projects
        projects = list_projects()
        targets = _resolve_targets(args.only, args.keep, args.clear_all)
        all_results = []
        for p in projects:
            p_root = Path(p["path"])
            result = _clear(targets, p_root)
            result["project"] = p["slug"]
            all_results.append(result)
            # If all domains cleared, remove the project dir too
            if p_root.exists() and not any(p_root.iterdir()):
                p_root.rmdir()
        if args.json:
            print(json.dumps({"mode": "cleared", "projects": all_results}, indent=2))
        else:
            for r in all_results:
                print(f"{r['project']}: cleared {', '.join(r['cleared']) or 'nothing'}")
        return

    scan = _scan(project_root)
    found = [s for s in scan if s["exists"]]
    targets = _resolve_targets(args.only, args.keep, args.clear_all)

    if not args.confirm:
        output = {
            "mode": "dry_run",
            "project": project_slug,
            "project_root": str(project_root),
            "domains": scan,
            "found_count": len(found),
            "total_size_bytes": sum(s["size_bytes"] for s in found),
            "targets": targets,
            "would_clear": [d for d in targets if any(s["exists"] for s in scan if s["domain"] == d)],
            "would_keep": [s["domain"] for s in scan if s["domain"] not in targets],
        }
    else:
        if not targets:
            output = {"mode": "cleared", "project": project_slug,
                       "cleared": [], "skipped": list(_DOMAIN_NAMES.keys()), "errors": [],
                       "message": "No domains specified. Use --only or --all."}
        else:
            result = _clear(targets, project_root)
            output = {"mode": "cleared", "project": project_slug, **result}

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        if not args.confirm:
            print(f"Project: {project_slug}")
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
                print(f"Project: {project_slug}")
                print(f"Cleared: {', '.join(result['cleared']) or 'nothing'}")
                if result["skipped"]:
                    print(f"Kept: {', '.join(result['skipped'])}")
                if result["errors"]:
                    for e in result["errors"]:
                        print(f"Error: {e['domain']} — {e['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
