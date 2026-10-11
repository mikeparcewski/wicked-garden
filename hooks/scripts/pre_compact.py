#!/usr/bin/env python3
"""
PreCompact hook — wicked-garden WIP snapshot before context compression.

v6: the v5 ticket-rail preservation path (HistoryCondenser + PressureTracker)
was removed with smaht/v2 in #428. The remaining jobs are:
1. Stamp SessionState.last_compact_ts (dedup guard)
2. Save the native in-progress task subjects as a project-scoped working
   memory (wicked-estate memory.capture), only when there are any
3. Prompt Claude to store any durable learning before context is lost

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


def _build_wip_markdown(active_project, in_progress):
    """Format the in-progress task state as markdown, capped at _MAX_WIP_CHARS."""
    sections = ["## WIP State (Pre-Compaction)"]
    if active_project:
        sections.append(f"### Active Project\n{active_project}")
    items = "\n".join(f"- {s}" for s in in_progress)
    sections.append(f"### In-Progress Tasks\n{items}")
    content = "\n\n".join(sections)
    if len(content) > _MAX_WIP_CHARS:
        content = content[:_MAX_WIP_CHARS - 3] + "..."
    return content


def _save_wip_state(session_id):
    """Save the in-progress task state as a project-scoped working memory.

    Writes nothing unless the session has real in-progress tasks: a turn count
    or an active-project name alone is not state worth restoring (that wrote
    one empty "WIP snapshot" per compaction). The write goes through
    _context_backend.capture_memory, which always scopes it to the current
    project; estate expires working memories after 24 h.
    Returns the memory id, or None when nothing was written.
    """
    in_progress = [t for t in _read_in_progress_tasks(session_id, limit=10) if str(t).strip()]
    if not in_progress:
        _log("context", "debug", "pre_compact.no_wip")
        return None

    active_project = ""
    try:
        from _session import SessionState
        active_project = getattr(SessionState.load(), "active_project", "") or ""
    except Exception:
        pass

    content = _build_wip_markdown(active_project, in_progress)
    title = f"WIP: {active_project or 'Session work'} — pre-compaction snapshot"
    try:
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
        return chunk_id
    except Exception as e:
        print(f"[wicked-garden] pre_compact WIP save error: {e}", file=sys.stderr)
        return None


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

    session_id = input_data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or ""

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

    # Save the in-progress task state (unless dedup guard triggered)
    saved = None
    if not skip_wip:
        saved = _save_wip_state(session_id)

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

    # Name the memory surface (estate memory.capture). Fail-open to the
    # same wording.
    try:
        from _context_backend import memory_directive_target
        _mem_target = memory_directive_target()
    except Exception:
        _mem_target = "the wicked-garden-mem skill (store action)"

    _log("context", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
    print(json.dumps({
        "continue": True,
        "systemMessage": (
            "[Memory] Context compression imminent. "
            + ("In-progress task state was saved as a working memory. " if saved else "")
            + f"Store any durable decision or gotcha NOW with {_mem_target}."
        ),
    }))


if __name__ == "__main__":
    main()
