#!/usr/bin/env python3
"""
PreToolUse hook — wicked-garden unified pre-tool dispatcher.

Consolidates: crew pretool_taskcreate, crew pretool_planmode, mem block_memory_md.

Dispatches by tool_name from hook payload:
  TaskCreate    → crew initiative metadata injection + one-time suggestion
  EnterPlanMode → crew phase validation (gate check)
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
    """Return (project_name, kanban_initiative_name) for most recently modified active project."""
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return None, None

    # Prefer project.json (has kanban fields)
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
                name = data.get("name") or pf.parent.name
                initiative = data.get("kanban_initiative") or name
                return name, initiative
        except (json.JSONDecodeError, OSError):
            continue

    # Fallback: project.md frontmatter
    for pf in sorted(
        projects_dir.glob("*/project.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            content = pf.read_text()
            if "status: active" in content.lower():
                for line in content.split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                        if name:
                            return name, name
        except OSError:
            continue

    return None, None


def _handle_task_create(tool_input: dict) -> str:
    """Inject crew initiative metadata into TaskCreate input."""
    project_name, initiative_name = _find_active_crew_project()

    if project_name:
        metadata = tool_input.get("metadata") or {}
        if not metadata.get("initiative"):
            metadata["initiative"] = initiative_name
            tool_input["metadata"] = metadata
        return _allow(updated_input=tool_input)

    # No active project — show one-time suggestion
    flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
    if not flag.exists():
        try:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch()
        except OSError:
            pass
        return _allow(
            system_message="Creating tasks? Consider `/wicked-garden:crew-start` for quality gates."
        )

    return _allow()


# ---------------------------------------------------------------------------
# Handler: EnterPlanMode
# (crew phase validation gate)
# ---------------------------------------------------------------------------

def _handle_enter_plan_mode(tool_input: dict) -> str:
    """Validate that entering plan mode is appropriate for the current crew phase.

    If a crew project is active and the current phase requires a gate, remind
    the user to run the gate command first. Non-blocking — always allows.
    """
    try:
        project_name, _ = _find_active_crew_project()
        if not project_name:
            return _allow()

        projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
        project_file = None
        for pf in sorted(
            projects_dir.glob("*/project.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(pf.read_text())
                if data.get("name") == project_name and not data.get("archived"):
                    project_file = pf
                    break
            except (json.JSONDecodeError, OSError):
                continue

        if not project_file:
            return _allow()

        data = json.loads(project_file.read_text())
        current_phase = data.get("current_phase", "")
        gate_required = data.get("gate_required", False)

        if gate_required and current_phase:
            return _allow(
                system_message=(
                    f"[Crew] Phase '{current_phase}' requires a gate review before proceeding. "
                    f"Run `/wicked-garden:crew-gate` to complete the gate."
                )
            )

    except Exception:
        pass

    return _allow()


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
            "Use /wicked-garden:mem-store to save decisions, patterns, and gotchas instead."
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
