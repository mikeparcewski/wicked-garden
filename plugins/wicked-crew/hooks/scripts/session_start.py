#!/usr/bin/env python3
"""SessionStart: Check for active wicked-crew project."""
import json
import sys
from pathlib import Path

def main():
    try:
        sys.stdin.read()  # consume input

        # Clear task suggestion flag
        flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
        flag.unlink(missing_ok=True)

        # Find most recent active project
        projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
        if not projects_dir.exists():
            print(json.dumps({"continue": True}))
            return

        for project_file in sorted(projects_dir.glob("*/project.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            content = project_file.read_text()
            if "status: active" in content.lower():
                name = phase = "unknown"
                for line in content.split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("current_phase:"):
                        phase = line.split(":", 1)[1].strip()
                print(json.dumps({"continue": True, "systemMessage": f"[Crew] Resuming: {name} ({phase})"}))
                return

        print(json.dumps({"continue": True}))
    except Exception:
        print(json.dumps({"continue": True}))

if __name__ == "__main__":
    main()
