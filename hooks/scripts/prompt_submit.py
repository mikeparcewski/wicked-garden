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

import hashlib
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
    """Return True if the prompt is a short continuation/confirmation.

    Matches when:
    - The full stripped phrase is a HOT token (e.g. "sounds good"), OR
    - The prompt is short (<=6 words) AND its opening token(s) signal continuation —
      this catches planning acknowledgments like "yes, continue with the plan" where
      the user is simply acknowledging and agreeing to proceed, not requesting new work.

    Opening-token matching checks both the first word and the first two-word phrase
    (e.g. "sounds good, let us proceed" starts with "sounds good" which is a HOT token).
    """
    stripped = prompt.strip().lower().rstrip("!.?,;")
    if not stripped:
        return True
    words = stripped.split()
    if len(words) > _HOT_MAX_WORDS:
        return False
    # Full-phrase match
    if stripped in _HOT_TOKENS:
        return True
    # First word matches a HOT token (e.g. "yes, continue with the plan")
    first_word = words[0].rstrip("!.?,;")
    if first_word in _HOT_TOKENS:
        return True
    # First two words as phrase match a HOT token (e.g. "sounds good, ...")
    if len(words) >= 2:
        first_two = (words[0].rstrip("!.?,;") + " " + words[1].rstrip("!.?,;"))
        if first_two in _HOT_TOKENS:
            return True
    return False


# ---------------------------------------------------------------------------
# Session state hash — change detection for deduplication
# ---------------------------------------------------------------------------

