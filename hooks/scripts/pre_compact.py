#!/usr/bin/env python3
"""
PreCompact hook — wicked-garden WIP snapshot before context compression.

v6: the v5 ticket-rail preservation path (HistoryCondenser + PressureTracker)
was removed with smaht/v2 in #428. The remaining jobs are:
1. Stamp SessionState.last_compact_ts (dedup guard)
2. Save a lightweight WIP memory to wicked-brain using SessionState + native
   in-progress task subjects as the input
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


def _read_in_progress_tasks(session_id, limit=10):
    """Read native in-progress task subjects for the session.

    Replaces the v5 HistoryCondenser "current_task" read — v6 has no ticket
    rail. Returns an empty list on any error.
    """
    out = []
    try:
        base = os.environ.get("CLAUDE_CONFIG_DIR")
        root = Path(base).expanduser() if base else Path.home() / ".claude"
        safe = (session_id or "").replace("/", "_").replace("\\", "_").replace("..", "_")
        tdir = root / "tasks" / safe
        if not tdir.is_dir():
            return out
        for entry in tdir.iterdir():
            if entry.name.startswith(".") or entry.suffix != ".json":
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict) and data.get("status") == "in_progress":
                subj = data.get("subject") or "untitled"
                out.append(subj)
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


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
    """Save a lightweight WIP memory to wicked-brain.

    v6: no HistoryCondenser ticket rail. Input is SessionState + native
    in-progress task subjects. The richer v5 snapshot (decisions, file scope,
    open questions) is gone.
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
