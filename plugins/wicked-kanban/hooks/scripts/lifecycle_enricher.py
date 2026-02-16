#!/usr/bin/env python3
"""
TaskCompleted hook: Enrich kanban tasks with outcome data from transcript.

Parses the session transcript JSONL to extract artifacts (Write/Edit),
git commits (Bash), and agent dispatches (Task) from the task's active window.
Writes enrichment to kanban store. Always exits 0 (never blocks completion).

Input: {task_id, task_subject, task_description, transcript_path, session_id, cwd}
"""

import json
import os
import re
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

# Max transcript lines to parse (from end of file)
MAX_LINES = 200


def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"project_id": None, "task_map": {}, "initiative_id": None}


def resolve_kanban_id(task_id: str, task_subject: str, state: dict,
                      store=None, project_id: str = None) -> str:
    """Resolve Claude task ID/subject to kanban task ID."""
    task_map = state.get("task_map", {})

    def _resolve(entry):
        if isinstance(entry, dict):
            return entry.get("kanban_id")
        return entry

    result = _resolve(task_map.get(task_subject)) or _resolve(task_map.get(task_id))

    # Fallback: search kanban store by subject/ID if task_map lookup failed
    if not result and store and project_id:
        try:
            results = store.search(task_subject or task_id, project_id)
            if results:
                result = results[0].get("task_id")
        except Exception:
            pass

    return result


def parse_transcript(transcript_path: str, task_subject: str, task_id: str = "") -> dict:
    """Parse transcript JSONL for enrichment data scoped to the task's active window."""
    enrichment = {
        "artifacts": [],
        "commits": [],
        "agents": [],
        "assigned_to": "claude",
        "outcome_summary": "",
    }

    if not transcript_path or not Path(transcript_path).exists():
        return enrichment

    try:
        lines = Path(transcript_path).read_text().strip().split('\n')
    except (IOError, OSError):
        return enrichment

    # Take last MAX_LINES to avoid parsing huge transcripts
    lines = lines[-MAX_LINES:]

    # Find the task's active window: look for TaskUpdate setting THIS task to in_progress
    start_idx = 0
    for i, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Look for TaskUpdate tool_use that set this task to in_progress
        msg = entry.get("message", {})
        if not isinstance(msg, dict):
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if block.get("name") != "TaskUpdate":
                continue
            tool_input = block.get("input", {})
            if tool_input.get("status") != "in_progress":
                continue
            # Verify this in_progress marker belongs to the completed task
            update_task_id = tool_input.get("taskId", "")
            if task_id and update_task_id and update_task_id != task_id:
                continue  # Different task — skip
            start_idx = i
            # Don't break — we want the LAST in_progress for this task

    # Parse tool calls from the active window
    seen_paths = set()
    seen_commits = set()
    seen_agents = set()

    for line in lines[start_idx:]:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg = entry.get("message", {})
        if not isinstance(msg, dict):
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue

            name = block.get("name", "")
            tool_input = block.get("input", {})

            # Extract file paths from Write/Edit
            if name in ("Write", "Edit"):
                file_path = tool_input.get("file_path", "")
                if file_path and file_path not in seen_paths:
                    seen_paths.add(file_path)
                    enrichment["artifacts"].append(file_path)

            # Extract commit hashes from Bash git commit commands
            elif name == "Bash":
                cmd = tool_input.get("command", "")
                if "git commit" in cmd:
                    # We'll also need the tool result for the hash
                    # but tool results are in separate JSONL entries
                    enrichment["_pending_git_commit"] = True

            # Extract agent dispatches from Task tool
            elif name == "Task":
                subagent = tool_input.get("subagent_type", "")
                desc = tool_input.get("description", "")
                if subagent and subagent not in seen_agents:
                    seen_agents.add(subagent)
                    enrichment["agents"].append({
                        "type": subagent,
                        "description": desc,
                    })
                    enrichment["assigned_to"] = subagent

        # Also check tool_result entries for git commit hashes
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_result":
                    continue
                result_content = block.get("content", "")
                if isinstance(result_content, str):
                    # Match: [branch abc1234] Commit message
                    commit_match = re.search(
                        r'\[[\w/-]+\s+([a-f0-9]{7,40})\]\s+(.+)',
                        result_content
                    )
                    if commit_match:
                        commit_hash = commit_match.group(1)
                        if commit_hash not in seen_commits:
                            seen_commits.add(commit_hash)
                            enrichment["commits"].append({
                                "hash": commit_hash,
                                "message": commit_match.group(2),
                            })

    # Clean up internal flag
    enrichment.pop("_pending_git_commit", None)

    # Build outcome summary
    parts = [task_subject]
    if enrichment["artifacts"]:
        parts.append(f"{len(enrichment['artifacts'])} file(s) modified")
    if enrichment["commits"]:
        parts.append(f"{len(enrichment['commits'])} commit(s)")
    if enrichment["agents"]:
        parts.append(f"{len(enrichment['agents'])} agent(s) dispatched")
    enrichment["outcome_summary"] = " | ".join(parts)

    return enrichment


