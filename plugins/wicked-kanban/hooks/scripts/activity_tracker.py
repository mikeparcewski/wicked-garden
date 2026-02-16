#!/usr/bin/env python3
"""
PostToolUse hook: Track activity (commits, agent work, file operations).

Logs activity to the active task in kanban for traceability.
"""

import json
import os
import re
import sys
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


def extract_commit_info(command: str, output: str) -> dict:
    """Extract commit hash and message from git commit output."""
    result = {}

    # Match: [branch abc1234] Commit message
    match = re.search(r'\[[\w/-]+\s+([a-f0-9]+)\]\s+(.+)', output)
    if match:
        result['hash'] = match.group(1)
        result['message'] = match.group(2)
        return result

    # Try to extract from command if -m flag present
    msg_match = re.search(r'-m\s+["\']([^"\']+)["\']', command)
    if msg_match:
        result['message'] = msg_match.group(1)

    return result


def is_git_commit(command: str) -> bool:
    """Check if command is a git commit."""
    return 'git commit' in command and '-m' in command


def is_git_push(command: str) -> bool:
    """Check if command is a git push."""
    return 'git push' in command


def track_bash_activity(store, tool_input: dict, tool_result: dict):
    """Track bash command activity."""
    command = tool_input.get("command", "")
    output = tool_result.get("output", "") if tool_result else ""

    # Get active task context
    ctx = store.get_active_context()
    project_id = ctx.get("project_id")
    task_id = ctx.get("active_task_id")

    if not project_id or not task_id:
        return {"status": "no_active_task"}

    # Track git commits
    if is_git_commit(command):
        commit_info = extract_commit_info(command, output)
        if commit_info.get('hash'):
            store.add_commit(
                project_id, task_id,
                commit_info['hash'],
                commit_info.get('message')
            )
            return {
                "status": "commit_linked",
                "commit": commit_info['hash']
            }
        elif commit_info.get('message'):
            # Log even without hash
            store.add_comment(
                project_id, task_id,
                f"Git commit: {commit_info['message']}"
            )
            return {"status": "commit_logged"}

    # Track git push
    if is_git_push(command):
        store.add_comment(
            project_id, task_id,
            f"Pushed to remote"
        )
        return {"status": "push_logged"}

    return {"status": "ignored"}


def track_agent_activity(store, tool_input: dict, tool_result: dict):
    """Track Task (subagent) activity."""
    description = tool_input.get("description", "")
    prompt = tool_input.get("prompt", "")
    subagent_type = tool_input.get("subagent_type", "")
    agent_output = tool_result.get("output", "") if tool_result else ""

    # Get active task context
    ctx = store.get_active_context()
    project_id = ctx.get("project_id")
    task_id = ctx.get("active_task_id")

    if not project_id or not task_id:
        return {"status": "no_active_task"}

    # Log agent activity
    activity_type = "Agent"
    if subagent_type:
        activity_type = subagent_type.replace("-", " ").title()

    # Create summary
    summary_parts = [f"{activity_type}: {description}"]

    # Extract key info from output (first 200 chars)
    if agent_output and len(agent_output) > 50:
        # Try to get a meaningful snippet
        lines = agent_output.strip().split('\n')
        first_meaningful = next(
            (l for l in lines if l.strip() and not l.startswith('#')),
            ""
        )
        if first_meaningful:
            summary_parts.append(f"Result: {first_meaningful[:150]}...")

    store.add_comment(
        project_id, task_id,
        '\n'.join(summary_parts),
        commenter=subagent_type or "agent"
    )

    return {"status": "agent_logged", "type": subagent_type}


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    tool_result = hook_input.get("tool_response", hook_input.get("tool_result", {}))

    store = get_store()
    result = {"continue": True}

    if tool_name == "Bash":
        track_result = track_bash_activity(store, tool_input, tool_result)
        result["activity"] = track_result

    elif tool_name == "Task":
        track_result = track_agent_activity(store, tool_input, tool_result)
        result["activity"] = track_result

    print(json.dumps(result))
    sys.exit(0)


if __name__ == '__main__':
    main()
