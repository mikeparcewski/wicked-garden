#!/usr/bin/env python3
"""SessionStart hook: Show kanban board status."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, str(Path(PLUGIN_ROOT) / 'scripts'))

try:
    from kanban import get_store
except ImportError:
    print(json.dumps({"continue": True}))
    sys.exit(0)


def get_repo_path() -> str:
    """Get current repository path."""
    return os.environ.get('PWD', os.getcwd())


def format_board_status(store, projects, current_project_id=None):
    """Format board status as multi-line project summary."""
    if not projects:
        return None  # No message if no projects

    lines = []
    lines.append(f"[Kanban] {len(projects)} Active Projects")

    # Sort by last modified (most recent first) and take top 5
    sorted_projects = sorted(
        projects,
        key=lambda p: p.get("updated_at", p.get("created_at", "")),
        reverse=True
    )[:5]

    for proj in sorted_projects:
        pid = proj["id"]
        name = proj.get("name", "Unnamed")
        is_current = pid == current_project_id

        # Get task counts by swimlane
        index = store._load_index(pid)
        by_swimlane = index.get("by_swimlane", {})

        todo = len(by_swimlane.get("todo", []))
        in_progress = len(by_swimlane.get("in_progress", []))
        done = len(by_swimlane.get("done", []))
        total = todo + in_progress + done

        marker = " *" if is_current else ""
        lines.append(f"[Kanban]   {name}{marker}: {total} tasks, {todo} todo, {in_progress} wip, {done} done")

    return "\n".join(lines)


def main():
    try:
        sys.stdin.read()  # consume input
    except IOError:
        pass

    store = get_store()
    repo_path = get_repo_path()

    # Get all projects and current project
    projects = store.list_projects()
    current_project_id = store.get_project_for_repo(repo_path)

    # Format status message
    status_msg = format_board_status(store, projects, current_project_id)

    result = {"continue": True}
    if status_msg:
        result["systemMessage"] = status_msg

    print(json.dumps(result))
    sys.exit(0)


if __name__ == '__main__':
    main()
