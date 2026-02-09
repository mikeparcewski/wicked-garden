#!/usr/bin/env python3
"""
PostToolUse hook (TaskUpdate) - Prompt for memory capture at task boundaries.

Every task status change or update is a natural checkpoint for capturing
decisions, context, and learnings.
"""

import json
import sys


PROMPTS = {
    "in_progress": (
        "[Memory] Task started. Note your approach, key assumptions, "
        "or any context that would help if this task is resumed later."
    ),
    "completed": (
        "[Memory] Task completed. If this task produced a decision with rationale, "
        "a gotcha worth avoiding, or a reusable pattern — store it now with /wicked-mem:store."
    ),
    "pending": (
        "[Memory] Task moved back to pending. Note why — was it blocked, "
        "deprioritized, or needs rework?"
    ),
}

UPDATE_PROMPT = (
    "[Memory] Task updated. If this reflects a decision, scope change, "
    "or new dependency — capture the context with /wicked-mem:store."
)


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    tool_input = input_data.get("tool_input", {})
    status = tool_input.get("status")

    # Status change
    if status:
        prompt = PROMPTS.get(status)
        if prompt is None:
            print(json.dumps({"continue": True}))
            return
        print(json.dumps({"continue": True, "systemMessage": prompt}))
        return

    # Non-status update (subject, description, owner, dependencies, metadata)
    has_meaningful_update = any(
        tool_input.get(field)
        for field in ("subject", "description", "owner", "addBlockedBy", "addBlocks")
    )

    if has_meaningful_update:
        print(json.dumps({"continue": True, "systemMessage": UPDATE_PROMPT}))
    else:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
