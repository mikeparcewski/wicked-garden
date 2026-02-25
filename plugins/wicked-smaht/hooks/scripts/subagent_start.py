#!/usr/bin/env python3
"""
wicked-smaht: SubagentStart hook.

Injects minimal orientation metadata into subagents so they know
WHERE to look for context, not WHAT the context is.

Output: ~50-100 tokens of pointers (project, task, session, phase).
Subagents pull actual content on demand via plugin APIs:
- TaskGet(taskId) for task details
- /wicked-mem:recall for decisions/constraints
- /wicked-search:code for code context
- context7 for library documentation
"""
import json
import os
import sys
import time
from pathlib import Path

# Add v2 scripts to path for HistoryCondenser access
V2_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_SCRIPTS_DIR))

# Only consider crew projects modified within the last 2 hours
MAX_PROJECT_AGE_SECONDS = 7200


def _safe_str(val, max_len: int = 120) -> str:
    """Safely convert value to string with length cap."""
    return str(val)[:max_len] if val else ""


def _get_crew_context() -> dict:
    """Get active crew project context if available."""
    crew_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not crew_dir.exists():
        return {}

    now = time.time()
    latest = None
    latest_mtime = 0
    for proj_json in crew_dir.glob("*/project.json"):
        try:
            mtime = proj_json.stat().st_mtime
            # Skip stale projects to avoid wrong-project injection
            if now - mtime > MAX_PROJECT_AGE_SECONDS:
                continue
            data = json.loads(proj_json.read_text())
            if data.get("current_phase"):
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest = data
        except Exception:
            continue

    if not latest:
        return {}

    # Sanitize: ensure all values are strings with caps
    signals = latest.get("signals_detected", [])
    if not isinstance(signals, list):
        signals = []

    return {
        "project": _safe_str(latest.get("name", ""), 64),
        "phase": _safe_str(latest.get("current_phase", ""), 30),
        "signals": [_safe_str(s, 30) for s in signals[:5]],
    }


def _get_session_pointers(session_id: str) -> dict:
    """Get lightweight session pointers from condenser state."""
    try:
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        state = condenser.get_session_state()

        pointers = {}
        if state.get("current_task"):
            pointers["current_task"] = state["current_task"][:120]
        if state.get("topics"):
            pointers["topics"] = state["topics"][:5]
        if state.get("file_scope"):
            pointers["active_files"] = state["file_scope"][-5:]
        return pointers
    except Exception:
        return {}


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")

    # Gather orientation metadata
    crew = _get_crew_context()
    session = _get_session_pointers(session_id)

    # Build compact orientation block with sanitized fields
    lines = []

    if crew.get("project"):
        lines.append(f"**Crew project**: {crew['project']} (phase: {crew.get('phase', '?')})")
    if crew.get("signals"):
        lines.append(f"**Signals**: {', '.join(crew['signals'])}")
    if session.get("current_task"):
        lines.append(f"**Parent task**: {_safe_str(session['current_task'], 120)}")
    if session.get("topics"):
        safe_topics = [_safe_str(t, 40) for t in session['topics'][:5]]
        lines.append(f"**Session topics**: {', '.join(safe_topics)}")
    if session.get("active_files"):
        safe_files = [_safe_str(f, 60) for f in session['active_files'][-5:]]
        lines.append(f"**Active files**: {', '.join(safe_files)}")

    # Add pull instructions
    lines.append("")
    lines.append("Use TaskGet/TaskList for task details, /wicked-mem:recall for decisions, /wicked-search:code for code context.")

    if not lines or len(lines) <= 2:
        # No meaningful context to inject
        print(json.dumps({"continue": True}))
        return

    context = "\n".join(lines)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": context,
        },
        "continue": True,
    }))


if __name__ == "__main__":
    main()