def _session_state_hash(state) -> str:
    """Compute a short hash of the fields that drive context injection.

    Turn count is rounded to the nearest 5 so that minor turn increments do
    not invalidate the hash on every turn — only meaningful state transitions
    (project change, CP availability change, etc.) force re-injection.

    Returns an 8-character hex string or "" on any error.
    """
    try:
        turn = getattr(state, "turn_count", 0) or 0
        state_dict = {
            "active_project": getattr(state, "active_project", None),
            "turn_bucket": (turn // 5) * 5,  # round to nearest 5
            "cp_available": getattr(state, "cp_available", None),
            "fallback_mode": getattr(state, "fallback_mode", None),
        }
        raw = json.dumps(state_dict, sort_keys=True).encode()
        return hashlib.md5(raw).hexdigest()[:8]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Complexity heuristic — prevents over-escalation to SLOW path
# ---------------------------------------------------------------------------

def _estimate_complexity(prompt: str) -> int:
    """Quick inline complexity estimate on a 0-3 scale.

    0 — trivially simple (short, no planning/architecture keywords)
    1 — moderate (planning vocabulary but not deep)
    2 — complex (long prompt OR architectural keywords)
    3 — very complex (multiple signals)
    """
    score = 0
    lower = prompt.lower()
    # Length signal
    if len(prompt.split()) > 80:
        score += 1
    # Architectural / systemic keywords
    if any(w in lower for w in [
        "multiple", "cross-cutting", "refactor", "migration", "architecture",
        "system", "end-to-end", "pipeline", "overhaul"
    ]):
        score += 1
    # Planning / decision vocabulary
    if any(w in lower for w in [
        "plan", "design", "strategy", "approach", "how should", "help me",
        "we need to", "roadmap", "options", "tradeoffs", "trade-off"
    ]):
        score += 1
    # Multi-step / scoped request
    if any(w in lower for w in [
        "then", "after that", "first", "second", "step", "phase",
        "implement and", "build and", "with testing", "with docs"
    ]):
        score = min(score + 1, 3)
    return score


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


def _is_planning_prompt(prompt: str) -> bool:
    """Return True if the prompt contains planning / design vocabulary."""
    planning_words = [
        "plan", "design", "strategy", "approach", "roadmap", "architecture",
        "trade-off", "tradeoff", "options", "alternatives", "pros and cons",
        "brainstorm", "should we", "how should",
    ]
    lower = prompt.lower()
    return any(w in lower for w in planning_words)


_JAM_AMBIGUITY_SIGNALS = [
    "options", "tradeoffs", "trade-off", "should we", "brainstorm",
    "alternatives", "pros and cons", "compare", "which approach",
    "what are the", "explore", "think through", "uncertain", "unclear",
    "not sure", "ideas", "different ways"
]


def _has_ambiguity_signals(prompt: str) -> bool:
    """Return True if prompt contains explicit ambiguity / exploration signals."""
    lower = prompt.lower()
    return any(sig in lower for sig in _JAM_AMBIGUITY_SIGNALS)


def _suggest_jam(prompt: str, state, merged_context: str) -> str:
    """Append a jam suggestion to merged_context if conditions are met.

    Conditions:
    1. Prompt contains ambiguity signals
    2. Prompt does not already reference a jam command
    3. Hint not shown this session

    Returns updated merged_context (unchanged if conditions not met).
    """
    if "/jam:" in prompt.lower():
        return merged_context  # Already using jam — no suggestion needed
    if not _has_ambiguity_signals(prompt):
        return merged_context
    jam_shown = getattr(state, "jam_hint_shown", False) if state else False
    if jam_shown:
        return merged_context

    jam_hint = (
        "[Suggestion] This prompt involves exploring options or tradeoffs. "
        "Consider /wicked-garden:jam:quick for fast structured thinking, "
        "or /wicked-garden:jam:brainstorm for a full multi-perspective session."
    )
    updated = merged_context[:-len("</system-reminder>")] + jam_hint + "\n</system-reminder>"
    try:
        if state:
            state.update(jam_hint_shown=True)
    except Exception:
        pass
    return updated


def _is_fast_path(prompt: str, intents: list) -> bool:
    """Return True for short prompts with clear, high-confidence intent.

    SLOW requires word_count > 40 OR complexity >= 2 OR (is_planning AND complexity >= 1).
    Short planning acknowledgments ("yes, continue with the plan") should stay HOT or FAST,
    not escalate to SLOW.
    """
    word_count = len(prompt.split())
    complexity = _estimate_complexity(prompt)
    is_planning = _is_planning_prompt(prompt)

    # Escalation conditions that push toward SLOW
    if word_count > 40:
        return False
    if complexity >= 2:
        return False
    if is_planning and complexity >= 1:
        return False

    return len(intents) >= 1


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


# ---------------------------------------------------------------------------
# Session-scoped adapter result cache (file-backed per session, TTL = session)
# ---------------------------------------------------------------------------
# Each hook invocation is a fresh process — module-level variables don't persist.
# We use a tmp file keyed by session_id so that cache entries survive across
# back-to-back hook calls within the same session without re-querying StorageManager.
# Cache keys are (adapter_name, state_hash) — if state changes, the hash changes
# and the old entry is simply not found (stale entries are benign dead weight).


def _read_adapter_cache(session_id: str) -> dict:
    """Read the session-scoped adapter result cache from tmp."""
    cache_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"wicked-smaht-cache-{session_id}.json"
    try:
        return json.loads(cache_path.read_text())
    except Exception:
        return {}


def _write_adapter_cache(session_id: str, cache: dict) -> None:
    """Persist the session-scoped adapter result cache to tmp."""
    cache_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"wicked-smaht-cache-{session_id}.json"
    try:
        cache_path.write_text(json.dumps(cache))
    except Exception:
        pass  # fail open — cache miss is safe


def _query_memory(project: str, prompt: str, session_id: str = "", state_hash: str = "") -> str:
    """Return relevant memory snippets for the prompt."""
    cache_key = f"memory:{state_hash}" if state_hash else ""
    if cache_key and session_id:
        cache = _read_adapter_cache(session_id)
        if cache_key in cache:
            return cache[cache_key]
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-mem")
        # Use a short keyword from the prompt as the recall query
        words = [w for w in prompt.split() if len(w) > 4][:5]
        query = " ".join(words) or prompt[:50]
        results = sm.list("memories", query=query, limit=3) or []
        if not results:
            result = ""
        else:
            items = []
            for r in results:
                title = r.get("title", "")
                content = r.get("content", "") or r.get("summary", "")
                if title or content:
                    items.append(f"- {title}: {content[:120]}" if title else f"- {content[:120]}")
            result = "\n".join(items) if items else ""
    except Exception:
        result = ""
    if cache_key and session_id:
        cache = _read_adapter_cache(session_id)
        cache[cache_key] = result
        _write_adapter_cache(session_id, cache)
    return result


def _query_crew(project: str, session_id: str = "", state_hash: str = "") -> str:
    """Return current crew project phase context, scoped to workspace."""
    cache_key = f"crew:{state_hash}" if state_hash else ""
    if cache_key and session_id:
        cache = _read_adapter_cache(session_id)
        if cache_key in cache:
            return cache[cache_key]
    try:
        workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        from _storage import StorageManager
        sm = StorageManager("wicked-crew")
        projects = sm.list("projects") or []
        result = ""
        # Filter to active projects in this workspace
        for p in sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True):
            if p.get("archived"):
                continue
            if workspace and p.get("workspace", "") != workspace:
                continue
            phase = p.get("current_phase", "")
            if phase and phase not in ("complete", "done", ""):
                name = p.get("name", "")
                result = f"Crew project: {name} | Phase: {phase}" if name else ""
                break
    except Exception:
        result = ""
    if cache_key and session_id:
        cache = _read_adapter_cache(session_id)
        cache[cache_key] = result
        _write_adapter_cache(session_id, cache)
    return result


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
        try:
            from _storage import get_local_file
            db_path = get_local_file("wicked-search", "unified_search.db")
        except Exception:
            return ""
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


