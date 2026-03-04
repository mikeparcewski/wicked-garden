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
    "test",
    "review",
    "document",
    "configure",
    "setup",
    "scaffold",
    "generate",
    "analyze",
)


def _is_deliverable_task(subject: str) -> bool:
    """Return True if the task subject suggests it produced a deliverable."""
    subject_lower = subject.lower()
    return any(kw in subject_lower for kw in _DELIVERABLE_PATTERNS)


def _infer_mem_type(subject: str) -> str:
    """Infer the most appropriate mem:store type from task subject."""
    s = subject.lower()
    if any(kw in s for kw in ("fix", "resolve", "bug", "defect")):
        return "decision"
    if any(kw in s for kw in ("phase:", "design", "architect", "strategy")):
        return "episodic"
    return "procedural"


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

        # Load session state, increment counters, and read escalation level
        escalations = 0
        try:
            from _session import SessionState
            state = SessionState.load()
            state.memory_compliance_tasks_completed = (
                (state.memory_compliance_tasks_completed or 0) + 1
            )
            compliance_required = bool(state.memory_compliance_required)
            # Increment escalation counter (reset by post_tool.py on mem:store)
            state.memory_compliance_escalations = (
                (state.memory_compliance_escalations or 0) + 1
            )
            escalations = state.memory_compliance_escalations
            state.save()
        except Exception as e:
            print(f"[wicked-garden] task_completed session state error: {e}", file=sys.stderr)
            compliance_required = False

        # Emit a memory directive only when compliance is required and the task
        # looks like it produced a deliverable worth storing.
        system_message = ""
        if compliance_required and subject and _is_deliverable_task(subject):
            mem_type = _infer_mem_type(subject)
            task_label = f'"{subject}"' if subject else f"task {task_id}"
            escalation_prefix = "[ESCALATION] " if escalations >= 3 else ""
            system_message = (
                f"{escalation_prefix}[Memory] Task {task_label} completed. "
                f"REQUIRED: Call /wicked-garden:mem:store with type={mem_type} "
                "to capture any decision, gotcha, or pattern from this work. "
                "If genuinely nothing is worth storing, respond with 'No memory stored: <reason>'."
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
