#!/usr/bin/env python3
"""SessionStart: Reconnect active wicked-crew project and validate kanban initiative link."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def discover_script(plugin_name: str, script_name: str):
    """Find a plugin script via cache or local repo sibling."""
    def _parse_version(v):
        v = v.lstrip("vV")
        m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
        return tuple(int(x) for x in m.groups()) if m else None

    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / plugin_name
    if cache_base.exists():
        versions = []
        for d in cache_base.iterdir():
            if d.is_dir():
                parsed = _parse_version(d.name)
                if parsed is not None:
                    versions.append((parsed, d))
        if versions:
            versions.sort(key=lambda x: x[0], reverse=True)
            script = versions[0][1] / "scripts" / script_name
            if script.exists():
                return script

    local = Path(__file__).parent.parent.parent.parent / plugin_name / "scripts" / script_name
    if local.exists():
        return local

    return None


def find_active_project():
    """Return (project_data, project_file) for the most recently modified active project."""
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return None, None

    for pf in sorted(projects_dir.glob("*/project.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(pf.read_text())
            if data.get("archived"):
                continue
            phase = data.get("current_phase", "")
            if phase and phase != "complete":
                return data, pf
        except (json.JSONDecodeError, OSError):
            continue

    return None, None


def validate_kanban_initiative(project_data: dict):
    """Check that the stored kanban_initiative_id still exists in kanban.

    Returns (valid, repaired_id_or_none).
    """
    initiative_name = project_data.get("kanban_initiative") or project_data.get("name")
    if not initiative_name:
        return False, None

    script = discover_script("wicked-kanban", "kanban_initiative.py")
    if not script:
        # kanban not installed — treat as valid (graceful degradation)
        return True, project_data.get("kanban_initiative_id")

    try:
        result = subprocess.run(
            [sys.executable, str(script), "lookup", initiative_name],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("found"):
                return True, data["initiative_id"]
        return False, None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        # On any error, assume valid (don't block session on kanban failure)
        return True, project_data.get("kanban_initiative_id")


def repair_project_initiative(project_file: Path, initiative_id: str) -> None:
    """Update project.json with the correct initiative_id (opportunistic repair)."""
    try:
        data = json.loads(project_file.read_text())
        data["kanban_initiative_id"] = initiative_id
        tmp = project_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, project_file)
    except OSError:
        pass  # Repair failure is non-fatal


def main():
    try:
        sys.stdin.read()  # consume input

        # Clear task suggestion flag
        flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
        flag.unlink(missing_ok=True)

        project_data, project_file = find_active_project()

        if not project_data:
            print(json.dumps({"continue": True}))
            return

        name = project_data.get("name", project_file.parent.name if project_file else "unknown")
        phase = project_data.get("current_phase", "unknown")
        initiative_name = project_data.get("kanban_initiative") or name
        stored_id = project_data.get("kanban_initiative_id")

        # Validate kanban linkage
        valid, resolved_id = validate_kanban_initiative(project_data)

        status_parts = [f"[Crew] Resuming: {name} ({phase})"]

        if valid and resolved_id:
            if resolved_id != stored_id:
                # Opportunistic repair: update project.json with correct ID
                repair_project_initiative(project_file, resolved_id)
                status_parts.append(f"Kanban: {initiative_name} (repaired link)")
            else:
                status_parts.append(f"Kanban: {initiative_name} (linked)")
        elif not valid:
            status_parts.append(
                f"Kanban: initiative '{initiative_name}' not found "
                f"(will be created on next task)"
            )

        print(json.dumps({
            "continue": True,
            "systemMessage": " | ".join(status_parts)
        }))

    except Exception:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
