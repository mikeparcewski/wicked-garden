#!/usr/bin/env python3
"""
Stop hook — wicked-garden unified session teardown (async, 30s timeout).

Consolidates: crew stop, kanban stop, mem stop, smaht session_end.

Flow:
1. Session outcome check (mismatch report from auto_issue_reporter state)
2. Memory flush reminder (directive for Claude to store learnings)
3. Run memory decay maintenance
4. Async heartbeat to control plane agents service
5. Session end event to control plane SSE endpoint
6. Persist final SessionState

Always fails open — any unhandled exception returns {"systemMessage": ...}.
Runs async so it does NOT block the user on exit.
"""

import json
import os
import sys
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session_id() -> str:
    raw = os.environ.get("CLAUDE_SESSION_ID", "default")
    return raw.replace("/", "_").replace("\\", "_").replace("..", "_")


def _session_dir(subdir: str) -> Path:
    tmpdir = os.environ.get("TMPDIR", "/tmp").rstrip("/")
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
                        signals.append(record.get("subject", "?")[:60])
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
# Step 1b: CP error summary
# ---------------------------------------------------------------------------

def _analyze_cp_errors() -> list:
    """Return summary messages if CP errors occurred this session."""
    try:
        from _session import SessionState
        state = SessionState.load()
        errors = state.cp_errors or []
        if not errors:
            return []

        # Count unique domain/source combos
        sources = set()
        for err in errors:
            parts = err.get("url", "").split("/data/")[-1].split("/") if "/data/" in err.get("url", "") else []
            if len(parts) >= 2:
                sources.add(f"{parts[0]}/{parts[1]}")

        if sources:
            return [
                f"[CP Errors] {len(errors)} CP error(s) across {len(sources)} source(s) this session. "
                f"Sources: {', '.join(sorted(sources))}. "
                "Run the session analyzer to file issues: "
                "python3 .claude/skills/cp-session-analyzer/scripts/analyze_session.py <transcript_path> --auto-file"
            ]
        return []
    except Exception:
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


# ---------------------------------------------------------------------------
# Step 4: Heartbeat to control plane
# ---------------------------------------------------------------------------

def _send_heartbeat(session_id: str, turn_count: int) -> None:
    """POST heartbeat to control plane agents service (non-blocking, best-effort)."""
    try:
        from _control_plane import ControlPlaneClient
        from _session import SessionState

        state = SessionState.load()
        if not state.cp_available:
            return

        client = ControlPlaneClient(hook_mode=True)
        client.request(
            "wicked-agents",
            "agents",
            "heartbeat",
            payload={"session_id": session_id, "turn_count": turn_count},
        )
    except Exception as e:
        print(f"[wicked-garden] heartbeat error: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Step 5: Session end event
# ---------------------------------------------------------------------------

def _send_session_end_event(session_id: str) -> None:
    """POST session end event to control plane events endpoint (best-effort)."""
    try:
        from _control_plane import ControlPlaneClient
        from _session import SessionState

        state = SessionState.load()
        if not state.cp_available:
            return

        client = ControlPlaneClient(hook_mode=True)
        client.request(
            "wicked-garden",
            "events",
            "create",
            payload={
                "event": "session:ended",
                "session_id": session_id,
                "turn_count": _get_turn_count(),
            },
        )
    except Exception as e:
        print(f"[wicked-garden] session-end event error: {e}", file=sys.stderr)


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
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    try:
        session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "default"))
        turn_count = _get_turn_count()

        all_messages = []

        # 1. Session outcome check
        outcome_messages = _check_session_outcome()
        all_messages.extend(outcome_messages)

        # 1b. CP error summary
        cp_messages = _analyze_cp_errors()
        all_messages.extend(cp_messages)

        # 3. Memory decay
        decay_messages = _run_memory_decay()
        all_messages.extend(decay_messages)

        # 4. Heartbeat (best-effort)
        _send_heartbeat(session_id, turn_count)

        # 5. Session end event (best-effort)
        _send_session_end_event(session_id)

        # Smaht history condenser persistence
        _persist_smaht_session_meta(session_id)

        # 6. Persist session state
        _persist_session_state()

        # 2. Memory flush reminder — always included as directive to Claude
        decay_prefix = f"{'; '.join(decay_messages)}. " if decay_messages else ""
        reflection = (
            f"[Memory] {decay_prefix}REQUIRED: Session ending. "
            "Run TaskList to review completed tasks from this session. "
            "For each completed task, evaluate: did it produce a decision, gotcha, or reusable pattern? "
            "Store each learning with /wicked-garden:mem:store "
            "(type: decision, procedural, or episodic). "
            "If no tasks completed or no learnings found, state 'No memories to store.' "
            "Do NOT skip silently."
        )

        # Prepend outcome messages if any
        if outcome_messages:
            final_message = "\n".join(outcome_messages) + "\n\n" + reflection
        else:
            final_message = reflection

        print(json.dumps({"systemMessage": final_message}))

    except Exception as e:
        print(f"[wicked-garden] stop hook error: {e}", file=sys.stderr)
        print(json.dumps({"systemMessage": ""}))


if __name__ == "__main__":
    main()
