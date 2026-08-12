#!/usr/bin/env python3
"""
PreCompact hook — wicked-garden WIP snapshot before context compression.

v6: the v5 ticket-rail preservation path (HistoryCondenser + PressureTracker)
was removed with smaht/v2 in #428. The remaining jobs are:
1. Stamp SessionState.last_compact_ts (dedup guard)
2. Save a lightweight WIP memory to the routed context backend (S4: estate
   memory.capture by default, legacy brain under WICKED_CONTEXT_BACKEND=brain)
   using SessionState + native in-progress task subjects as the input
3. Prompt Claude to store any additional memories before context is lost

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
import time
import uuid as _uuid_mod
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


# ---------------------------------------------------------------------------
# WIP content cap (chars)
# ---------------------------------------------------------------------------
_MAX_WIP_CHARS = 4000


def _read_in_progress_tasks(session_id, limit=10):
    """Read native in-progress task subjects for the session.

    Replaces the v5 HistoryCondenser "current_task" read — v6 has no ticket
    rail. Returns an empty list on any error.

    Routing: WG_DAEMON_ENABLED=false → direct file read (unchanged);
             WG_DAEMON_ENABLED=true  → daemon HTTP with fallback (#596 v8-PR-2).
    """
    if not session_id:
        return []
    try:
        from crew._task_reader import list_in_progress_tasks  # type: ignore[import]
        return list_in_progress_tasks(session_id, limit=limit)
    except Exception:
        return []


def _build_wip_markdown(session_state_dict, in_progress):
    """Format lightweight WIP state as markdown, capped at _MAX_WIP_CHARS."""
    sections = ["## WIP State (Pre-Compaction)"]

    active_project = session_state_dict.get("active_project") or ""
    if active_project:
        sections.append(f"### Active Project\n{active_project}")

    turn_count = session_state_dict.get("turn_count")
    if turn_count:
        sections.append(f"### Turn Count\n{turn_count}")

    if in_progress:
        items = "\n".join(f"- {s}" for s in in_progress)
        sections.append(f"### In-Progress Tasks\n{items}")

    content = "\n\n".join(sections)
    if len(content) > _MAX_WIP_CHARS:
        content = content[:_MAX_WIP_CHARS - 3] + "..."
    return content


def _save_wip_state(session_id, project):
    """Save a lightweight WIP memory to the routed context backend.

    v6: no HistoryCondenser ticket rail. Input is SessionState + native
    in-progress task subjects. The richer v5 snapshot (decisions, file scope,
    open questions) is gone. S4: the write routes through
    _context_backend.capture_memory (estate primary).
    """
    try:
        from _session import SessionState
        state = SessionState.load()
    except Exception:
        state = None

    ss_fields = {}
    if state:
        ss_fields = {
            "active_project": getattr(state, "active_project", ""),
            "active_project_id": getattr(state, "active_project_id", ""),
            "turn_count": getattr(state, "turn_count", 0),
            "failure_counts": getattr(state, "failure_counts", None),
            "bash_count": getattr(state, "bash_count", 0),
        }

    in_progress = _read_in_progress_tasks(session_id, limit=10)

    # Nothing to save if we have no signal at all
    if not any(ss_fields.values()) and not in_progress:
        _log("context", "debug", "pre_compact.empty_wip")
        return

    content = _build_wip_markdown(ss_fields, in_progress)
    active_project = ss_fields.get("active_project") or ""
    title = f"WIP: {active_project or 'Session work'} — pre-compaction snapshot"

    try:
        # S4: routed capture — estate memory.capture by default, the legacy
        # brain file+index path under WICKED_CONTEXT_BACKEND=brain.
        from _context_backend import capture_memory
        chunk_id = capture_memory(
            title=title,
            content=content,
            tier="working",
            tags=["wip", "pre-compact", "auto-saved"],
        )
        if chunk_id:
            _log("context", "verbose", "pre_compact.wip_saved", ok=True,
                 detail={"title": title[:60], "chars": len(content)})
    except Exception as e:
        print(f"[wicked-garden] pre_compact WIP save error: {e}", file=sys.stderr)


def main():
    _t0 = time.monotonic()
    _log("context", "debug", "hook.start")

    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    # Normal-level log fires regardless of log level (AC-07)
    _log("context", "normal", "pre_compact")

    session_id = os.environ.get("CLAUDE_SESSION_ID") or f"sess_{_uuid_mod.uuid4().hex[:8]}"
    project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name

    # Dedup guard: skip WIP save if compaction happened <60s ago
    skip_wip = False
    try:
        from _session import SessionState
        state = SessionState.load()
        if state.last_compact_ts:
            last_ts = datetime.fromisoformat(state.last_compact_ts)
            now = datetime.now(timezone.utc)
            # Ensure both are offset-aware for comparison
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            if (now - last_ts).total_seconds() < 60:
                skip_wip = True
                _log("context", "debug", "pre_compact.dedup_skip",
                     ok=True, detail={"last_ts": state.last_compact_ts})
    except Exception:
        state = None

    # Save structured WIP state (unless dedup guard triggered)
    if not skip_wip:
        _save_wip_state(session_id, project)

    # v6: PressureTracker was deleted with smaht/v2 in #428. There is no
    # cumulative-byte pressure model to reset — the pull-model architecture
    # does not rely on it.

    # Update last_compact_ts after successful processing
    if not skip_wip:
        try:
            if state is None:
                from _session import SessionState
                state = SessionState.load()
            state.update(last_compact_ts=datetime.now(timezone.utc).isoformat())
        except Exception:
            pass  # fail open

    # S4: name the memory surface for the routed backend (brain while the
    # bridge is alive; estate memory.capture after retirement). Fail-open to
    # the legacy wording.
    try:
        from _context_backend import memory_directive_target
        _mem_target = memory_directive_target()
    except Exception:
        _mem_target = "wicked-brain:memory"

    _log("context", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
    print(json.dumps({
        "continue": True,
        "systemMessage": (
            "[Memory] Context compression imminent. WIP state has been auto-saved. "
            "After compaction, your WIP will be automatically restored on the next prompt. "
            f"Store any additional decisions or patterns NOW with {_mem_target}."
        ),
    }))


if __name__ == "__main__":
    main()
