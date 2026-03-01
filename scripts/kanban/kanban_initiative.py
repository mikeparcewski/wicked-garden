#!/usr/bin/env python3
"""Kanban initiative helper — CLI for crew-kanban integration.

Called by wicked-crew hooks via direct import or subprocess.
Commands:
  lookup <name>       - Find initiative by crew project name
  create <name>       - Create initiative for a crew project
  ensure-issues       - Ensure "Issues" default initiative exists

All output is JSON to stdout. Exit code 0 on success, 1 on error.
"""

import json
import os
import sys
from pathlib import Path

# Add scripts root to path for shared modules, then kanban dir for local imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from _storage import StorageManager
from kanban import KanbanStore

_sm = StorageManager("wicked-kanban")


def get_store() -> KanbanStore:
    return KanbanStore()


def get_repo_path() -> str:
    return os.environ.get('PWD', os.getcwd())


def get_project_id(store: KanbanStore) -> str | None:
    """Get the kanban project ID for the current repo."""
    repo_path = get_repo_path()
    project_id = store.get_project_for_repo(repo_path)
    if project_id:
        return project_id
    return None


def cmd_lookup(name: str) -> dict:
    """Look up a crew initiative by name via StorageManager."""
    store = get_store()
    project_id = get_project_id(store)
    if not project_id:
        return {"found": False, "reason": "no_kanban_project"}

    # Query initiatives through StorageManager (CP-first, local fallback)
    try:
        initiatives = _sm.list("initiatives", project_id=project_id)
        for init in initiatives:
            if init.get("name") == name:
                return {
                    "found": True,
                    "initiative_id": init["id"],
                    "project_id": project_id,
                }
    except Exception as e:
        print(f"[kanban-initiative] lookup error: {e}", file=sys.stderr)

    return {"found": False}


def cmd_create(name: str) -> dict:
    """Create a crew initiative. Returns the initiative ID."""
    store = get_store()
    project_id = get_project_id(store)
    if not project_id:
        # Try to create a project for this repo
        repo_path = get_repo_path()
        repo_name = Path(repo_path).name or "Claude Tasks"
        project = store.create_project(
            name=f"{repo_name} Tasks",
            description=f"Tasks for {repo_path}",
            repo_path=repo_path
        )
        if not project:
            return {"error": "failed_to_create_project"}
        project_id = project["id"]
        store.set_project_for_repo(repo_path, project_id)

    # Check if already exists
    lookup = cmd_lookup(name)
    if lookup.get("found"):
        return {
            "initiative_id": lookup["initiative_id"],
            "project_id": lookup["project_id"],
            "already_existed": True,
        }

    # Create via KanbanStore (which uses StorageManager internally)
    initiative = store.create_initiative(
        project_id,
        name=name,
        goal=f"Crew project: {name}"
    )
    if not initiative:
        return {"error": "failed_to_create_initiative"}

    return {
        "initiative_id": initiative["id"],
        "project_id": project_id,
        "already_existed": False,
    }


def cmd_ensure_issues() -> dict:
    """Ensure the default 'Issues' initiative exists for this repo."""
    store = get_store()
    project_id = get_project_id(store)
    if not project_id:
        return {"status": "no_project"}

    try:
        initiatives = store.list_initiatives(project_id) or []
        for init in initiatives:
            if init.get("name") == "Issues":
                return {"status": "exists", "initiative_id": init["id"]}
    except Exception as e:
        print(f"[kanban-initiative] ensure-issues scan error: {e}", file=sys.stderr)

    initiative = store.create_initiative(
        project_id,
        name="Issues",
        goal="General fixes, bugs, and non-project tasks"
    )
    if initiative:
        return {"status": "created", "initiative_id": initiative["id"]}
    return {"status": "failed"}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: kanban_initiative.py <lookup|create|ensure-issues> [name]"}))
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "lookup":
            if len(sys.argv) < 3:
                print(json.dumps({"error": "lookup requires a name argument"}))
                sys.exit(1)
            result = cmd_lookup(sys.argv[2])
        elif command == "create":
            if len(sys.argv) < 3:
                print(json.dumps({"error": "create requires a name argument"}))
                sys.exit(1)
            result = cmd_create(sys.argv[2])
        elif command == "ensure-issues":
            result = cmd_ensure_issues()
        else:
            result = {"error": f"unknown command: {command}"}
            print(json.dumps(result))
            sys.exit(1)

        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        print(json.dumps({"error": "internal_error"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
