#!/usr/bin/env python3
"""
TaskCompleted hook - Prompt for memory capture when tasks complete.

Input: {"task_id", "task_subject", "task_description", "teammate_name", "team_name"}
Exit 0: stdout/stderr not shown
Exit 2: stderr shown to model, prevents completion
"""

import json
import sys


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    task_subject = input_data.get("task_subject", "")

    # Always prompt for memory capture on task completion
    print(json.dumps({
        "continue": True,
        "systemMessage": (
            "[Memory] Task completed. If this task produced a decision with rationale, "
            "a gotcha worth avoiding, or a reusable pattern — store it now with /wicked-mem:store."
        )
    }))


if __name__ == "__main__":
    main()
