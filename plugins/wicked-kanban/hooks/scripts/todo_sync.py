#!/usr/bin/env python3
"""
PostToolUse hook: Sync TaskCreate/TaskUpdate/TaskList and TodoWrite to kanban.

Makes wicked-kanban the source of truth for all task management.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, str(Path(PLUGIN_ROOT) / 'scripts'))

try:
    from kanban import get_store, get_utc_timestamp
except ImportError:
    print(json.dumps({"continue": True}))
    sys.exit(0)

# Configuration
DATA_DIR = Path(os.environ.get('WICKED_KANBAN_DATA_DIR',
                               Path.home() / '.something-wicked' / 'wicked-kanban'))
SYNC_STATE_FILE = DATA_DIR / 'sync_state.json'

# Status mapping
STATUS_TO_SWIMLANE = {
    "pending": "todo",
    "in_progress": "in_progress",
    "completed": "done"
}

SWIMLANE_TO_STATUS = {v: k for k, v in STATUS_TO_SWIMLANE.items()}

# Priority inference
PRIORITY_KEYWORDS = {
    "P0": ["critical", "urgent", "blocker", "hotfix", "security"],
    "P1": ["fix", "bug", "error", "broken", "failing", "important"],
    "P2": [],
    "P3": ["refactor", "cleanup", "nice to have", "polish", "minor"]
}


def load_sync_state() -> dict:
    """Load sync state mapping Claude task IDs to kanban task IDs."""
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"project_id": None, "task_map": {}, "initiative_id": None, "initiative_map": {}}


def save_sync_state(state: dict):
    """Save sync state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))


def get_session_id() -> str:
    """Get current session ID."""
    session_id = os.environ.get('CLAUDE_SESSION_ID', '')
    if not session_id:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        session_id = f"daily-{date_str}"
    return session_id


def get_repo_path() -> str:
    """Get current repository path."""
    return os.environ.get('PWD', os.getcwd())


def infer_priority(content: str) -> str:
    """Infer priority from task content."""
    content_lower = content.lower()
    for priority, keywords in PRIORITY_KEYWORDS.items():
        if any(kw in content_lower for kw in keywords):
            return priority
    return "P2"


def parse_crew_initiative(subject: str) -> str | None:
    """Extract crew project name from task subject convention.

    Crew tasks follow: "Phase: project-name - description"
    e.g. "Clarify: fix-kanban-board-isolation - Define outcome"
    Returns the project name or None if subject doesn't match.
    """
    match = re.match(r'^[A-Za-z-]+:\s+([a-zA-Z0-9][a-zA-Z0-9_-]*)\s+-\s+', subject)
    if match:
        return match.group(1)
    return None


def resolve_task_map_entry(entry) -> tuple[str | None, str | None]:
    """Extract kanban_id and initiative_id from a task_map entry.

    Handles both old format (string) and new enriched format (dict).
    """
    if isinstance(entry, dict):
        return entry.get("kanban_id"), entry.get("initiative_id")
    if isinstance(entry, str):
        return entry, None
    return None, None


def migrate_task_map(state: dict):
    """Inline migration: convert old flat task_map entries to enriched format.

    Old: {"subject": "kanban_task_id"}
    New: {"subject": {"kanban_id": "kanban_task_id", "initiative_id": "init_id"}}

    Entries without a known initiative_id get None (backfilled on next update).
    """
    task_map = state.get("task_map", {})
    migrated = False
    for key, value in task_map.items():
        if isinstance(value, str):
            task_map[key] = {"kanban_id": value, "initiative_id": None}
            migrated = True
    if migrated:
        state["task_map"] = task_map


