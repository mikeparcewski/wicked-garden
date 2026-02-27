#!/usr/bin/env python3
"""
SessionStart hook — wicked-garden unified bootstrap.

Consolidates: crew session_start, kanban session_start, mem session_start,
search session_start, smaht session_start, startah session_start.

Flow:
1. Read config from ~/.something-wicked/wicked-garden/config.json
2. If missing or setup_complete=false: emit setup instructions, return
3. Health check control plane (2s timeout)
4. Write SessionState (cp_available, fallback_mode)
5. Load dynamic agents
6. Drain offline write queue if CP available
7. Load active crew project
8. Load kanban board summary
9. Run memory decay
10. Assemble session briefing
11. Return {"continue": true, "systemMessage": "<briefing>"}

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
from pathlib import Path

# Add shared scripts directory to path so hook can import shared modules
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Shared module imports — each wrapped so missing modules degrade gracefully
# ---------------------------------------------------------------------------

def _load_session_state():
    try:
        from _session import SessionState
        return SessionState.load()
    except Exception:
        return None


def _save_session_state(state):
    try:
        state.save()
    except Exception:
        pass


def _check_health(config):
    """Return (ok, version) from control plane health check. Timeout: 2s."""
    try:
        from _control_plane import ControlPlaneClient
        client = ControlPlaneClient(hook_mode=True)
        return client.check_health()
    except Exception:
        return False, ""


def _drain_queue():
    """Replay offline write queue against the control plane."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-garden")
        sm.drain_queue()
    except Exception as e:
        print(f"[wicked-garden] queue drain error: {e}", file=sys.stderr)


def _load_agents(cp_available):
    """Load dynamic agents (CP overlay + disk defaults). Returns agent count."""
    try:
        from _agents import AgentLoader
        loader = AgentLoader()
        loader.load_disk_agents(_PLUGIN_ROOT / "agents")
        if cp_available:
            from _storage import StorageManager
            sm = StorageManager("wicked-agents")
            cp_agents = sm.list("agents") or []
            loader.overlay_cp_agents(cp_agents)
        agents = loader.all()
        return len(agents)
    except Exception as e:
        print(f"[wicked-garden] agent load error: {e}", file=sys.stderr)
        return 0


