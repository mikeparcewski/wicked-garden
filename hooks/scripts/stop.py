#!/usr/bin/env python3
"""
Stop hook — wicked-garden unified session teardown (async, 30s timeout).

Consolidates: crew stop, mem stop.

The hook writes no memories: what a session learned is captured on purpose
(the wicked-garden-mem skill's capture/store actions), never pattern-matched
out of the transcript.

Flow:
1. Session outcome check (mismatch report from auto_issue_reporter state)
2. Persist final SessionState
3. Event store retention purge
4. Heavy cadence teardown (telemetry + guard pipeline, once per session)

Always fails open — any unhandled exception returns {"systemMessage": ...}.
Runs async so it does NOT block the user on exit.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

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
# Helpers
# ---------------------------------------------------------------------------

def _get_session_id() -> str:
    raw = os.environ.get("CLAUDE_SESSION_ID", "default")
    return raw.replace("/", "_").replace("\\", "_").replace("..", "_")


def _session_dir(subdir: str) -> Path:
    tmpdir = (os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()).rstrip("/")
    return Path(tmpdir) / subdir / _get_session_id()


# ---------------------------------------------------------------------------
# Output governance — once-per-session rules audit (garden#984, AW-16, #1333)
# ---------------------------------------------------------------------------
#
# The per-turn line ("If the estate MCP is connected: call rules.recall…") is
# gone: no estate MCP is registered on a seat by design, so it was an
# instruction that could never run, repeated every turn (garden#1333). In its
# place, the FIRST Stop of a session runs `rules.recall` itself through the
# read-only shim (the one way to estate on every seat) and, only when the store
# holds policy rules, names them once with the command that lists them all.
# Zero rules, an unreachable estate, or any error: silent.
#
# WG_OUTGOV=warn (default) | strict | off (per-repo opt-out, P-5). Any
# unrecognized value is treated as off. Two-tier doctrine (TARGET-ARCHITECTURE
# contract 3): fail-open ADVISORY at every mode; `strict` only strengthens the
# wording. Fail-closed enforcement lives in the crew/core gates, never here.

_OUTGOV_RULES_ARGS = {"rule_type": "policy", "limit": 5}
_OUTGOV_LIST_CMD = (
    "wicked-garden run scripts/_estate_client.py --readonly call "
    '\'{"tool":"rules.recall","arguments":{"rule_type":"policy"}}\''
)


def _recall_policy_rules(timeout: float = 15.0) -> Optional[dict]:
    """`rules.recall {"rule_type":"policy"}` through the read-only shim.

    Returns the tool's result (`{"rules": [...], "total": N, ...}`) or None on
    any failure (shim missing, estate unreachable, timeout, bad JSON).
    """
    try:
        import subprocess
        shim = _PLUGIN_ROOT / "scripts" / "_estate_client.py"
        if not shim.is_file():
            return None
        req = json.dumps({"tool": "rules.recall", "arguments": _OUTGOV_RULES_ARGS,
                          "all_pages": False})
        proc = subprocess.run(
            [sys.executable, str(shim), "--readonly", "call", req],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        out = json.loads((proc.stdout or "").strip().splitlines()[-1])
        result = out.get("result") if isinstance(out, dict) else None
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def _check_outgov_compliance(_input_data: dict, recall=None, state=None) -> list:
    """Once-per-session policy-rules audit unless WG_OUTGOV is off.

    `recall` / `state` are test seams (default: the shim, SessionState).
    """
    try:
        mode = os.environ.get("WG_OUTGOV", "warn").strip().lower()
        if mode not in ("warn", "strict"):
            return []
        if os.environ.get("WICKED_CONTEXT_BACKEND", "").strip().lower() == "off":
            return []  # operator turned estate-backed context off: designed silence
        if state is None:
            from _session import SessionState
            state = SessionState.load()
        if getattr(state, "outgov_audited", False):
            return []
        # Latch BEFORE the call: a slow or failing estate costs one attempt per
        # session, never one per turn.
        state.update(outgov_audited=True)
        result = (recall or _recall_policy_rules)()
        if not isinstance(result, dict):
            return []
        rules = [r for r in (result.get("rules") or []) if isinstance(r, dict)]
        try:
            total = int(result.get("total") or len(rules))
        except (TypeError, ValueError):
            total = len(rules)
        if total <= 0 or not rules:
            return []
        shown = []
        for r in rules[:3]:
            statement = " ".join(str(r.get("statement") or "").split())
            if len(statement) > 100:
                statement = statement[:97] + "..."
            shown.append(f"{r.get('id') or '?'} ({r.get('severity') or '?'}): {statement}")
        deny_hint = (
            " For CRITICAL severity violations: stop and explain the policy conflict "
            "before writing or executing the action that would worsen it."
            if mode == "strict"
            else ""
        )
        return [
            f"[Output Governance] {total} policy rule(s) apply in this store; check "
            "this session's changes against them (advisory). Top: "
            + "; ".join(shown)
            + f". Full list: {_OUTGOV_LIST_CMD}" + deny_hint
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Claim sentinel (answer tier) — claim-gated at the Stop boundary.
# Replaces the old PostToolUse ref-watch that fired on every Bash call. Reads
# the turn's final assistant message from the transcript; only a real
# done/passing/shipped claim with no verdict for HEAD produces a nudge.
# ---------------------------------------------------------------------------

def _extract_text(content) -> Optional[str]:
    """Pull concatenated text from a transcript message's `content` — either a
    raw string or a list of {type:'text', text:...} blocks."""
    if isinstance(content, str):
        return content or None
    if isinstance(content, list):
        parts = [b["text"] for b in content
                 if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
        return "\n".join(parts) if parts else None
    return None


def _read_final_assistant_text(transcript_path: str) -> Optional[str]:
    """Return the text of the LAST assistant message in the transcript JSONL,
    or None. Fail-open — any read/parse error yields None (no claim => no fire)."""
    try:
        p = Path(transcript_path)
        if not p.is_file():
            return None
        last = None
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(rec, dict):
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else None
            role = (msg or {}).get("role") or rec.get("role") or rec.get("type")
            if role != "assistant":
                continue
            text = _extract_text((msg or {}).get("content", rec.get("content")))
            if text:
                last = text
        return last
    except Exception:
        return None


def _check_claim_sentinel(input_data: dict) -> list:
    """If the turn's final assistant message asserts done/passing/shipped and
    HEAD has no re-derived verdict, return a one-line nudge (debounced per sha
    per session via SessionState). Fail-open — never breaks Stop."""
    try:
        transcript = input_data.get("transcript_path")
        final_text = _read_final_assistant_text(transcript) if transcript else None
        if not final_text:
            return []
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "sentinel"))
        from invariants import claim_tick, render  # type: ignore
        from _session import SessionState
        state = SessionState.load()
        cwd = input_data.get("cwd")
        violation = claim_tick(
            lambda k: getattr(state, k, None),
            lambda k, v: state.update(**{k: v}),
            final_message=final_text,
            cwd=Path(cwd) if cwd else None,
        )
        return [render(violation)] if violation else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Step 1: Session outcome check
# ---------------------------------------------------------------------------

def _check_session_outcome() -> list:
    """Return a list of outcome messages from the issue reporter state.

    v9.2.12: Pre-fix, this function emitted the [Issue Reporter] banner on
    EVERY Stop hook (i.e. every model response) as long as pending_issues.jsonl
    or mismatches.jsonl had any content. Users saw the same banner re-fire
    every turn until the issues were filed — chronic noise. The change-gated
    latches (last_outcome_pending_count / last_outcome_mismatch_count on
    SessionState) suppress re-emission unless the count has actually grown
    since the previous emission. The first emission per session ALWAYS fires
    (compares against default 0). Subsequent emissions only fire when new
    issues / mismatches accumulate.
    """
    messages = []
    try:
        # Latch state — fail-open if SessionState is unreachable.
        try:
            from _session import SessionState
            session_state = SessionState.load()
        except Exception:
            session_state = None

        sdir = _session_dir("wicked-issue-reporter")
        pending_file = sdir / "pending_issues.jsonl"
        mismatches_file = sdir / "mismatches.jsonl"

        # Count pending issues
        if pending_file.exists():
            lines = [l.strip() for l in pending_file.read_text().splitlines() if l.strip()]
            count = len(lines)
            last_count = (
                int(getattr(session_state, "last_outcome_pending_count", 0) or 0)
                if session_state else 0
            )
            if count and count > last_count:
                messages.append(
                    f"[Issue Reporter] {count} issue(s) queued this session. "
                    "Review via the wicked-garden-core skill's report-issue action (--list-unfiled)."
                )
                if session_state is not None:
                    session_state.update(last_outcome_pending_count=count)

        # Count task mismatches
        if mismatches_file.exists():
            lines = [l.strip() for l in mismatches_file.read_text().splitlines() if l.strip()]
            count = len(lines)
            last_count = (
                int(getattr(session_state, "last_outcome_mismatch_count", 0) or 0)
                if session_state else 0
            )
            if count and count > last_count:
                signals = []
                for line in lines[:3]:
                    try:
                        record = json.loads(line)
                        # Sanitize subject — strip control chars, truncate
                        subj = record.get("subject", "?")[:60]
                        subj = "".join(c for c in subj if c.isprintable())
                        signals.append(subj)
                    except (json.JSONDecodeError, ValueError):
                        pass
                messages.append(
                    f"[Issue Reporter] {count} task completion mismatch(es) detected: "
                    + "; ".join(signals)
                )
                if session_state is not None:
                    session_state.update(last_outcome_mismatch_count=count)
    except Exception:
        pass
    return messages




def _get_turn_count() -> int:
    try:
        from _session import SessionState
        state = SessionState.load()
        return state.turn_count or 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Step 6: Persist final session state
# ---------------------------------------------------------------------------

def _persist_session_state() -> None:
    """Mark session as ended in session state file."""
    try:
        from _session import SessionState
        state = SessionState.load()
        state.update(session_ended=True)
        state.save()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Step 7: Event store retention purge
# ---------------------------------------------------------------------------

def _purge_old_events() -> None:
    """Purge events older than retention period (default 90 days)."""
    try:
        from _event_store import EventStore
        EventStore.ensure_schema()
        deleted = EventStore.purge_before(days=90)
        if deleted > 0:
            _log("stop", "debug", f"event_store.purged {deleted} events")
    except Exception:
        pass  # fire-and-forget


# ---------------------------------------------------------------------------
# Cross-session quality telemetry (Issue #443)
#
# Captures a JSONL record of session-level quality metrics and runs drift
# classification against the 4-session baseline. Always fail-open — must
# never break Stop. Target budget: <100ms typical, <500ms worst.
# ---------------------------------------------------------------------------

def _run_quality_telemetry(session_id: str) -> list:
    """Append a timeline record + detect drift. Returns any messages."""
    messages = []
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "delivery"))
        import telemetry as _telemetry
        import drift as _drift

        t_cap = time.monotonic()
        record = _telemetry.capture_session(session_id)
        cap_ms = int((time.monotonic() - t_cap) * 1000)
        _log("telemetry", "debug", "telemetry.capture", ok=record is not None, ms=cap_ms)
        if record is None:
            return messages

        project = record.get("project") or "_global"
        records = _telemetry.read_timeline(project)
        cls = _drift.classify(records)
        # Emit bus event when drift actionable; fail-open when bus is absent.
        emitted = _drift.emit_drift_event(project, cls)
        if cls.get("drift"):
            messages.append(
                f"[Telemetry] Drift detected for {project}: " + _drift.summarize(cls)
                + (" (emitted to wicked-bus)" if emitted else "")
            )
        elif cls.get("zone") == "warn":
            messages.append(
                f"[Telemetry] Watch signal for {project}: " + _drift.summarize(cls)
            )
    except Exception as e:
        print(f"[wicked-garden] telemetry error: {e}", file=sys.stderr)
    return messages


# ---------------------------------------------------------------------------
# Step 6: Autonomous guard pipeline (Issue #448)
# ---------------------------------------------------------------------------
#
# Runs a tiered profile of surface-level verification at session close:
#   * scalpel  (<1s)  — always runs when the pipeline is reachable
#   * standard (~5s)  — build-phase just closed, or substantial changes
#   * deep     (~30s) — release-branch sessions or explicit WG_GUARD_PROFILE=deep
#
# Always fails open — never hard-blocks session close.  Findings are written
# to a session-scoped file that bootstrap.py can surface in the next briefing,
# and emitted as a `wicked.garden.guard.surfaced` event on wicked-bus.
#
# Ordering: runs AFTER telemetry (#443) so both can share the end-of-session
# snapshot without blocking each other.

def _run_guard_pipeline() -> list:
    """Run the autonomous session-close guard pipeline.

    Returns a list of human-readable message strings to prepend to the session
    message.  Always fails open — any error returns an empty list.
    """
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "platform"))
        from guard_pipeline import (
            run_pipeline,
            write_briefing_file,
            emit_guard_surfaced_event,
            render_summary,
        )
    except Exception as exc:
        print(f"[wicked-garden] guard pipeline unavailable: {exc}", file=sys.stderr)
        return []

    try:
        # Detect whether build phase just closed — best-effort via session state
        build_just_closed = False
        try:
            from _session import SessionState
            state = SessionState.load()
            build_just_closed = bool(
                getattr(state, "last_phase_approved", None) == "build"
            )
        except Exception:
            pass  # fail open — treat unknown phase as "not just closed"

        report = run_pipeline(build_phase_just_closed=build_just_closed)

        # Write briefing file (next session pickup)
        write_briefing_file(report)

        # Emit bus event (fire-and-forget)
        emit_guard_surfaced_event(report)

        # Only return a summary line when we actually have findings or budget blew.
        if report.total_findings > 0 or report.status != "ok":
            return [render_summary(report)]
        return []
    except Exception as exc:
        print(f"[wicked-garden] guard pipeline error: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _t0 = time.monotonic()
    _log("session", "debug", "hook.start")

    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    try:
        session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "default"))
        turn_count = _get_turn_count()

        # 1. Session outcome check
        outcome_messages = _check_session_outcome()

        # 2. Persist session state
        _persist_session_state()

        # 3. Event store retention purge
        _purge_old_events()

        # 4. Heavy cadence — Stop is a reliable co-primary carrier of the
        # teardown (v9.2.16, #842). SessionEnd fires on <40% of exits (~1% for
        # agents), so it can't be the sole primary. Stop fires every turn and IS
        # reliable, so it now runs the SAME heavy work, guarded by
        # should_run_fallback() to fire at most ONCE per session: a de-dupe on
        # session_id (so SessionEnd + Stop never double-run and per-turn Stops
        # don't repeat) plus a turn-count-OR-60-min gate that catches short
        # sessions SessionEnd would have dropped. Sidecar at <local store>/
        # wicked-garden/heavy-cadence/last_run.json makes the guard
        # deterministic and records which trigger actually ran the work.
        consolidation_messages: list = []
        decay_messages: list = []
        telemetry_messages: list = []
        guard_messages: list = []
        try:
            sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))
            from _heavy_cadence import (  # type: ignore
                run_heavy_cadence, should_run_fallback, TRIGGER_STOP_FALLBACK,
            )
            if should_run_fallback(session_id=session_id, turn_count=turn_count):
                fallback_messages = run_heavy_cadence(
                    TRIGGER_STOP_FALLBACK, session_id=session_id, plugin_root=_PLUGIN_ROOT,
                )
                # Single combined list — semantics preserved for downstream
                # joining; per-category split was only used by the deleted
                # [Memory] reflection block.
                consolidation_messages = fallback_messages
        except Exception as e:
            print(f"[wicked-garden] heavy cadence fallback error: {e}", file=sys.stderr)

        # Read session state for task completion count (fail open)
        tasks_completed_this_session = 0
        try:
            sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))
            from _session import SessionState
            session_state = SessionState.load()
            tasks_completed_this_session = session_state.memory_compliance_tasks_completed or 0
        except Exception:
            pass

        # The v9.2.15 [Memory] reflection block is gone (an end-of-turn
        # "store a memory" reminder added no signal), and since w9-memfix the
        # hook writes no memories at all. `tasks_completed_this_session` feeds
        # only the session.end log line below.
        reflection = ""
        # for this session (post-first-Stop) — only join with separator if both
        # halves have content.
        # Answer-tier claim sentinel — claim-gated, computed here (after
        # _persist_session_state) so its debounce write is the last state write
        # of the turn (avoids clobbering session_ended).
        sentinel_messages = _check_claim_sentinel(input_data)
        outgov_messages = _check_outgov_compliance(input_data)
        prepend_messages = sentinel_messages + outgov_messages + outcome_messages + consolidation_messages + telemetry_messages + guard_messages
        if prepend_messages and reflection:
            final_message = "\n".join(prepend_messages) + "\n\n" + reflection
        elif prepend_messages:
            final_message = "\n".join(prepend_messages)
        else:
            final_message = reflection

        # Compute log file path for session summary
        _ops_log_path = str(
            Path(os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()) / f"wicked-ops-{_get_session_id()}.jsonl"
        )
        _log("session", "verbose", "session.end",
             detail={"turns": turn_count,
                     "tasks_completed": tasks_completed_this_session,
                     "log_file": _ops_log_path})
        _log("session", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
        print(json.dumps({"systemMessage": final_message}))

    except Exception as e:
        print(f"[wicked-garden] stop hook error: {e}", file=sys.stderr)
        print(json.dumps({"systemMessage": ""}))


if __name__ == "__main__":
    main()