def _assemble_fast(prompt: str, intents: list, project: str, session_id: str, state_hash: str = "") -> str:
    """FAST path: query 2-5 domains matched by intent."""
    parts = []

    # Session state is always included
    state_summary = _query_session_state(session_id)
    if state_summary:
        parts.append(state_summary)

    # Domain-specific queries (pass session_id + state_hash for adapter caching)
    if "memory" in intents or "crew" in intents or "kanban" in intents or not intents:
        mem_result = _query_memory(project, prompt, session_id=session_id, state_hash=state_hash)
        if mem_result:
            parts.append(f"[Memory]\n{mem_result}")

    if "crew" in intents:
        crew_result = _query_crew(project, session_id=session_id, state_hash=state_hash)
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


def _assemble_slow(prompt: str, project: str, session_id: str, state_hash: str = "") -> str:
    """SLOW path: query all domains plus history condenser."""
    parts = []

    state_summary = _query_session_state(session_id)
    if state_summary:
        parts.append(state_summary)

    condenser_result = _query_condenser(session_id)
    if condenser_result:
        parts.append(f"[History]\n{condenser_result}")

    mem_result = _query_memory(project, prompt, session_id=session_id, state_hash=state_hash)
    if mem_result:
        parts.append(f"[Memory]\n{mem_result}")

    crew_result = _query_crew(project, session_id=session_id, state_hash=state_hash)
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


