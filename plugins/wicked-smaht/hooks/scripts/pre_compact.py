#!/usr/bin/env python3
"""
wicked-smaht: PreCompact hook.

PreCompact firing means the pressure system FAILED to prevent auto-compaction.
This is a bug — the pressure directives should have caused Claude to /compact
before Claude Code's auto-compaction kicked in.

This hook:
1. Captures diagnostic info about WHY pressure tracking didn't prevent this
2. Logs a structured bug report to stderr and session files
3. Still saves state and marks compaction (safety net)
4. Never blocks compaction
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

V2_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_SCRIPTS_DIR))


def _capture_diagnostics(session_id: str) -> dict:
    """Capture diagnostic info about why auto-compaction was needed."""
    diag = {
        "event": "unexpected_auto_compaction",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
    }

    # Pressure state at time of compaction
    try:
        from context_pressure import PressureTracker
        tracker = PressureTracker()
        diag["pressure"] = tracker.get_state_summary()
    except Exception as e:
        diag["pressure_error"] = str(e)

    # Session state
    try:
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        state = condenser.get_session_state()
        diag["session_topics"] = state.get("topics", [])[:5]
        diag["current_task"] = state.get("current_task", "")[:100]
        diag["file_scope_count"] = len(state.get("file_scope", []))
        diag["turn_count"] = state.get("turn_count", 0)
    except Exception as e:
        diag["session_error"] = str(e)

    return diag


def _save_diagnostic_report(session_id: str, diag: dict):
    """Save diagnostic report to session directory for later analysis."""
    try:
        session_dir = Path.home() / ".something-wicked" / "wicked-smaht" / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Append to compaction log (one per session, multiple events possible)
        log_path = session_dir / "compaction_bugs.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(diag) + "\n")
    except Exception:
        pass


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")

    # Capture diagnostics BEFORE saving state (get current pressure)
    diag = _capture_diagnostics(session_id)

    # Log the bug prominently
    pressure_info = diag.get("pressure", {})
    print(
        f"smaht: BUG — auto-compaction triggered at "
        f"pressure={pressure_info.get('level', '?')} "
        f"({pressure_info.get('cumulative_kb', '?')}KB), "
        f"turn={pressure_info.get('turn_count', '?')}. "
        f"Pressure directives should have prevented this. "
        f"Diagnostics saved to compaction_bugs.jsonl",
        file=sys.stderr
    )

    # Save diagnostic report for later analysis
    _save_diagnostic_report(session_id, diag)

    # Safety net: save condenser state so recovery briefing has data
    try:
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        condenser.save()
        condenser.persist_session_meta()
    except Exception as e:
        print(f"smaht: pre-compact save failed: {e}", file=sys.stderr)

    # Mark pressure tracker for recovery briefing on next prompt
    try:
        from context_pressure import PressureTracker
        tracker = PressureTracker()
        tracker.mark_compacted()
    except Exception as e:
        print(f"smaht: pre-compact pressure mark failed: {e}", file=sys.stderr)

    # Always continue — never block compaction
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
