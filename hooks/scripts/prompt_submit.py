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

        if not briefing:
            print(json.dumps({"continue": True}))
            return

        # Build output: single <system-reminder> block with all context parts
        header = (
            f"<!-- wicked-garden | path={path} "
            f"| turn={turn_count} -->"
        )
        all_parts = [header]

        if briefing:
            sanitized = briefing.replace("</system-reminder>", "")
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
