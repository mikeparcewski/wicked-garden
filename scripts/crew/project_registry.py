#!/usr/bin/env python3
"""
project_registry.py -- Formalized multi-project isolation for parallel crew projects.

Provides a project registry with lifecycle management (create, archive, switch)
and the get_project_filter() abstraction that other domains use to scope their
queries to the active project.

Storage:
    - Project records: DomainStore("wicked-crew") source="projects"
      (same source as crew.py -- fully compatible)
    - Registry state:  DomainStore("wicked-crew") source="registry-state"
      (active project tracking per workspace)

Usage as library:
    from project_registry import create_project, get_project_filter

    project = create_project("auth-rewrite")
    pf = get_project_filter()  # uses active project
    memories = mem_store.list("memories", **pf)

Usage as CLI:
    project_registry.py create --name "auth-rewrite" [--workspace W] [--directory /path]
    project_registry.py list [--workspace W] [--active]
    project_registry.py get --id X
    project_registry.py find --name "auth-rewrite" [--workspace W]
    project_registry.py set-active --id X
    project_registry.py get-active [--workspace W]
    project_registry.py archive --id X
    project_registry.py unarchive --id X
    project_registry.py switch --id X
    project_registry.py filter [--id X]

All commands support --json for JSON output (default for filter).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Import DomainStore from the parent scripts/ directory
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _domain_store import DomainStore

# ---------------------------------------------------------------------------
# Module-level store instances
# ---------------------------------------------------------------------------

_store = DomainStore("wicked-crew")
_PROJECTS_SOURCE = "projects"
_STATE_SOURCE = "registry-state"

# State record ID is keyed by workspace to allow per-workspace active tracking
_STATE_PREFIX = "active-"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _default_workspace() -> str:
    """Resolve the default workspace name.

    Priority: CLAUDE_PROJECT_NAME env var > current directory name.
    """
    return os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name


def _state_id(workspace: str) -> str:
    """Derive a deterministic state record ID for a workspace."""
    # Sanitize workspace to a filesystem-safe slug
    safe = workspace.replace(os.sep, "-").replace("/", "-").replace("\\", "-")
    return _STATE_PREFIX + safe


# ---------------------------------------------------------------------------
# API Functions
# ---------------------------------------------------------------------------


def create_project(
    name: str,
    workspace: Optional[str] = None,
    directory: Optional[str] = None,
) -> dict:
    """Create a new project record and return it.

    Args:
        name:      Human-readable project name (e.g. "auth-rewrite").
        workspace: Workspace scope. Defaults to CLAUDE_PROJECT_NAME or cwd name.
        directory: Absolute path to the project directory. Defaults to cwd.

    Returns:
        The created project record dict.
    """
    workspace = workspace or _default_workspace()
    directory = directory or str(Path.cwd())

    record = {
        "id": str(uuid.uuid4()),
        "name": name,
        "workspace": workspace,
        "directory": directory,
        "phase": "",
        "status": "active",
        "created_at": _now(),
        "updated_at": _now(),
    }

    result = _store.create(_PROJECTS_SOURCE, record)
    if result is None:
        # Defensive: create should always return a dict, but handle None
        return record
    return result


def list_projects(
    workspace: Optional[str] = None,
    active_only: bool = False,
) -> List[dict]:
    """List projects with optional filters.

    Args:
        workspace:   Filter to this workspace. None = all workspaces.
        active_only: If True, exclude archived projects.

    Returns:
        List of project record dicts.
    """
    projects = _store.list(_PROJECTS_SOURCE)

    if workspace:
        projects = [p for p in projects if p.get("workspace") == workspace]

    if active_only:
        projects = [p for p in projects if p.get("status") != "archived"]

    # Sort by updated_at descending (most recent first)
    projects.sort(
        key=lambda p: p.get("updated_at", p.get("created_at", "")),
        reverse=True,
    )

    return projects


def get_project(project_id: str) -> Optional[dict]:
    """Get a project by its ID.

    Args:
        project_id: The UUID of the project.

    Returns:
        Project record dict, or None if not found.
    """
    return _store.get(_PROJECTS_SOURCE, project_id)


def find_by_name(
    name: str,
    workspace: Optional[str] = None,
) -> Optional[dict]:
    """Find a project by name, optionally scoped to a workspace.

    If multiple projects share the same name, returns the most recently
    updated one.

    Args:
        name:      Project name to search for.
        workspace: Optional workspace filter.

    Returns:
        Project record dict, or None if not found.
    """
    projects = _store.list(_PROJECTS_SOURCE)

    matches = [p for p in projects if p.get("name") == name]

    if workspace:
        matches = [p for p in matches if p.get("workspace") == workspace]

    if not matches:
        return None

    # Return most recently updated
    matches.sort(
        key=lambda p: p.get("updated_at", p.get("created_at", "")),
        reverse=True,
    )
    return matches[0]


def set_active(project_id: str) -> Optional[dict]:
    """Set a project as the active project for its workspace.

    Args:
        project_id: The UUID of the project to activate.

    Returns:
        The project record, or None if the project was not found.
    """
    project = get_project(project_id)
    if project is None:
        return None

    workspace = project.get("workspace", _default_workspace())
    sid = _state_id(workspace)

    # Check if state record already exists
    existing = _store.get(_STATE_SOURCE, sid)
    if existing:
        _store.update(_STATE_SOURCE, sid, {
            "active_project_id": project_id,
            "workspace": workspace,
        })
    else:
        _store.create(_STATE_SOURCE, {
            "id": sid,
            "active_project_id": project_id,
            "workspace": workspace,
        })

    return project


def get_active(workspace: Optional[str] = None) -> Optional[dict]:
    """Get the current active project for a workspace.

    Args:
        workspace: Workspace to check. Defaults to current workspace.

    Returns:
        Active project record dict, or None if no active project.
    """
    workspace = workspace or _default_workspace()
    sid = _state_id(workspace)

    state = _store.get(_STATE_SOURCE, sid)
    if not state:
        return None

    active_id = state.get("active_project_id")
    if not active_id:
        return None

    project = get_project(active_id)
    # Only return if the project is not archived
    if project and project.get("status") != "archived":
        return project

    return None


def archive_project(project_id: str) -> Optional[dict]:
    """Mark a project as archived.

    Args:
        project_id: The UUID of the project to archive.

    Returns:
        Updated project record, or None if not found.
    """
    project = get_project(project_id)
    if project is None:
        return None

    result = _store.update(_PROJECTS_SOURCE, project_id, {
        "status": "archived",
    })

    # If this was the active project, clear it
    workspace = project.get("workspace", _default_workspace())
    active = get_active(workspace)
    if active and active.get("id") == project_id:
        sid = _state_id(workspace)
        _store.update(_STATE_SOURCE, sid, {"active_project_id": ""})

    return result


def unarchive_project(project_id: str) -> Optional[dict]:
    """Restore a project from archived status.

    Args:
        project_id: The UUID of the project to unarchive.

    Returns:
        Updated project record, or None if not found.
    """
    project = get_project(project_id)
    if project is None:
        return None

    return _store.update(_PROJECTS_SOURCE, project_id, {
        "status": "active",
    })


def switch_project(project_id: str) -> Optional[dict]:
    """Set a project as active and return its data.

    Convenience function combining set_active + get_project.

    Args:
        project_id: The UUID of the project to switch to.

    Returns:
        The project record, or None if not found.
    """
    return set_active(project_id)


def get_project_filter(project_id: Optional[str] = None) -> Dict[str, str]:
    """Return a filter dict for scoping domain queries to a project.

    This is the primary integration point for cross-domain isolation.
    Other domains import this function and spread the result into their
    query parameters:

        from project_registry import get_project_filter
        pf = get_project_filter()  # uses active project
        memories = mem_store.list("memories", **pf)

    When no project is active (or project_id is not provided and there
    is no active project), returns an empty dict -- maintaining full
    backward compatibility with unscoped queries.

    Args:
        project_id: Explicit project ID. If None, uses the active project.

    Returns:
        {"project_id": "<uuid>"} or {} if no project context.
    """
    if not project_id:
        active = get_active()
        project_id = active["id"] if active else None

    if not project_id:
        return {}

    return {"project_id": project_id}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="wicked-crew project registry -- multi-project isolation",
    )
    subparsers = parser.add_subparsers(dest="command")

    # create
    p = subparsers.add_parser("create", help="Create a new project")
    p.add_argument("--name", required=True, help="Project name")
    p.add_argument("--workspace", default=None, help="Workspace name")
    p.add_argument("--directory", default=None, help="Project directory path")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # list
    p = subparsers.add_parser("list", help="List projects")
    p.add_argument("--workspace", default=None, help="Filter by workspace")
    p.add_argument("--active", action="store_true", help="Active projects only")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # get
    p = subparsers.add_parser("get", help="Get a project by ID")
    p.add_argument("--id", required=True, dest="project_id", help="Project ID")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # find
    p = subparsers.add_parser("find", help="Find a project by name")
    p.add_argument("--name", required=True, help="Project name")
    p.add_argument("--workspace", default=None, help="Filter by workspace")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # set-active
    p = subparsers.add_parser("set-active", help="Set a project as active")
    p.add_argument("--id", required=True, dest="project_id", help="Project ID")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # get-active
    p = subparsers.add_parser("get-active", help="Get the active project")
    p.add_argument("--workspace", default=None, help="Workspace name")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # archive
    p = subparsers.add_parser("archive", help="Archive a project")
    p.add_argument("--id", required=True, dest="project_id", help="Project ID")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # unarchive
    p = subparsers.add_parser("unarchive", help="Unarchive a project")
    p.add_argument("--id", required=True, dest="project_id", help="Project ID")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # switch
    p = subparsers.add_parser("switch", help="Switch to a project (set active + return data)")
    p.add_argument("--id", required=True, dest="project_id", help="Project ID")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # filter
    p = subparsers.add_parser("filter", help="Output project filter JSON for piping")
    p.add_argument("--id", default=None, dest="project_id", help="Project ID (default: active)")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output (always JSON)")

    return parser


def _output(data: Any, as_json: bool = False, label: str = "") -> None:
    """Print output in human-readable or JSON format."""
    if as_json:
        print(json.dumps(data, indent=2))
        return

    if data is None:
        print("Not found.")
        return

    if isinstance(data, list):
        if not data:
            print("No projects found.")
            return
        for p in data:
            status = p.get("status", "?")
            phase = p.get("phase", "") or "-"
            print(
                "  {name} [{status}] phase={phase} workspace={workspace}".format(
                    name=p.get("name", p.get("id", "?")),
                    status=status,
                    phase=phase,
                    workspace=p.get("workspace", "?"),
                )
            )
        return

    if isinstance(data, dict):
        if label:
            print(label)
        # Project record
        if "name" in data:
            print("  ID:        {id}".format(id=data.get("id", "?")))
            print("  Name:      {name}".format(name=data.get("name", "?")))
            print("  Workspace: {ws}".format(ws=data.get("workspace", "?")))
            print("  Status:    {s}".format(s=data.get("status", "?")))
            print("  Phase:     {p}".format(p=data.get("phase", "") or "-"))
            print("  Directory: {d}".format(d=data.get("directory", "?")))
            print("  Created:   {c}".format(c=data.get("created_at", "?")))
            print("  Updated:   {u}".format(u=data.get("updated_at", "?")))
        # Filter dict
        elif "project_id" in data:
            print("  project_id: {pid}".format(pid=data["project_id"]))
        elif not data:
            print("  (no project filter -- all projects)")
        else:
            print(json.dumps(data, indent=2))
        return

    print(str(data))


def main() -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    as_json = getattr(args, "as_json", False)

    if args.command == "create":
        result = create_project(
            name=args.name,
            workspace=args.workspace,
            directory=args.directory,
        )
        _output(result, as_json, label="Created project:")

    elif args.command == "list":
        result = list_projects(
            workspace=args.workspace,
            active_only=args.active,
        )
        _output(result, as_json)

    elif args.command == "get":
        result = get_project(args.project_id)
        _output(result, as_json)

    elif args.command == "find":
        result = find_by_name(
            name=args.name,
            workspace=args.workspace,
        )
        _output(result, as_json)

    elif args.command == "set-active":
        result = set_active(args.project_id)
        if result:
            _output(result, as_json, label="Active project set:")
        else:
            _output(None, as_json)

    elif args.command == "get-active":
        result = get_active(workspace=args.workspace)
        if result:
            _output(result, as_json, label="Active project:")
        else:
            if as_json:
                print(json.dumps(None))
            else:
                print("No active project for this workspace.")

    elif args.command == "archive":
        result = archive_project(args.project_id)
        if result:
            _output(result, as_json, label="Archived project:")
        else:
            _output(None, as_json)

    elif args.command == "unarchive":
        result = unarchive_project(args.project_id)
        if result:
            _output(result, as_json, label="Unarchived project:")
        else:
            _output(None, as_json)

    elif args.command == "switch":
        result = switch_project(args.project_id)
        if result:
            _output(result, as_json, label="Switched to project:")
        else:
            _output(None, as_json)

    elif args.command == "filter":
        # Filter is always useful as JSON, but respect the flag
        result = get_project_filter(project_id=args.project_id)
        if args.command == "filter":
            # Default to JSON for filter command
            _output(result, as_json=True)
        else:
            _output(result, as_json)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
