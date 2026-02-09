#!/usr/bin/env python3
"""Stop hook: Log session activity to kanban."""
import json
import os
import sys
from pathlib import Path

# Add scripts directory to path
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if PLUGIN_ROOT:
    sys.path.insert(0, str(Path(PLUGIN_ROOT) / "scripts"))

try:
    from kanban import get_store
except ImportError:
    sys.exit(0)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        hook_input = {}

    store = get_store()
    repo_path = os.environ.get("PWD", os.getcwd())
    project_id = store.get_project_for_repo(repo_path)

    if not project_id:
        sys.exit(0)

    # Check for in-progress tasks
    index = store._load_index(project_id)
    in_progress = index.get("by_swimlane", {}).get("in_progress", [])

    if not in_progress:
        sys.exit(0)

    print(json.dumps({
        "systemMessage": f"[Kanban] {len(in_progress)} task(s) still in progress"
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
