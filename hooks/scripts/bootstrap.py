#!/usr/bin/env python3
"""
SessionStart hook — wicked-garden unified bootstrap.

Consolidates: crew session_start, kanban session_start, mem session_start,
search session_start, smaht session_start.

Flow:
1. Read config from ~/.something-wicked/wicked-garden/config.json
2. If missing or setup_complete=false: emit setup instructions, return
3. Load dynamic agents
4. Load active crew project + kanban summary
5. Run memory decay
6. Check onboarding status → imperative directive if needed
7. Assemble session briefing
8. Return {"continue": true, "systemMessage": "<briefing>"}

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
# Ops logger wrapper — fail-silent, never crashes the hook
# ---------------------------------------------------------------------------

def _log(domain, level, event, ok=True, ms=None, detail=None):
    """Ops logger — fail-silent, never crashes the hook."""
    try:
        from _logger import log
        log(domain, level, event, ok=ok, ms=ms, detail=detail)
    except Exception:
        pass


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


def _load_agents():
    """Load dynamic agents from disk. Returns agent count."""
    try:
        from _agents import AgentLoader
        loader = AgentLoader()
        loader.load_disk_agents(_PLUGIN_ROOT / "agents")
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

    Uses DomainStore for consistent data access. Falls back to filesystem
    scan if DomainStore fails (legacy compat for one release).
    """
    try:
        from _domain_store import DomainStore
        ds = DomainStore("wicked-crew", hook_mode=True)
        projects = ds.list("projects") or []
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
        from _domain_store import DomainStore
        ds = DomainStore("wicked-kanban", hook_mode=True)
        tasks = ds.list("tasks", status="in_progress") or []
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