def apply_artifacts(store, project_id, kanban_task_id, task, artifacts):
    """Add artifacts to task, deduplicating by path."""
    existing_paths = {
        a.get("path", "") for a in task.get("artifacts", [])
    }
    for path in artifacts:
        if path not in existing_paths:
            name = Path(path).name
            store.add_artifact(project_id, kanban_task_id,
                               name=name, artifact_type="file", path=path)


def apply_commits(store, project_id, kanban_task_id, task, commits):
    """Add commits to task. kanban.py already deduplicates by hash."""
    for commit in commits:
        store.add_commit(project_id, kanban_task_id,
                         commit["hash"], commit.get("message"))


def apply_agent_comment(store, project_id, kanban_task_id, task, agents):
    """Add agent dispatch summary as a comment. Uses description marker for idempotency."""
    if not agents:
        return

    # Use task description as idempotency marker — if outcome already present,
    # enrichment (including comments) was already applied
    current_desc = task.get("description", "") or ""
    if "## Outcome" in current_desc:
        return

    # Build summary
    lines = ["Agents dispatched:"]
    for agent in agents:
        lines.append(f"  - {agent['type']}: {agent.get('description', '')}")

    comment_text = '\n'.join(lines)

    store.add_comment(project_id, kanban_task_id, comment_text,
                      commenter="lifecycle-enricher")


def apply_assignment(store, project_id, kanban_task_id, task, assigned_to):
    """Set task assignment if not already set."""
    if assigned_to and not task.get("assigned_to"):
        store.update_task(project_id, kanban_task_id, assigned_to=assigned_to)


def apply_outcome(store, project_id, kanban_task_id, task, outcome_summary):
    """Append outcome section to task description if not already present."""
    if not outcome_summary:
        return

    current_desc = task.get("description", "") or ""
    if "## Outcome" in current_desc:
        return

    new_desc = current_desc + f"\n\n## Outcome\n{outcome_summary}"
    store.update_task(project_id, kanban_task_id, description=new_desc)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path", "")
    task_id = hook_input.get("task_id", "")
    task_subject = hook_input.get("task_subject", "")

    if not task_subject:
        sys.exit(0)

    try:
        store = get_store()
    except Exception:
        sys.exit(0)

    state = load_sync_state()
    project_id = state.get("project_id")
    kanban_task_id = resolve_kanban_id(task_id, task_subject, state,
                                       store=store, project_id=project_id)

    if not project_id or not kanban_task_id:
        sys.exit(0)

    task = store.get_task(project_id, kanban_task_id)
    if not task:
        sys.exit(0)

    # Parse transcript for enrichment data
    enrichment = parse_transcript(transcript_path, task_subject, task_id)

    # Apply enrichment (idempotent) — wrapped in try/except to guarantee exit 0
    try:
        apply_artifacts(store, project_id, kanban_task_id, task,
                        enrichment.get("artifacts", []))
        apply_commits(store, project_id, kanban_task_id, task,
                      enrichment.get("commits", []))
        apply_agent_comment(store, project_id, kanban_task_id, task,
                            enrichment.get("agents", []))
        apply_assignment(store, project_id, kanban_task_id, task,
                         enrichment.get("assigned_to"))
        apply_outcome(store, project_id, kanban_task_id, task,
                      enrichment.get("outcome_summary"))
    except Exception as e:
        print(f"Enrichment error (non-blocking): {e}", file=sys.stderr)

    # Always exit 0 — never block completion
    sys.exit(0)


if __name__ == '__main__':
    main()
