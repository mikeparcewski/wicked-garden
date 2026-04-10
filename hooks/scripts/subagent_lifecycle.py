#!/usr/bin/env python3
"""
SubagentStart / SubagentStop hook — wicked-garden agent lifecycle tracking.

Issue #330: Track subagent start/stop events for observability and crew coordination.
Issue #365: Record specialist engagement for approve-command gate enforcement.

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
    - Record specialist engagement to phases/{phase}/specialist-engagement.json

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
# Specialist engagement tracking (Issue #365)
# ---------------------------------------------------------------------------

def _load_specialist_domains() -> set:
    """Return the set of specialist domain names from specialist.json.

    Reads .claude-plugin/specialist.json relative to CLAUDE_PLUGIN_ROOT.
    Returns an empty set on any error so the hook stays fail-open.
    """
    try:
        specialist_path = _PLUGIN_ROOT / ".claude-plugin" / "specialist.json"
        data = json.loads(specialist_path.read_text(encoding="utf-8"))
        return {s["name"] for s in data.get("specialists", []) if "name" in s}
    except Exception:
        return set()


def _parse_specialist_from_agent_type(agent_type: str, specialist_domains: set):
    """Parse domain and agent name from a wicked-garden subagent_type string.

    Expected format: ``wicked-garden:{domain}:{agent-name}``

    Returns ``(domain, agent_name)`` if the domain is a known specialist domain,
    otherwise returns ``(None, None)``.
    """
    if not agent_type or not agent_type.startswith("wicked-garden:"):
        return None, None

    parts = agent_type.split(":")
    # Expect at least 3 parts: "wicked-garden", domain, agent-name
    if len(parts) < 3:
        return None, None

    domain = parts[1]
    agent_name = ":".join(parts[2:])  # preserve any colons in agent name

    if domain not in specialist_domains:
        return None, None

    return domain, agent_name


def _record_specialist_engagement(domain: str, agent_name: str) -> None:
    """Append a specialist engagement entry to the active phase directory.

    Writes to:
        {project_dir}/phases/{current_phase}/specialist-engagement.json

    The file is a JSON array. If it does not exist it is created; if it
    exists the new entry is appended.  All errors are silently swallowed so
    the hook never blocks on I/O failures.
    """
    try:
        from _session import SessionState
        from _paths import get_local_path

        state = SessionState.load()

        # Resolve current phase — prefer the cached active_project dict, fall
        # back to loading the project state file directly.
        current_phase: str | None = None
        project_id: str | None = state.active_project_id

        if state.active_project and isinstance(state.active_project, dict):
            current_phase = state.active_project.get("current_phase")

        if not current_phase and project_id:
            try:
                import re
                if re.match(r'^[a-zA-Z0-9_-]{1,64}$', project_id):
                    base = get_local_path("wicked-crew", "projects")
                    project_json = base / project_id / "project.json"
                    if project_json.exists():
                        pdata = json.loads(project_json.read_text(encoding="utf-8"))
                        current_phase = pdata.get("current_phase")
            except Exception:
                pass

        if not current_phase or not project_id:
            # No active crew project — nothing to record
            return

        # Validate project_id before using it in a path
        import re
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', project_id):
            return

        base = get_local_path("wicked-crew", "projects")
        phase_dir = base / project_id / "phases" / current_phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        engagement_file = phase_dir / "specialist-engagement.json"

        # Load existing entries or start fresh
        entries: list = []
        if engagement_file.exists():
            try:
                entries = json.loads(engagement_file.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []

        entries.append({
            "domain": domain,
            "agent": agent_name,
            "completed_at": _now_iso(),
        })

        tmp_path = engagement_file.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        os.replace(tmp_path, engagement_file)

    except Exception as exc:
        print(f"[wicked-garden] specialist engagement record error: {exc}", file=sys.stderr)


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

    # Record specialist engagement (Issue #365)
    # subagent_type is the canonical identifier; agent_name may be a display name.
    agent_type = payload.get("subagent_type", agent_name)
    try:
        specialist_domains = _load_specialist_domains()
        domain, specialist_agent = _parse_specialist_from_agent_type(agent_type, specialist_domains)
        if domain is not None:
            _record_specialist_engagement(domain, specialist_agent)
    except Exception as exc:
        print(f"[wicked-garden] specialist engagement check error: {exc}", file=sys.stderr)


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
    output = {"continue": True}

    # Inject tool-discovery reminder for all agents on start
    if phase == "start":
        output["systemMessage"] = (
            "[Tool Discovery] Before claiming you cannot do something, "
            "review your available skills and tools. You have capabilities for "
            "browser automation, visual testing, accessibility auditing, "
            "API testing, code search, memory, and more. Use them."
        )

    print(json.dumps(output))


if __name__ == "__main__":
    main()
