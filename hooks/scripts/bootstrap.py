#!/usr/bin/env python3
"""
SessionStart hook — wicked-garden unified bootstrap.

Consolidates: crew session_start, kanban session_start, mem session_start,
search session_start, smaht session_start.

Flow:
1. Read config from ~/.something-wicked/wicked-garden/config.json
2. If missing or setup_complete=false: emit setup instructions, return
3. Mode-branched initialization:
   - local-install: health check → auto-start if down → poll → open browser
   - remote: health check → report status
   - offline: storage summary → opportunistic probe
4. Load dynamic agents
5. Drain offline write queue if CP available
6. Load active crew project + kanban summary
7. Run memory decay
8. Check onboarding status → imperative directive if needed
9. Assemble session briefing
10. Return {"continue": true, "systemMessage": "<briefing>"}

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import subprocess
import sys
import time
import webbrowser
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
    """Return (project_data, project_name) for most recently updated active crew project.

    Uses StorageManager for consistent data access. Falls back to filesystem
    scan if StorageManager fails (legacy compat for one release).
    """
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-crew", hook_mode=True)
        projects = sm.list("projects") or []
        # Sort by updated_at descending, return first non-archived, non-complete
        for p in sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True):
            if p.get("archived"):
                continue
            phase = p.get("current_phase", "")
            if phase and phase != "complete":
                return p, p.get("name")
        return None, None
    except Exception:
        pass

    # Legacy fallback: direct filesystem scan (remove after one release)
    return _find_active_crew_project_legacy()


def _find_active_crew_project_legacy():
    """Filesystem-based crew project scan. Legacy fallback."""
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
                return data, data.get("name", pf.parent.name)
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


def _check_onboarding_status():
    """Check if the current project has been onboarded (search index + memories).

    Returns an imperative directive string if onboarding is needed, or None if done.
    Both checks fail open — if we can't determine status, assume onboarded.
    """
    project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
    cwd = str(Path.cwd())

    has_index = True   # default: assume done (fail open)
    has_memories = True  # default: assume done (fail open)

    # Check search index (local SQLite database)
    try:
        import sqlite3
        db_path = Path.home() / ".something-wicked" / "wicked-search" / "unified_search.db"
        if not db_path.exists():
            has_index = False
        else:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
            try:
                # Introspect tables for a file/path column, check for entries under cwd
                tables = [
                    row[0] for row in
                    conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                ]
                _FILE_COLS = {"file", "path", "file_path", "filepath"}
                found = False
                for table in tables:
                    cols = [
                        row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                    ]
                    for col in cols:
                        if col in _FILE_COLS:
                            cursor = conn.execute(
                                f'SELECT 1 FROM "{table}" WHERE "{col}" LIKE ? LIMIT 1',
                                (cwd + "%",),
                            )
                            if cursor.fetchone() is not None:
                                found = True
                                break
                    if found:
                        break
                has_index = found
            finally:
                conn.close()
    except Exception:
        pass  # Fail open

    # Check onboarding memories
    try:
        from mem.memory import MemoryStore
        store = MemoryStore(project)
        memories = store.recall(tags=["onboarding"], limit=1)
        has_memories = len(memories) > 0
    except Exception:
        pass  # Fail open

    if not has_memories and not has_index:
        return (
            f"[Onboarding] IMPORTANT: Project '{project}' has not been onboarded. "
            "You MUST run /wicked-garden:smaht:onboard now before doing any other work. "
            "Do not ask for confirmation — start onboarding immediately."
        )
    elif not has_memories:
        return (
            f"[Onboarding] IMPORTANT: Project '{project}' has a search index but no onboarding memories. "
            "You MUST run /wicked-garden:smaht:onboard now to build project knowledge."
        )
    elif not has_index:
        return (
            f"[Onboarding] IMPORTANT: Project '{project}' has memories but no search index. "
            "You MUST run /wicked-garden:search:index now to build the search index."
        )
    return None


def _validate_and_repair_kanban_link(project_data, project_name, cp_available):
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
                if resolved_id != stored_id and project_name:
                    _repair_project_initiative(project_name, resolved_id)
                return True, resolved_id
        return False, None
    except Exception:
        # On any error, assume valid (don't block session on kanban failure)
        return True, project_data.get("kanban_initiative_id")


def _repair_project_initiative(project_name, initiative_id):
    """Update project.json with the correct initiative_id via StorageManager."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-crew", hook_mode=True)
        sm.update("projects", project_name, {"kanban_initiative_id": initiative_id})
    except Exception:
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
# Auto-start helpers (local-install mode)
# ---------------------------------------------------------------------------

