#!/usr/bin/env python3
"""
wicked-crew query CLI — exposes project data for cross-plugin access.

Usage:
    crew.py list-projects [--active] [--json]
    crew.py get-project <name> [--json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager, get_local_path

_sm = StorageManager("wicked-crew")


def list_projects(active_only: bool = False) -> dict:
    """List crew projects, optionally filtered to active ones."""
    projects = _sm.list("projects")

    if active_only:
        projects = [
            p for p in projects
            if p.get("status", "").lower() in ("active", "in_progress")
        ]

    return {"projects": projects}


def get_project(name: str) -> dict:
    """Get a specific project by name."""
    data = _sm.get("projects", name)
    if not data:
        return {"error": f"Project not found: {name}"}

    # Include outcome summary if available (local markdown file)
    projects_dir = get_local_path("wicked-crew", "projects")
    outcome_md = projects_dir / name / "outcome.md"
    if outcome_md.exists():
        try:
            content = outcome_md.read_text()
            if "## Desired Outcome" in content:
                after = content.split("## Desired Outcome")[1]
                paragraphs = after.strip().split("\n\n")
                if paragraphs:
                    data["outcome_summary"] = paragraphs[0].strip()[:300]
        except OSError:
            pass

    return {"project": data}


def main():
    parser = argparse.ArgumentParser(description="wicked-crew query CLI")
    subparsers = parser.add_subparsers(dest="command")

    ls_parser = subparsers.add_parser("list-projects", help="List crew projects")
    ls_parser.add_argument("--active", action="store_true", help="Only active projects")
    ls_parser.add_argument("--json", action="store_true", help="Output as JSON")

    get_parser = subparsers.add_parser("get-project", help="Get a specific project")
    get_parser.add_argument("name", help="Project name")
    get_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list-projects":
        result = list_projects(active_only=args.active)
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            for p in result["projects"]:
                status = "active" if p.get("status") in ("active", "in_progress") else p.get("status", "?")
                print(f"  {p['name']}: {p['current_phase']} phase [{status}]")

    elif args.command == "get-project":
        result = get_project(args.name)
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                print(result["error"])
            else:
                p = result["project"]
                print(f"Project: {p['name']}")
                print(f"Phase: {p['current_phase']}")
                print(f"Status: {p.get('status', '?')}")
                if p.get("outcome_summary"):
                    print(f"Outcome: {p['outcome_summary']}")


if __name__ == "__main__":
    main()
