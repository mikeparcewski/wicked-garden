#!/usr/bin/env python3
"""
UserPromptSubmit hook — wicked-garden pull-model context assembly.

v6 replaced the v5 push-model orchestrator (deleted in #428) with a pull-model
architecture. The hook is now responsible only for session-level concerns:
  - Setup gate (hard-block / onboarding directive)
  - Facilitator re-evaluation directive (v6 Gate 3, #428)
  - Turn counter increment
  - Session goal capture (turns 1-2)
  - HOT fast-exit on continuation tokens
  - Pull-model directive injection (tiny, ~60-150 chars)
  - Memory nudge (every 10 turns)
  - Jam / discovery suggestion
  - Output formatting

Subagents pull context on demand via wicked-brain:search/query and
wicked-garden:search rather than having a briefing pushed every turn.
The hook is stdlib-only.

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add shared scripts directory to path.
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
_SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

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

    # Compact recent turns summary for the skill.
    # v6: the v5 HistoryCondenser ticket rail is gone; pull what SessionState
    # exposes (session_goal + active chain) as a minimal substitute.
    turns_summary = ""
    try:
        from _session import SessionState
        s = SessionState.load()
        parts = []
        goal = getattr(s, "session_goal", "") or ""
        if goal:
            parts.append(f"goal={goal[:80]}")
        chain = getattr(s, "active_chain_id", "") or ""
        if chain:
            parts.append(f"chain={chain}")
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


def _assemble_current_chain(chain_id: str) -> dict | None:
    """Invoke scripts/crew/current_chain.py to assemble re-eval context.

    Returns the assembled dict (tasks + counts + evidence manifests) or None on
    any failure. Used by the re-eval directive so Claude has real data to feed
    into propose-process instead of being told to 'figure it out'. Issue #431.
    """
    try:
        import subprocess
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if not plugin_root:
            return None
        script = Path(plugin_root) / "scripts" / "crew" / "current_chain.py"
        if not script.exists():
            return None
        python_shim = Path(plugin_root) / "scripts" / "_python.sh"
        cmd = ["sh", str(python_shim), str(script), chain_id]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None  # fail-open — directive still fires without the data


def _consume_facilitator_reeval(state) -> str | None:
    """v6 Gate 3 (#428): emit facilitator re-eval directive if flag is set.

    Reads ``state.facilitator_reeval_due`` and ``state.facilitator_reeval_chain``.
    When set, returns a systemMessage directive instructing Claude to invoke
    ``wicked-garden:crew:propose-process`` in re-evaluation mode on that chain
    BEFORE addressing the user's prompt.

    Clears the flag immediately (idempotent — fires exactly once per completion).
    Hooks cannot run the skill themselves (stdlib-only); this function just
    surfaces the directive.

    Issue #431: augments the directive with a structured ``current_chain`` dict
    so the re-eval call has real data (task states, counts, evidence) rather
    than prose "figure it out."

    Fail-open: returns None on any error.
    """
    if state is None:
        return None
    try:
        if not getattr(state, "facilitator_reeval_due", False):
            return None
        chain_id = getattr(state, "facilitator_reeval_chain", None) or "unknown"
        # Clear flag BEFORE returning so a handler failure still produces a
        # single-shot emission — not an infinite loop.
        state.update(facilitator_reeval_due=False, facilitator_reeval_chain=None)

        # Issue #431: assemble structured current_chain data for the re-eval.
        chain_data = _assemble_current_chain(chain_id) if chain_id != "unknown" else None
        # AC-5: build structured current_chain dict with required keys so the
        # re-eval directive contains "current_chain" as a JSON key — not prose.
        chain_block = ""
        if chain_data:
            counts = chain_data.get("counts", {})
            structured_chain = {
                "tasks": chain_data.get("tasks", []),
                "completed_count": counts.get("completed", 0),
                "evidence_manifests": chain_data.get("evidence_manifests", []),
            }
            chain_json = json.dumps(structured_chain, separators=(",", ":"))
            chain_block = (
                f"\n\ncurrent_chain: {chain_json}"
            )

        return (
            f"[Facilitator re-evaluation due] Chain `{chain_id}` had a task completion — "
            f"before addressing the user's prompt, invoke "
            f"`wicked-garden:crew:propose-process` in re-evaluation mode on this chain. "
            f"Update the process-plan.md and emit any task mutations "
            f"(prune, augment, re-tier) as TaskUpdate/TaskCreate calls with reasoning."
            f"{chain_block}"
        )
    except Exception:
        # Best-effort clear on error to avoid repeating directive in a tight loop
        try:
            state.update(facilitator_reeval_due=False, facilitator_reeval_chain=None)
        except Exception:
            pass
        return None


def _consume_phase_start_gate(state) -> "str | None":
    """Phase-start gate (#AC-11): emit directive if phase_start_gate_due is set.

    Reads ``state.phase_start_gate_due`` set by task_completed.py on
    phase-transition events.  When set, calls ``phase_start_gate.py::check()``
    via subprocess and surfaces the resulting systemMessage (if any).

    Clears the flag immediately (single-shot emission).
    Fail-open: any exception or missing script returns None without raising.
    """
    if state is None:
        return None
    try:
        if not getattr(state, "phase_start_gate_due", False):
            return None

        # Clear flag before subprocess call so a crash doesn't loop
        state.update(phase_start_gate_due=False)

        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if not plugin_root:
            return None
        gate_script = Path(plugin_root) / "scripts" / "crew" / "phase_start_gate.py"
        if not gate_script.exists():
            return None

        # Assemble chain snapshot (fail-open if unavailable)
        chain_id = getattr(state, "facilitator_reeval_chain", None) or "unknown"
        chain_data = _assemble_current_chain(chain_id) if chain_id != "unknown" else {}
        chain_data = chain_data or {}

        # Build state dict for the gate
        gate_state = {
            "last_reeval_ts": getattr(state, "last_reeval_ts", None),
            "last_reeval_task_count": getattr(state, "last_reeval_task_count", 0) or 0,
        }

        # Call gate check inline by importing (same process, stdlib-only script)
        import subprocess
        python_shim = Path(plugin_root) / "scripts" / "_python.sh"
        gate_input = json.dumps({"state": gate_state, "chain_snapshot": chain_data})

        result = subprocess.run(
            ["sh", str(python_shim), "-c",
             (
                 "import sys, json; "
                 f"sys.path.insert(0, '{Path(plugin_root) / 'scripts' / 'crew'}'); "
                 "from phase_start_gate import check; "
                 "data = json.loads(sys.stdin.read()); "
                 "out = check(data['state'], data['chain_snapshot']); "
                 "print(json.dumps(out))"
             )],
            input=gate_input,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        gate_result = json.loads(result.stdout.strip())
        return gate_result.get("systemMessage")
    except Exception:
        return None  # fail-open always


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

    v6: the v5 compaction-detection path (PressureTracker.was_just_compacted +
    HistoryCondenser wip_snapshot) was deleted with smaht/v2 in #428. For v6
    we rely on native in-progress tasks as the sole WIP source — if the task
    dir is empty we emit nothing. Acceptable per gate4-deletion-manifest.md §5.2
    ("compaction is rare and facilitator re-evaluate-on-TaskCompleted covers
    the crew case").

    Returns a formatted markdown block listing in-progress tasks, or an
    empty string when there's no signal worth showing.
    """
    # v6: no compaction-detection; always try to surface native in-progress
    # tasks. Fail-open to empty string on any error.
    wip_data = None

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
    # v6: only surface in-progress tasks. The v5 ticket-rail fields
    # (current_task, decisions, file_scope, active_constraints, open_questions)
    # are gone. If nothing is in-progress, emit nothing.
    if not in_progress_tasks:
        _log("smaht", "debug", "wip_recovery.empty")
        return ""

    parts = ["## [Recovery] Work in progress\n"]
    parts.append("### In-Progress Tasks")
    for task in in_progress_tasks:
        parts.append(f"- {task[:80]}")
    parts.append("\n**IMPORTANT**: Review before proceeding. Do NOT repeat completed work.")

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

    # v6 Gate 3 (#428) — facilitator re-evaluation directive.
    # Load session state here (cheap — single JSON read) so we can check the
    # flag set by task_completed.py. Idempotent: the consumer clears the flag
    # so a subsequent turn doesn't re-fire.
    facilitator_reeval_directive = None
    phase_start_gate_directive = None
    try:
        from _session import SessionState
        _preload_state = SessionState.load()
        facilitator_reeval_directive = _consume_facilitator_reeval(_preload_state)
        # AC-11: phase-start gate — consume phase_start_gate_due flag set by
        # task_completed.py on phase-transition events.  On change-detected,
        # emits a systemMessage asking Claude to invoke propose-process in
        # re-evaluate mode with the current_chain data before engaging specialists.
        phase_start_gate_directive = _consume_phase_start_gate(_preload_state)
    except Exception:
        pass

    # ---------------------------------------------------------------------------
    # HOT fast-exit: known continuation tokens bypass all imports and any
    # downstream classification. Keeps HOT path p95 well under 100ms SLO.
    # These words carry no new intent — there is nothing for context assembly
    # to add beyond what is already in the conversation window.
    #
    # v6 note: the v5 CONTINUATION_PATTERNS in scripts/smaht/v2/router.py was
    # deleted in #428. This in-hook fast-exit is now the sole continuation
    # detector — it's just a set membership check, no regex needed.
    # ---------------------------------------------------------------------------
    _HOT_CONTINUATIONS = frozenset({
        "yes", "ok", "okay", "sure", "yep", "yup",
        "continue", "proceed", "go", "go ahead", "do it",
        "lgtm", "looks good", "approved", "approve",
        "no", "nope", "cancel", "stop", "skip",
        "next", "done",
    })
    if prompt.strip().lower() in _HOT_CONTINUATIONS:
        # v6: no history condenser to update. The HOT path is a pure no-op
        # bypass — session counter increment still happens via the normal
        # path for non-continuation turns.

        # Even on HOT path, inject onboarding directive + facilitator re-eval
        # directive so the gate + re-eval can never be bypassed via continuation
        # tokens. Re-eval must fire before the user's acknowledgement drives
        # the next step on a facilitator-owned chain.
        hot_parts = []
        if facilitator_reeval_directive:
            hot_parts.append(facilitator_reeval_directive)
        if phase_start_gate_directive:
            hot_parts.append(phase_start_gate_directive)
        if onboarding_directive:
            hot_parts.append(onboarding_directive)
        if hot_parts:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": "\n\n".join(hot_parts),
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
    # v6: the v5 Router + Orchestrator pre-fetch were deleted in #428. Classification
    # is now an inline heuristic; the synthesize skill is expected to pull its own
    # context via brain+search if it needs more than the raw prompt.
    # Synthesis is skipped if onboarding is pending (no context yet to synthesize from).
    if not onboarding_directive:
        complexity, is_risky = _score_complexity_and_risk(prompt, state)
        _word_count = len(prompt.split())
        _prompt_lower = prompt.lower()
        _has_technical = (
            "?" in prompt
            or any(s in _prompt_lower for s in _DEEP_WORK_SIGNALS)
            or any(s in _prompt_lower for s in _RISK_SIGNALS)
        )
        # Near-HOT guard: very short phrases with no technical signals are continuations.
        _is_near_hot = (_word_count <= 6) and not _has_technical
        _should_synthesize = (
            not _is_near_hot
            and (
                is_risky
                or (complexity >= _SYNTHESIS_THRESHOLD and _word_count > 8)
            )
        )

        if _should_synthesize:
            # v6: synthesize without a pre-fetched briefing. The synthesize skill
            # pulls context on demand via brain + search rather than having a
            # push orchestrator run first.
            synthesis_directive = _build_synthesis_directive(
                prompt, complexity, is_risky, state, context_briefing=""
            )
            _log("smaht", "debug", "synthesis.triggered",
                 detail={"complexity": complexity, "risk": is_risky, "turn": turn_count})
            # v6 Gate 3 (#428): prepend facilitator re-eval directive if pending,
            # so synthesis-path prompts still honour the re-eval signal.
            _synth_reeval_prefix = (
                f"{facilitator_reeval_directive}\n\n" if facilitator_reeval_directive else ""
            )
            merged = (
                f"<system-reminder>\n"
                f"<!-- wicked-garden | path=synthesis | turn={turn_count} -->\n"
                f"{_synth_reeval_prefix}{synthesis_directive}\n"
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
        # Instead of pushing a full briefing every turn, inject a tiny pull
        # directive (~60-150 chars) that tells the model to fetch context on
        # demand via wicked-brain:query/search.
        #
        # v6: the smaht/v2 orchestrator (and its HOT/FAST/SLOW tiers) was
        # deleted in #428. The synthesize skill remains as the one path that
        # still pulls a briefing — see the complexity+risk gate above.

        # Build the pull directive
        pull_directive = _build_pull_directive(turn_count, state)

        # WIP recovery: surface native in-progress tasks (v5 ticket rail gone)
        wip_block = _build_wip_recovery_block(session_id, project)

        # Build output: single <system-reminder> block with all context parts
        all_parts = []

        # v6 Gate 3 (#428): facilitator re-evaluation directive has highest
        # priority — a completed facilitator-owned task must re-plan before
        # the model addresses the user's prompt.
        if facilitator_reeval_directive:
            all_parts.append(facilitator_reeval_directive)

        # AC-11: phase-start gate directive — fires when a phase-transition
        # event was detected and material changes exist since last re-eval.
        if phase_start_gate_directive:
            all_parts.append(phase_start_gate_directive)

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
