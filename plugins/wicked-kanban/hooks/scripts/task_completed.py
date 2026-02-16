#!/usr/bin/env python3
"""
TaskCompleted hook: Move kanban task to done when Claude marks it completed.

Input: {"task_id", "task_subject", "task_description", "teammate_name", "team_name"}
Exit 0: success (stdout/stderr not shown)
Exit 2: stderr shown to model, prevents completion
Other: stderr shown to user only
"""

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, str(Path(PLUGIN_ROOT) / 'scripts'))

try:
    from kanban import get_store
except ImportError:
    sys.exit(0)

DATA_DIR = Path(os.environ.get('WICKED_KANBAN_DATA_DIR',
                               Path.home() / '.something-wicked' / 'wicked-kanban'))
SYNC_STATE_FILE = DATA_DIR / 'sync_state.json'


def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"project_id": None, "task_map": {}, "initiative_id": None}


def save_sync_state(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        sys.exit(0)

    task_id = hook_input.get("task_id", "")
    task_subject = hook_input.get("task_subject", "")

    if not task_subject:
        sys.exit(0)

    store = get_store()
    state = load_sync_state()
    project_id = state.get("project_id")

    if not project_id:
        sys.exit(0)

    # Find kanban task: try task_map by subject first, then by task_id, then search
    # Handle both old format (string) and enriched format (dict with kanban_id)
    task_map = state.get("task_map", {})

    def _resolve(entry):
        if isinstance(entry, dict):
            return entry.get("kanban_id")
        return entry

    kanban_task_id = _resolve(task_map.get(task_subject)) or _resolve(task_map.get(task_id))

    if not kanban_task_id:
        results = store.search(task_subject, project_id)
        if results:
            kanban_task_id = results[0]["task_id"]

    if not kanban_task_id:
        sys.exit(0)

    # Move to done
    task = store.update_task(project_id, kanban_task_id, swimlane="done")
    if task:
        store.add_comment(project_id, kanban_task_id, "Completed via TaskCompleted hook")
        store.set_active_context(active_task_id=None)

        # Update task_map with task_id if we only had subject mapping
        if task_id and task_id not in task_map:
            state["task_map"][task_id] = {"kanban_id": kanban_task_id, "initiative_id": None}
            save_sync_state(state)

    sys.exit(0)


if __name__ == '__main__':
    main()
