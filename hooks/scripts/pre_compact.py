#!/usr/bin/env python3
"""
PreCompact hook — wicked-garden structured WIP snapshot before context compression.

Three jobs:
1. Save structured WIP state to wicked-garden:mem (decisions, constraints, file scope, etc.)
2. Write a fast-retrieval JSON snapshot for the briefing system
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

def _resolve_brain_port():
    try:
        from _brain_port import resolve_port
        return resolve_port()
    except Exception:
        return int(os.environ.get("WICKED_BRAIN_PORT", "4242"))

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
# Brain API helpers
# ---------------------------------------------------------------------------

def _brain_api(action, params=None, timeout=3):
    """Call brain API. Returns parsed JSON or None."""
    try:
        import urllib.request
        port = _resolve_brain_port()
        payload = json.dumps({"action": action, "params": params or {}}).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _write_brain_memory(title, content, tier="episodic", tags=None, mem_type="episodic", importance=5):
    """Write a memory chunk to brain. Returns chunk_id or None."""
    try:
        mem_id = str(_uuid_mod.uuid4())
        chunk_id = f"memories/{tier}/mem-{mem_id}"
        chunk_path = Path.home() / ".wicked-brain" / f"{chunk_id}.md"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)

        tags_list = tags or []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        lines = ["---"]
        lines.append("source: wicked-garden:mem")
        lines.append(f"memory_type: {mem_type}")
        lines.append(f"memory_tier: {tier}")
        lines.append(f"title: {title}")
        lines.append(f"importance: {importance}")
        lines.append("contains:")
        for t in tags_list:
            lines.append(f"  - {t}")
        lines.append(f'indexed_at: "{now}"')
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(content)

        chunk_path.write_text("\n".join(lines), encoding="utf-8")

        # Index in brain FTS5
        search_text = f"{title} {content} {' '.join(tags_list)}"
        _brain_api("index", {"id": f"{chunk_id}.md", "path": f"{chunk_id}.md", "content": search_text, "brain_id": "wicked-brain"})
        return chunk_id
    except Exception:
        return None


# ---------------------------------------------------------------------------
# WIP content cap (chars)
# ---------------------------------------------------------------------------
_MAX_WIP_CHARS = 4000


def _build_wip_markdown(session_state_dict, condensed_history):
    """Format structured WIP state as markdown, capped at _MAX_WIP_CHARS."""
    sections = []
    sections.append("## WIP State (Pre-Compaction)")

    current_task = session_state_dict.get("current_task") or ""
    if current_task:
        sections.append(f"### Current Task\n{current_task}")

    decisions = session_state_dict.get("decisions") or []
    if decisions:
        items = "\n".join(f"- {d}" for d in decisions)
        sections.append(f"### Decisions Made\n{items}")

    file_scope = session_state_dict.get("file_scope") or []
    if file_scope:
        items = "\n".join(f"- {f}" for f in file_scope)
        sections.append(f"### Files In Scope\n{items}")

    constraints = session_state_dict.get("active_constraints") or []
    if constraints:
        items = "\n".join(f"- {c}" for c in constraints)
        sections.append(f"### Active Constraints\n{items}")

    questions = session_state_dict.get("open_questions") or []
    if questions:
        items = "\n".join(f"- {q}" for q in questions)
        sections.append(f"### Open Questions\n{items}")

    if condensed_history:
        sections.append(f"### Condensed History\n{condensed_history}")

    content = "\n\n".join(sections)
    if len(content) > _MAX_WIP_CHARS:
        content = content[:_MAX_WIP_CHARS - 3] + "..."
    return content


def _save_wip_state(session_id, project):
    """Save structured WIP state to wicked-garden:mem and a JSON snapshot file."""
    try:
        from _session import SessionState
        state = SessionState.load()
    except Exception:
        state = None

    # Collect SessionState fields
    ss_fields = {}
    if state:
        ss_fields = {
            "active_project": state.active_project,
            "active_project_id": state.active_project_id,
            "turn_count": state.turn_count,
            "failure_counts": state.failure_counts,
            "bash_count": state.bash_count,
        }

    # Try to load smaht HistoryCondenser state
    condenser_state = {}
    condensed_history = ""
    condenser = None
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        condenser_state = condenser.get_session_state()
        condensed_history = condenser.get_condensed_history()
    except Exception as e:
        _log("context", "debug", "pre_compact.condenser_unavailable",
             ok=True, detail={"error": str(e)[:100]})

    # Merge into a single dict for the snapshot
    snapshot = {**ss_fields, **condenser_state, "timestamp": datetime.now(timezone.utc).isoformat()}

    # Write JSON snapshot for fast retrieval by the briefing system
    if condenser is not None:
        try:
            snapshot_path = condenser.session_dir / "wip_snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            _log("context", "debug", "pre_compact.snapshot_write_failed",
                 ok=True, detail={"error": str(e)[:100]})

    # Build structured markdown content
    content = _build_wip_markdown(condenser_state or ss_fields, condensed_history)

    current_task = condenser_state.get("current_task") or ""
    title = f"WIP: {current_task or 'Session work'} — pre-compaction snapshot"

    # Store via brain API (write chunk file + index)
    try:
        chunk_id = _write_brain_memory(
            title=title,
            content=content,
            tier="working",
            tags=["wip", "pre-compact", "auto-saved"],
            mem_type="working",
            importance=5,
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

    session_id = os.environ.get("CLAUDE_SESSION_ID") or f"sess_{uuid.uuid4().hex[:8]}"
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

    # Notify the pressure tracker that compaction just occurred so it resets
    # cumulative byte pressure by ~70% (avoids over-aggressive budget scaling
    # on the first turns after a compaction).
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
        from context_pressure import PressureTracker
        PressureTracker(session_id).mark_compacted()
    except Exception:
        pass  # fail open

    # Update last_compact_ts after successful processing
    if not skip_wip:
        try:
            if state is None:
                from _session import SessionState
                state = SessionState.load()
            state.update(last_compact_ts=datetime.now(timezone.utc).isoformat())
        except Exception:
            pass  # fail open

    _log("context", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
    print(json.dumps({
        "continue": True,
        "systemMessage": (
            "[Memory] Context compression imminent. WIP state has been auto-saved. "
            "After compaction, your WIP will be automatically restored on the next prompt. "
            "Store any additional decisions or patterns NOW with /wicked-garden:mem:store."
        ),
    }))


if __name__ == "__main__":
    main()
