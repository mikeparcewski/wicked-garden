#!/usr/bin/env python3
"""
Stop hook — wicked-garden unified session teardown (async, 30s timeout).

Consolidates: crew stop, kanban stop, mem stop, smaht session_end.

Flow:
1. Session outcome check (mismatch report from auto_issue_reporter state)
2. Automatic memory promotion from smaht session
3. Run memory decay maintenance
4. Persist smaht history condenser session metadata
5. Persist final SessionState
6. Emit memory flush reminder directive

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
# Step 2b: Automatic memory promotion via MemoryPromoter
# ---------------------------------------------------------------------------

def _run_memory_promotion(session_id: str) -> list:
    """Promote high-value facts from the smaht session to wicked-mem.

    Returns a list of message strings (empty when nothing was promoted or on
    any error). Always fails open — exceptions are caught and logged to stderr.
    """
    try:
        smaht_dir = _session_dir("wicked-smaht")
        if not smaht_dir.exists():
            # No smaht session this run — nothing to promote
            if os.environ.get("WICKED_DEBUG"):
                print(f"[wicked-garden] memory promotion: no smaht session at {smaht_dir}", file=sys.stderr)
            return []

        # Add smaht/v2 to sys.path so FactExtractor / MemoryPromoter are importable.
        # This mirrors the pattern used in _persist_smaht_session_meta().
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))

        from fact_extractor import FactExtractor
        from memory_promoter import MemoryPromoter

        fact_extractor = FactExtractor(smaht_dir)
        promoter = MemoryPromoter(smaht_dir, fact_extractor)
        result = promoter.promote()

        status = result.get("status", "")
        promoted = result.get("promoted", 0)

        if status == "no_candidates" or promoted == 0:
            return []

        failed = result.get("failed", 0)
        msg = f"[Memory] Auto-extracted {promoted} memory/memories from this session."
        if failed:
            msg += f" ({failed} failed — review with /wicked-garden:mem:recall)"
        return [msg]

    except Exception as e:
        print(f"[wicked-garden] memory promotion error: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Step 2 & 3: Memory flush reminder + decay
# ---------------------------------------------------------------------------

def _run_memory_decay() -> list:
    """Run decay maintenance. Return list of result message strings."""
    messages = []
    try:
        from mem.memory import MemoryStore
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        store = MemoryStore(project)
        result = store.run_decay()
        if result.get("archived", 0) > 0 or result.get("deleted", 0) > 0:
            messages.append(
                f"[Memory] Decay: {result['archived']} archived, {result['deleted']} cleaned"
            )
    except Exception as e:
        print(f"[wicked-garden] decay error: {e}", file=sys.stderr)
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
# Smaht session meta persistence
# ---------------------------------------------------------------------------

def _persist_smaht_session_meta(session_id: str) -> None:
    """Persist smaht history condenser session metadata for cross-session recall."""
    try:
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "smaht" / "v2"))
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        condenser.persist_session_meta()
    except ImportError:
        pass
    except Exception as e:
        print(f"[wicked-garden] smaht session persist error: {e}", file=sys.stderr)


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
        promotion_messages = _run_memory_promotion(session_id)

        # 3. Memory decay
        decay_messages = _run_memory_decay()

        # Smaht history condenser persistence
        _persist_smaht_session_meta(session_id)

        # 4. Persist session state
        _persist_session_state()

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
                "Review or supplement with /wicked-garden:mem:recall if needed. "
                "If additional decisions or discoveries were made that were not captured, "
                "store them with /wicked-garden:mem:store (type: decision, procedural, or episodic)."
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
                "Store each learning with /wicked-garden:mem:store "
                "(type: decision, procedural, or episodic). "
                "If no tasks completed or no learnings found, state 'No memories to store.' "
                "Do NOT skip silently."
            )

        # Combine all pre-reflection messages (outcome + promotion notices)
        # Note: decay_messages already included via decay_prefix in reflection
        prepend_messages = outcome_messages + promotion_messages
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
