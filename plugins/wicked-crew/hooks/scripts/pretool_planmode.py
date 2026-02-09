#!/usr/bin/env python3
"""PreToolUse/EnterPlanMode: Redirect plan mode to wicked-crew."""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


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


def _find_active_project(projects_dir):
    """Find the most recently modified active project."""
    if not projects_dir.exists():
        return None
    for project_file in sorted(
        projects_dir.glob("*/project.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        content = project_file.read_text()
        lower = content.lower()
        if "status: active" in lower or "status: in_progress" in lower:
            name = project_file.parent.name
            for line in content.split("\n"):
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                    break
            return name
    return None


def main():
    try:
        sys.stdin.read()  # consume input

        crew_dir = Path.home() / ".something-wicked" / "wicked-crew"
        prefs_file = crew_dir / "preferences.yaml"

        # Check opt-out preference
        if prefs_file.exists():
            content = prefs_file.read_text()
            if yaml:
                prefs = yaml.safe_load(content) or {}
                if prefs.get("plan_mode_intercept") is False:
                    print(_allow())
                    return
            else:
                # Fallback: simple string check
                if "plan_mode_intercept: false" in content:
                    print(_allow())
                    return

        # Check for active project
        projects_dir = crew_dir / "projects"
        active = _find_active_project(projects_dir)

        if active:
            print(_deny(
                f"Do not enter default plan mode. An active wicked-crew project "
                f"exists: '{active}'. Use `/wicked-crew:execute` to continue "
                f"work on this project, or `/wicked-crew:status` to check progress."
            ))
        else:
            print(_deny(
                "Do not enter default plan mode. Instead, use "
                "`/wicked-crew:start <description>` to begin a structured project "
                "with quality gates, specialist discovery, and phased execution. "
                "If the user explicitly asked for basic plan mode, tell them they "
                "can opt out with `/wicked-crew:profile --plan-mode off`."
            ))
    except Exception:
        # Graceful degradation: allow normal plan mode on any error
        print(_allow())


if __name__ == "__main__":
    main()
