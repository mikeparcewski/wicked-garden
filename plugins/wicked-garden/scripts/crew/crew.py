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


def get_projects_dir() -> Path:
    """Get the projects storage directory."""
    return Path.home() / ".something-wicked" / "wicked-crew" / "projects"


def list_projects(active_only: bool = False) -> dict:
    """List crew projects, optionally filtered to active ones."""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return {"projects": []}

    results = []

    for project_dir in sorted(
        projects_dir.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        if not project_dir.is_dir():
            continue

        project_data = _load_project(project_dir)
        if not project_data:
            continue

        if active_only:
            status = project_data.get("status", "").lower()
            if status not in ("active", "in_progress"):
                continue

        results.append(project_data)

    return {"projects": results}


def get_project(name: str) -> dict:
    """Get a specific project by name."""
    projects_dir = get_projects_dir()
    project_dir = projects_dir / name

    if not project_dir.exists():
        return {"error": f"Project not found: {name}"}

    data = _load_project(project_dir)
    if not data:
        return {"error": f"Could not read project: {name}"}

    # Include outcome summary if available
    outcome_md = project_dir / "outcome.md"
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


def _load_project(project_dir: Path) -> dict:
    """Load project data from project.json or project.md."""
    # Try project.json first
    project_json = project_dir / "project.json"
    if project_json.exists():
        try:
            with open(project_json) as f:
                data = json.load(f)
            return {
                "name": data.get("name", project_dir.name),
                "current_phase": data.get("current_phase", "unknown"),
                "status": data.get("status", "unknown"),
                "complexity_score": data.get("complexity_score", 0),
                "signals_detected": data.get("signals_detected", []),
            }
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to project.md frontmatter
    project_md = project_dir / "project.md"
    if project_md.exists():
        try:
            content = project_md.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    data = {}
                    for line in parts[1].split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            data[key.strip()] = value.strip()
                    return {
                        "name": data.get("name", project_dir.name),
                        "current_phase": data.get("current_phase", "unknown"),
                        "status": data.get("status", "unknown"),
                        "complexity_score": 0,
                        "signals_detected": [],
                    }
        except OSError:
            pass

    return None


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
