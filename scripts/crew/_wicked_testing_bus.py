"""
crew/_wicked_testing_bus.py — wicked.verdict.recorded bus subscriber.

Subscribes to wicked-testing verdict events from wicked-bus and maps them
to crew gate verdicts for BLEND aggregation.

Verdict mapping (AC-26):
  PASS  -> APPROVE
  FAIL  -> REJECT
  N-A   -> CONDITIONAL
  SKIP  -> CONDITIONAL
  *     -> REJECT  (logged as error)

Deduplication: first-seen wins, keyed by (reviewer, run_id).

Bus-absent fallback (AC-27): when wicked-bus is not available, returns an
empty iterator and logs one DEBUG line. The caller falls back to the
dispatch-log / gate-result.json path.

Stdlib-only.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Optional, Set, Tuple

# Ensure scripts/ is on the path for _bus import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-crew.wicked-testing-bus")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_TYPE = "wicked.verdict.recorded"
EXPECTED_DOMAIN = "wicked-testing"

# AC-26 — verdict value mapping
_VERDICT_MAP: Dict[str, str] = {
    "PASS": "APPROVE",
    "FAIL": "REJECT",
    "N-A": "CONDITIONAL",
    "SKIP": "CONDITIONAL",
}


# ---------------------------------------------------------------------------
# Verdict record
# ---------------------------------------------------------------------------

class Verdict(NamedTuple):
    """A mapped crew gate verdict from a wicked-testing reviewer event."""

    reviewer: str       # wicked-testing:* agent name
    run_id: str         # dedupe key
    verdict: str        # APPROVE | REJECT | CONDITIONAL
    score: float        # raw score from event (0.0-1.0); 0.5 default if absent
    delivery_path: str  # "bus" or "dispatch-log"
    raw_verdict: str    # original wicked-testing verdict string


# ---------------------------------------------------------------------------
# Verdict mapping
# ---------------------------------------------------------------------------

def map_verdict(raw: str) -> str:
    """Map a wicked-testing verdict to a crew gate verdict.

    AC-26: unmapped values are treated as REJECT and logged as errors.
    """
    mapped = _VERDICT_MAP.get(raw)
    if mapped is None:
        logger.error(
            "wicked-testing bus: unmapped verdict value %r — treating as REJECT",
            raw,
        )
        return "REJECT"
    return mapped


# ---------------------------------------------------------------------------
# Bus availability check (injectable for tests)
# ---------------------------------------------------------------------------

def _is_bus_available() -> bool:
    """Return True if wicked-bus is available. Fail-open on import errors."""
    try:
        from _bus import _check_available  # type: ignore[import]
        return _check_available()
    except Exception:
        return False


def _poll_bus_events(event_type: str) -> List[Dict]:
    """Poll wicked-bus for events. Returns empty list on any failure."""
    try:
        from _bus import poll_pending  # type: ignore[import]
        return poll_pending(event_type_prefix=event_type) or []
    except Exception:
        return []


def _ack_bus_events(last_id: int) -> None:
    """Acknowledge bus events up to last_id. Fail-open."""
    try:
        from _bus import ack_events  # type: ignore[import]
        ack_events(last_id)
    except Exception:
        pass  # fail open — bus ack is best-effort


# ---------------------------------------------------------------------------
# Bus subscriber
# ---------------------------------------------------------------------------

def subscribe_to_verdicts(
    chain_id: str,
    *,
    seen: Optional[Set[Tuple[str, str]]] = None,
    _bus_available_fn=None,
    _poll_fn=None,
    _ack_fn=None,
) -> Iterator[Verdict]:
    """Yield Verdict records from wicked.verdict.recorded bus events.

    Polls the bus for events matching the wicked-testing domain and the
    supplied chain_id. Deduplicates by (reviewer, run_id) — first-seen wins.

    When wicked-bus is unavailable, yields nothing and logs one DEBUG line.

    Args:
        chain_id: The crew chain_id to filter events by (e.g. "proj.design").
        seen: Optional external dedupe set; mutated in-place. Useful when
              merging bus verdicts with dispatch-log verdicts.
        _bus_available_fn: Injectable availability check (default: _is_bus_available).
        _poll_fn: Injectable poll function (default: _poll_bus_events).
        _ack_fn: Injectable ack function (default: _ack_bus_events).

    Yields:
        Verdict named tuples in arrival order (after deduplication).

    AC-25, AC-27.
    """
    if seen is None:
        seen = set()

    bus_available = _bus_available_fn if _bus_available_fn is not None else _is_bus_available
    poll_fn = _poll_fn if _poll_fn is not None else _poll_bus_events
    ack_fn = _ack_fn if _ack_fn is not None else _ack_bus_events

    if not bus_available():
        logger.debug(
            "wicked-testing bus: wicked-bus not available — falling back to dispatch-log"
        )
        return

    try:
        events = poll_fn(EVENT_TYPE)
    except Exception as exc:
        logger.debug(
            "wicked-testing bus: poll raised %r — falling back to dispatch-log",
            exc,
        )
        return

    max_event_id = 0
    for event in events:
        event_id = event.get("event_id", 0)
        if event_id > max_event_id:
            max_event_id = event_id

        if event.get("event_type") != EVENT_TYPE:
            continue

        metadata = event.get("metadata", {})
        if metadata.get("chain_id") and metadata["chain_id"] != chain_id:
            continue

        payload = event.get("payload", {})
        domain = payload.get("domain", "")
        if domain and domain != EXPECTED_DOMAIN:
            continue

        reviewer = payload.get("reviewer", "")
        run_id = payload.get("run_id", "")
        raw_verdict = payload.get("verdict", "")
        score = float(payload.get("score", 0.5))

        if not reviewer or not run_id:
            logger.debug(
                "wicked-testing bus: skipping event missing reviewer or run_id: %r",
                payload,
            )
            continue

        dedupe_key = (reviewer, run_id)
        if dedupe_key in seen:
            logger.debug(
                "wicked-testing bus: duplicate (reviewer=%r, run_id=%r) — skipping",
                reviewer,
                run_id,
            )
            continue

        seen.add(dedupe_key)
        yield Verdict(
            reviewer=reviewer,
            run_id=run_id,
            verdict=map_verdict(raw_verdict),
            score=score,
            delivery_path="bus",
            raw_verdict=raw_verdict,
        )

    if max_event_id > 0:
        ack_fn(max_event_id)


def collect_verdicts_from_bus(
    chain_id: str,
    expected_reviewers: List[str],
    *,
    seen: Optional[Set[Tuple[str, str]]] = None,
    _bus_available_fn=None,
    _poll_fn=None,
    _ack_fn=None,
) -> List[Verdict]:
    """Collect wicked-testing bus verdicts for the given reviewers and chain.

    Filters to only verdicts whose reviewer is in expected_reviewers.
    Returns an empty list when bus is absent (caller falls through to
    dispatch-log path).

    AC-25, AC-27.
    """
    expected_set = set(expected_reviewers)
    results: List[Verdict] = []
    for verdict in subscribe_to_verdicts(
        chain_id,
        seen=seen,
        _bus_available_fn=_bus_available_fn,
        _poll_fn=_poll_fn,
        _ack_fn=_ack_fn,
    ):
        if not expected_set or verdict.reviewer in expected_set:
            results.append(verdict)
    return results
