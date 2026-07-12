#!/usr/bin/env python3
"""SessionEnd hook — heavy cadence work that previously ran every Stop.

Provenance: v9.2.15 redesign. Stop fires per-turn (~30/session). The four
heavy functions (memory decay/consolidation, telemetry, guard pipeline) are
session-scope work and do not need to run after every model response.

This hook is the PRIMARY cadence path. The stop.py time-gated fallback
exists only for the partial-session failure mode (SessionEnd never fires
because the CLI was killed, network dropped, user walked away).

Always fails open — never blocks session end. The ledger artifacts written
here (timeline.jsonl, findings.json, brain wiki articles) are picked up by
the next bootstrap, so a missed run is recoverable.
"""

import json
import os
import sys
import time
from pathlib import Path

_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


def _log(domain, level, event, ok=True, ms=None, detail=None):
    """Mirror stop.py's _log shape — append to operational log if available."""
    try:
        from _logging import log_event  # type: ignore
        log_event(domain, level, event, ok=ok, ms=ms, detail=detail)
    except Exception:
        pass  # logging is observability, not load-bearing


def main() -> None:
    _t0 = time.monotonic()
    _log("session", "debug", "session_end.start")

    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    session_id = input_data.get(
        "session_id", os.environ.get("CLAUDE_SESSION_ID", "default")
    )

    try:
        from _heavy_cadence import (  # type: ignore
            run_heavy_cadence, already_ran_this_session, TRIGGER_SESSION_END,
        )
        # De-dupe guard (v9.2.16, #842): the Stop hook now also carries the
        # heavy-cadence teardown (SessionEnd is unreliable — fires on <40% of
        # exits). If a Stop already ran the heavy work for this session, skip —
        # the work is done and the sidecar already records it. Otherwise run it
        # here; SessionEnd is the best end-of-session snapshot when it fires.
        if already_ran_this_session(session_id):
            _log("session", "debug", "session_end.dedupe_skip")
            messages = []
        else:
            messages = run_heavy_cadence(
                TRIGGER_SESSION_END, session_id=session_id, plugin_root=_PLUGIN_ROOT
            )
    except Exception as e:
        # Fail open — SessionEnd must never block the user closing their CLI.
        print(f"[wicked-garden] session_end error: {e}", file=sys.stderr)
        messages = []

    # Claim sentinel — info-tier session-close lines (never blocking): a
    # significant session that captured zero brain memories, or repo playbooks
    # (wicked-understanding) that have drifted well behind HEAD. Observed state
    # only; each check is fail-open and silent when its layer is absent.
    try:
        sentinel_dir = str(_PLUGIN_ROOT / "scripts" / "sentinel")
        if sentinel_dir not in sys.path:
            sys.path.insert(0, sentinel_dir)
        from invariants import session_end_lines  # type: ignore
        from _session import SessionState  # type: ignore
        state = SessionState.load()
        started = float(getattr(state, "created_at_epoch", 0) or 0)
        if not started:
            started = time.time() - 3600  # unknown start — assume the last hour
        activity = int(getattr(state, "bash_count", 0) or 0) + int(
            getattr(state, "memory_compliance_tasks_completed", 0) or 0)
        messages.extend(session_end_lines(None, started, activity))
    except Exception:  # noqa: BLE001 — the sentinel never blocks session end
        pass

    elapsed_ms = int((time.monotonic() - _t0) * 1000)
    _log("session", "info", "session_end.done", ms=elapsed_ms,
         detail={"messages": len(messages)})

    # SessionEnd hook output convention: emit any messages as a systemMessage
    # so the next session's bootstrap can surface them in the briefing. If
    # nothing material happened (no decay, no drift, no guard findings), stay
    # silent.
    if messages:
        print(json.dumps({"continue": True, "systemMessage": "\n".join(messages)}))
    else:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
