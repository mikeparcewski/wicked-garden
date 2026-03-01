#!/usr/bin/env python3
"""
UserPromptSubmit hook — wicked-garden unified context assembly.

Consolidates: wicked-smaht prompt_submit, wicked-mem prompt_submit.

Three-tier context routing:
  HOT  (<100ms): continuation/confirmation → session state only
  FAST (<1s):    short prompt + high confidence intent → 2-5 domain queries
  SLOW (2-5s):   complex/ambiguous → all domains + history condenser

Session goal capture on turns 1-2 (from wicked-mem's prompt_submit behavior).
Turn counter incremented on every call.

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# HOT path: tokens that indicate a continuation, not a new task
# ---------------------------------------------------------------------------

_HOT_TOKENS = frozenset({
    "yes", "no", "ok", "okay", "sure", "go", "do it", "proceed", "continue",
    "yep", "yup", "nope", "agreed", "correct", "right", "wrong", "good",
    "sounds good", "looks good", "lgtm", "ship it", "done", "thanks",
    "thank you", "great", "perfect", "nice", "cool", "approve", "approved",
    "confirmed", "confirm", "next", "skip", "stop", "cancel", "abort",
})

_HOT_MAX_WORDS = 6


def _is_hot_path(prompt: str) -> bool:
    """Return True if the prompt is a short continuation/confirmation."""
    stripped = prompt.strip().lower().rstrip("!.?,;")
    if not stripped:
        return True
    words = stripped.split()
    if len(words) > _HOT_MAX_WORDS:
        return False
    return stripped in _HOT_TOKENS or (len(words) == 1 and stripped in _HOT_TOKENS)


# ---------------------------------------------------------------------------
# Intent classification for FAST-path domain selection
# ---------------------------------------------------------------------------

_INTENT_DOMAINS = {
    "memory": ["remember", "recall", "store", "mem", "save", "forgot", "history", "past"],
    "crew": ["project", "phase", "crew", "workflow", "plan", "gate", "approve"],
    "kanban": ["task", "todo", "board", "kanban", "ticket", "issue", "backlog"],
    "search": ["find", "search", "symbol", "class", "function", "where", "locate", "reference"],
    "jam": ["brainstorm", "ideas", "jam", "explore", "think", "options"],
    "delivery": ["metrics", "delivery", "status", "report", "sprint", "velocity"],
}


def _classify_intents(prompt: str) -> list:
    """Return a list of matched domain names, ordered by strength."""
    lower = prompt.lower()
    matched = []
    for domain, keywords in _INTENT_DOMAINS.items():
        if any(kw in lower for kw in keywords):
            matched.append(domain)
    return matched


def _is_fast_path(prompt: str, intents: list) -> bool:
    """Return True for short prompts with clear, high-confidence intent."""
    word_count = len(prompt.split())
    return word_count <= 40 and len(intents) >= 1


# ---------------------------------------------------------------------------
# Domain query helpers — each fails gracefully to empty string
# ---------------------------------------------------------------------------

def _query_session_state(session_id: str) -> str:
    """Return a brief session context summary from SessionState."""
    try:
        from _session import SessionState
        state = SessionState.load()
        parts = []
        if state.active_project:
            name = state.active_project.get("name", "")
            phase = state.active_project.get("phase", "")
            if name:
                parts.append(f"Active project: {name} ({phase})")
        if state.turn_count:
            parts.append(f"Turn: {state.turn_count}")
        return " | ".join(parts) if parts else ""
    except Exception:
        return ""


def _query_memory(project: str, prompt: str) -> str:
    """Return relevant memory snippets for the prompt."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-mem")
        # Use a short keyword from the prompt as the recall query
        words = [w for w in prompt.split() if len(w) > 4][:5]
        query = " ".join(words) or prompt[:50]
        results = sm.list("memories", query=query, limit=3) or []
        if not results:
            return ""
        items = []
        for r in results:
            title = r.get("title", "")
            content = r.get("content", "") or r.get("summary", "")
            if title or content:
                items.append(f"- {title}: {content[:120]}" if title else f"- {content[:120]}")
        return "\n".join(items) if items else ""
    except Exception:
        return ""


