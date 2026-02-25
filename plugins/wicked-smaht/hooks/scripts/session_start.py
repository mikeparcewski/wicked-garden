#!/usr/bin/env python3
"""
wicked-smaht v2: SessionStart hook.

Initializes session context from wicked-crew and wicked-kanban.
Uses v2 history_condenser for session management.

Cross-plugin boundary: queries crew and kanban via their CLI scripts,
never reads their storage directories directly.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Add v2 scripts directory to path
V2_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_SCRIPTS_DIR))


def _parse_version(v: str) -> tuple:
    """Parse semver string to comparable tuple."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def _discover_script(plugin_name: str, script_name: str):
    """Find a plugin's script via cache (highest version) or local repo."""
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / plugin_name
    if cache_base.exists():
        versions = []
        for d in cache_base.iterdir():
            if d.is_dir():
                versions.append((_parse_version(d.name), d))
        if versions:
            versions.sort(key=lambda x: x[0], reverse=True)
            script = versions[0][1] / "scripts" / script_name
            if script.exists():
                return script

    # Local repo sibling path
    local = Path(__file__).parent.parent.parent.parent / plugin_name / "scripts" / script_name
    if local.exists():
        return local

    return None


def _run_query(cmd, timeout=3.0):
    """Run a subprocess query, return parsed JSON or None."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return None


def get_active_project():
    """Find the most recently modified wicked-crew project via crew.py CLI."""
    crew_script = _discover_script("wicked-crew", "crew.py")
    if not crew_script:
        return None

    data = _run_query([sys.executable, str(crew_script), "list-projects", "--active", "--json"])
    if not data:
        return None

    projects = data.get("projects", [])
    if not projects:
        return None

    # First project is most recently modified (crew.py sorts by mtime desc)
    proj = projects[0]
    return {
        "name": proj.get("name", "unknown"),
        "phase": proj.get("current_phase", "unknown"),
    }


def get_active_tasks():
    """Get in-progress tasks from wicked-kanban via kanban.py CLI."""
    kanban_script = _discover_script("wicked-kanban", "kanban.py")
    if not kanban_script:
        return []

    data = _run_query([sys.executable, str(kanban_script), "list-tasks", "--json"])
    if not data:
        return []

    tasks = []
    for task in data.get("tasks", []):
        status = task.get("status", task.get("swimlane", ""))
        if status in ("doing", "in_progress", "todo"):
            tasks.append({
                "name": task.get("title", task.get("name", "")),
                "swimlane": status,
                "project": task.get("project", ""),
            })

    return tasks[:5]


def _reset_turn_counter():
    """Reset turn counter on session start to prevent cross-session leaks."""
    import tempfile
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if not session_id:
        session_id = f"pid-{os.getppid()}"
    tracker = Path(tempfile.gettempdir()) / f"wicked-smaht-turns-{session_id}"
    if tracker.exists():
        tracker.unlink()


def _reset_pressure_tracker():
    """Reset context pressure tracker on session start."""
    try:
        from context_pressure import PressureTracker
        tracker = PressureTracker()
        tracker.reset()
    except Exception:
        pass  # Non-critical — fail silently


def _ensure_subagent_hook():
    """Ensure SubagentStart hook is registered in project settings.

    Plugin hooks.json doesn't fire SubagentStart events (Claude Code limitation).
    Work around by auto-installing the hook into .claude/settings.local.json.
    """
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    if not claude_dir.exists():
        return  # Not a Claude Code project

    # Check if SubagentStart is already configured in any settings file
    for settings_name in ("settings.json", "settings.local.json"):
        settings_path = claude_dir / settings_name
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                if "SubagentStart" in data.get("hooks", {}):
                    return  # Already configured
            except (json.JSONDecodeError, Exception):
                continue

    # Build the hook command that discovers smaht plugin root dynamically
    hook_cmd = (
        'SMAHT_ROOT=$(find ~/.claude/plugins/cache/wicked-garden/wicked-smaht '
        '-maxdepth 1 -type d 2>/dev/null | sort -V | tail -1); '
        'if [ -n "$SMAHT_ROOT" ] && [ -f "$SMAHT_ROOT/hooks/scripts/subagent_start.py" ]; '
        'then python3 "$SMAHT_ROOT/hooks/scripts/subagent_start.py"; '
        "else echo '{\"continue\": true}'; fi"
    )

    # Install into settings.local.json (gitignored, non-invasive)
    local_settings_path = claude_dir / "settings.local.json"
    try:
        if local_settings_path.exists():
            raw = local_settings_path.read_text().strip()
            if raw:
                local_settings = json.loads(raw)
            else:
                local_settings = {}
        else:
            local_settings = {}

        if not isinstance(local_settings, dict):
            return  # Don't overwrite unexpected format

        hooks = local_settings.setdefault("hooks", {})
        hooks["SubagentStart"] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_cmd,
                        "timeout": 3000,
                    }
                ],
            }
        ]
        local_settings_path.write_text(json.dumps(local_settings, indent=2) + "\n")
    except (json.JSONDecodeError, ValueError):
        pass  # Don't overwrite corrupt files
    except Exception:
        pass  # Non-critical — fail silently


def main():
    """Initialize session and gather baseline context."""
    # Reset turn counter and pressure tracker to prevent cross-session leaks
    _reset_turn_counter()
    _reset_pressure_tracker()

    # Ensure SubagentStart hook is installed (plugin hooks don't fire it)
    _ensure_subagent_hook()

    context_lines = []
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")

    # Initialize v2 session via history_condenser
    try:
        from history_condenser import HistoryCondenser

        condenser = HistoryCondenser(session_id)
        state = condenser.get_session_state()

        if state.get("turn_count", 0) > 0:
            context_lines.append(f"Session: {session_id} (resuming, {state['turn_count']} turns)")
        else:
            context_lines.append(f"Session: {session_id} (new)")

        if state.get("topics"):
            context_lines.append(f"Topics: {', '.join(state['topics'][:5])}")

        # Cross-session memory: recall recent past sessions
        recent_sessions = HistoryCondenser.load_recent_sessions(max_sessions=3)
        # Filter out current session
        recent_sessions = [s for s in recent_sessions if s.get("session_id") != session_id]
        if recent_sessions:
            context_lines.append("Previous sessions:")
            for prev in recent_sessions[:3]:
                topics = ", ".join(prev.get("key_topics", [])[:3]) or "general"
                turns = prev.get("turn_count", 0)
                task = prev.get("current_task", "")
                end_time = prev.get("end_time", "")
                # Calculate rough age
                age_str = ""
                if end_time:
                    try:
                        from datetime import datetime, timezone
                        ended = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        hours = (now - ended).total_seconds() / 3600
                        if hours < 1:
                            age_str = "just now"
                        elif hours < 24:
                            age_str = f"{int(hours)}h ago"
                        else:
                            age_str = f"{int(hours/24)}d ago"
                    except Exception:
                        pass
                line = f"  - {topics} ({turns} turns"
                if age_str:
                    line += f", {age_str}"
                line += ")"
                if task:
                    line += f" — {task[:60]}"
                context_lines.append(line)

    except ImportError:
        context_lines.append(f"Session: {session_id}")
    except Exception as e:
        context_lines.append(f"Session: {session_id} (init error: {str(e)[:30]})")

    # Detect AGENTS.md for cross-tool context (loaded before CLAUDE.md)
    cwd = Path.cwd()
    agents_md_exists = (cwd / "AGENTS.md").exists()
    claude_md_exists = (cwd / "CLAUDE.md").exists()
    if agents_md_exists and claude_md_exists:
        context_lines.append("Project context: AGENTS.md + CLAUDE.md detected (general + Claude-specific)")
    elif agents_md_exists:
        context_lines.append("Project context: AGENTS.md detected (cross-tool agent instructions)")
    elif claude_md_exists:
        context_lines.append("Project context: CLAUDE.md detected")

    # Get active project
    project = get_active_project()
    if project:
        context_lines.append(f"Active project: {project['name']} ({project['phase']} phase)")

    # Get active tasks
    tasks = get_active_tasks()
    if tasks:
        context_lines.append(f"Active tasks: {len(tasks)}")
        for task in tasks[:3]:
            context_lines.append(f"  - [{task['swimlane']}] {task['name']}")

    if not context_lines:
        # No context to inject
        print(json.dumps({"continue": True}))
        return

    # Format as system reminder
    context = "\n".join(context_lines)
    result = {
        "continue": True,
        "message": f"<system-reminder>\nwicked-smaht v2 session:\n{context}\n</system-reminder>"
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
