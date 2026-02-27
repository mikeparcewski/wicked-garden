#!/usr/bin/env python3
"""
PostToolUse hook for Task — records specialist subagent dispatches.

Tracks which specialist subagent_types were dispatched during the session.
This data is read by pretool_write_edit.py and phase_manager.py to enforce
specialist routing and orchestrator-only principles.

Always returns {"continue": true} — never blocks.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def get_session_file() -> Path:
    """Get path to session state file."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"wicked-crew-session-{session_id}.json"


def load_session_state() -> dict:
    """Load session state, returning empty state on any error."""
    try:
        return json.loads(get_session_file().read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return {"specialist_dispatches": [], "write_guard_warned": False}


def save_session_state(state: dict) -> None:
    """Save session state. Silently ignores errors."""
    try:
        get_session_file().write_text(json.dumps(state))
    except OSError:
        pass


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        tool_input = input_data.get("tool_input", {})

        # Extract subagent_type from Task dispatch
        subagent_type = tool_input.get("subagent_type", "")
        if not subagent_type:
            print(json.dumps({"continue": True}))
            return

        # Extract plugin name (first segment before ':')
        plugin = subagent_type.split(":")[0] if ":" in subagent_type else subagent_type

        # Record the dispatch
        state = load_session_state()
        state.setdefault("specialist_dispatches", []).append({
            "subagent_type": subagent_type,
            "plugin": plugin,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        save_session_state(state)

        print(json.dumps({"continue": True}))

    except Exception:
        # Never block on errors
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
