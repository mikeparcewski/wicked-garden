#!/usr/bin/env python3
"""
PreToolUse hook - Block direct Write/Edit to MEMORY.md files.

Claude Code's built-in "auto memory" system instructs Claude to write
learnings to MEMORY.md files. This project uses wicked-mem instead.
This hook intercepts those writes and redirects to /wicked-mem:store.
"""

import json
import sys

# The auto memory directory pattern used by Claude Code
AUTO_MEMORY_MARKER = ".claude/projects/"


def _allow():
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow"
        }
    })


def _deny(reason):
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason
        }
    })


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        tool_input = input_data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        # Block writes to MEMORY.md files or Claude's auto memory directory
        # but NOT to plugin files that happen to have "memory" in the path
        is_memory_md = file_path.endswith("MEMORY.md")
        is_auto_memory = AUTO_MEMORY_MARKER in file_path and "/memory/" in file_path

        if is_memory_md or is_auto_memory:
            print(_deny(
                "Do not write to MEMORY.md or the auto memory directory. "
                "This project uses wicked-mem for memory persistence. "
                "Use /wicked-mem:store to save decisions, patterns, and gotchas instead."
            ))
            return

        print(_allow())

    except Exception:
        # Never block on errors — allow the write
        print(_allow())


if __name__ == "__main__":
    main()
