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
        port = int(os.environ.get("WICKED_BRAIN_PORT", "4242"))
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
        lines.append("source: wicked-mem")
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


def _build_synthesis_directive(prompt: str, complexity: float, is_risky: bool, state) -> str:
    """Build the synthesis skill invocation directive for complex/risky prompts."""
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

    # Encode args as JSON so the skill can unambiguously parse all fields,
    # including turns_summary which is itself pipe-separated internally.
    import json as _json
    args_dict = {
        "complexity": round(complexity, 2),
        "risk": is_risky,
        "prompt": prompt[:500],
    }
    if turns_summary:
        args_dict["turns"] = turns_summary[:300]

    args_str = _json.dumps(args_dict)

    return (
        "[Context Assembly] This prompt requires deep context synthesis.\n"
        "BEFORE answering, invoke the synthesis skill:\n\n"
        f"  Skill(skill='wicked-garden:smaht:synthesize', args='{args_str}')\n\n"
        "Read the CONTEXT BRIEFING it produces. Use it to ground your response. "
        "Answer the original prompt only after the briefing is complete."
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

    # --- Source 3: Kanban in-progress tasks (optional, fail gracefully) ---
    in_progress_tasks = []
    try:
        kanban_script = _SCRIPTS_DIR / "kanban" / "kanban.py"
        if kanban_script.exists():
            import subprocess
            python_shim = _PLUGIN_ROOT / "scripts" / "_python.sh"
            result = subprocess.run(
                ["sh", str(python_shim), str(kanban_script), "list-tasks",
                 "--status", "in_progress", "--json"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                tasks_data = json.loads(result.stdout)
                if isinstance(tasks_data, list):
                    in_progress_tasks = [
                        t.get("subject", t.get("title", "untitled"))
                        for t in tasks_data[:5]
                    ]
    except Exception:
        pass  # kanban query is best-effort

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

    # Session goal capture on turns 1-2
    _capture_session_goal(prompt, turn_count, project, session_id)

    # Complexity + risk gate — inject synthesis skill directive for complex/risky prompts.
    # Uses Router path decision (most accurate) with inline risk scoring as a fallback.
    # Synthesis is skipped if onboarding is pending (no context yet to synthesize from).
    if not onboarding_directive:
        complexity, is_risky = _score_complexity_and_risk(prompt, state)
        _should_synthesize = False
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
            _should_synthesize = (
                not _is_near_hot
                and (
                    (_r.path.value == "slow" and _has_technical)
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
            synthesis_directive = _build_synthesis_directive(prompt, complexity, is_risky, state)
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
        # Delegate all routing and context assembly to smaht v2 Orchestrator.
        # The Orchestrator handles HOT/FAST/SLOW routing, adapter queries,
        # history condenser updates, and budget enforcement.
        from orchestrator import Orchestrator
        orchestrator = Orchestrator(session_id=session_id)
        result = _gather_context_sync(orchestrator, prompt)
        briefing = result.briefing
        path = result.path_used

        _log("smaht", "verbose", "prompt.routed",
             detail={"path": path, "turn": turn_count,
                     "word_count": len(prompt.split()),
                     "latency_ms": result.latency_ms,
                     "sources": result.sources_queried})

        # Feed context pressure tracker with this turn's byte contribution
        try:
            from context_pressure import PressureTracker, PressureLevel
            pressure_tracker = PressureTracker(session_id)
            pressure_tracker.increment_turn(
                prompt_bytes=len(prompt.encode("utf-8")),
                briefing_bytes=len(briefing.encode("utf-8")) if briefing else 0,
            )
        except Exception:
            pass  # fail open

        # WIP recovery: inject working state after context compaction
        wip_block = _build_wip_recovery_block(session_id, project)

        if not briefing and not onboarding_directive and not wip_block:
            print(json.dumps({"continue": True}))
            return

        # Build output: single <system-reminder> block with all context parts
        header = (
            f"<!-- wicked-garden | path={path} "
            f"| turn={turn_count} -->"
        )
        all_parts = [header]

        # WIP recovery block goes first so it's the first thing the model sees
        if wip_block:
            all_parts.append(wip_block)

        # Onboarding directive goes next for high priority
        if onboarding_directive:
            all_parts.append(onboarding_directive)

        if briefing:
            sanitized = briefing.replace("</system-reminder>", "")
            # Directive framing: makes the briefing authoritative rather than supplementary.
            # Claude should ground its response in this context, not supplement it with guesses.
            all_parts.append(
                "Ground your response in this project context. "
                "Do not assume or infer beyond what is stated here.\n"
            )
            all_parts.append(sanitized)

        # Periodic memory storage nudge (every 10 turns)
        _STORAGE_NUDGE_INTERVAL = 10
        if turn_count > 0 and turn_count % _STORAGE_NUDGE_INTERVAL == 0:
            all_parts.append(
                "[Memory] Checkpoint: If recent work produced any decisions, gotchas, "
                "or reusable patterns, store them now with /wicked-garden:mem:store."
            )

        # Crew routing suggestion: SLOW + high complexity, once per session
        if path == "slow" and "/crew:" not in prompt:
            try:
                from router import Router
                _complexity = Router()._estimate_complexity(prompt)
            except Exception:
                _complexity = 0
            _is_crew_eligible = _complexity >= 3
            if _is_crew_eligible:
                _active_project = getattr(state, "active_project_id", None) if state else None
                _hint_shown = getattr(state, "crew_hint_shown", False) if state else False
                if not _active_project and not _hint_shown:
                    _brief = prompt.strip()[:60].rstrip().rstrip(",.")
                    all_parts.append(
                        "[Suggestion] This request looks like a structured multi-phase project. "
                        "Consider starting a crew workflow:\n\n"
                        f"/wicked-garden:crew:start \"{_brief}...\"\n\n"
                        "Reply with the command above to start, or continue inline if you prefer."
                    )
                    try:
                        if state:
                            state.update(crew_hint_shown=True)
                    except Exception:
                        pass

        # Jam suggestion: on FAST or SLOW path when ambiguity signals present
        if path in ("fast", "slow"):
            jam_hint = _suggest_jam(prompt, state)
            if jam_hint:
                all_parts.append(jam_hint)

        # Discovery hints: suggest commands based on prompt intent (Issue #322)
        if path in ("fast", "slow"):
            discovery_hint = _suggest_discovery(prompt, state)
            if discovery_hint:
                all_parts.append(discovery_hint)

        merged_context = f"<system-reminder>\n{chr(10).join(all_parts)}\n</system-reminder>"

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
