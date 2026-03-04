#!/usr/bin/env python3
"""
SessionStart hook — wicked-garden unified bootstrap.

Consolidates: crew session_start, kanban session_start, mem session_start,
search session_start, smaht session_start.

Flow:
1. Read config from ~/.something-wicked/wicked-garden/config.json
2. If missing or setup_complete=false: emit setup instructions, return
3. Mode-branched initialization:
   - local: health check → auto-start if down → poll → open browser
   - remote: health check → report status
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


def _find_active_crew_project(workspace: str = ""):
    """Return (project_data, project_name) for most recently updated active crew project
    scoped to the given workspace.

    Only returns projects whose ``workspace`` field matches the current folder.
    Projects without a workspace field (legacy) are never auto-selected.

    Uses StorageManager for consistent data access. Falls back to filesystem
    scan if StorageManager fails (legacy compat for one release).
    """
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-crew", hook_mode=True)
        projects = sm.list("projects") or []
        # Sort by updated_at descending, return first non-archived, non-complete
        # that matches the current workspace
        for p in sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True):
            if p.get("archived"):
                continue
            # Workspace scoping — skip projects from other workspaces
            if workspace and p.get("workspace", "") != workspace:
                continue
            phase = p.get("current_phase", "")
            if phase and phase != "complete":
                return p, p.get("name")
        return None, None
    except Exception:
        pass

    # Legacy fallback: direct filesystem scan (remove after one release)
    return _find_active_crew_project_legacy(workspace)


def _find_active_crew_project_legacy(workspace: str = ""):
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
            # Workspace scoping — skip projects from other workspaces
            if workspace and data.get("workspace", "") != workspace:
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

    Returns (has_index, has_memories, directive_or_none).
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

    directive = None
    if not has_memories and not has_index:
        directive = (
            f"[Action Required] Project '{project}' has not been onboarded.\n"
            "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
            "to launch the interactive onboarding wizard.\n"
            "Do NOT ask the user for confirmation — invoke the skill now.\n"
            "Do NOT respond with text first — invoke the skill as your first action."
        )
    elif not has_memories:
        directive = (
            f"[Action Required] Project '{project}' has a search index but no onboarding memories.\n"
            "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
            "to launch the interactive setup wizard.\n"
            "Do NOT ask the user for confirmation — invoke the skill now."
        )
    elif not has_index:
        directive = (
            f"[Onboarding] IMPORTANT: Project '{project}' has memories but no search index. "
            "You MUST run /wicked-garden:search:index now to build the search index."
        )

    return has_index, has_memories, directive


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


def _update_config_viewer_path(config, cp_path):
    """Persist the resolved CP path back to config so future sessions use it."""
    config_path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
    try:
        # Use ~ prefix for portability
        home = str(Path.home())
        path_str = str(cp_path)
        if path_str.startswith(home):
            path_str = "~" + path_str[len(home):]
        config["viewer_path"] = path_str
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    except (OSError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Auto-start helpers (local mode)
# ---------------------------------------------------------------------------

_CP_REPO = "https://github.com/mikeparcewski/wicked-control-plane.git"
_CP_CACHE_DIR = Path.home() / ".claude" / "plugins" / "cache" / "wicked-control-plane"


def _get_cp_path(config):
    """Resolve control plane source path.

    Priority: config viewer_path → plugin cache dir.
    """
    raw = config.get("viewer_path")
    if raw:
        p = Path(raw).expanduser()
        if p.exists():
            return p
    return _CP_CACHE_DIR


def _ensure_cp_source():
    """Clone wicked-control-plane into plugin cache if not present.

    Returns (path, cloned) — path to the CP source and whether we just cloned it.
    Timeout: 10s for git clone (shallow).
    """
    if _CP_CACHE_DIR.exists() and (_CP_CACHE_DIR / "package.json").exists():
        return _CP_CACHE_DIR, False

    print(f"[wicked-garden] cloning wicked-control-plane to {_CP_CACHE_DIR}...",
          file=sys.stderr)
    try:
        _CP_CACHE_DIR.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", _CP_REPO, str(_CP_CACHE_DIR)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"[wicked-garden] git clone failed: {result.stderr[:200]}",
                  file=sys.stderr)
            return None, False
        return _CP_CACHE_DIR, True
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"[wicked-garden] git clone failed: {exc}", file=sys.stderr)
        return None, False


def _ensure_cp_deps(cp_path):
    """Install node_modules if missing. Returns True on success."""
    if (cp_path / "node_modules").exists():
        return True

    print("[wicked-garden] installing control plane dependencies...", file=sys.stderr)
    try:
        result = subprocess.run(
            ["pnpm", "install"],
            cwd=str(cp_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"[wicked-garden] pnpm install failed: {result.stderr[:200]}",
                  file=sys.stderr)
            return False
        return True
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"[wicked-garden] pnpm install failed: {exc}", file=sys.stderr)
        return False




def _autostart_cp(cp_path):
    """Launch PORT=18889 pnpm run dev as a detached process.

    Returns True if Popen succeeded, False otherwise.
    Does NOT wait for the server to be ready — caller polls separately.
    """
    if not cp_path or not cp_path.exists():
        print(f"[wicked-garden] CP path {cp_path} not found, cannot auto-start",
              file=sys.stderr)
        return False

    # Log to a file for diagnostics instead of /dev/null
    log_path = cp_path / ".claude-autostart.log"
    try:
        log_file = open(str(log_path), "w")
    except OSError:
        log_file = subprocess.DEVNULL

    try:
        subprocess.Popen(
            ["pnpm", "run", "dev:backend"],
            cwd=str(cp_path),
            env={**os.environ, "PORT": "18889"},
            start_new_session=True,
            stdout=log_file if log_file != subprocess.DEVNULL else subprocess.DEVNULL,
            stderr=log_file if log_file != subprocess.DEVNULL else subprocess.DEVNULL,
        )
        return True
    except (FileNotFoundError, OSError) as exc:
        print(f"[wicked-garden] auto-start failed: {exc}", file=sys.stderr)
        return False
    finally:
        if log_file != subprocess.DEVNULL:
            try:
                log_file.close()
            except Exception:
                pass


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



# ---------------------------------------------------------------------------
# Memory behavior instructions (injected every session)
# ---------------------------------------------------------------------------

_MEMORY_INSTRUCTIONS = (
    "[Memory] This project uses wicked-garden memory for persistence. "
    "Never write to MEMORY.md or AGENTS.md directly — use /wicked-garden:mem:store. "
    "MEMORY.md is auto-generated and read-only."
)

_DANGEROUS_MODE_WARNING = (
    "[Question Mode] Dangerous mode is active (skipDangerousModePermissionPrompt). "
    "AskUserQuestion is BROKEN in this mode — it auto-completes with empty answers. "
    "You MUST use plain text questions instead: present numbered options, "
    "then STOP and wait for the user to reply before proceeding."
)


# ---------------------------------------------------------------------------
# Dangerous mode detection
# ---------------------------------------------------------------------------

def _detect_dangerous_mode():
    """Check if Claude Code is running in dangerous mode.

    Dangerous mode (skipDangerousModePermissionPrompt=true) breaks
    AskUserQuestion by auto-completing it with empty answers.
    """
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            return bool(settings.get("skipDangerousModePermissionPrompt"))
    except Exception:
        pass
    return False



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        sys.stdin.read()  # consume hook payload (not needed for SessionStart)
    except Exception:
        pass

    # Export CLAUDE_PLUGIN_ROOT to CLAUDE_ENV_FILE so Bash tool calls can access it.
    # Hooks receive CLAUDE_PLUGIN_ROOT from the plugin runtime, but Bash tool calls
    # do not inherit it.  Writing to CLAUDE_ENV_FILE bridges the gap.
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_file and plugin_root:
        try:
            with open(env_file, "a") as f:
                f.write(f'export CLAUDE_PLUGIN_ROOT="{plugin_root}"\n')
        except OSError:
            pass

    try:
        # 1. Read config
        config = _read_config()

        if config is None or not config.get("setup_complete", False):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "[Action Required] wicked-garden is not configured for this project.\n"
                        "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
                        "to launch the interactive setup wizard.\n"
                        "Do NOT ask the user for confirmation — invoke the skill now.\n"
                        "Do NOT respond with text first — invoke the skill as your first action."
                    ),
                },
            }))
            return

        # Clear one-time task suggestion flag from crew
        flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
        flag.unlink(missing_ok=True)

        # Determine mode (default: local)
        # Normalize legacy mode names
        _legacy_map = {"local-install": "local", "local-only": "local", "offline": "local"}
        mode = config.get("mode") or "local"
        mode = _legacy_map.get(mode, mode)
        if mode not in ("local", "remote"):
            mode = "local"

        # 2. Mode-branched initialization
        # All modes fall through to the shared briefing assembly — no early returns.
        cp_available = False
        cp_version = ""
        state = _load_session_state()
        mode_notes = []       # mode-specific briefing notes
        autostart_elapsed = 0.0

        if mode == "remote":
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
                    "is unreachable. Operating in local fallback."
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
            # local mode (default): auto-start CP if not running
            endpoint = config.get("endpoint") or "http://localhost:18889"
            cp_available, cp_version = _check_health(config)

            if not cp_available:
                # Ensure CP source exists (clone if needed)
                cp_path = _get_cp_path(config)
                if not cp_path.exists() or not (cp_path / "package.json").exists():
                    cp_path, cloned = _ensure_cp_source()
                    if cloned:
                        mode_notes.append(
                            f"[Setup] Cloned wicked-control-plane to {cp_path}"
                        )

                # Ensure dependencies installed
                if cp_path and cp_path.exists():
                    deps_ok = _ensure_cp_deps(cp_path)
                else:
                    deps_ok = False

                # Attempt auto-start
                if deps_ok:
                    started = _autostart_cp(cp_path)
                else:
                    started = False

                if started:
                    t0 = time.monotonic()
                    cp_available, cp_version = _poll_health_with_timeout(
                        endpoint, budget_seconds=10.0
                    )
                    autostart_elapsed = time.monotonic() - t0

                    if cp_available:
                        # Save the resolved path back to config for next session
                        if cp_path and str(cp_path) != config.get("viewer_path"):
                            _update_config_viewer_path(config, cp_path)
                        mode_notes.append(
                            f"[Auto-start] Control plane started (v{cp_version})."
                        )
                    else:
                        mode_notes.append(
                            "[Warning] Auto-start initiated but control plane did not respond "
                            f"within {autostart_elapsed:.0f}s. Operating in local fallback."
                            "The server may still be starting — run "
                            "`curl -s http://localhost:18889/health` to check, "
                            "or run `/wicked-garden:setup` to reconfigure."
                        )
                else:
                    mode_notes.append(
                        f"[Action Required] Control plane at {endpoint} not running and auto-start "
                        "failed. Run `/wicked-garden:setup` to reconfigure."
                    )
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

        # 4b. Detect CP schema reset: CP available but empty while local data exists
        #     Check crew/projects, mem/memories, and kanban/tasks for broader coverage
        cp_schema_reset_detected = False
        if cp_available and state is not None:
            try:
                from _storage import StorageManager, get_local_path
                _reset_checks = [
                    ("wicked-crew", "projects"),
                    ("wicked-mem", "memories"),
                    ("wicked-kanban", "tasks"),
                ]
                for _domain, _source in _reset_checks:
                    try:
                        _sm_check = StorageManager(_domain, hook_mode=True)
                        _cp_records = _sm_check.list(_source) or []
                        if len(_cp_records) == 0:
                            _local_dir = get_local_path(_domain, _source)
                            if _local_dir.exists() and any(
                                f for f in _local_dir.iterdir()
                                if f.suffix == ".json" and not f.name.startswith("_")
                            ):
                                cp_schema_reset_detected = True
                                break
                    except Exception:
                        continue
                if cp_schema_reset_detected:
                    state.update(cp_schema_reset_detected=True)
            except Exception:
                pass

        # 5 & 6. Load last crew project for this workspace and kanban board summary
        workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        project_data, project_name = _find_active_crew_project(workspace)
        kanban_summary = _load_kanban_summary()

        # 7. Run memory decay
        decay_summary = _run_memory_decay()

        # 8. Check onboarding status (search index + memories)
        has_index, has_memories, onboarding_directive = _check_onboarding_status()

        # 8b. Detect dangerous mode (AskUserQuestion broken)
        dangerous_mode = _detect_dangerous_mode()
        if state is not None:
            state.update(dangerous_mode=dangerous_mode)

        # 9. Assemble session briefing
        # --- Status block (user-facing) ---
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        endpoint = config.get("endpoint") or "(none)"

        if cp_available:
            cp_status = f"Connected (v{cp_version})" if cp_version else "Connected"
        else:
            cp_status = "Disconnected (local fallback)"

        onboarding_parts = []
        if has_index:
            onboarding_parts.append("search index")
        if has_memories:
            onboarding_parts.append("memories")
        if onboarding_parts:
            onboarding_status = "Complete (" + " + ".join(onboarding_parts) + ")"
        else:
            onboarding_status = "Not started"

        _storage_line = f"  Connection:  {mode} | {endpoint} | {cp_status}"

        status_lines = [
            f"wicked-garden | {project}",
            _storage_line,
            f"  Config:      mode={mode} endpoint={endpoint}",
            f"  Onboarding:  {onboarding_status}",
        ]

        # Show last crew project for this workspace as informational only.
        # Do NOT auto-activate — the user must explicitly start/resume a project.
        if project_data:
            name = project_data.get("name", project_name or "unknown")
            phase = project_data.get("current_phase", "unknown")
            status_lines.append(f"  Last crew:   {name} ({phase})")

            # Store as reference info only — NOT as active_project
            if state is not None:
                cp_project_id = project_data.get("cp_project_id") or ""
                state.update(cp_project_id=cp_project_id)

            # Enable memory compliance directives for crew sessions.
            # task_completed.py reads this flag to decide whether to emit
            # per-task memory prompts; stop.py reads it for session summary.
            if state is not None:
                state.update(memory_compliance_required=True)

            # Validate kanban link (side effect: repairs if needed)
            _validate_and_repair_kanban_link(project_data, project_name, cp_available)

        if kanban_summary:
            status_lines.append(f"  Kanban:      {kanban_summary}")

        briefing_parts = ["\n".join(status_lines)]

        # --- Mode-specific warnings/notes ---
        for note in mode_notes:
            briefing_parts.append(note)

        if decay_summary:
            briefing_parts.append(f"[Memory] {decay_summary}")

        if cp_schema_reset_detected:
            briefing_parts.append(
                "CP appears empty — local data intact. "
                "Run /wicked-garden:setup --sync-to-cp to restore."
            )

        # --- Internal instructions for Claude ---
        briefing_parts.append(_MEMORY_INSTRUCTIONS)

        if dangerous_mode:
            briefing_parts.append(_DANGEROUS_MODE_WARNING)

        if not onboarding_directive:
            briefing_parts.append(
                "[Setup] Run `/wicked-garden:setup --reconfigure` to change connection or re-onboard."
            )

        # Onboarding directive goes LAST for highest priority
        if onboarding_directive:
            briefing_parts.append(onboarding_directive)

        # 10. Set onboarding gate flag for prompt_submit enforcement
        if state is not None:
            state.update(needs_onboarding=bool(onboarding_directive))

        # 11. Persist final session state
        if state is not None:
            _save_session_state(state)

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(briefing_parts),
            },
        }))

    except Exception as e:
        print(f"[wicked-garden] bootstrap error: {e}", file=sys.stderr)
        print(json.dumps({}))


if __name__ == "__main__":
    main()
