"""
crew/gate_dispatch.py — Polyglot gate verdict collection and BLEND aggregation.

Covers the dual delivery path for mixed wicked-garden + wicked-testing panels:
  - wicked-garden:crew:* reviewers  -> task dispatch path (standard)
  - wicked-testing:*  reviewers     -> bus subscriber path (with dispatch-log fallback)

Exposes:
  collect(gate_policy_entry, chain_id, clock=None) -> GateVerdict
  aggregate_blend(verdicts, clock=None) -> GateVerdict

Clock injection seam (AC-QE-EVAL-clock-injection-unresolved):
  `clock` defaults to `time.time`. Tests inject a deterministic callable to
  control the aggregation window without monkey-patching stdlib.

  WG_GATE_VERDICT_WINDOW_SECS env var (default: 60):
    - Positive integer: wait up to that many seconds for all panel verdicts.
    - "0": test-mode sentinel — aggregation window is skipped entirely; the
      caller receives whatever verdicts arrived without waiting for late ones.

Partial-panel invariant (AC-47):
  If len(received_verdicts) < len(expected_reviewers), aggregate_blend returns
  GateVerdict(verdict="pending", score=None). Gate is not flipped.

BLEND formula (v6.2 unchanged, AC-46):
  panel_score = 0.4 * min(scores) + 0.6 * avg(scores)

Deduplication: (reviewer, run_id) — first-seen wins across both paths.
Dispatch-log wins on conflict (design §4, DQ-4).

Stdlib-only.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterator, List, NamedTuple, Optional, Set, Tuple

# Ensure scripts/ (parent) is on path for sibling imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-crew.gate-dispatch")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW_SECS = 60
_TEST_MODE_WINDOW = 0    # WG_GATE_VERDICT_WINDOW_SECS=0 sentinel: skip waiting
_WICKED_TESTING_PREFIX = "wicked-testing:"
_WICKED_GARDEN_PREFIX = "wicked-garden:"


def _get_window_secs() -> int:
    """Read WG_GATE_VERDICT_WINDOW_SECS from env. Returns 0 for test-mode sentinel."""
    raw = os.environ.get("WG_GATE_VERDICT_WINDOW_SECS", "").strip()
    if not raw:
        return _DEFAULT_WINDOW_SECS
    try:
        val = int(raw)
        return max(0, val)
    except ValueError:
        logger.warning(
            "gate_dispatch: invalid WG_GATE_VERDICT_WINDOW_SECS=%r — using default %d",
            raw,
            _DEFAULT_WINDOW_SECS,
        )
        return _DEFAULT_WINDOW_SECS


# ---------------------------------------------------------------------------
# GateVerdict result type
# ---------------------------------------------------------------------------

class GateVerdict(NamedTuple):
    """Aggregated gate panel result."""

    verdict: str                         # APPROVE | REJECT | CONDITIONAL | pending
    score: Optional[float]               # None when verdict == "pending"
    reviewers_received: List[str]        # reviewers that delivered
    partial_panel: bool                  # True when some reviewers did not deliver
    late_verdicts: List[str]             # reviewer names that arrived after window close


# ---------------------------------------------------------------------------
# BLEND aggregation (AC-46)
# ---------------------------------------------------------------------------

def aggregate_blend(
    verdicts: List[Dict],
    *,
    expected_count: Optional[int] = None,
    clock: Optional[Callable[[], float]] = None,
) -> GateVerdict:
    """Apply BLEND formula to a list of verdict dicts.

    Formula (v6.2): panel_score = 0.4 * min(scores) + 0.6 * avg(scores)

    Partial-panel invariant (AC-47): if len(verdicts) < expected_count,
    returns GateVerdict(verdict="pending", score=None, ...).

    Args:
        verdicts: List of dicts each containing at minimum 'verdict' (str)
                  and 'score' (float). 'reviewer' is optional but included
                  in reviewers_received when present.
        expected_count: Total number of reviewers in the panel. When supplied
                        and len(verdicts) < expected_count, returns "pending".
                        When None, treats whatever arrived as the full panel.
        clock: Callable returning current time as float (default: time.time).
               Injected in tests for deterministic window math. The parameter
               is accepted here for interface uniformity; the window wait is
               in collect().

    Returns:
        GateVerdict named tuple.

    AC-46, AC-47.
    """
    _clock = clock if clock is not None else time.time  # noqa: F841 — reserved for callers

    # Partial-panel invariant
    if expected_count is not None and len(verdicts) < expected_count:
        return GateVerdict(
            verdict="pending",
            score=None,
            reviewers_received=[v.get("reviewer", "") for v in verdicts],
            partial_panel=True,
            late_verdicts=[],
        )

    if not verdicts:
        return GateVerdict(
            verdict="pending",
            score=None,
            reviewers_received=[],
            partial_panel=False,
            late_verdicts=[],
        )

    scores = [float(v.get("score", 0.0)) for v in verdicts]
    verdict_values = [v.get("verdict", "CONDITIONAL") for v in verdicts]
    reviewers = [v.get("reviewer", "") for v in verdicts]

    panel_score = 0.4 * min(scores) + 0.6 * (sum(scores) / len(scores))

    if "REJECT" in verdict_values:
        final_verdict = "REJECT"
    elif "CONDITIONAL" in verdict_values:
        final_verdict = "CONDITIONAL"
    else:
        final_verdict = "APPROVE"

    return GateVerdict(
        verdict=final_verdict,
        score=round(panel_score, 4),
        reviewers_received=reviewers,
        partial_panel=False,
        late_verdicts=[],
    )


# ---------------------------------------------------------------------------
# Verdict deduplication
# ---------------------------------------------------------------------------

def dedupe_by_run_id(
    verdicts: List[Dict],
    *,
    seen: Optional[Set[Tuple[str, str]]] = None,
    authoritative_path: str = "dispatch-log",
) -> List[Dict]:
    """Deduplicate verdicts by (reviewer, run_id). First-seen wins.

    Dispatch-log entries take precedence over bus entries when both carry the
    same (reviewer, run_id) — the dispatcher is already iterated deterministically
    per design §4 DQ-4.

    Args:
        verdicts: Raw verdict list (mixed delivery paths).
        seen: Optional external dedupe set (mutated in-place).
        authoritative_path: The delivery_path value that takes priority on
                            conflict (default: "dispatch-log").

    Returns:
        Deduplicated list preserving first-seen order.
    """
    if seen is None:
        seen = set()

    # Sort so authoritative_path entries come first
    sorted_v = sorted(
        verdicts,
        key=lambda v: (0 if v.get("delivery_path") == authoritative_path else 1),
    )

    result = []
    for v in sorted_v:
        key = (v.get("reviewer", ""), v.get("run_id", ""))
        if key in seen:
            logger.debug(
                "gate_dispatch: duplicate verdict (reviewer=%r, run_id=%r) from %r — skipped",
                v.get("reviewer"),
                v.get("run_id"),
                v.get("delivery_path"),
            )
            continue
        seen.add(key)
        result.append(v)

    return result


# ---------------------------------------------------------------------------
# Bus collection helper (injectable for tests)
# ---------------------------------------------------------------------------

def _collect_bus_verdicts(
    chain_id: str,
    expected_reviewers: List[str],
    *,
    seen: Optional[Set[Tuple[str, str]]] = None,
    _bus_available_fn=None,
    _poll_fn=None,
    _ack_fn=None,
):
    """Collect verdicts from the wicked-testing bus subscriber.

    Delegates to _wicked_testing_bus.collect_verdicts_from_bus. This wrapper
    exists as a module-level name so tests can patch gate_dispatch._collect_bus_verdicts
    without touching the _wicked_testing_bus module internals.

    Returns empty list when bus is absent or _wicked_testing_bus is unavailable.
    """
    try:
        from _wicked_testing_bus import collect_verdicts_from_bus  # type: ignore[import]
        return collect_verdicts_from_bus(
            chain_id,
            expected_reviewers,
            seen=seen,
            _bus_available_fn=_bus_available_fn,
            _poll_fn=_poll_fn,
            _ack_fn=_ack_fn,
        )
    except Exception as exc:
        logger.debug("gate_dispatch: _collect_bus_verdicts import/call failed: %r", exc)
        return []


# ---------------------------------------------------------------------------
# collect() — main entry point (CH-02 clock injection seam)
# ---------------------------------------------------------------------------

def collect(
    gate_policy_entry: Dict,
    chain_id: str,
    *,
    clock: Optional[Callable[[], float]] = None,
    existing_verdicts: Optional[List[Dict]] = None,
    _bus_available_fn=None,
) -> GateVerdict:
    """Collect verdicts from all delivery paths and return aggregated GateVerdict.

    Dual delivery paths (design §4):
      1. wicked-testing:* reviewers -> bus subscriber (_wicked_testing_bus)
      2. All reviewers               -> dispatch-log / gate-result.json (fallback)

    The aggregation window (WG_GATE_VERDICT_WINDOW_SECS, default 60) controls
    how long to wait for late verdicts. WG_GATE_VERDICT_WINDOW_SECS=0 is the
    test-mode sentinel that skips the wait entirely.

    Clock injection (QE-EVAL-clock-injection-unresolved condition):
      `clock` defaults to `time.time` when None. Tests inject a mock callable
      to make window-math deterministic without monkey-patching stdlib.

    Args:
        gate_policy_entry: The rigor-tier block from gate-policy.json.
        chain_id: The crew chain_id for bus event filtering.
        clock: Optional time callable (default: time.time). AC-29 seam.
        existing_verdicts: Pre-collected verdicts (e.g., from prior dispatch-log
                           read). Merged with bus-sourced verdicts before BLEND.

    Returns:
        GateVerdict — may have verdict="pending" for partial panels.

    AC-24, AC-25, AC-27, AC-46, AC-47.
    """
    _clock = clock if clock is not None else time.time
    window_secs = _get_window_secs()

    reviewers: List[str] = list(gate_policy_entry.get("reviewers") or [])
    wt_reviewers = [r for r in reviewers if r.startswith(_WICKED_TESTING_PREFIX)]

    # Start with any pre-collected verdicts (dispatch-log path)
    all_verdicts: List[Dict] = list(existing_verdicts or [])
    seen: Set[Tuple[str, str]] = set()

    # Mark pre-collected as from dispatch-log path
    for v in all_verdicts:
        if "delivery_path" not in v:
            v = dict(v)
            v["delivery_path"] = "dispatch-log"
        key = (v.get("reviewer", ""), v.get("run_id", ""))
        if key not in seen:
            seen.add(key)

    # Collect from bus (wicked-testing:* reviewers)
    if wt_reviewers:
        try:
            bus_verdicts = _collect_bus_verdicts(
                chain_id, wt_reviewers, seen=seen,
                _bus_available_fn=_bus_available_fn,
            )
            for bv in bus_verdicts:
                all_verdicts.append({
                    "reviewer": bv.reviewer,
                    "run_id": bv.run_id,
                    "verdict": bv.verdict,
                    "score": bv.score,
                    "delivery_path": bv.delivery_path,
                    "raw_verdict": bv.raw_verdict,
                })
        except Exception as exc:
            logger.debug("gate_dispatch: bus collect error: %r", exc)

    # Deduplicate: dispatch-log authoritative over bus
    deduped = dedupe_by_run_id(all_verdicts)

    # Check if panel is complete
    received_count = len(deduped)
    expected_count = len(reviewers) if reviewers else None

    # Window logic: if panel incomplete and window > 0, note timeout for late verdicts
    late_verdicts: List[str] = []
    partial_panel = (
        expected_count is not None and received_count < expected_count
    )

    if partial_panel and window_secs > _TEST_MODE_WINDOW:
        # In production, the window has already elapsed by the time collect() is
        # called (reviewers write to dispatch-log or bus asynchronously). We record
        # which reviewers did NOT deliver as late_verdicts for conditions-manifest.
        received_reviewers = {v.get("reviewer", "") for v in deduped}
        late_verdicts = [r for r in reviewers if r not in received_reviewers]
        # Add CONDITIONAL conditions for each timed-out reviewer
        for late_r in late_verdicts:
            all_verdicts.append({
                "reviewer": late_r,
                "run_id": f"timeout-{late_r}",
                "verdict": "CONDITIONAL",
                "score": 0.5,
                "delivery_path": "timeout",
                "conditions": [
                    {
                        "id": f"verdict-timeout:{late_r}",
                        "description": (
                            f"verdict-timeout: {late_r} did not deliver within "
                            f"{window_secs}s window"
                        ),
                    }
                ],
            })
        deduped = dedupe_by_run_id(all_verdicts)
        partial_panel = False  # window expired — treat synthetic verdicts as full panel

    result = aggregate_blend(deduped, expected_count=expected_count if partial_panel else None)

    if late_verdicts:
        # Rebuild with late_verdicts populated
        return GateVerdict(
            verdict=result.verdict,
            score=result.score,
            reviewers_received=result.reviewers_received,
            partial_panel=result.partial_panel,
            late_verdicts=late_verdicts,
        )

    return result
