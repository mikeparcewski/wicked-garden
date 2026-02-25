#!/usr/bin/env python3
"""
wicked-smaht: PostToolUse hook.

Tracks tool output sizes in the context pressure tracker.
Must be FAST (<100ms) — just reads stdin size and updates a counter.
Never blocks tool execution.
"""

import json
import sys
from pathlib import Path

# Add v2 scripts to path
V2_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_SCRIPTS_DIR))


def main():
    try:
        raw = sys.stdin.read()
        input_size = len(raw)

        # Parse to get tool name for logging, but size is what matters
        try:
            data = json.loads(raw)
            tool_name = data.get("tool_name", "unknown")
        except (json.JSONDecodeError, Exception):
            tool_name = "unknown"

        # Update pressure tracker with the content size
        # The stdin includes tool_input + tool_output, which approximates
        # what Claude sees in its context window from this tool call
        if input_size > 0:
            try:
                from context_pressure import PressureTracker
                tracker = PressureTracker()
                tracker.add_content(input_size)
            except Exception:
                pass  # Never block on tracking failure

    except Exception:
        pass  # Never block, never fail

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
