#!/usr/bin/env python3
"""PreToolUse/TaskCreate: Suggest wicked-crew on first task creation."""
import json
import sys
from pathlib import Path

def main():
    try:
        sys.stdin.read()  # consume input

        flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"

        if not flag.exists():
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch()
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow"
                },
                "systemMessage": "Creating tasks? Consider `/wicked-crew:start` for quality gates."
            }))
        else:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow"
                }
            }))
    except Exception:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }))

if __name__ == "__main__":
    main()
