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


# Map from task metadata.event_type to procedure bundle injected at SubagentStart
_EVENT_TYPE_PROCEDURES: dict = {
    "coding-task": (
        "[Bulletproof Coding Standards] R1: No dead code. R2: No bare panics — "
        "all errors handled and logged. R3: No magic values — use named constants. "
        "R4: No swallowed errors — propagate or log with context. "
        "R5: No unbounded ops — all loops/queries have limits. "
        "R6: No god functions — max 50 lines, single responsibility."
    ),
    "gate-finding": (
        "[Gate Finding Protocol] Document the finding with: what was observed, "
        "what standard was violated, severity (BLOCK/WARN/INFO), and suggested fix. "
        "Reference the specific requirement or quality rule that applies."
    ),
    "phase-transition": (
        "[Phase Transition Protocol] Verify all gate conditions are met before "
        "advancing. Write a transition summary: what was completed, what evidence "
        "exists, what the next phase expects as input."
    ),
    "subtask": (
        "[Subtask Execution] You are executing a subtask. Scope is narrow — "
        "complete exactly what was assigned. Report back with structured output: "
        "what was done, what evidence exists, any blockers found."
    ),
    "procedure-trigger": (
        "[Procedure Execution] Follow the procedure exactly as specified. "
        "Do not improvise or skip steps. Record each step's outcome."
    ),
}


# ---------------------------------------------------------------------------
# Active task event_type reader — routed via _task_reader (#596 v8-PR-2)
# ---------------------------------------------------------------------------
#
# WG_DAEMON_ENABLED=false (default): direct file read, bit-identical to pre-PR-2.
# WG_DAEMON_ENABLED=true:            daemon HTTP with 45ms timeout + file fallback.
# WG_DAEMON_ENABLED=always:          daemon HTTP only.
#
# _task_reader is stdlib-only and imported lazily so this hook remains
# fail-open even if the scripts/ directory is not on sys.path yet.


def _get_active_task_event_type(session_id: str) -> "str | None":
    """Return event_type of the most-recently-modified in-progress native task.

    Fail-silent — never blocks the hook.  Routing is delegated to
    scripts/crew/_task_reader.py per #596.
    """
    if not session_id:
        return None
    try:
        from crew._task_reader import get_active_task_event_type  # type: ignore[import]
        return get_active_task_event_type(session_id)
    except Exception:
        return None


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
    """Parse domain and agent name from a subagent identifier (Issue #573).

    Two accepted forms:

    * Fully-qualified: ``wicked-garden:{domain}:{agent-name}`` — parsed in
      place, no resolver needed. The domain must be a known specialist
      domain (``specialist_domains`` from ``specialist.json``) for the
      engagement tracker to accept it.
    * Bare role: ``requirements-analyst`` — expanded to the full form by
      :mod:`crew.specialist_resolver`, which walks ``agents/**/*.md``
      frontmatter. This is the path the facilitator emits by default.

    Returns ``(domain, agent_name)`` on success, ``(None, None)`` when
    the name cannot be resolved. The hook remains fail-open on any
    resolver import / walk error (engagement tracking is best-effort).
    """
    if not agent_type:
        return None, None

    if agent_type.startswith("wicked-garden:"):
        parts = agent_type.split(":")
        # Expect at least 3 parts: "wicked-garden", domain, agent-name
        if len(parts) < 3:
            return None, None

        domain = parts[1]
        agent_name = ":".join(parts[2:])  # preserve any colons in agent name

        if domain not in specialist_domains:
            return None, None

        return domain, agent_name

    # Bare-role path (Issue #573): resolve via agents/**/*.md frontmatter.
    # Fail-closed to the old behavior on any resolver error — engagement
    # tracking is best-effort and the hook must never block the agent.
    try:
        from crew.specialist_resolver import build_resolver, resolve_role

        resolver = build_resolver(_PLUGIN_ROOT)
        domain, subagent_type = resolve_role(agent_type, resolver)
        if domain is None or subagent_type is None:
            return None, None
        if domain not in specialist_domains:
            return None, None
        # The tracker stores bare role as the agent_name — callers feed
        # it straight into the engagement ledger, matching the existing
        # wicked-garden:{domain}:{role} parsing shape.
        return domain, agent_type
    except Exception:
        return None, None


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

def _handle_start(payload: dict) -> "str | None":
    """Track a subagent starting. Returns active event_type if any."""
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

    session_id = _get_session_id()

    # Write trace entry
    _write_trace({
        "event": "subagent_start",
        "agent_name": agent_name,
        "agent_id": agent_id,
        "timestamp": _now_iso(),
        "session_id": session_id,
    })

    # Get active task event_type from native on-disk task store
    return _get_active_task_event_type(session_id)


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

    event_type = None
    try:
        if phase == "start":
            event_type = _handle_start(payload)
        elif phase == "stop":
            _handle_stop(payload)
        else:
            _log("subagent", "warn", "subagent.unknown_phase",
                 detail={"phase": phase})
    except Exception as e:
        print(f"[wicked-garden] subagent_lifecycle error: {e}", file=sys.stderr)

    # Always succeed — lifecycle tracking should never block
    output = {"continue": True}

    if phase == "start":
        tool_discovery = (
            "[Tool Discovery] Before claiming you cannot do something, "
            "review your available skills and tools. You have capabilities for "
            "browser automation, visual testing, accessibility auditing, "
            "API testing, code search, memory, and more. Use them."
        )
        procedure_bundle = _EVENT_TYPE_PROCEDURES.get(event_type, "") if event_type else ""
        if procedure_bundle:
            output["systemMessage"] = f"{tool_discovery}\n\n{procedure_bundle}"
        else:
            output["systemMessage"] = tool_discovery

    print(json.dumps(output))


if __name__ == "__main__":
    main()