def _query_crew(project: str) -> str:
    """Return current crew project phase context."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-crew")
        projects = sm.list("projects", archived=False, limit=1) or []
        if not projects:
            return ""
        p = projects[0]
        name = p.get("name", "")
        phase = p.get("current_phase", "")
        return f"Crew project: {name} | Phase: {phase}" if name else ""
    except Exception:
        return ""


def _query_kanban(project: str) -> str:
    """Return in-progress task names from kanban."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-kanban")
        tasks = sm.list("tasks", status="in_progress", limit=5) or []
        if not tasks:
            return ""
        names = [t.get("name", "") for t in tasks if t.get("name")]
        return f"In-progress: {', '.join(names[:3])}" if names else ""
    except Exception:
        return ""


def _query_search_index(prompt: str) -> str:
    """Return a quick symbol hit if prompt references a code identifier."""
    try:
        import re
        import sqlite3
        # Extract potential symbol: first CamelCase or snake_case word
        symbols = re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}|[a-z_][a-z0-9_]{3,}\b", prompt)
        if not symbols:
            return ""
        db_path = Path.home() / ".something-wicked" / "wicked-search" / "unified_search.db"
        if not db_path.exists():
            return ""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
        try:
            # Try common table/column patterns for symbol lookup
            for table, name_col, file_col, line_col in [
                ("symbols", "name", "file", "line"),
                ("code_symbols", "name", "file_path", "line"),
            ]:
                try:
                    cursor = conn.execute(
                        f"SELECT {file_col}, {line_col} FROM {table} WHERE {name_col} = ? LIMIT 2",
                        (symbols[0],),
                    )
                    rows = cursor.fetchall()
                    if rows:
                        hits = [f"{r[0]}:{r[1]}" for r in rows if r[0]]
                        return f"Symbol '{symbols[0]}' found at: {', '.join(hits)}" if hits else ""
                except sqlite3.OperationalError:
                    continue
            return ""
        finally:
            conn.close()
    except Exception:
        return ""


def _query_condenser(session_id: str) -> str:
    """Return condensed history from smaht history condenser if available."""
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        state = condenser.get_session_state()
        parts = []
        if state.get("current_task"):
            parts.append(f"Current task: {state['current_task']}")
        if state.get("decisions"):
            parts.append(f"Decisions: {'; '.join(state['decisions'][:3])}")
        if state.get("file_scope"):
            parts.append(f"Active files: {', '.join(state['file_scope'][-5:])}")
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Session goal capture (turns 1-2)
# ---------------------------------------------------------------------------