def _enforce_budget_scaled(content: str, path: str, multiplier: float) -> str:
    """Apply a pressure-scaled budget cap.

    Delegates to BudgetEnforcer.scale() when available for a consistent budget
    value. Falls back to the local _BUDGETS dict on import failure.

    Args:
        content: The assembled briefing text.
        path: "hot", "fast", or "slow".
        multiplier: Scale factor — 1.0=normal, 0.5=HIGH pressure, 0.25=CRITICAL.

    Returns:
        Content truncated to the scaled budget limit.
    """
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
        from budget_enforcer import BudgetEnforcer
        limit = BudgetEnforcer.scale(path, multiplier)
    except Exception:
        limit = int(_BUDGETS.get(path, 2000) * multiplier)

    if len(content) <= limit:
        return content
    return content[:limit - 3] + "..."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _check_setup_gate(prompt: str) -> str | None:
    """Check if wicked-garden setup/onboarding is needed.

    Returns None if no action needed.
    Returns a directive string if onboarding is required — caller includes
    it in additionalContext so Claude sees the full context every turn.
    Calls sys.exit(2) only for hard failures (no config at all).

    Allows /wicked-garden:setup and /wicked-garden:help through the gate.
    Also allows prompts through when setup is in progress (user answering
    AskUserQuestion during the setup flow).
    """
    stripped = prompt.strip().lower()

    # Let setup and help commands through, and mark setup as in progress
    if stripped.startswith(("/wicked-garden:setup", "/wicked-garden:help", "/setup", "/help")):
        try:
            from _session import SessionState
            state = SessionState.load()
            state.update(setup_in_progress=True)
        except Exception:
            pass
        return None

    # Allow prompts through when setup is actively running (user answering questions)
    try:
        from _session import SessionState
        state = SessionState.load()
        if state.setup_in_progress:
            return None
    except Exception:
        pass  # fail open

    # Check 1: config.json setup_complete — hard block
    config_path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
    config_ok = False
    try:
        if config_path.exists():
            config = json.loads(config_path.read_text())
            config_ok = config.get("setup_complete", False)
    except (json.JSONDecodeError, OSError):
        pass

    if not config_ok:
        print(
            "wicked-garden requires setup before first use.\n"
            "Run: /wicked-garden:setup",
            file=sys.stderr,
        )
        sys.exit(2)

    # Check 2: session state onboarding_complete / needs_onboarding — soft gate with directive
    try:
        from _session import SessionState
        state = SessionState.load()
        if state.onboarding_complete:
            return None  # confirmed complete at bootstrap, no re-check needed
        if state.needs_onboarding:
            # Re-verify at each turn in case onboarding was completed mid-session
            try:
                from mem.memory import MemoryStore
                import os as _os
                _project = _os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
                store = MemoryStore(_project)
                memories = store.recall(tags=["onboarding"], limit=1)
                has_memories = len(memories) > 0
            except Exception:
                has_memories = True  # fail open — don't block if check fails
            project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
            if not has_memories:
                return (
                    f"[Action Required] Project '{project}' has not been onboarded.\n"
                    "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
                    "to launch the interactive onboarding wizard.\n"
                    "Do NOT ask the user for confirmation — invoke the skill now.\n"
                    "Do NOT respond with text first — invoke the skill as your first action."
                )
    except Exception:
        pass  # fail open if session state unavailable

    return None


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

    # Setup gate — hard-block if no config, soft-gate with directive if needs onboarding
    onboarding_directive = _check_setup_gate(prompt)

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
        # --- Change 1: Hash-based deduplication ---
        # Compute the current session state hash. If it matches the stored hash
        # AND we're beyond the early turns AND the prompt resolves to HOT, skip
        # re-injection entirely — the context hasn't changed.
        current_hash = _session_state_hash(state)
        stored_hash = getattr(state, "context_hash", "") if state else ""

        # Routing decision
        if _is_hot_path(prompt):
            path = "hot"
            # HOT path dedup: if state is unchanged since last turn, short-circuit
            if (
                current_hash
                and current_hash == stored_hash
                and turn_count > 2
                and not getattr(state, "needs_onboarding", False)
            ):
                # State unchanged and no onboarding required — skip context re-injection
                print(json.dumps({"continue": True}))
                return
            briefing = _assemble_hot(_query_session_state(session_id))
        else:
            intents = _classify_intents(prompt)
            if _is_fast_path(prompt, intents):
                path = "fast"
                briefing = _assemble_fast(prompt, intents, project, session_id, state_hash=current_hash)
            else:
                path = "slow"
                briefing = _assemble_slow(prompt, project, session_id, state_hash=current_hash)

        # Persist new hash after routing (only update when we proceed past the short-circuit)
        if state and current_hash and current_hash != stored_hash:
            try:
                state.update(context_hash=current_hash)
            except Exception:
                pass

        # --- Change 2: Pressure-scaled budget ---
        # Query context pressure level and apply corresponding budget multiplier
        budget_multiplier = 1.0
        try:
            sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
            from context_pressure import PressureTracker, PressureLevel
            pressure = PressureTracker(session_id).get_level()
            if pressure == PressureLevel.CRITICAL:
                budget_multiplier = 0.25
            elif pressure == PressureLevel.HIGH:
                budget_multiplier = 0.5
        except Exception:
            pass  # fail open — use default 1.0 multiplier

        if budget_multiplier < 1.0:
            briefing = _enforce_budget_scaled(briefing, path, budget_multiplier)
        else:
            briefing = _enforce_budget(briefing, path)

        # --- Feed the pressure tracker with this turn's byte contribution ---
        try:
            sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
            from context_pressure import PressureTracker
            _tracker = PressureTracker(session_id)
            _tracker.increment_turn(
                prompt_bytes=len(prompt.encode("utf-8")),
                briefing_bytes=len(briefing.encode("utf-8")) if briefing else 0,
            )
        except Exception:
            pass  # fail open

        if not briefing and not onboarding_directive and not _reconnect_notification:
            print(json.dumps({"continue": True}))
            return

        # --- Change 3: Merge all content into a single <system-reminder> block ---
        # Sanitize injection attempts in each part individually
        header = (
            f"<!-- wicked-garden | path={path} "
            f"| turn={turn_count} -->"
        )
        all_parts = [header]

        if briefing:
            sanitized = briefing.replace("</system-reminder>", "")
            all_parts.append(sanitized)

        if _reconnect_notification:
            reconnect_safe = _reconnect_notification.replace("</system-reminder>", "")
            all_parts.append(f"[Reconnect] {reconnect_safe}")

        if onboarding_directive:
            onboarding_safe = onboarding_directive.replace("</system-reminder>", "")
            all_parts.append(onboarding_safe)

        merged_context = f"<system-reminder>\n{chr(10).join(all_parts)}\n</system-reminder>"

        # --- Crew recommendation heuristic ---
        # Suggest crew on SLOW path for complex requests when:
        #   1. Path is "slow" (complex / ambiguous prompt)
        #   2. Inline complexity estimate >= 2
        #   3. Prompt does not already reference a crew command
        #   4. No active crew project in session state (uses active_project_id, not cp_project_id)
        #   5. Hint not shown OR complexity is very high (>= 3) — re-fires once at max complexity
        complexity_score = _estimate_complexity(prompt)
        if path == "slow" and complexity_score >= 2:
            if "/crew:" not in prompt:
                # Use active_project_id (not cp_project_id) to correctly gate the hint
                _active_project = getattr(state, "active_project_id", None) if state else None
                _hint_shown = getattr(state, "crew_hint_shown", False) if state else False
                # Re-fire if very high complexity (3), even if hint was shown before
                _should_show = (not _hint_shown) or (complexity_score >= 3)
                if not _active_project and _should_show:
                    crew_hint = (
                        "[Suggestion] This request has characteristics of a complex multi-phase project. "
                        "Consider using /wicked-garden:crew:start to manage it as a structured crew project."
                    )
                    # Append hint inside the existing merged block (still one block)
                    merged_context = merged_context[:-len("</system-reminder>")] + crew_hint + "\n</system-reminder>"
                    # Mark as shown (caps re-fires until next session)
                    try:
                        if state:
                            state.update(crew_hint_shown=True)
                    except Exception:
                        pass

        # --- Jam session suggestion ---
        # Suggest jam on FAST or SLOW path when prompt contains ambiguity signals,
        # not blocked by an urgent onboarding directive.
        if path in ("fast", "slow") and not onboarding_directive:
            merged_context = _suggest_jam(prompt, state, merged_context)

        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": merged_context,
            },
            "continue": True,
        }
        print(json.dumps(output))

    except Exception as e:
        print(f"[wicked-garden] prompt_submit error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
