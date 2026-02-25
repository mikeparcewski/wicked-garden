#!/usr/bin/env python3
"""
wicked-smaht: PreToolUse hook.

Pressure gate that fires BEFORE every heavy tool call (Bash, Task).
At CRITICAL pressure, blocks the tool call and tells Claude to compact.
At HIGH pressure, allows but injects pressure awareness.

This is the main defense against context exhaustion during autonomous
operation — between user prompts, Claude may make dozens of tool calls.
Each one is a checkpoint.
"""

import json
import sys
from pathlib import Path

V2_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_SCRIPTS_DIR))


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        print(json.dumps({"continue": True}))
        return

    tool_name = data.get("tool_name", "")

    # Track input size (the parameters being sent to the tool)
    try:
        from context_pressure import PressureTracker
        tracker = PressureTracker()

        # Add the tool input size to pressure tracking
        input_size = len(raw)
        if input_size > 0:
            tracker.add_content(input_size)

        level = tracker.get_level()
        pressure_kb = tracker.get_pressure_kb()
    except Exception:
        # If pressure tracker fails, never block
        print(json.dumps({"continue": True}))
        return

    from context_pressure import PressureLevel

    if level == PressureLevel.CRITICAL:
        # BLOCK: Context is near capacity. Force compaction.
        print(json.dumps({
            "continue": False,
            "reason": (
                f"Context pressure is CRITICAL ({pressure_kb}KB). "
                "You MUST run /compact before making any more tool calls. "
                "Session state is tracked externally by wicked-smaht and will be "
                "reconstructed after compaction — nothing will be lost."
            )
        }))
        return

    if level == PressureLevel.HIGH:
        # ALLOW but warn via stderr (model sees blocked reasons, not stderr,
        # but UserPromptSubmit will inject the directive on next prompt)
        print(
            f"smaht: pressure HIGH ({pressure_kb}KB) on {tool_name} call. "
            "Compact soon.",
            file=sys.stderr
        )

    # LOW/MEDIUM: proceed normally
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
