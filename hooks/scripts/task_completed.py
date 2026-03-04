#!/usr/bin/env python3
"""
TaskCompleted hook — wicked-garden memory compliance tracking.

Fires when Claude Code marks a task as completed (TaskCompleted event).
This hook does NOT use matchers — it fires for all task completions.

Responsibilities:
1. Increment memory_compliance_tasks_completed in session state.
2. When memory_compliance_required is True (crew project active), emit a
   brief systemMessage directive asking Claude to evaluate the completed
   task for storable learnings if the task looks like it produced a
   deliverable.

Always returns {"ok": true} — task completion is never blocked.
Wraps all logic in try/except and fails open.

Input schema (from Claude Code):
    {"task_id": "...", "subject": "...", "status": "completed"}
"""

import json
import os
import sys
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))

# Keywords that suggest a deliverable-producing task
_DELIVERABLE_PATTERNS = (
    "phase:",
    "implement",
    "write",
    "design",
    "build",
    "create",
    "develop",
    "refactor",
    "migrate",
    "fix",
    "resolve",
    "deploy",
    "integrate",
    "add",
    "update",
)


def _is_deliverable_task(subject: str) -> bool:
    """Return True if the task subject suggests it produced a deliverable."""
    subject_lower = subject.lower()
    return any(kw in subject_lower for kw in _DELIVERABLE_PATTERNS)


def main():
    # Read task data from stdin
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    try:
        subject = input_data.get("subject", "")
        task_id = input_data.get("task_id", "")

        # Load session state and increment the completion counter
        try:
            from _session import SessionState
            state = SessionState.load()
            state.memory_compliance_tasks_completed = (
                (state.memory_compliance_tasks_completed or 0) + 1
            )
            compliance_required = bool(state.memory_compliance_required)
            state.save()
        except Exception as e:
            print(f"[wicked-garden] task_completed session state error: {e}", file=sys.stderr)
            compliance_required = False

        # Emit a memory directive only when compliance is required and the task
        # looks like it produced a deliverable worth storing.
        system_message = ""
        if compliance_required and subject and _is_deliverable_task(subject):
            task_label = f'"{subject}"' if subject else f"task {task_id}"
            system_message = (
                f"[Memory] Task {task_label} completed. "
                "Evaluate whether this task produced a decision, gotcha, or reusable pattern. "
                "If yes, store it now with /wicked-garden:mem:store before continuing. "
                "If no learnings apply, proceed without storing."
            )

        output: dict = {"ok": True}
        if system_message:
            output["systemMessage"] = system_message

        print(json.dumps(output))

    except Exception as e:
        print(f"[wicked-garden] task_completed hook error: {e}", file=sys.stderr)
        print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
