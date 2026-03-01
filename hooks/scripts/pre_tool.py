#!/usr/bin/env python3
"""
PreToolUse hook — wicked-garden unified pre-tool dispatcher.

Consolidates: crew pretool_taskcreate, crew pretool_planmode, mem block_memory_md.

Dispatches by tool_name from hook payload:
  TaskCreate    → crew initiative metadata injection + one-time suggestion
  EnterPlanMode → deny and redirect to crew workflow
  Write / Edit  → MEMORY.md / AGENTS.md write guard

Always fails open — any unhandled exception returns permissionDecision: "allow".
"""

import json
import os
import sys
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _allow(updated_input=None, system_message=None) -> str:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    if updated_input is not None:
        output["hookSpecificOutput"]["updatedInput"] = updated_input
    if system_message:
        output["systemMessage"] = system_message
    return json.dumps(output)


def _deny(reason: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


# ---------------------------------------------------------------------------
# Handler: TaskCreate
# (inject crew initiative metadata, one-time crew suggestion)
# ---------------------------------------------------------------------------

def _find_active_crew_project():
    """Return (project_data_dict, project_name, kanban_initiative_name).

    Uses StorageManager exclusively — SM handles CP-first with local fallback.
    """
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-crew", hook_mode=True)
        projects = sm.list("projects") or []
        for p in sorted(projects, key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True):
            if p.get("archived"):
                continue
            phase = p.get("current_phase", "")
            if phase and phase not in ("complete", "done", ""):
                name = p.get("name", "")
                initiative = p.get("kanban_initiative") or name
                return p, name, initiative
    except Exception:
        pass

    return None, None, None


def _handle_task_create(tool_input: dict) -> str:
    """Inject crew initiative metadata into TaskCreate input."""
    _data, project_name, initiative_name = _find_active_crew_project()

    if project_name:
        metadata = tool_input.get("metadata") or {}
        if not metadata.get("initiative"):
            metadata["initiative"] = initiative_name
            tool_input["metadata"] = metadata
        return _allow(updated_input=tool_input)

    # No active project — show one-time suggestion via SessionState
    try:
        from _session import SessionState
        state = SessionState.load()
        if not state.task_suggest_shown:
            state.update(task_suggest_shown=True)
            return _allow(
                system_message="Creating tasks? Consider `/wicked-garden:crew:start` for quality gates."
            )
    except Exception:
        pass

    return _allow()


# ---------------------------------------------------------------------------
# Handler: EnterPlanMode
# (deny native plan mode, redirect to crew workflow)
# ---------------------------------------------------------------------------

def _handle_enter_plan_mode(tool_input: dict) -> str:
    """Block native plan mode — redirect to crew workflow instead.

    wicked-garden uses crew projects for planning, not Claude's built-in
    plan mode. Always deny and point to /wicked-garden:crew:start.
    """
    try:
        data, project_name, _ = _find_active_crew_project()
        if project_name and data:
            current_phase = data.get("current_phase", "")
            return _deny(
                f"Do not use native plan mode. A crew project '{project_name}' is already active "
                f"(phase: {current_phase}). Continue working within the crew workflow. "
                f"Use `/wicked-garden:crew:execute` to proceed or `/wicked-garden:crew:status` to check progress."
            )
    except Exception:
        pass

    return _deny(
        "Do not use native plan mode. This project uses wicked-garden crew workflows for planning. "
        "Use `/wicked-garden:crew:start` to create a new crew project with outcome clarification, "
        "phased execution, and quality gates."
    )


# ---------------------------------------------------------------------------
# Handler: Write / Edit
# (MEMORY.md and AGENTS.md write guard)
# ---------------------------------------------------------------------------

# Claude Code auto-memory directory pattern
_AUTO_MEMORY_MARKER = ".claude/projects/"


def _handle_write_guard(tool_input: dict) -> str:
    """Block direct writes to MEMORY.md, auto-memory directory, and AGENTS.md."""
    file_path = tool_input.get("file_path", "")

    # Block writes to AGENTS.md — cross-tool read-only file
    if file_path.lower().endswith("agents.md"):
        return _deny(
            "Do not write to AGENTS.md. It is a cross-tool agent instruction "
            "file shared with other AI coding tools (Codex, Cursor, Amp, etc.) "
            "and must remain read-only. Use CLAUDE.md for Claude-specific instructions."
        )

    # Block writes to MEMORY.md or Claude's auto-memory directory
    is_memory_md = file_path.endswith("MEMORY.md")
    is_auto_memory = _AUTO_MEMORY_MARKER in file_path and "/memory/" in file_path

    if is_memory_md or is_auto_memory:
        return _deny(
            "Do not write to MEMORY.md or the auto memory directory. "
            "This project uses wicked-garden memory for persistence. "
            "Use /wicked-garden:mem:store to save decisions, patterns, and gotchas instead."
        )

    return _allow()


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main():
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        print(_allow())
        return

    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}

        if tool_name == "TaskCreate":
            print(_handle_task_create(tool_input))
            return

        if tool_name == "EnterPlanMode":
            print(_handle_enter_plan_mode(tool_input))
            return

        if tool_name in ("Write", "Edit"):
            print(_handle_write_guard(tool_input))
            return

        # All other tools — allow
        print(_allow())

    except Exception as e:
        print(f"[wicked-garden] pre_tool error: {e}", file=sys.stderr)
        # Always fail open on error
        print(_allow())


if __name__ == "__main__":
    main()
