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
# Step 1: Session outcome check
# ---------------------------------------------------------------------------

def _check_session_outcome() -> list:
    """Return a list of outcome messages from the issue reporter state."""
    messages = []
    try:
        sdir = _session_dir("wicked-issue-reporter")
        pending_file = sdir / "pending_issues.jsonl"
        mismatches_file = sdir / "mismatches.jsonl"

        # Count pending issues
        if pending_file.exists():
            lines = [l.strip() for l in pending_file.read_text().splitlines() if l.strip()]
            if lines:
                messages.append(
                    f"[Issue Reporter] {len(lines)} issue(s) queued this session. "
                    "Review with /wicked-garden:report-issue --list-unfiled."
                )

        # Count task mismatches
        if mismatches_file.exists():
            lines = [l.strip() for l in mismatches_file.read_text().splitlines() if l.strip()]
            if lines:
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
                    f"[Issue Reporter] {len(lines)} task completion mismatch(es) detected: "
                    + "; ".join(signals)
                )
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
# Emission shape is unchanged: wicked.fact.extracted events on wicked-bus,
# picked up by wicked-brain's auto-memorize subscriber, which re-applies its
# own type/length/dedup policy.

# Fact types eligible for emission — mirrors brain's auto-memorize policy.
# Brain will re-check these; this pre-filter keeps bus traffic sensible.
_EMITTABLE_FACT_TYPES = frozenset({"decision", "discovery"})
_MIN_FACT_CONTENT_LENGTH = 15


def _run_memory_promotion(session_id: str) -> list:
    """Emit high-value session facts as wicked.fact.extracted events on wicked-bus.

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
                "wicked.fact.extracted",
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
# and emitted as a `wicked.guard.findings` event on wicked-bus.
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

# ---------------------------------------------------------------------------
# Pull-model calibration update (Issue #416)
# ---------------------------------------------------------------------------

def _update_pull_calibration() -> None:
    """Update pull-model calibration stats at the end of each model response.

    Tracks whether the model pulled context this turn (via pull_count delta)
    and increments unpulled_ok when it didn't pull but wasn't corrected.
    Correction detection happens in prompt_submit.py at the START of the
    next turn by checking if the new prompt contains correction signals.
    Here we just track the "didn't pull" baseline.
    """
    try:
        from _session import SessionState
        state = SessionState.load()

        # Snapshot pull_count at turn end so next turn can detect delta
        # (stored as a transient field — no schema change needed, we use turn_tool_count)
        # If pull_count hasn't changed since turn start, model didn't pull this turn
        # We'll increment unpulled_ok optimistically; prompt_submit corrects on next turn
        # if the user's follow-up contains correction signals.
        state.update(unpulled_ok=(state.unpulled_ok or 0) + 1)
    except Exception:
        pass  # fail open


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

        # 0. Pull-model calibration update (Issue #416)
        _update_pull_calibration()

        # 1. Session outcome check
        outcome_messages = _check_session_outcome()

        # 2b. Automatic memory promotion (fail open — never blocks session end)
        promotion_messages = _run_memory_promotion(session_id)

        # 2c. Consolidate working-tier memories to episodic (fail open)
        consolidation_messages = _run_working_consolidation()

        # 3. Memory decay
        decay_messages = _run_memory_decay()

        # 4. Persist session state
        _persist_session_state()

        # 5. Event store retention purge
        _purge_old_events()

        # 5b. Cross-session quality telemetry + drift detection (Issue #443)
        telemetry_messages = _run_quality_telemetry(session_id)

        # 6. Autonomous guard pipeline (Issue #448)
        # Runs AFTER telemetry — additive, order-independent.
        guard_messages = _run_guard_pipeline()

        # Read session state for task completion count (fail open)
        tasks_completed_this_session = 0
        try:
            sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))
            from _session import SessionState
            session_state = SessionState.load()
            tasks_completed_this_session = session_state.memory_compliance_tasks_completed or 0
        except Exception:
            pass

        # 2. Memory flush reminder — always included as directive to Claude.
        # Auto-promotion already ran (step 2b); adjust directive accordingly.
        decay_prefix = f"{'; '.join(decay_messages)}. " if decay_messages else ""
        promoted_count = sum(
            int(m.split("Auto-extracted ")[1].split(" ")[0])
            for m in promotion_messages
            if "Auto-extracted" in m
        ) if promotion_messages else 0

        if promoted_count > 0:
            reflection = (
                f"[Memory] {decay_prefix}"
                f"Auto-extracted {promoted_count} memories this session. "
                "Review or supplement with wicked-brain:memory (recall mode) if needed. "
                "If additional decisions or discoveries were made that were not captured, "
                "store them with wicked-brain:memory (type: decision, procedural, or episodic)."
            )
        else:
            task_count_note = (
                f"You completed {tasks_completed_this_session} tasks this session — review each with TaskList. "
                if tasks_completed_this_session > 0
                else "Run TaskList to review completed tasks from this session. "
            )
            reflection = (
                f"[Memory] {decay_prefix}REQUIRED: Session ending. "
                f"{task_count_note}"
                "For each completed task, evaluate: did it produce a decision, gotcha, or reusable pattern? "
                "Store each learning with wicked-brain:memory "
                "(type: decision, procedural, or episodic). "
                "If no tasks completed or no learnings found, state 'No memories to store.' "
                "Do NOT skip silently."
            )

        # Combine all pre-reflection messages (outcome + promotion + consolidation + guard notices)
        # Note: decay_messages already included via decay_prefix in reflection
        prepend_messages = outcome_messages + promotion_messages + consolidation_messages + telemetry_messages + guard_messages
        if prepend_messages:
            final_message = "\n".join(prepend_messages) + "\n\n" + reflection
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
