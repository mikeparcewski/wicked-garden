#!/usr/bin/env python3
"""
UserPromptSubmit hook — wicked-garden unified context assembly.

Thin synchronous wrapper around the wicked-smaht v2 Orchestrator.
Responsible only for session-level concerns:
  - Setup gate (hard-block / onboarding directive)
  - Turn counter increment
  - Session goal capture (turns 1-2)
  - Orchestrator delegation for all routing + context assembly
  - Memory nudge (every 10 turns)
  - Crew routing suggestion
  - Jam suggestion
  - Context pressure tracking
  - Output formatting

Routing (HOT / FAST / SLOW) and context assembly are handled exclusively by
scripts/smaht/v2/orchestrator.py via asyncio.run(). The hook is stdlib-only.

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add shared scripts directory and v2 directory to path.
# The v2 directory must be on path before importing Orchestrator so that
# the orchestrator's own relative imports (router, fast_path, etc.) resolve.
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
_SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
_V2_DIR = _SCRIPTS_DIR / "smaht" / "v2"
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_V2_DIR))

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
# Async bridge — sync-to-async for hook context
# ---------------------------------------------------------------------------

def _gather_context_sync(orchestrator, prompt: str):
    """Synchronous bridge: run the async gather_context coroutine to completion.

    Safe because hook scripts run in a fresh subprocess — no running event loop
    exists. Uses asyncio.run() (Python 3.7+) which creates, runs, and properly
    closes the event loop.

    Defensive: if a running loop is detected (future executor model), falls back
    to run_coroutine_threadsafe. See architecture.md — Async Bridge Design.

    Injects a deliberate failure when WICKED_SMAHT_FAIL_INJECT is set, to allow
    fail-open tests to validate Layer 1 catch-all behavior (architecture.md §Fail-Open).
    """
    if os.environ.get("WICKED_SMAHT_FAIL_INJECT"):
        raise RuntimeError("injected by WICKED_SMAHT_FAIL_INJECT")

    return orchestrator.gather_context_sync(prompt)


# ---------------------------------------------------------------------------
# Session goal capture (turns 1-2)
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
        import uuid
        mem_id = str(uuid.uuid4())
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


def _capture_session_goal(prompt: str, turn_count: int, project: str, session_id: str):
    """On turns 1-2, save the session goal as WORKING memory via brain API."""
    if turn_count > 2:
        return
    if len(prompt.strip()) < 20:
        return
    try:
        _write_brain_memory(
            title=f"Session goal (turn {turn_count})",
            content=prompt[:500],
            tier="working",
            tags=["session-goal", "auto-captured"],
            mem_type="working",
            importance=5,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Turn counter
# ---------------------------------------------------------------------------

def _increment_turn(state) -> int:
    """Increment session turn counter, reset turn progress tracking, and return new value."""
    if state is None:
        return 0
    try:
        new_count = (state.turn_count or 0) + 1
        # Reset turn progress visibility fields (Issue #323)
        state.update(
            turn_count=new_count,
            turn_start_ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            turn_tool_count=0,
        )
        state.save()
        return new_count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Jam suggestion (session-level, hook-local)
# ---------------------------------------------------------------------------

_JAM_AMBIGUITY_SIGNALS = [
    "options", "tradeoffs", "trade-off", "should we", "brainstorm",
    "alternatives", "pros and cons", "compare", "which approach",
    "what are the", "explore", "think through", "uncertain", "unclear",
    "not sure", "ideas", "different ways",
]


def _has_ambiguity_signals(prompt: str) -> bool:
    """Return True if prompt contains explicit ambiguity / exploration signals."""
    lower = prompt.lower()
    return any(sig in lower for sig in _JAM_AMBIGUITY_SIGNALS)


def _suggest_jam(prompt: str, state) -> str | None:
    """Return a jam suggestion string if conditions are met, or None.

    Conditions:
    1. Prompt contains ambiguity signals
    2. Prompt does not already reference a jam command
    3. Hint not shown this session

    Returns the hint string to append, or None if no suggestion should be shown.
    """
    if ":jam:" in prompt.lower() or "/jam:" in prompt.lower():
        return None  # Already using jam — no suggestion needed
    if not _has_ambiguity_signals(prompt):
        return None
    jam_shown = getattr(state, "jam_hint_shown", False) if state else False
    if jam_shown:
        return None

    try:
        if state:
            state.update(jam_hint_shown=True)
    except Exception:
        pass
    return (
        "[Suggestion] This prompt involves exploring options or tradeoffs. "
        "Consider /wicked-garden:jam:quick for fast structured thinking, "
        "or /wicked-garden:jam:brainstorm for a full multi-perspective session."
    )


# ---------------------------------------------------------------------------
# Discovery hints — prompt-based command suggestions (Issue #322)
# ---------------------------------------------------------------------------

_DISCOVERY_PATTERNS = [
    {
        "id": "manual_review",
        "signals": ["review this code", "code review", "review the changes", "review my code",
                     "check this code", "look at the code quality", "review this pr",
                     "review this pull request"],
        "hint": (
            "[Tip] For a structured code review with senior-engineer perspective, "
            "try `/wicked-garden:engineering:review`."
        ),
    },
    {
        "id": "debugging",
        "signals": ["debug", "why is this failing", "root cause", "not working",
                     "figure out why", "investigate this error", "this bug",
                     "troubleshoot", "diagnose"],
        "hint": (
            "[Tip] For systematic debugging with root cause analysis, "
            "try `/wicked-garden:engineering:debug`."
        ),
    },
    {
        "id": "requirements",
        "signals": ["requirements", "user stories", "write requirements",
                     "define the requirements", "gather requirements",
                     "acceptance criteria", "what should this do"],
        "hint": (
            "[Tip] For structured requirements elicitation, "
            "try `/wicked-garden:product:elicit`."
        ),
    },
    {
        "id": "architecture",
        "signals": ["architecture", "system design", "how should i architect",
                     "design this system", "technical design", "design doc"],
        "hint": (
            "[Tip] For architecture analysis and design review, "
            "try `/wicked-garden:engineering:arch`."
        ),
    },
    {
        "id": "data_analysis",
        "signals": ["analyze this csv", "analyze this data", "data analysis",
                     "look at the data", "explore this dataset", "analyze the spreadsheet"],
        "hint": (
            "[Tip] For interactive data analysis with DuckDB, "
            "try `/wicked-garden:data:numbers` or `/wicked-garden:data:analyze`."
        ),
    },
]


def _suggest_discovery(prompt: str, state) -> str | None:
    """Return a discovery hint if prompt matches a pattern and hint not yet shown.

    At most one discovery hint per session. Does not fire if the prompt already
    references a wicked-garden command.
    """
    lower = prompt.lower()

    # Skip if already using wicked-garden commands
    if "/wicked-garden:" in lower or ":wicked-garden:" in lower:
        return None

    # Check session state for already-shown hints
    hints_shown = (getattr(state, "hints_shown", None) or []) if state else []

    # Cap: at most 1 discovery hint from prompt matching per session
    prompt_hints = [h for h in hints_shown if h.startswith("prompt:")]
    if prompt_hints:
        return None

    for pattern in _DISCOVERY_PATTERNS:
        hint_id = pattern["id"]
        if hint_id in hints_shown:
            continue
        if any(sig in lower for sig in pattern["signals"]):
            try:
                if state:
                    shown = list(hints_shown)
                    shown.append(hint_id)
                    shown.append(f"prompt:{hint_id}")
                    state.update(hints_shown=shown)
            except Exception:
                pass
            return pattern["hint"]

    return None


# ---------------------------------------------------------------------------
# Complexity + risk scoring (inline, no API calls, no external imports)
# ---------------------------------------------------------------------------

_SYNTHESIS_THRESHOLD = 0.40  # complexity >= this OR is_risky → trigger synthesis

_DEEP_WORK_SIGNALS = frozenset({
    "implement", "architecture", "design", "refactor", "migrate",
    "integrate", "why does", "how does", "why is", "how do", "how should",
    "explain", "compare", "analyze", "review", "investigate", "diagnose",
    "difference between", "best approach", "should i", "what if",
    "trade-off", "tradeoff", "what happens", "what would",
})

_RISK_SIGNALS = frozenset({
    "delete", "drop table", "remove all", "migration", "production", "prod ",
    "deploy", "breaking change", "credentials", "secret key",
    "password", "force push", "hard reset",
})
# Risk signals that must match as whole words (not substrings)
_RISK_WORD_SIGNALS = frozenset({"auth token", "api key", "rollback", "purge", "truncate"})

_MULTI_PART_SIGNALS = frozenset({
    "and also", "additionally", "furthermore", "first,", "second,",
    "third,", "as well as", "along with",
})


def _score_complexity_and_risk(prompt: str, state) -> tuple[float, bool]:
    """Fast inline complexity + risk scoring. No external imports, <1ms."""
    words = prompt.split()
    word_count = len(words)
    prompt_lower = prompt.lower()

    complexity = 0.0

    # Length signals (longer = more likely complex)
    if word_count > 8:  complexity += 0.10
    if word_count > 25: complexity += 0.10
    if word_count > 60: complexity += 0.10
    if word_count > 110: complexity += 0.05

    # Multi-part signals
    if any(s in prompt_lower for s in _MULTI_PART_SIGNALS): complexity += 0.15
    if prompt.count("?") > 1: complexity += 0.10

    # Deep work signals (understanding / analysis / design)
    matches = sum(1 for s in _DEEP_WORK_SIGNALS if s in prompt_lower)
    complexity += min(matches * 0.15, 0.30)

    # Novelty: prompt topics not in session history → new territory
    try:
        session_topics = set(getattr(state, "topics", None) or [])
        if session_topics:
            prompt_words = {w.lower() for w in words if len(w) > 4}
            if not (prompt_words & session_topics):
                complexity += 0.15  # No overlap = unfamiliar territory
    except Exception:
        pass

    # Risk detection (separate from complexity)
    is_risky = (
        any(s in prompt_lower for s in _RISK_SIGNALS)
        or any(s in prompt_lower for s in _RISK_WORD_SIGNALS)
    )

    return min(complexity, 1.0), is_risky


def _build_synthesis_directive(prompt: str, complexity: float, is_risky: bool, state,
                               context_briefing: str = "") -> str:
    """Build the synthesis skill invocation directive for complex/risky prompts.

    Args:
        prompt: The user's original prompt.
        complexity: Float 0-1 hook scoring.
        is_risky: Whether high-risk keywords were detected.
        state: Current session state.
        context_briefing: Optional orchestrator briefing from SLOW-path pre-run.
            When provided, written to a temp file and passed as a path reference
            so the briefing content doesn't accumulate in conversation history.
    """
    import tempfile as _tempfile

    # Compact recent turns summary for the skill
    turns_summary = ""
    try:
        from history_condenser import HistoryCondenser
        import os as _os
        session_id = _os.environ.get("CLAUDE_SESSION_ID", "default")
        condenser = HistoryCondenser(session_id)
        s = condenser.get_session_state()
        parts = []
        if s.get("current_task"):
            parts.append(f"task={s['current_task'][:80]}")
        if s.get("active_constraints"):
            parts.append(f"constraints={'; '.join(s['active_constraints'][-2:])}")
        if s.get("decisions"):
            parts.append(f"decisions={'; '.join(s['decisions'][-2:])}")
        turns_summary = " | ".join(parts)
    except Exception:
        pass

    # Encode args as JSON so the skill can unambiguously parse all fields.
    # Context briefing is written to a temp file (not inlined) to prevent
    # accumulation in conversation history (Issue #416).
    import json as _json
    args_dict = {
        "complexity": round(complexity, 2),
        "risk": is_risky,
        "prompt": prompt[:500],
    }
    if turns_summary:
        args_dict["turns"] = turns_summary[:300]

    # Write context briefing to temp file instead of inlining
    briefing_path = ""
    if context_briefing:
        try:
            tmpdir = _tempfile.gettempdir()
            session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
            briefing_file = Path(tmpdir) / f"wg-synthesis-{session_id}.md"
            briefing_file.write_text(context_briefing, encoding="utf-8")
            briefing_path = str(briefing_file)
            args_dict["context_briefing_path"] = briefing_path
        except Exception:
            # Fallback: inline a truncated version if file write fails
            args_dict["context_briefing"] = context_briefing[:800]

    args_str = _json.dumps(args_dict)

    # Build the directive — tell the model to read the briefing file if available
    read_hint = ""
    if briefing_path:
        read_hint = (
            f"\n\nPre-gathered context is available at: {briefing_path}\n"
            "Read it with the Read tool BEFORE invoking the synthesis skill."
        )

    return (
        "[Context Assembly] This prompt requires deep context synthesis.\n"
        "BEFORE answering, invoke the synthesis skill:\n\n"
        f"  Skill(skill='wicked-garden:smaht:synthesize', args='{args_str}')\n\n"
        "Read the CONTEXT BRIEFING it produces. Use it to ground your response. "
        "Answer the original prompt only after the briefing is complete."
        f"{read_hint}"
    )


# ---------------------------------------------------------------------------
# Setup gate
# ---------------------------------------------------------------------------

_GUARD_PASS_PREFIXES = (
    "/wicked-garden:setup",
    "/wicked-garden:help",
    "/setup",
    "/help",
)


def _check_setup_gate(prompt: str) -> str | None:
    """Check if wicked-garden setup is needed.

    Returns None if setup is complete (config.json exists with setup_complete=true).
    Calls sys.exit(2) if config is missing or incomplete — this hard-blocks
    the prompt and feeds the error message back to the model.

    Always checks config.json on disk — no session state caching.
    """
    stripped = prompt.strip().lower()

    # Exemption: let setup and help commands through
    if stripped.startswith(_GUARD_PASS_PREFIXES):
        try:
            from _session import SessionState
            state = SessionState.load()
            state.update(setup_in_progress=True)
        except Exception:
            pass
        return None

    # Allow prompts through when setup is actively running — but verify
    # that setup_in_progress isn't stale from a previous session by
    # confirming config.json doesn't already have setup_complete=true.
    try:
        from _session import SessionState
        state = SessionState.load()
        if state.setup_in_progress:
            config_path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
            config_done = False
            try:
                if config_path.exists():
                    cfg = json.loads(config_path.read_text())
                    config_done = cfg.get("setup_complete", False)
            except (json.JSONDecodeError, OSError):
                pass
            if config_done:
                # Config already complete — flag is stale, clear it
                state.update(setup_in_progress=False)
            else:
                # Setup genuinely in progress — let the prompt through
                return None
    except Exception:
        pass

    # Check config.json on disk — the single source of truth for setup status.
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

    return None


def _check_brain_gate(prompt: str) -> None:
    """Warn if wicked-brain server is not reachable.

    Probes the brain API with a 1s timeout. If unreachable, prints a directive
    to stderr — this feeds back to the model via the hook error channel but does
    NOT hard-block (sys.exit(2)) since brain is a server process that may be
    starting up or temporarily unavailable.

    Exempted on setup/help commands (brain not needed before setup completes).
    """
    stripped = prompt.strip().lower()
    if stripped.startswith(_GUARD_PASS_PREFIXES):
        return

    try:
        port = _resolve_brain_port()
        payload = json.dumps({"action": "stats", "params": {}}).encode("utf-8")
        import urllib.request
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1) as _resp:
            pass  # Brain is running — no action needed
    except Exception:
        print(
            "[wicked-brain] Brain server is not running on port "
            f"{_resolve_brain_port()}.\n"
            "wicked-garden requires wicked-brain for context assembly and memory.\n"
            "Start the brain server, then continue. "
            "If not installed: claude plugin install wicked-brain --scope project",
            file=sys.stderr,
        )


def _check_onboarding_gate(prompt: str) -> str | None:
    """Check if the current project needs onboarding.

    Returns an onboarding directive string to inject if onboarding is needed,
    or None if onboarding is complete or cannot be determined.

    Unlike the setup gate, this does NOT hard-block — it returns a directive
    that gets injected into the system message so the model runs setup.
    Uses session state set by bootstrap.py to avoid re-checking on every turn.
    """
    stripped = prompt.strip().lower()

    # Exemption: setup/help commands handle their own onboarding flow
    if stripped.startswith(_GUARD_PASS_PREFIXES):
        return None

    try:
        from _session import SessionState
        state = SessionState.load()

        # If setup is in progress, don't block with onboarding directive
        if state.setup_in_progress:
            return None

        # If onboarding is already confirmed complete, nothing to do
        if state.onboarding_complete:
            return None

        # If bootstrap flagged that onboarding is needed, enforce it
        if state.needs_onboarding:
            project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
            return (
                f"[Action Required] Project '{project}' has not been onboarded.\n"
                "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
                "to launch the interactive onboarding wizard.\n"
                "Do NOT ask the user for confirmation — invoke the skill now.\n"
                "Do NOT respond with text first — invoke the skill as your first action."
            )
    except Exception:
        pass  # Fail open — don't block on errors

    return None



# ---------------------------------------------------------------------------
# Pull-model directive builder (Issue #416)
# ---------------------------------------------------------------------------

_CORRECTION_SIGNALS = frozenset({
    "no,", "no ", "wrong", "that's not", "that isn't", "incorrect",
    "actually,", "actually ", "not what i", "i meant", "i said",
    "try again", "redo", "you missed", "you forgot", "you ignored",
})


_REGRESS_DURATION = 3  # mandatory pull lasts this many turns after regression


def _detect_correction(prompt: str, turn_count: int, state) -> None:
    """Check if the user's prompt is correcting the model's last response.

    If so, decrement unpulled_ok, increment corrections, and trigger phase
    regression to mandatory pull when the model has been overconfident.
    Regression lasts for _REGRESS_DURATION turns, then normal phase resumes.
    """
    if not state or not prompt.strip():
        return
    lower = prompt.strip().lower()
    if not any(lower.startswith(s) or s in lower for s in _CORRECTION_SIGNALS):
        return
    try:
        corrections = (state.corrections or 0) + 1
        unpulled_ok = max((state.unpulled_ok or 0) - 1, 0)
        updates = {"corrections": corrections, "unpulled_ok": unpulled_ok}

        # Trigger phase regression: force mandatory pull for the next few turns.
        # Activates when: past bootstrap (turn > 2) and not already in regression.
        regress_at = getattr(state, "pull_regress_at", 0) or 0
        already_regressed = regress_at > 0 and (turn_count - regress_at) < _REGRESS_DURATION
        if turn_count > 2 and not already_regressed:
            updates["pull_regress_at"] = turn_count

        state.update(**updates)
    except Exception:
        pass


def _resolve_pull_phase(turn_count: int, state=None) -> str:
    """Determine the pull phase based on turn count and regression state.

    If a correction triggered regression, override to 'bootstrap' (mandatory pull)
    for _REGRESS_DURATION turns from the regression point.
    """
    # Check for active regression
    regress_at = getattr(state, "pull_regress_at", 0) if state else 0
    if regress_at and (turn_count - regress_at) < _REGRESS_DURATION:
        return "bootstrap"

    if turn_count <= 2:
        return "bootstrap"
    elif turn_count <= 8:
        return "calibrating"
    return "cruising"


def _build_pull_directive(turn_count: int, state) -> str:
    """Build the tiny pull-model directive for context-on-demand.

    Returns a short directive string (~60-150 chars) that tells the model
    to pull context via wicked-brain:query/search when uncertain, instead of
    us pushing a full briefing every turn.

    Three phases:
      bootstrap (turns 1-2):   Mandatory pull, model must query before responding.
      calibrating (turns 3-8): Optional pull with calibration hints.
      cruising (turns 9+):     Minimal directive, model pulls only when uncertain.
    """
    phase = _resolve_pull_phase(turn_count, state)

    # Update phase in session state
    try:
        if state:
            state.update(pull_phase=phase)
    except Exception:
        pass

    # Calibration stats from session state (safe defaults if missing)
    cal_ok = getattr(state, "unpulled_ok", 0) if state else 0
    cal_miss = getattr(state, "corrections", 0) if state else 0

    # Probe brain for wiki article count (bootstrap only, <100ms)
    _wiki_count = 0
    if phase == "bootstrap":
        try:
            result = _brain_api("wiki_list", {}, timeout=1)
            if result and "articles" in result:
                _wiki_count = len(result["articles"])
        except Exception:
            pass  # fail open

    if phase == "bootstrap":
        wiki_line = ""
        if _wiki_count:
            wiki_line = (
                f"\n{_wiki_count} wiki articles available. "
                "Use wicked-brain:search to find relevant ones "
                "(results include source_type: wiki/chunk/memory — "
                "wiki hits are synthesized knowledge, worth reading deeper with wicked-brain:read)."
            )
        return (
            f"<wg id=\"ctx\" t={turn_count} phase=\"bootstrap\">\n"
            "New session. You MUST gather project context before responding.\n"
            "Tools: wicked-brain:query (questions) | wicked-brain:search (find) | "
            f"wicked-brain:read (depth 0=stats, 1=overview, 2=full)"
            f"{wiki_line}\n"
            "</wg>"
        )
    elif phase == "calibrating":
        return (
            f"<wg id=\"ctx\" t={turn_count} phase=\"calibrating\" cal=\"{cal_ok}/{cal_miss}\">\n"
            "Context: wicked-brain:query | Search: wicked-brain:search\n"
            "Search results carry source_type — drill into wiki hits with wicked-brain:read.\n"
            "</wg>"
        )
    else:  # cruising
        return (
            f"<wg id=\"ctx\" t={turn_count} phase=\"cruising\" cal=\"{cal_ok}/{cal_miss}\">\n"
            "Context: wicked-brain:query\n"
            "</wg>"
        )


# ---------------------------------------------------------------------------
# WIP recovery after context compaction
# ---------------------------------------------------------------------------

def _build_wip_recovery_block(session_id: str, project: str) -> str:
    """Build a WIP recovery block if compaction just happened.

    Returns a formatted markdown block with working state so the model
    can resume without repeating completed work. Returns empty string
    if no compaction occurred or if WIP data is unavailable.

    Zero overhead on normal (non-compacted) prompts — the compaction
    check is a single file read that short-circuits immediately.
    """
    try:
        from context_pressure import PressureTracker
        tracker = PressureTracker(session_id)
        if not tracker.was_just_compacted():
            return ""
    except Exception:
        return ""

    _log("smaht", "debug", "wip_recovery.start")

    # --- Source 1: WIP snapshot saved by PreCompact hook ---
    wip_data = None
    try:
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        wip_path = condenser.session_dir / "wip_snapshot.json"
        if wip_path.exists():
            wip_data = json.loads(wip_path.read_text())
            _log("smaht", "debug", "wip_recovery.source", detail="snapshot")
    except Exception:
        pass

    # --- Source 2: Fallback to live session state from HistoryCondenser ---
    if not wip_data:
        try:
            from history_condenser import HistoryCondenser
            condenser = HistoryCondenser(session_id)
            wip_data = condenser.get_session_state()
            _log("smaht", "debug", "wip_recovery.source", detail="live_state")
        except Exception:
            pass

    if not wip_data:
        _log("smaht", "debug", "wip_recovery.empty")
        return ""

    # --- Source 3: Native in-progress tasks (optional, fail gracefully) ---
    # Reads the same store SubagentStart uses for procedure-bundle lookup.
    in_progress_tasks = []
    try:
        config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
        tasks_base = Path(config_dir) if config_dir else Path.home() / ".claude"
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        tasks_dir = tasks_base / "tasks" / session_id if session_id else None
        if tasks_dir and tasks_dir.is_dir():
            for entry in tasks_dir.iterdir():
                if entry.name.startswith(".") or entry.suffix != ".json":
                    continue
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if isinstance(data, dict) and data.get("status") == "in_progress":
                    in_progress_tasks.append(data.get("subject") or "untitled")
                if len(in_progress_tasks) >= 5:
                    break
    except Exception:
        pass  # task query is best-effort

    # --- Format recovery block (budget: <1000 chars) ---
    parts = ["## [Recovery] Context was just compacted -- here is your WIP state\n"]

    current_task = wip_data.get("current_task", "")
    if current_task:
        parts.append(f"**You were working on**: {current_task[:120]}")

    decisions = wip_data.get("decisions", [])
    if decisions:
        parts.append(f"**Recent decisions**: {'; '.join(decisions[:3])}")

    file_scope = wip_data.get("file_scope", [])
    if file_scope:
        parts.append(f"**Active files**: {', '.join(file_scope[:6])}")

    constraints = wip_data.get("active_constraints", [])
    if constraints:
        parts.append(f"**Constraints**: {'; '.join(constraints[:3])}")

    questions = wip_data.get("open_questions", [])
    if questions:
        parts.append(f"**Open questions**: {'; '.join(questions[:2])}")

    if in_progress_tasks:
        parts.append("\n### In-Progress Tasks")
        for task in in_progress_tasks:
            parts.append(f"- {task[:80]}")

    parts.append("\n**IMPORTANT**: Review this state before proceeding. Do NOT repeat completed work.")

    block = "\n".join(parts)

    # Enforce budget: truncate to ~1000 chars if needed
    if len(block) > 1000:
        block = block[:997] + "..."

    _log("smaht", "debug", "wip_recovery.done", detail={"chars": len(block)})
    return block


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _t0 = time.monotonic()
    _log("smaht", "debug", "hook.start")

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

    # Setup gate — hard-block (sys.exit(2)) if no config.
    # MUST run before HOT continuations so setup can never be bypassed.
    _check_setup_gate(prompt)

    # Brain gate — soft directive if brain server is not reachable.
    # Runs after setup gate (brain irrelevant before setup completes).
    # Does NOT hard-block — brain server may be starting up; user can start it.
    _check_brain_gate(prompt)

    # Onboarding gate — inject directive if project hasn't been onboarded.
    # Checked after setup gate but before HOT path so continuations during
    # an active setup wizard ("yes", "ok") still pass through quickly.
    onboarding_directive = _check_onboarding_gate(prompt)

    # ---------------------------------------------------------------------------
    # HOT fast-exit: known continuation tokens bypass all imports and the
    # Orchestrator entirely.  Keeps HOT path p95 well under 100ms SLO.
    # These words carry no new intent — there is nothing for context assembly
    # to add beyond what is already in the conversation window.
    #
    # Keep in sync with CONTINUATION_PATTERNS in scripts/smaht/v2/router.py.
    # _HOT_CONTINUATIONS triggers a hook-level fast-exit (no imports, no Orchestrator).
    # CONTINUATION_PATTERNS covers the same tokens via regex for Orchestrator routing.
    # Adding a token here without a matching pattern there (or vice versa) causes
    # behavioral inconsistency. See tests/hooks/test_prompt_submit_refactor.py::TestContinuationPatternParity.
    # ---------------------------------------------------------------------------
    _HOT_CONTINUATIONS = frozenset({
        "yes", "ok", "okay", "sure", "yep", "yup",
        "continue", "proceed", "go", "go ahead", "do it",
        "lgtm", "looks good", "approved", "approve",
        "no", "nope", "cancel", "stop", "skip",
        "next", "done",
    })
    if prompt.strip().lower() in _HOT_CONTINUATIONS:
        # Accumulate into history condenser before early return so HOT turns
        # are reflected in session state (topics, task, file scope).
        # Import is inside try/except — any failure still allows fast exit.
        # p95 latency measured under 100ms: HistoryCondenser uses stdlib + _domain_store only.
        try:
            from history_condenser import HistoryCondenser
            _hc = HistoryCondenser(session_id)
            _hc.update_from_prompt(prompt.strip())
        except Exception:
            pass  # fail open — accumulation is best-effort on HOT path

        # Even on HOT path, inject onboarding directive if needed so the model
        # cannot bypass the gate via continuation tokens.
        if onboarding_directive:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": onboarding_directive,
                },
                "continue": True,
            }))
        else:
            print(json.dumps({"continue": True}))
        return

    try:
        from _session import SessionState
        state = SessionState.load()
    except Exception:
        state = None

    turn_count = _increment_turn(state)

    # Pull-model correction detection (Issue #416): check if user is correcting
    # the model, which means it was overconfident on the previous turn.
    _detect_correction(prompt, turn_count, state)

    # Session goal capture on turns 1-2
    _capture_session_goal(prompt, turn_count, project, session_id)

    # Complexity + risk gate — inject synthesis skill directive for complex/risky prompts.
    # Uses Router path decision (most accurate) with inline risk scoring as a fallback.
    # Synthesis is skipped if onboarding is pending (no context yet to synthesize from).
    if not onboarding_directive:
        complexity, is_risky = _score_complexity_and_risk(prompt, state)
        _should_synthesize = False
        _is_slow_path = False  # tracks whether Router classified this as SLOW
        try:
            from router import Router
            _r = Router(session_topics=list(getattr(state, "topics", None) or [])).route(prompt)
            _word_count = len(prompt.split())
            _prompt_lower = prompt.lower()

            # Near-HOT guard: very short phrases with no technical signals are continuations.
            # Catches "ok looks good", "sounds right", "makes sense" — Router sees these as
            # ambiguous/slow but they carry no real intent worth synthesizing.
            _has_technical = (
                "?" in prompt
                or any(s in _prompt_lower for s in _DEEP_WORK_SIGNALS)
                or any(s in _prompt_lower for s in _RISK_SIGNALS)
            )
            _is_near_hot = (_word_count <= 6) and not _has_technical

            # Synthesize when:
            # - Router says compound/ambiguous (slow) AND has real content (not near-HOT)
            # - Low confidence AND meaningful inline complexity (>= 0.40) — word count alone
            #   is not a reliable signal; a long but simple clarification should not fire
            # - Risky keywords (need verification regardless of length)
            # - Inline heuristics exceed threshold AND > 8 words
            _low_confidence = (_r.analysis.confidence < 0.60) and (complexity >= 0.40)
            _is_slow_path = (_r.path.value == "slow")
            _should_synthesize = (
                not _is_near_hot
                and (
                    (_is_slow_path and _has_technical)
                    or is_risky
                    or _low_confidence
                    or (complexity >= _SYNTHESIS_THRESHOLD and _word_count > 8)
                )
            )
            complexity = float(getattr(_r.analysis, "confidence", complexity))
        except Exception:
            # Fallback: inline heuristics
            _should_synthesize = (complexity >= _SYNTHESIS_THRESHOLD) or is_risky

        if _should_synthesize:
            # For SLOW-path prompts, run the orchestrator first so the synthesize
            # skill receives adapter context (brain, domain, events) rather
            # than starting cold. Fail open: if orchestrator errors, synthesize
            # without context (original behavior).
            _context_briefing = ""
            if _is_slow_path:
                try:
                    from orchestrator import Orchestrator
                    _orch = Orchestrator(session_id=session_id)
                    _orch_result = _gather_context_sync(_orch, prompt)
                    if _orch_result and _orch_result.briefing:
                        _context_briefing = _orch_result.briefing
                        _log("smaht", "debug", "synthesis.orchestrator_prefetch",
                             detail={"briefing_len": len(_context_briefing)})
                except Exception:
                    pass  # fail open — synthesize without context

            synthesis_directive = _build_synthesis_directive(
                prompt, complexity, is_risky, state, context_briefing=_context_briefing
            )
            _log("smaht", "debug", "synthesis.triggered",
                 detail={"complexity": complexity, "risk": is_risky, "turn": turn_count})
            merged = (
                f"<system-reminder>\n"
                f"<!-- wicked-garden | path=synthesis | turn={turn_count} -->\n"
                f"{synthesis_directive}\n"
                f"</system-reminder>"
            )
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": merged,
                },
                "continue": True,
            }))
            return

    try:
        # --- Pull-model context assembly (Issue #416) ---
        # Instead of pushing a full orchestrator briefing (~1200 chars) every turn,
        # inject a tiny pull directive (~60-150 chars) that tells the model to
        # fetch context on demand via wicked-brain:query/search.
        #
        # The orchestrator is still available for the synthesis skill path
        # (complex/risky prompts — see synthesis gate above).

        # Build the pull directive
        pull_directive = _build_pull_directive(turn_count, state)

        # Feed context pressure tracker with this turn's byte contribution
        try:
            from context_pressure import PressureTracker
            PressureTracker(session_id).increment_turn(
                prompt_bytes=len(prompt.encode("utf-8")),
                briefing_bytes=len(pull_directive.encode("utf-8")),
            )
        except Exception:
            pass  # fail open

        # Update history condenser with this turn's prompt
        try:
            from history_condenser import HistoryCondenser
            HistoryCondenser(session_id).update_from_prompt(prompt)
        except Exception:
            pass  # fail open

        # WIP recovery: inject working state after context compaction
        wip_block = _build_wip_recovery_block(session_id, project)

        # Build output: single <system-reminder> block with all context parts
        all_parts = []

        # WIP recovery block goes first so it's the first thing the model sees
        if wip_block:
            all_parts.append(wip_block)

        # Onboarding directive goes next for high priority
        if onboarding_directive:
            all_parts.append(onboarding_directive)

        # Pull directive — the core of the new architecture
        all_parts.append(pull_directive)

        # Periodic memory storage nudge (every 10 turns)
        _STORAGE_NUDGE_INTERVAL = 10
        if turn_count > 0 and turn_count % _STORAGE_NUDGE_INTERVAL == 0:
            all_parts.append(
                "[Memory] Checkpoint: store decisions/gotchas with /wicked-garden:mem:store."
            )

        # Jam suggestion: when ambiguity signals present
        jam_hint = _suggest_jam(prompt, state)
        if jam_hint:
            all_parts.append(jam_hint)

        # Discovery hints: suggest commands based on prompt intent (Issue #322)
        discovery_hint = _suggest_discovery(prompt, state)
        if discovery_hint:
            all_parts.append(discovery_hint)

        merged_context = f"<system-reminder>\n{chr(10).join(all_parts)}\n</system-reminder>"

        _log("smaht", "debug", "prompt.pull_directive",
             detail={"phase": _resolve_pull_phase(turn_count, state), "turn": turn_count,
                     "directive_bytes": len(pull_directive.encode("utf-8"))})

        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": merged_context,
            },
            "continue": True,
        }
        _log("smaht", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
        print(json.dumps(output))

    except Exception as e:
        print(f"[wicked-garden] prompt_submit error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