def get_or_create_project(store, state: dict) -> str:
    """Get or create the kanban project for current repo."""
    repo_path = get_repo_path()

    # Check if repo already mapped to a project
    existing_project_id = store.get_project_for_repo(repo_path)
    if existing_project_id:
        project = store.get_project(existing_project_id)
        if project:
            state["project_id"] = existing_project_id
            return existing_project_id

    # Check if we have a project in sync state
    if state.get("project_id"):
        project = store.get_project(state["project_id"])
        if project:
            return state["project_id"]

    # Create new project
    repo_name = Path(repo_path).name or "Claude Tasks"
    project = store.create_project(
        name=f"{repo_name} Tasks",
        description=f"Tasks for {repo_path}",
        repo_path=repo_path
    )

    if project:
        project_id = project["id"]
        state["project_id"] = project_id
        store.set_project_for_repo(repo_path, project_id)
        return project_id

    return None


def get_or_create_initiative(store, project_id: str, state: dict,
                             initiative_name: str = None) -> str:
    """Get or create initiative by name.

    Routes tasks to named initiatives:
    - If initiative_name provided (from task metadata): use/create that initiative
    - Otherwise: use/create the default "Issues" initiative

    Every repo gets two default kinds of initiatives:
    1. "Issues" - general fixes, small tasks, non-crew work
    2. One per crew project - named after the project
    """
    target_name = initiative_name or "Issues"

    # Check cache: initiative_map stores name -> id
    initiative_map = state.get("initiative_map", {})
    cached_id = initiative_map.get(target_name)
    if cached_id:
        initiative = store.get_initiative(project_id, cached_id)
        if initiative:
            return cached_id

    # Search existing initiatives by name
    try:
        initiatives = store.list_initiatives(project_id) or []
        for init in initiatives:
            if init.get("name") == target_name:
                initiative_map[target_name] = init["id"]
                state["initiative_map"] = initiative_map
                return init["id"]
    except Exception:
        pass

    # Create new initiative
    if target_name == "Issues":
        goal = "General fixes, bugs, and non-project tasks"
    else:
        goal = f"Crew project: {target_name}"

    initiative = store.create_initiative(
        project_id,
        name=target_name,
        goal=goal
    )

    if initiative:
        initiative_map[target_name] = initiative["id"]
        state["initiative_map"] = initiative_map
        return initiative["id"]

    return None


def sync_task_create(store, project_id: str, initiative_id: str,
                     tool_input: dict, state: dict) -> dict:
    """Handle TaskCreate: create in kanban, return mapping."""
    subject = tool_input.get("subject", "")
    description = tool_input.get("description", "")
    active_form = tool_input.get("activeForm", "")
    metadata = tool_input.get("metadata", {}) or {}

    # Create in kanban with all available fields
    task = store.create_task(
        project_id,
        name=subject,
        swimlane="todo",
        priority=metadata.get("priority") or infer_priority(subject + " " + description),
        description=description or active_form,
        initiative_id=initiative_id,
        assigned_to=metadata.get("assigned_to"),
        metadata={
            "source": "TaskCreate",
            "session_id": get_session_id(),
            **{k: v for k, v in metadata.items() if k not in ("priority", "assigned_to")}
        }
    )

    if task:
        # Store enriched mapping with initiative context
        state.setdefault("task_map", {})[subject] = {
            "kanban_id": task["id"],
            "initiative_id": initiative_id
        }

        # Set as active task with correct initiative
        store.set_active_context(
            project_id=project_id,
            active_task_id=task["id"],
            initiative_id=initiative_id
        )

        return {"kanban_task_id": task["id"], "status": "created"}

    return {"status": "failed"}


