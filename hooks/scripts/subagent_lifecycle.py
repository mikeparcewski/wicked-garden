#!/usr/bin/env python3
"""
SubagentStart / SubagentStop hook — wicked-garden agent lifecycle tracking.

Issue #330: Track subagent start/stop events for observability and crew coordination.

Receives the lifecycle phase as the first CLI argument ("start" or "stop").
Reads the hook payload from stdin (JSON with agent metadata).

Responsibilities:
  SubagentStart:
    - Log agent launch to ops logger
    - Track active subagent count in session state
    - Record agent start time for duration tracking
  SubagentStop:
    - Log agent completion to ops logger
    - Decrement active subagent count
    - Calculate and record duration
    - Write trace entry for the subagent execution

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add shared scripts directory to path
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_session_id(raw: str) -> str:
    """Strip path separators and traversal sequences from session ID."""
    sanitized = raw.replace("/", "_").replace("\\", "_").replace("..", "_")
    return sanitized if sanitized else "default"


def _get_session_id() -> str:
    return _sanitize_session_id(os.environ.get("CLAUDE_SESSION_ID", "default"))


# ---------------------------------------------------------------------------
# Trace writer — append JSONL to session trace file
# ---------------------------------------------------------------------------

def _write_trace(entry: dict) -> None:
    """Append a trace entry to the session JSONL trace file."""
    try:
        import tempfile
        session_id = _get_session_id()
        trace_dir = Path(tempfile.gettempdir()) / "wicked-garden" / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = trace_dir / f"{session_id}.jsonl"
        with open(trace_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Handler: SubagentStart
# ---------------------------------------------------------------------------

def _handle_start(payload: dict) -> None:
    """Track a subagent starting."""
    agent_name = payload.get("agent_name", payload.get("subagent_type", "unknown"))
    agent_id = payload.get("agent_id", "")

    _log("subagent", "normal", "subagent.start",
         detail={"agent": agent_name, "agent_id": agent_id})

    # Track in session state
    try:
        from _session import SessionState
        state = SessionState.load()
        active_agents = state.active_subagents or {}
        active_agents[agent_id or agent_name] = {
            "name": agent_name,
            "started_at": _now_iso(),
            "started_mono": time.monotonic(),
        }
        active_count = state.active_subagent_count or 0
        state.update(
            active_subagents=active_agents,
            active_subagent_count=active_count + 1,
            total_subagents_launched=(state.total_subagents_launched or 0) + 1,
        )
    except Exception:
        pass

    # Write trace entry
    _write_trace({
        "event": "subagent_start",
        "agent_name": agent_name,
        "agent_id": agent_id,
        "timestamp": _now_iso(),
        "session_id": _get_session_id(),
    })


# ---------------------------------------------------------------------------
# Handler: SubagentStop
# ---------------------------------------------------------------------------

def _handle_stop(payload: dict) -> None:
    """Track a subagent stopping."""
    agent_name = payload.get("agent_name", payload.get("subagent_type", "unknown"))
    agent_id = payload.get("agent_id", "")

    # Calculate duration from session state
    duration_ms = None
    try:
        from _session import SessionState
        state = SessionState.load()
        active_agents = state.active_subagents or {}
        agent_key = agent_id or agent_name

        if agent_key in active_agents:
            started_mono = active_agents[agent_key].get("started_mono")
            if started_mono is not None:
                duration_ms = int((time.monotonic() - started_mono) * 1000)
            del active_agents[agent_key]

        active_count = max(0, (state.active_subagent_count or 1) - 1)
        state.update(
            active_subagents=active_agents,
            active_subagent_count=active_count,
        )
    except Exception:
        pass

    _log("subagent", "normal", "subagent.stop",
         ms=duration_ms,
         detail={"agent": agent_name, "agent_id": agent_id})

    # Write trace entry
    _write_trace({
        "event": "subagent_stop",
        "agent_name": agent_name,
        "agent_id": agent_id,
        "duration_ms": duration_ms,
        "timestamp": _now_iso(),
        "session_id": _get_session_id(),
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Determine phase from CLI argument
    phase = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        if phase == "start":
            _handle_start(payload)
        elif phase == "stop":
            _handle_stop(payload)
        else:
            _log("subagent", "warn", "subagent.unknown_phase",
                 detail={"phase": phase})
    except Exception as e:
        print(f"[wicked-garden] subagent_lifecycle error: {e}", file=sys.stderr)

    # Always succeed — lifecycle tracking should never block
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
