#!/usr/bin/env python3
"""
Stop hook — wicked-garden unified session teardown (async, 30s timeout).

Consolidates: crew stop, mem stop, session-end fact emission.

Flow:
1. Session outcome check (mismatch report from auto_issue_reporter state)
2. Automatic memory promotion from native tasks (session_fact_extractor)
3. Working-tier consolidation via brain compile + lint
4. Memory decay maintenance
5. Persist final SessionState
6. Event store retention purge
7. Emit memory flush reminder directive

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
# Helpers
# ---------------------------------------------------------------------------

def _get_session_id() -> str:
    raw = os.environ.get("CLAUDE_SESSION_ID", "default")
    return raw.replace("/", "_").replace("\\", "_").replace("..", "_")


def _session_dir(subdir: str) -> Path:
    tmpdir = (os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()).rstrip("/")
    return Path(tmpdir) / subdir / _get_session_id()


# ---------------------------------------------------------------------------
# Output governance — per-turn policy compliance advisory (garden#984)
# ---------------------------------------------------------------------------
#
# When WG_OUTGOV=warn|strict, returns a systemMessage asking Claude to recall
# Policy-type conformance rules from the estate graph and evaluate this turn's
# output.  WG_OUTGOV=off (default) → skip silently.  Always fails open.

def _check_outgov_compliance(_input_data: dict) -> list:
    """Per-turn policy compliance advisory when WG_OUTGOV is enabled."""
    try:
        mode = os.environ.get("WG_OUTGOV", "off").strip().lower()
        if mode not in ("warn", "strict"):
            return []
        deny_hint = (
            " For CRITICAL severity violations: stop and explain the policy conflict "
            "before writing or executing the action that would worsen it."
            if mode == "strict"
            else ""
        )
        return [
            "[Output Governance] Evaluate this turn's output against applicable policy rules. "
            "If the estate MCP is connected: use estate tools to list nodes with kind=Rule "
            "and rule_type=Policy, identify applicable rules, and report any violations with "
            "rule ID, severity, and a brief explanation. "
            "If estate is unavailable: skip silently." + deny_hint
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




# ---------------------------------------------------------------------------
# Step 2b: Session-end fact emission → wicked-brain auto-memorize
# ---------------------------------------------------------------------------
#
# v6: Session facts are extracted from native Claude tasks
# (${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json) by
# scripts/mem/session_fact_extractor.py. This replaces the v5 smaht
# FactExtractor/HistoryCondenser pipeline deleted in Gate 4 Phase 2 (#428).
# Emission shape is unchanged: wicked.garden.fact.extracted events on wicked-bus,
# picked up by wicked-brain's auto-memorize subscriber, which re-applies its
# own type/length/dedup policy.

# Fact types eligible for emission — mirrors brain's auto-memorize policy.
# Brain will re-check these; this pre-filter keeps bus traffic sensible.
_EMITTABLE_FACT_TYPES = frozenset({"decision", "discovery"})
_MIN_FACT_CONTENT_LENGTH = 15


def _run_memory_promotion(session_id: str) -> list:
    """Emit high-value session facts as wicked.garden.fact.extracted events on wicked-bus.

    Reads native task records (TaskCreate/TaskUpdate output) via
    scripts/mem/session_fact_extractor.py, filters to decisions + discoveries
    over the length threshold, and emits one event per fact. Brain's
    auto-memorize subscriber handles persistence asynchronously.

    Returns a list of message strings (empty when nothing was emitted or the
    bus is unavailable). Always fails open — exceptions are caught and logged
    to stderr.
    """
    try:
        # scripts/ is on sys.path via the hook bootstrap; _brain_ingest is a
        # package under scripts/ so the qualified import resolves without any
        # additional sys.path manipulation.
        from _brain_ingest.session_fact_extractor import extract_session_facts
        from _bus import emit_event

        facts = extract_session_facts(session_id, limit=20)
        if not facts:
            if os.environ.get("WICKED_DEBUG"):
                print(
                    f"[wicked-garden] fact emit: no promotable facts in session {session_id}",
                    file=sys.stderr,
                )
            return []

        emitted = 0
        for fact in facts:
            if fact.type not in _EMITTABLE_FACT_TYPES:
                continue
            if len(fact.content) < _MIN_FACT_CONTENT_LENGTH:
                continue
            emit_event(
                "wicked.garden.fact.extracted",
                {
                    "type": fact.type,
                    "content": fact.content,
                    "entities": list(fact.entities)[:5] if fact.entities else [],
                    "source": fact.source or "task",
                    "session_id": session_id,
                },
            )
            emitted += 1

        if emitted == 0:
            return []
        return [f"[Memory] Emitted {emitted} fact event(s); wicked-brain will auto-memorize eligible ones."]

    except Exception as e:
        print(f"[wicked-garden] fact emit error: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Step 2 & 3: Memory flush reminder + decay
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


def _run_memory_decay() -> list:
    """Run decay maintenance via brain lint API. Return list of result message strings."""
    messages = []
    try:
        # Session-end maintenance writes — auto-start the server so a stopped
        # server doesn't silently skip decay (fail-open, lock-safe, one
        # spawn attempt per process).
        try:
            from _brain_port import ensure_server
            ensure_server(wait_secs=2.0)
        except Exception:
            pass
        result = _brain_api("lint", {}, timeout=5)
        if result and (result.get("archived", 0) > 0 or result.get("deleted", 0) > 0):
            messages.append(
                f"[Memory] Decay: {result.get('archived', 0)} archived, {result.get('deleted', 0)} cleaned"
            )
    except Exception as e:
        print(f"[wicked-garden] decay error: {e}", file=sys.stderr)
    return messages


def _run_working_consolidation() -> list:
    """Consolidate working-tier memories via brain compile + lint.

    Returns a list of message strings. Fails open — never blocks session end.
    """
    messages = []
    try:
        try:
            from _brain_port import ensure_server
            ensure_server(wait_secs=2.0)
        except Exception:
            pass
        compile_result = _brain_api("compile", {}, timeout=10)
        lint_result = _brain_api("lint", {}, timeout=5)
        compiled = compile_result.get("compiled", 0) if compile_result else 0
        cleaned = lint_result.get("deleted", 0) if lint_result else 0
        if compiled > 0 or cleaned > 0:
            messages.append(
                f"[Memory] Consolidation: {compiled} compiled, {cleaned} cleaned"
            )
    except Exception as e:
        print(f"[wicked-garden] consolidation error: {e}", file=sys.stderr)
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
# and emitted as a `wicked.garden.guard.findings` event on wicked-bus.
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
            emit_findings_event,
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
        emit_findings_event(report)

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

        # 2b. Automatic memory promotion (fail open — never blocks session end)
        # KEPT in stop.py per-turn — lightweight (single bus emit per fact),
        # self-reports cleanly, and the next session's bootstrap relies on
        # memories being current. Heavy cadence work (decay/consolidation/
        # telemetry/guard) was extracted in v9.2.15 — see _heavy_cadence.py.
        promotion_messages = _run_memory_promotion(session_id)

        # 4. Persist session state
        _persist_session_state()

        # 5. Event store retention purge
        _purge_old_events()

        # 6. Heavy cadence — Stop is a reliable co-primary carrier of the
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

        # NOTE (v9.2.15): the [Memory] reflection block was deleted.
        #   - It had a parser bug: looked for substring "Auto-extracted " but
        #     _run_memory_promotion emits "Emitted N fact event(s)" — so
        #     `promoted_count` was ALWAYS 0 and only the fallback prompt-mode
        #     branch ever fired. The "smart" branching had never executed in
        #     production.
        #   - _run_memory_promotion already self-reports when facts are
        #     auto-extracted ("[Memory] Emitted N fact event(s); wicked-brain
        #     will auto-memorize..."), so the reflection's "use wicked-brain:
        #     memory" guidance was duplicate noise.
        #   - The brainstorm in v9.2.15 chose Option A (delete) over Option B
        #     (fix the parser + re-gate) because the smart branch is dead
        #     code defending behavior no user has seen. CLAUDE.md's "Memory
        #     Management" section already tells Claude to use wicked-brain:
        #     memory for decisions; an end-of-turn reminder adds no signal.
        # `tasks_completed_this_session` is no longer read; the variable
        # remains in scope above for any future use without breaking the
        # `session_state` load.
        reflection = ""
        # for this session (post-first-Stop) — only join with separator if both
        # halves have content.
        # Answer-tier claim sentinel — claim-gated, computed here (after
        # _persist_session_state) so its debounce write is the last state write
        # of the turn (avoids clobbering session_ended).
        sentinel_messages = _check_claim_sentinel(input_data)
        outgov_messages = _check_outgov_compliance(input_data)
        prepend_messages = sentinel_messages + outgov_messages + outcome_messages + promotion_messages + consolidation_messages + telemetry_messages + guard_messages
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