def sync_task_update(store, project_id: str, tool_input: dict, state: dict) -> dict:
    """Handle TaskUpdate: update kanban task with all fields."""
    task_id = tool_input.get("taskId", "")
    status = tool_input.get("status")
    subject = tool_input.get("subject")
    description = tool_input.get("description")
    owner = tool_input.get("owner")
    add_blocked_by = tool_input.get("addBlockedBy", [])
    add_blocks = tool_input.get("addBlocks", [])
    metadata = tool_input.get("metadata")

    # Find kanban task ID and initiative from enriched mapping
    kanban_task_id = None
    task_initiative_id = None
    task_map = state.get("task_map", {})

    # Try direct mapping by Claude task ID
    entry = task_map.get(task_id)
    if entry:
        kanban_task_id, task_initiative_id = resolve_task_map_entry(entry)

    # Try by subject if we stored it that way
    if not kanban_task_id and subject:
        entry = task_map.get(subject)
        if entry:
            kanban_task_id, task_initiative_id = resolve_task_map_entry(entry)

    if not kanban_task_id:
        # Try to find by searching
        results = store.search(subject or task_id, project_id)
        if results:
            kanban_task_id = results[0]["task_id"]

    if not kanban_task_id:
        return {"status": "not_found"}

    updates = {}

    if status:
        new_swimlane = STATUS_TO_SWIMLANE.get(status)
        if new_swimlane:
            updates["swimlane"] = new_swimlane

    if subject:
        updates["name"] = subject

    if description:
        updates["description"] = description

    if owner:
        updates["assigned_to"] = owner

    # Sync dependency relationships
    if add_blocked_by or add_blocks:
        kanban_task = store.get_task(project_id, kanban_task_id)
        if kanban_task:
            current_deps = set(kanban_task.get("depends_on", []))

            # addBlockedBy = tasks that must complete before this one
            for blocker_id in add_blocked_by:
                blocker_kanban_id, _ = resolve_task_map_entry(task_map.get(blocker_id))
                if blocker_kanban_id:
                    current_deps.add(blocker_kanban_id)

            # addBlocks = tasks that depend on this one (reverse: add this task as dep on them)
            for blocked_id in add_blocks:
                blocked_kanban_id, _ = resolve_task_map_entry(task_map.get(blocked_id))
                if blocked_kanban_id:
                    blocked_task = store.get_task(project_id, blocked_kanban_id)
                    if blocked_task:
                        blocked_deps = set(blocked_task.get("depends_on", []))
                        blocked_deps.add(kanban_task_id)
                        store.update_task(project_id, blocked_kanban_id,
                                          depends_on=list(blocked_deps))

            updates["depends_on"] = list(current_deps)

    if metadata:
        updates["metadata"] = metadata

        # Process lifecycle extension fields from metadata
        if "comment" in metadata and isinstance(metadata["comment"], str):
            store.add_comment(project_id, kanban_task_id, metadata["comment"])

        if "artifacts" in metadata and isinstance(metadata["artifacts"], list):
            # Dedupe: check existing artifacts by path before adding
            kanban_task_for_artifacts = store.get_task(project_id, kanban_task_id)
            existing_paths = set()
            if kanban_task_for_artifacts:
                existing_paths = {
                    a.get("path", "") for a in kanban_task_for_artifacts.get("artifacts", [])
                }
            for artifact_path in metadata["artifacts"]:
                if isinstance(artifact_path, str) and artifact_path and artifact_path not in existing_paths:
                    existing_paths.add(artifact_path)
                    name = Path(artifact_path).name
                    store.add_artifact(project_id, kanban_task_id,
                                       name=name, artifact_type="file",
                                       path=artifact_path)

        if "priority" in metadata:
            updates["priority"] = metadata["priority"]

        if "assigned_to" in metadata:
            updates["assigned_to"] = metadata["assigned_to"]

        if "outcome" in metadata:
            # Determine the base description: prefer explicit description param, else fetch current
            base_desc = description if description else None
            if base_desc is None:
                kanban_task_for_outcome = store.get_task(project_id, kanban_task_id)
                base_desc = (kanban_task_for_outcome.get("description", "") or "") if kanban_task_for_outcome else ""
            else:
                base_desc = base_desc or ""
            if "## Outcome" not in base_desc:
                updates["description"] = base_desc + f"\n\n## Outcome\n{metadata['outcome']}"

    # Build a meaningful comment instead of just "Status changed to: X"
    comment_parts = []
    if status:
        comment_parts.append(f"Status → {status}")
    if owner:
        comment_parts.append(f"Assigned to {owner}")
    if add_blocked_by:
        comment_parts.append(f"Blocked by {len(add_blocked_by)} task(s)")
    if add_blocks:
        comment_parts.append(f"Blocks {len(add_blocks)} task(s)")

    if comment_parts:
        store.add_comment(project_id, kanban_task_id, " | ".join(comment_parts))

    if updates:
        task = store.update_task(project_id, kanban_task_id, **updates)
        if task:
            # Update active context — preserve the task's original initiative
            if status == "in_progress":
                ctx = {"active_task_id": kanban_task_id}
                if task_initiative_id:
                    ctx["initiative_id"] = task_initiative_id
                store.set_active_context(**ctx)
            elif status == "completed":
                store.set_active_context(active_task_id=None)

            return {"kanban_task_id": kanban_task_id, "status": "updated"}

    return {"status": "no_changes"}