def _check_search_staleness():
    """Detect stale search index via watcher.py and trigger an incremental reindex.

    Runs `watcher.py check --reindex --json` via subprocess against the directories
    that are already indexed in the SQLite DB (falling back to cwd).

    Returns a briefing note string, or None to skip (no index, not stale, or error).
    Fails open — any exception returns None so the session always continues.
    """
    try:
        import sqlite3

        db_path = Path.home() / ".something-wicked" / "wicked-search" / "unified_search.db"
        if not db_path.exists():
            return None  # No index yet — nothing to check

        # --- Discover indexed directories from the DB ---
        indexed_dirs = []
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
            try:
                tables = [
                    row[0] for row in
                    conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                ]
                _FILE_COLS = {"file", "path", "file_path", "filepath"}
                seen_roots = set()
                for table in tables:
                    cols = [
                        row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                    ]
                    for col in cols:
                        if col in _FILE_COLS:
                            rows = conn.execute(
                                f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT 500'
                            ).fetchall()
                            for (fpath,) in rows:
                                if fpath:
                                    p = Path(fpath)
                                    # Walk up to find a plausible root (first existing ancestor)
                                    candidate = p if p.is_dir() else p.parent
                                    if str(candidate) not in seen_roots and candidate.exists():
                                        seen_roots.add(str(candidate))
                # Collapse to top-level roots (remove subdirs already covered by a parent)
                sorted_roots = sorted(seen_roots)
                for root in sorted_roots:
                    if not any(root.startswith(other + os.sep) for other in sorted_roots if other != root):
                        indexed_dirs.append(root)
            finally:
                conn.close()
        except Exception:
            pass  # DB read failed — fall back to cwd

        if not indexed_dirs:
            indexed_dirs = [str(Path.cwd())]

        # --- Invoke watcher.py check --reindex --json ---
        watcher_script = str(_PLUGIN_ROOT / "scripts" / "search" / "watcher.py")
        cmd = [
            "uv", "run", "python", watcher_script,
            "check", "--reindex", "--json",
            "--dirs", *indexed_dirs,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(_PLUGIN_ROOT),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        data = json.loads(result.stdout)
        if not data.get("stale"):
            return None  # Up to date — nothing to report

        changed_count = data.get("changed_count", 0)
        reindex_ok = data.get("reindex_ok")  # May be absent if reindex wasn't triggered

        if reindex_ok is True:
            return f"Search index auto-updated ({changed_count} file(s) changed)"
        elif reindex_ok is False:
            return f"Search index may be stale — {changed_count} file(s) changed but reindex failed"
        else:
            # Stale but reindex wasn't run (shouldn't happen with --reindex flag, but be safe)
            return f"Search index may be stale — {changed_count} file(s) changed"

    except Exception:
        return None  # Always fail-open


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
    if not has_memories:
        directive = (
            f"[Action Required] Project '{project}' has not been onboarded.\n"
            "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
            "to launch the interactive onboarding wizard.\n"
            "Do NOT ask the user for confirmation — invoke the skill now.\n"
            "Do NOT respond with text first — invoke the skill as your first action."
        )
    elif not has_index:
        directive = (
            f"[Onboarding] IMPORTANT: Project '{project}' has memories but no search index. "
            "You MUST run /wicked-garden:search:index now to build the search index."
        )

    return has_index, has_memories, directive


def _validate_and_repair_kanban_link(project_data, project_name):
    """Validate that the crew project's kanban initiative still exists.

    Returns (valid, resolved_id).
    """
    initiative_name = project_data.get("kanban_initiative") or project_data.get("name")
    if not initiative_name:
        return False, None

    try:
        from _domain_store import DomainStore
        ds = DomainStore("wicked-kanban", hook_mode=True)
        initiatives = ds.list("initiatives") or []
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
    """Update project.json with the correct initiative_id via DomainStore."""
    try:
        from _domain_store import DomainStore
        ds = DomainStore("wicked-crew", hook_mode=True)
        ds.update("projects", project_name, {"kanban_initiative_id": initiative_id})
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
    _t0 = time.monotonic()
    _log("bootstrap", "debug", "hook.start")

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

        # 2. Load session state
        state = _load_session_state()
        if state is not None:
            state.update(
                setup_complete=True,
            )

        _log("bootstrap", "normal", "storage.local", ok=True)

        # 3. Load dynamic agents
        agents_loaded = _load_agents()
        if state is not None:
            state.update(agents_loaded=agents_loaded)

        # 4 & 5. Load last crew project for this workspace and kanban board summary
        workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        project_data, project_name = _find_active_crew_project(workspace)
        kanban_summary = _load_kanban_summary()

        # 6. Run memory decay
        decay_summary = _run_memory_decay()

        # 6b. Check search index staleness and auto-reindex if needed
        search_staleness_note = _check_search_staleness()
        mode_notes = []
        if search_staleness_note:
            mode_notes.append(f"[Search] {search_staleness_note}")

        # 7. Check onboarding status (search index + memories)
        has_index, has_memories, onboarding_directive = _check_onboarding_status()
        _log("bootstrap", "normal", "onboarding.status",
             ok=(has_memories and has_index),
             detail={"has_memories": has_memories, "has_index": has_index})

        # 7b. Detect dangerous mode (AskUserQuestion broken)
        dangerous_mode = _detect_dangerous_mode()
        if state is not None:
            state.update(dangerous_mode=dangerous_mode)

        # 8. Assemble session briefing
        # --- Status block (user-facing) ---
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name

        onboarding_parts = []
        if has_index:
            onboarding_parts.append("search index")
        if has_memories:
            onboarding_parts.append("memories")
        if onboarding_parts:
            onboarding_status = "Complete (" + " + ".join(onboarding_parts) + ")"
        else:
            onboarding_status = "Not started"

        status_lines = [
            f"wicked-garden | {project}",
            "  Storage:     local",
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
                # active_project_id: only set when project is in a non-complete, non-skipped phase
                active_phase = project_data.get("current_phase", "")
                is_active = active_phase not in ("", "complete", "done", "archived")
                state.update(active_project_id=project_name if is_active else None)

            # Enable memory compliance directives for crew sessions.
            # task_completed.py reads this flag to decide whether to emit
            # per-task memory prompts; stop.py reads it for session summary.
            if state is not None:
                state.update(memory_compliance_required=True)

            # Validate kanban link (side effect: repairs if needed)
            _validate_and_repair_kanban_link(project_data, project_name)

        if kanban_summary:
            status_lines.append(f"  Kanban:      {kanban_summary}")

        briefing_parts = ["\n".join(status_lines)]

        # --- Mode-specific warnings/notes ---
        for note in mode_notes:
            briefing_parts.append(note)

        if decay_summary:
            briefing_parts.append(f"[Memory] {decay_summary}")

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

        # 9. Set onboarding gate flag for prompt_submit enforcement
        if state is not None:
            state.update(
                needs_onboarding=bool(onboarding_directive),
                onboarding_complete=(has_memories and has_index),
            )

        # 10. Persist final session state
        if state is not None:
            _save_session_state(state)

        _log("bootstrap", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
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
