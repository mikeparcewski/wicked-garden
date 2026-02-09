#!/usr/bin/env python3
"""Stop hook: Update crew project state on session end."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def find_active_project() -> Optional[Path]:
    """Find the most recent active crew project."""
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return None

    for project_file in sorted(
        projects_dir.glob("*/project.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        content = project_file.read_text()
        if "status: active" in content.lower():
            return project_file.parent
    return None


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        hook_input = {}

    project_dir = find_active_project()
    if not project_dir:
        sys.exit(0)

    # Update last_activity in state.json
    state_file = project_dir / "state.json"
    try:
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        state["last_activity"] = datetime.now(timezone.utc).isoformat()
        state_file.write_text(json.dumps(state, indent=2))

        name = project_dir.name
        print(json.dumps({"systemMessage": f"[Crew] {name}: session state updated"}))
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