def _get_viewer_path(config):
    """Resolve viewer_path from config with fallback to ~/Projects/wicked-viewer."""
    raw = config.get("viewer_path") or "~/Projects/wicked-viewer"
    return Path(raw).expanduser()


def _viewer_already_opened():
    """Return True if the browser was already opened this session."""
    flag = Path.home() / ".something-wicked" / "wicked-garden" / ".viewer_opened"
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    if not flag.exists():
        return False
    try:
        return flag.read_text().strip() == session_id
    except OSError:
        return False


def _mark_viewer_opened():
    """Write the session ID to the viewer-opened flag file."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    flag = Path.home() / ".something-wicked" / "wicked-garden" / ".viewer_opened"
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(session_id)
    except OSError:
        pass


def _autostart_viewer(viewer_path):
    """Launch PORT=18889 pnpm run dev in viewer_path as a detached process.

    Returns True if Popen succeeded, False otherwise.
    Does NOT wait for the server to be ready — caller polls separately.
    """
    if not viewer_path.exists():
        print(f"[wicked-garden] viewer_path {viewer_path} not found, cannot auto-start",
              file=sys.stderr)
        return False
    if not (viewer_path / "node_modules").exists():
        print(f"[wicked-garden] {viewer_path}/node_modules missing, run pnpm install first",
              file=sys.stderr)
        return False
    try:
        subprocess.Popen(
            ["pnpm", "run", "dev"],
            cwd=str(viewer_path),
            env={**os.environ, "PORT": "18889"},
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (FileNotFoundError, OSError) as exc:
        print(f"[wicked-garden] auto-start failed: {exc}", file=sys.stderr)
        return False


def _poll_health_with_timeout(endpoint, budget_seconds):
    """Poll CP health at endpoint until ok or budget exhausted.

    Polls every 0.5s. Returns (ok, version).
    """
    import urllib.request
    import urllib.error
    url = f"{endpoint.rstrip('/')}/health"
    deadline = time.monotonic() + budget_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                data = json.loads(resp.read().decode())
                if data.get("status") in ("ok", "healthy"):
                    return True, data.get("version", "")
        except Exception:
            pass
        time.sleep(0.5)
    return False, ""


def _open_browser_once(url):
    """Open url in the default browser, but only once per session."""
    if _viewer_already_opened():
        return
    try:
        webbrowser.open(url)
        _mark_viewer_opened()
    except Exception:
        pass


def _offline_storage_summary():
    """Return a formatted offline storage status string."""
    local_root = Path.home() / ".something-wicked" / "wicked-garden" / "local"
    queue_file = local_root / "_queue.jsonl"

    parts = [f"Storage: {local_root}"]

    if local_root.exists():
        domains = sorted(
            d.name for d in local_root.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        if domains:
            parts.append(f"Domains: {', '.join(domains)}")

    if queue_file.exists():
        try:
            count = sum(1 for line in queue_file.read_text().splitlines() if line.strip())
            if count > 0:
                parts.append(f"Queued writes: {count}")
        except OSError:
            pass

    return " | ".join(parts)


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

        # Determine mode (default: local-install for backward compat)
        mode = config.get("mode") or "local-install"
        if mode not in ("remote", "local-install", "offline"):
            mode = "local-install"

        # 2. Mode-branched initialization
        # All modes fall through to the shared briefing assembly — no early returns.
        cp_available = False
        cp_version = ""
        state = _load_session_state()
        mode_notes = []       # mode-specific briefing notes
        autostart_elapsed = 0.0

        if mode == "offline":
            # Offline mode: init local dirs, mark offline, opportunistic CP probe
            try:
                from _storage import get_local_path
                get_local_path("wicked-garden")  # ensure local root exists
            except Exception:
                pass

            if state is not None:
                state.update(
                    cp_available=False,
                    fallback_mode=True,
                    setup_complete=True,
                )

            # Storage summary for briefing
            mode_notes.append(f"[Offline] {_offline_storage_summary()}")

            # Opportunistic: check if a CP has appeared (1s timeout)
            endpoint = config.get("endpoint")
            if endpoint:
                probe_ok, probe_version = _check_health(config)
                if probe_ok:
                    mode_notes.append(
                        f"[Info] Control plane detected at {endpoint} (v{probe_version}). "
                        "Run /wicked-garden:setup to switch from offline to connected mode."
                    )

        elif mode == "remote":
            # Remote mode: CP required, report status
            endpoint = config.get("endpoint")
            if endpoint:
                cp_available, cp_version = _check_health(config)
            if not cp_available:
                if state is not None:
                    state.update(
                        cp_available=False,
                        fallback_mode=True,
                        setup_complete=True,
                    )
                mode_notes.append(
                    f"[Warning] Remote control plane at {endpoint or '(not configured)'} "
                    "is unreachable. Operating in offline fallback. "
                    "Run /wicked-garden:setup to reconfigure."
                )
            else:
                if state is not None:
                    state.update(
                        cp_available=True,
                        cp_version=cp_version,
                        fallback_mode=False,
                        setup_complete=True,
                    )

        else:
            # local-install mode (default): auto-start if CP not running
            endpoint = config.get("endpoint") or "http://localhost:18889"
            cp_available, cp_version = _check_health(config)

            if not cp_available:
                # Attempt auto-start
                viewer_path = _get_viewer_path(config)
                started = _autostart_viewer(viewer_path)
                if started:
                    t0 = time.monotonic()
                    cp_available, cp_version = _poll_health_with_timeout(
                        endpoint, budget_seconds=6.0
                    )
                    autostart_elapsed = time.monotonic() - t0

                    if cp_available:
                        _open_browser_once("http://localhost:5173")
                        mode_notes.append(
                            f"[Auto-start] Control plane started (v{cp_version}). "
                            "Dashboard opened in browser."
                        )
                    else:
                        mode_notes.append(
                            "[Warning] Auto-start initiated but control plane did not respond "
                            f"within {autostart_elapsed:.0f}s. Operating in offline fallback. "
                            "The server may still be starting — check http://localhost:18889/health"
                        )
                else:
                    mode_notes.append(
                        f"[Warning] Control plane at {endpoint} not running and auto-start "
                        "failed. Operating in offline fallback. "
                        "Run /wicked-garden:setup to reconfigure."
                    )
            else:
                # CP already running — open browser once per session
                _open_browser_once("http://localhost:5173")

            # Write session state
            if state is not None:
                state.update(
                    cp_available=cp_available,
                    cp_version=cp_version,
                    fallback_mode=not cp_available,
                    setup_complete=True,
                )

        # 3. Load dynamic agents
        agents_loaded = _load_agents(cp_available)
        if state is not None:
            state.update(agents_loaded=agents_loaded)

        # 4. Drain offline write queue (only when CP is available)
        if cp_available:
            _drain_queue()

        # 5 & 6. Load active crew project and kanban board summary (independent reads)
        project_data, project_name = _find_active_crew_project()
        kanban_summary = _load_kanban_summary()

        # 7. Run memory decay
        decay_summary = _run_memory_decay()

        # 8. Check onboarding status (search index + memories)
        onboarding_note = _check_onboarding_status()

        # 9. Assemble session briefing
        briefing_parts = [_MEMORY_INSTRUCTIONS]

        # Mode-specific notes
        for note in mode_notes:
            briefing_parts.append(note)

        if project_data:
            name = project_data.get("name", project_name or "unknown")
            phase = project_data.get("current_phase", "unknown")
            initiative_name = project_data.get("kanban_initiative") or name

            valid, resolved_id = _validate_and_repair_kanban_link(
                project_data, project_name, cp_available
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

        # Onboarding directive goes LAST for highest priority
        if onboarding_note:
            briefing_parts.append(onboarding_note)

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
