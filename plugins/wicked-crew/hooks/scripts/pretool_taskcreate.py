#!/usr/bin/env python3
"""PreToolUse/TaskCreate: Inject crew initiative metadata and suggest crew if no project."""
import json
import sys
from pathlib import Path


ALLOW_RESPONSE = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow"
    }
}


def find_active_project() -> tuple:
    """Return (project_name, kanban_initiative_name) for most recently modified active project.

    Checks project.json first (structured), falls back to project.md frontmatter.
    Returns (None, None) if no active project found.
    """
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return None, None

    # Prefer project.json (has kanban fields)
    for pf in sorted(projects_dir.glob("*/project.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(pf.read_text())
            if data.get("archived"):
                continue
            phase = data.get("current_phase", "")
            if phase and phase != "complete":
                name = data.get("name") or pf.parent.name
                initiative = data.get("kanban_initiative") or name
                return name, initiative
        except (json.JSONDecodeError, OSError):
            continue

    # Fallback: project.md frontmatter
    for pf in sorted(projects_dir.glob("*/project.md"),
                     key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            content = pf.read_text()
            if "status: active" in content.lower():
                name = None
                for line in content.split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                        break
                if name:
                    return name, name
        except OSError:
            continue

    return None, None


def main():
    try:
        try:
            hook_input = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, IOError):
            hook_input = {}

        tool_input = hook_input.get("tool_input", {})

        project_name, initiative_name = find_active_project()

        if project_name:
            # Inject initiative metadata if not already set
            metadata = tool_input.get("metadata") or {}
            if not metadata.get("initiative"):
                metadata["initiative"] = initiative_name
                tool_input["metadata"] = metadata

            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": tool_input,
                }
            }))
        else:
            # No active project — show one-time suggestion
            flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
            if not flag.exists():
                flag.parent.mkdir(parents=True, exist_ok=True)
                flag.touch()
                response = dict(ALLOW_RESPONSE)
                response["systemMessage"] = (
                    "Creating tasks? Consider `/wicked-crew:start` for quality gates."
                )
                print(json.dumps(response))
            else:
                print(json.dumps(ALLOW_RESPONSE))
    except Exception:
        print(json.dumps(ALLOW_RESPONSE))


if __name__ == "__main__":
    main()