def _capture_session_goal(prompt: str, turn_count: int, project: str, session_id: str):
    """On turns 1-2, save the session goal as WORKING memory."""
    if turn_count > 2:
        return
    if len(prompt.strip()) < 20:
        return
    try:
        from mem.memory import MemoryStore, MemoryType, Scope, Importance
        store = MemoryStore(project)
        store.store(
            title=f"Session goal (turn {turn_count})",
            content=prompt[:500],
            type=MemoryType.WORKING,
            summary="Session goal captured from opening prompt",
            context="Auto-captured on session start",
            importance=Importance.MEDIUM,
            scope=Scope.PROJECT,
            source="hook:prompt_submit",
            session_id=session_id,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Reconnect probe — checks for CP availability when in offline/fallback mode
# ---------------------------------------------------------------------------

_reconnect_notification = ""  # set by _maybe_attempt_reconnect, read by main()


def _maybe_attempt_reconnect(state) -> None:
    """Probe CP health when in fallback mode, rate-limited by config interval.

    On successful reconnect: flips session state online, drains the offline
    queue, and sets a notification message for the user.
    """
    global _reconnect_notification

    if state is None or not state.fallback_mode:
        return

    now = time.time()
    interval = 60  # default
    try:
        from _control_plane import load_config
        cfg = load_config()
        interval = cfg.get("health_check_interval_seconds", 60)
    except Exception:
        pass

    last = getattr(state, "cp_last_checked_at", 0.0) or 0.0
    if now - last < interval:
        return

    # Stamp before attempt to avoid racing with concurrent hooks
    state.update(cp_last_checked_at=now)

    try:
        from _control_plane import ControlPlaneClient
        ok, version = ControlPlaneClient(hook_mode=True).check_health()
        if ok:
            state.mark_online(version)
            from _storage import drain_offline_queue
            replayed, failed = drain_offline_queue(hook_mode=True)
            parts = [f"Control plane reconnected (v{version})."]
            if replayed:
                parts.append(f"Replayed {replayed} queued writes.")
            if failed:
                parts.append(f"{failed} failed entries in _queue_failed.jsonl.")
            _reconnect_notification = " ".join(parts)
    except Exception:
        pass  # fail open — stay in fallback mode


# ---------------------------------------------------------------------------
# Turn counter
# ---------------------------------------------------------------------------

def _increment_turn(state) -> int:
    """Increment session turn counter and return new value."""
    if state is None:
        return 0
    try:
        new_count = (state.turn_count or 0) + 1
        state.update(turn_count=new_count)
        state.save()
        return new_count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Context assembly per path
# ---------------------------------------------------------------------------

def _assemble_hot(state_summary: str) -> str:
    """HOT path: return session state only."""
    return state_summary


def _assemble_fast(prompt: str, intents: list, project: str, session_id: str) -> str:
    """FAST path: query 2-5 domains matched by intent."""
    parts = []

    # Session state is always included
    state_summary = _query_session_state(session_id)
    if state_summary:
        parts.append(state_summary)

    # Domain-specific queries
    if "memory" in intents or "crew" in intents or "kanban" in intents or not intents:
        mem_result = _query_memory(project, prompt)
        if mem_result:
            parts.append(f"[Memory]\n{mem_result}")

    if "crew" in intents:
        crew_result = _query_crew(project)
        if crew_result:
            parts.append(f"[Crew] {crew_result}")

    if "kanban" in intents:
        kanban_result = _query_kanban(project)
        if kanban_result:
            parts.append(f"[Kanban] {kanban_result}")

    if "search" in intents:
        search_result = _query_search_index(prompt)
        if search_result:
            parts.append(f"[Search] {search_result}")

    return "\n".join(parts)


def _assemble_slow(prompt: str, project: str, session_id: str) -> str:
    """SLOW path: query all domains plus history condenser."""
    parts = []

    state_summary = _query_session_state(session_id)
    if state_summary:
        parts.append(state_summary)

    condenser_result = _query_condenser(session_id)
    if condenser_result:
        parts.append(f"[History]\n{condenser_result}")

    mem_result = _query_memory(project, prompt)
    if mem_result:
        parts.append(f"[Memory]\n{mem_result}")

    crew_result = _query_crew(project)
    if crew_result:
        parts.append(f"[Crew] {crew_result}")

    kanban_result = _query_kanban(project)
    if kanban_result:
        parts.append(f"[Kanban] {kanban_result}")

    search_result = _query_search_index(prompt)
    if search_result:
        parts.append(f"[Search] {search_result}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Budget enforcement (simple character cap by path)
# ---------------------------------------------------------------------------

_BUDGETS = {"hot": 400, "fast": 2000, "slow": 4000}


def _enforce_budget(content: str, path: str) -> str:
    limit = _BUDGETS.get(path, 2000)
    if len(content) <= limit:
        return content
    return content[:limit - 3] + "..."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        print(json.dumps({"continue": True}))
        return

    prompt = input_data.get("prompt", "")
    session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "default"))
    project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name

    if not prompt.strip():
        print(json.dumps({"continue": True}))
        return

    try:
        # Load and increment turn counter
        from _session import SessionState
        state = SessionState.load()
    except Exception:
        state = None

    # Reconnect probe — check for CP when in fallback/offline mode
    _maybe_attempt_reconnect(state)

    turn_count = _increment_turn(state)

    # Session goal capture on turns 1-2
    _capture_session_goal(prompt, turn_count, project, session_id)

    try:
        # Routing decision
        if _is_hot_path(prompt):
            path = "hot"
            briefing = _assemble_hot(_query_session_state(session_id))
        else:
            intents = _classify_intents(prompt)
            if _is_fast_path(prompt, intents):
                path = "fast"
                briefing = _assemble_fast(prompt, intents, project, session_id)
            else:
                path = "slow"
                briefing = _assemble_slow(prompt, project, session_id)

        briefing = _enforce_budget(briefing, path)

        if not briefing:
            print(json.dumps({"continue": True}))
            return

        # Sanitize against injection
        sanitized = briefing.replace("</system-reminder>", "")

        header = (
            f"<!-- wicked-garden | path={path} "
            f"| turn={turn_count} -->"
        )

        # Include reconnect notification if CP was just restored
        context_parts = [f"<system-reminder>\n{header}\n{sanitized}\n</system-reminder>"]
        if _reconnect_notification:
            context_parts.append(
                f"<system-reminder>\n[wicked-garden] {_reconnect_notification}\n</system-reminder>"
            )

        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(context_parts),
            },
            "continue": True,
        }
        print(json.dumps(output))

    except Exception as e:
        print(f"[wicked-garden] prompt_submit error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