def sync_todo_write(store, project_id: str, initiative_id: str,
                    tool_input: dict, state: dict) -> dict:
    """Handle legacy TodoWrite: sync all todos."""
    todos = tool_input.get("todos", [])
    synced = 0

    for todo in todos:
        content = todo.get("content", "")
        if not content:
            continue

        status = todo.get("status", "pending")
        swimlane = STATUS_TO_SWIMLANE.get(status, "todo")

        # Check if already exists
        task_map = state.get("task_map", {})
        existing_kanban_id, _ = resolve_task_map_entry(task_map.get(content))

        if existing_kanban_id:
            # Update existing
            store.update_task(project_id, existing_kanban_id, swimlane=swimlane)
        else:
            # Create new
            task = store.create_task(
                project_id,
                name=content,
                swimlane=swimlane,
                priority=infer_priority(content),
                description=todo.get("activeForm"),
                initiative_id=initiative_id,
                metadata={"source": "TodoWrite"}
            )
            if task:
                state.setdefault("task_map", {})[content] = {
                    "kanban_id": task["id"],
                    "initiative_id": initiative_id
                }

        synced += 1

    return {"synced": synced}


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only process task-related tools
    if tool_name not in ["TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TodoWrite"]:
        print(json.dumps({"continue": True}))
        sys.exit(0)

    store = get_store()
    state = load_sync_state()

    # Inline migration: convert old flat task_map entries to enriched format
    migrate_task_map(state)

    # Get or create project
    project_id = get_or_create_project(store, state)
    if not project_id:
        print(json.dumps({"continue": True}))
        sys.exit(0)

    # Get or create initiative — route by task metadata, then crew subject, then "Issues"
    initiative_name = None
    if tool_name in ("TaskCreate", "TodoWrite"):
        metadata = tool_input.get("metadata", {}) or {}
        initiative_name = metadata.get("initiative")
        # Fallback: parse crew project name from task subject convention
        if not initiative_name and tool_name == "TaskCreate":
            subject = tool_input.get("subject", "")
            initiative_name = parse_crew_initiative(subject)
    initiative_id = get_or_create_initiative(store, project_id, state,
                                             initiative_name=initiative_name)

    result = {"continue": True}

    if tool_name == "TaskCreate":
        sync_result = sync_task_create(store, project_id, initiative_id, tool_input, state)
        result["kanban"] = sync_result

        # Prompt Claude to enrich the task with context it already has
        enrichment_hints = []
        if not tool_input.get("description"):
            enrichment_hints.append("- Add a description: WHY does this task exist? What problem does it solve?")
        if not tool_input.get("metadata", {}).get("priority"):
            enrichment_hints.append("- Set priority via metadata: {\"priority\": \"P0\"} (critical) through P3 (minor)")

        if enrichment_hints:
            result["systemMessage"] = (
                "[Kanban] Task synced. Consider enriching it:\n"
                + "\n".join(enrichment_hints)
                + "\n- Use addBlockedBy/addBlocks if this task has dependencies"
                + "\n- When completing, update description with what was decided or learned"
            )

    elif tool_name == "TaskUpdate":
        sync_result = sync_task_update(store, project_id, tool_input, state)
        result["kanban"] = sync_result

    elif tool_name == "TodoWrite":
        sync_result = sync_todo_write(store, project_id, initiative_id, tool_input, state)
        result["kanban"] = sync_result

    # TaskList and TaskGet just pass through - kanban is updated, native tools still work

    save_sync_state(state)
    print(json.dumps(result))
    sys.exit(0)


if __name__ == '__main__':
    main()
