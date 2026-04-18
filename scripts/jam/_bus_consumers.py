#!/usr/bin/env python3
"""
jam/_bus_consumers.py — Bus event consumers for the jam domain.

Synthesis-trigger consumer: tracks per-session Round 1 persona contributions
and emits `wicked.session.synthesis_ready` when either:
  - contribution count for a session reaches its `expected_persona_count`, OR
  - 120 seconds have elapsed since the last contribution for that session.

Poll-on-invoke pattern — callable from jam commands (or any startup hook) to
drain pending events. Fails open: bus errors never propagate.

Round 1 only: contributions with round != 1 are ignored so Round 2 sequential
persona dialogue is not interfered with.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-jam.bus-consumers")

# Timeout: if no new contribution arrives within this window, mark synthesis ready.
_SYNTHESIS_TIMEOUT_SECONDS = 120.0

# Default expected persona count when the session object lacks one. 4 matches the
# /wicked-garden:jam:quick default; full brainstorms typically override via the
# session record.
_DEFAULT_EXPECTED_PERSONAS = 4

# Ledger file tracking per-session contribution state. Separate from the global
# _bus_processed.json ledger because we track *per-session aggregate*, not
# per-event idempotency.
_JAM_LEDGER_FILE = os.path.join(
    os.path.expanduser("~"),
    ".something-wicked", "wicked-garden", "local",
    "wicked-jam", "_synthesis_tracker.json",
)


def _load_tracker() -> Dict[str, Dict[str, Any]]:
    """Load the per-session tracker. Returns {session_id: {...}}."""
    try:
        with open(_JAM_LEDGER_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_tracker(tracker: Dict[str, Dict[str, Any]]) -> None:
    """Persist the tracker. Fails open."""
    try:
        os.makedirs(os.path.dirname(_JAM_LEDGER_FILE), exist_ok=True)
        with open(_JAM_LEDGER_FILE, "w") as f:
            json.dump(tracker, f)
    except OSError:
        pass  # fail open


def _lookup_expected_persona_count(session_id: str) -> Optional[int]:
    """Look up expected_persona_count from the jam session record, if present."""
    try:
        from _domain_store import DomainStore
        ds = DomainStore("wicked-jam")
        sessions = ds.list("sessions") or []
        for s in sessions:
            if s.get("id") == session_id or s.get("session_id") == session_id:
                n = s.get("expected_persona_count")
                if isinstance(n, int) and n > 0:
                    return n
        return None
    except Exception:
        return None


def _resolve_expected(session_id: str, tracker_entry: Dict[str, Any]) -> int:
    """Return expected_persona_count, preferring tracker → store → default."""
    n = tracker_entry.get("expected_persona_count")
    if isinstance(n, int) and n > 0:
        return n
    looked = _lookup_expected_persona_count(session_id)
    if looked:
        return looked
    return _DEFAULT_EXPECTED_PERSONAS


def _emit_synthesis_ready(
    session_id: str,
    received: int,
    expected: int,
    reason: str,
    chain_id: Optional[str],
) -> None:
    """Emit wicked.session.synthesis_ready. Fails open."""
    try:
        from _bus import emit_event
        emit_event(
            "wicked.session.synthesis_ready",
            {
                "session_id": session_id,
                "received_count": received,
                "expected_count": expected,
                "reason": reason,  # "all_received" | "timeout"
            },
            chain_id=chain_id,
        )
    except Exception as e:
        logger.debug(f"synthesis_ready emit failed (non-blocking): {e}")


def process_pending_events(now: Optional[float] = None) -> List[str]:
    """Poll wicked.persona.contributed events, track per-session counts, and emit
    wicked.session.synthesis_ready once a session reaches expected count or times out.

    Returns list of action strings (for logging / tests).
    `now` override enables deterministic testing; real calls pass None.
    """
    actions: List[str] = []
    now_ts = time.time() if now is None else now

    try:
        from _bus import poll_pending, ack_events
    except Exception as e:
        logger.debug(f"bus import failed (non-blocking): {e}")
        return actions

    try:
        events = poll_pending(event_type_prefix="wicked.persona.") or []

        tracker = _load_tracker()
        max_event_id = 0
        changed = False

        for event in events:
            event_id = event.get("event_id", 0)
            if isinstance(event_id, int) and event_id > max_event_id:
                max_event_id = event_id

            if event.get("event_type") != "wicked.persona.contributed":
                continue

            payload = event.get("payload") or {}
            session_id = payload.get("session_id")
            if not session_id:
                continue

            # Round 1 only — Round 2 sequential dialogue must not be triggered.
            round_num = payload.get("round", 1)
            try:
                round_num = int(round_num)
            except (TypeError, ValueError):
                round_num = 1
            if round_num != 1:
                continue

            metadata = event.get("metadata") or {}
            chain_id = metadata.get("chain_id")

            entry = tracker.get(session_id) or {
                "received_count": 0,
                "last_contribution_ts": now_ts,
                "processed_event_ids": [],
                "ready_emitted": False,
                "chain_id": None,
                "expected_persona_count": None,
            }

            # Per-event idempotency inside this session's ledger entry
            processed_ids = entry.get("processed_event_ids") or []
            if event_id and event_id in processed_ids:
                continue

            entry["received_count"] = int(entry.get("received_count", 0)) + 1
            entry["last_contribution_ts"] = now_ts
            if event_id:
                processed_ids.append(event_id)
                # Cap ledger size — last 64 ids per session is plenty for Round 1.
                entry["processed_event_ids"] = processed_ids[-64:]
            if chain_id and not entry.get("chain_id"):
                entry["chain_id"] = chain_id
            # Allow first-contribution emitter to seed expected count via payload.
            if not entry.get("expected_persona_count"):
                n = payload.get("expected_persona_count")
                if isinstance(n, int) and n > 0:
                    entry["expected_persona_count"] = n

            tracker[session_id] = entry
            changed = True

            if not entry.get("ready_emitted"):
                expected = _resolve_expected(session_id, entry)
                if entry["received_count"] >= expected:
                    _emit_synthesis_ready(
                        session_id,
                        received=entry["received_count"],
                        expected=expected,
                        reason="all_received",
                        chain_id=entry.get("chain_id"),
                    )
                    entry["ready_emitted"] = True
                    actions.append(
                        f"synthesis_ready emitted for {session_id} "
                        f"({entry['received_count']}/{expected}, all_received)"
                    )

        # Timeout sweep — any session with unemitted readiness whose last
        # contribution is older than the timeout gets flushed.
        for session_id, entry in list(tracker.items()):
            if entry.get("ready_emitted"):
                continue
            last = float(entry.get("last_contribution_ts") or 0.0)
            if last <= 0:
                continue
            if (now_ts - last) >= _SYNTHESIS_TIMEOUT_SECONDS:
                received = int(entry.get("received_count", 0))
                if received <= 0:
                    continue
                expected = _resolve_expected(session_id, entry)
                _emit_synthesis_ready(
                    session_id,
                    received=received,
                    expected=expected,
                    reason="timeout",
                    chain_id=entry.get("chain_id"),
                )
                entry["ready_emitted"] = True
                tracker[session_id] = entry
                changed = True
                actions.append(
                    f"synthesis_ready emitted for {session_id} "
                    f"({received}/{expected}, timeout)"
                )

        # Prune emitted sessions older than 24h to bound ledger growth.
        cutoff = now_ts - 86400
        pruned = {
            sid: e for sid, e in tracker.items()
            if not (e.get("ready_emitted") and float(e.get("last_contribution_ts") or 0.0) < cutoff)
        }
        if len(pruned) != len(tracker):
            tracker = pruned
            changed = True

        if changed:
            _save_tracker(tracker)

        if max_event_id > 0:
            ack_events(max_event_id)

    except Exception as e:
        logger.debug(f"jam bus consumer error (non-blocking): {e}")

    return actions


if __name__ == "__main__":
    # Manual invocation for testing / debug:
    #   python3 scripts/jam/_bus_consumers.py
    logging.basicConfig(level=logging.INFO)
    results = process_pending_events()
    for line in results:
        print(line)