def _find_active_crew_project():
    """Return (project_data, project_file) for most recently modified active crew project."""
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return None, None

    for pf in sorted(
        projects_dir.glob("*/project.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
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


def _load_kanban_summary():
    """Return a short kanban board summary string."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-kanban")
        tasks = sm.list("tasks", status="in_progress") or []
        if not tasks:
            return None
        count = len(tasks)
        names = [t.get("name", "?") for t in tasks[:3]]
        summary = f"{count} in-progress: {', '.join(names)}"
        if count > 3:
            summary += f" (+{count - 3} more)"
        return summary
    except Exception:
        return None


def _run_memory_decay():
    """Run memory decay maintenance. Returns a summary string or None."""
    try:
        from mem.memory import MemoryStore
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        store = MemoryStore(project)
        result = store.run_decay()
        if result.get("archived", 0) > 0 or result.get("deleted", 0) > 0:
            return f"Memory: {result['archived']} archived, {result['deleted']} cleaned"
        return None
    except Exception:
        return None


def _validate_and_repair_kanban_link(project_data, project_file, cp_available):
    """Validate that the crew project's kanban initiative still exists.

    Returns (valid, resolved_id).
    """
    initiative_name = project_data.get("kanban_initiative") or project_data.get("name")
    if not initiative_name:
        return False, None

    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-kanban")
        initiatives = sm.list("initiatives") or []
        for init in initiatives:
            if init.get("name") == initiative_name:
                resolved_id = init["id"]
                stored_id = project_data.get("kanban_initiative_id")
                if resolved_id != stored_id and project_file:
                    _repair_project_initiative(project_file, resolved_id)
                return True, resolved_id
        return False, None
    except Exception:
        # On any error, assume valid (don't block session on kanban failure)
        return True, project_data.get("kanban_initiative_id")


def _repair_project_initiative(project_file, initiative_id):
    """Atomically update project.json with the correct initiative_id."""
    try:
        data = json.loads(project_file.read_text())
        data["kanban_initiative_id"] = initiative_id
        tmp = project_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, project_file)
    except OSError:
        pass


def _read_config():
    """Read config from ~/.something-wicked/wicked-garden/config.json."""
    config_path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
    if not config_path.exists():
        return None
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Memory behavior instructions (injected every session)
# ---------------------------------------------------------------------------

_MEMORY_INSTRUCTIONS = (
    "[Memory] This project uses wicked-garden memory for persistence. "
    "Never write to MEMORY.md or AGENTS.md directly — use /wicked-garden:mem:store. "
    "MEMORY.md is auto-generated and read-only."
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        sys.stdin.read()  # consume hook payload (not needed for SessionStart)
    except Exception:
        pass

    try:
        # 1. Read config
        config = _read_config()

        if config is None or not config.get("setup_complete", False):
            print(json.dumps({
                "continue": True,
                "systemMessage": (
                    "wicked-garden needs configuration. "
                    "Run /wicked-garden:setup to connect to a local or remote control plane, "
                    "or /wicked-garden:offline to use offline-only mode with local file storage."
                ),
            }))
            return

        # Clear one-time task suggestion flag from crew
        flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
        flag.unlink(missing_ok=True)

        # 2. Health check control plane
        cp_available = False
        cp_version = ""
        fallback_message = ""

        endpoint = config.get("endpoint")
        if endpoint:
            cp_available, cp_version = _check_health(config)
            if not cp_available:
                fallback_message = (
                    "[wicked-garden] Offline mode: control plane unreachable. "
                    "Using local storage and disk agents."
                )

        # 3. Write session state
        state = _load_session_state()
        if state is not None:
            state.update(
                cp_available=cp_available,
                cp_version=cp_version,
                fallback_mode=not cp_available,
                setup_complete=True,
            )

        # 4. Load dynamic agents
        agents_loaded = _load_agents(cp_available)
        if state is not None:
            state.update(agents_loaded=agents_loaded)

        # 5. Drain offline write queue (only when CP is available)
        if cp_available:
            _drain_queue()

        # 6 & 7. Load active crew project and kanban board summary (independent reads)
        project_data, project_file = _find_active_crew_project()
        kanban_summary = _load_kanban_summary()

        # 8. Run memory decay
        decay_summary = _run_memory_decay()

        # 9. Assemble session briefing
        briefing_parts = [_MEMORY_INSTRUCTIONS]

        if fallback_message:
            briefing_parts.append(fallback_message)

        if project_data:
            name = project_data.get("name", project_file.parent.name if project_file else "unknown")
            phase = project_data.get("current_phase", "unknown")
            initiative_name = project_data.get("kanban_initiative") or name

            valid, resolved_id = _validate_and_repair_kanban_link(
                project_data, project_file, cp_available
            )

            crew_line = f"[Crew] Resuming: {name} ({phase})"
            if valid and resolved_id:
                crew_line += f" | Kanban: {initiative_name} (linked)"
            elif not valid:
                crew_line += f" | Kanban: initiative '{initiative_name}' not found (will be created on next task)"

            briefing_parts.append(crew_line)

            if state is not None:
                state.update(active_project={"name": name, "phase": phase})

        if kanban_summary:
            briefing_parts.append(f"[Kanban] {kanban_summary}")

        if decay_summary:
            briefing_parts.append(f"[Memory] {decay_summary}")

        # 10. Persist final session state
        if state is not None:
            _save_session_state(state)

        print(json.dumps({
            "continue": True,
            "systemMessage": "\n".join(briefing_parts),
        }))

    except Exception as e:
        print(f"[wicked-garden] bootstrap error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
