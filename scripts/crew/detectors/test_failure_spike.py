#!/usr/bin/env python3
"""
crew/detectors/test_failure_spike.py — Test-failure spike detector.

PR-4 of the steering detector epic (#679). Fires
``wicked.steer.escalated`` when the session has hit ``CONSECUTIVE_FAILURE_THRESHOLD``
consecutive non-zero pytest exit codes AFTER at least one green baseline.

Recommended action: ``regen-test-strategy``.

Subdomain: ``crew.detector.test-failure-spike``.

------------------------------------------------------------------------
SIGNAL SOURCE
------------------------------------------------------------------------

A repository scan at PR-4 time confirmed the framework does NOT currently
track pytest exit codes. The relevant places that SHOULD eventually carry
this signal are:

  * ``hooks/scripts/post_tool.py`` (the Bash PostToolUse handler — no test
    framework awareness today).
  * ``scripts/_session.py`` (no per-session test_result list).
  * ``scripts/delivery/telemetry.py`` (gate-rate metrics only — no test
    aggregation).

Per the brainstorm fallback plan, this detector ships with a clean public
API and an explicit-input CLI (``--exit-codes 1,1,1,0,1,1,1``) that lets
callers (tests, ad-hoc invocations, future hook wiring) drive it directly.
The signal source is a TODO — see follow-up issue suggestion in epic #679.

# TODO(epic #679): wire signal source — add a PostToolUse-Bash handler in
#   hooks/scripts/post_tool.py that detects pytest invocations, records
#   exit codes onto SessionState, and invokes this detector when the
#   threshold trips.

------------------------------------------------------------------------
THRESHOLD
------------------------------------------------------------------------

Per epic brainstorm:

  * ``N=3`` consecutive non-zero exits AFTER at least one ``0``.
  * The "after first green baseline" guard avoids firing on session-start
    before any test has been run (sessions that open with N pre-existing
    red exits from a prior run, or a CI scrape, shouldn't auto-trip).
  * Counting is "trailing window": only the most recent N matters. A series
    like ``[0, 1, 1, 0, 1, 1, 1]`` fires (the last 3 are non-zero and we've
    seen at least one ``0`` somewhere in the prefix).

Edge cases the test suite locks in:

  * ``[0, 1, 1, 1]``       → fires (baseline 0, then 3 failures)
  * ``[1, 1, 1]``          → does NOT fire (no baseline)
  * ``[0, 1, 1]``          → does NOT fire (only 2 trailing failures)
  * ``[0, 1, 0, 1, 1, 1]`` → fires (trailing 3 are non-zero, baseline at idx 2)
  * ``[]``                 → no-op
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

# Allow running directly as a script.
_REPO_SCRIPTS = Path(__file__).resolve().parents[2]
if str(_REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_REPO_SCRIPTS))

from crew.detectors._common import (  # noqa: E402
    build_standard_arg_parser,
    emit_validated_payloads,
    require_non_empty_string,
    utc_iso8601,
)
from crew.steering_event_schema import (  # noqa: E402
    KNOWN_DETECTORS,
    validate_payload,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DETECTOR_NAME = "test-failure-spike"
EVENT_TYPE = "wicked.steer.escalated"
EVENT_SUBDOMAIN = f"crew.detector.{DETECTOR_NAME}"

assert DETECTOR_NAME in KNOWN_DETECTORS, (
    f"detector {DETECTOR_NAME!r} not in KNOWN_DETECTORS — "
    "schema (steering_event_schema.py) and detector are out of sync"
)

#: Number of consecutive trailing non-zero exits required to fire.
CONSECUTIVE_FAILURE_THRESHOLD: int = 3

RECOMMENDED_ACTION = "regen-test-strategy"


# ---------------------------------------------------------------------------
# Public API — detector
# ---------------------------------------------------------------------------

def detect_test_failure_spike(
    *,
    exit_codes: Sequence[int],
    session_id: str,
    project_slug: str,
    threshold: int = CONSECUTIVE_FAILURE_THRESHOLD,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Return zero or one validated payload depending on trailing failures.

    Args:
        exit_codes: Chronological pytest exit codes for the session, oldest
            first. Each entry must be an int (``0`` = pass, non-zero =
            failure). Booleans rejected even though ``isinstance(True, int)``
            — they're almost always a caller bug.
        session_id: Session id (required by schema).
        project_slug: Crew project slug (required by schema).
        threshold: Consecutive failure count required to fire. Defaults to
            ``CONSECUTIVE_FAILURE_THRESHOLD=3``. Must be ``>= 1``.
        now: Override for the timestamp source — only used by tests.

    Returns:
        A list with at most one payload. Empty list = below threshold or
        pre-baseline.

    Raises:
        ValueError: bad ``threshold``, non-int entries in ``exit_codes``,
            or empty ``session_id`` / ``project_slug``.
    """
    require_non_empty_string(session_id, "session_id")
    require_non_empty_string(project_slug, "project_slug")
    if (
        not isinstance(threshold, int)
        or isinstance(threshold, bool)
        or threshold < 1
    ):
        raise ValueError(f"threshold must be int >= 1, got {threshold!r}")

    # Guard inputs — catch the common "list of strings" foot-gun early.
    cleaned: List[int] = []
    for entry in exit_codes:
        if isinstance(entry, bool) or not isinstance(entry, int):
            raise ValueError(
                f"exit_codes entries must be int, got {type(entry).__name__} "
                f"({entry!r})"
            )
        cleaned.append(entry)

    if len(cleaned) < threshold:
        # Not enough datapoints — even if all were failures, we don't have
        # threshold-many to trigger.
        return []

    # Find the most recent baseline (0). The "after first green baseline"
    # guard applies. If there's no zero anywhere, we never fire.
    if 0 not in cleaned:
        return []

    # Count trailing non-zero exits.
    trailing_failures = 0
    for code in reversed(cleaned):
        if code == 0:
            break
        trailing_failures += 1

    if trailing_failures < threshold:
        return []

    # Defense-in-depth: if the trailing streak consumed the entire list,
    # there's no baseline before it (we'd already have returned above on
    # ``0 not in cleaned``, but this keeps the invariant explicit).
    baseline_index = _last_zero_index(cleaned)
    if baseline_index is None or baseline_index >= len(cleaned) - trailing_failures:
        # No baseline appeared BEFORE the trailing streak. Could happen if
        # the only zero IS inside the trailing streak — by definition
        # trailing-streak is non-zero, so we just confirm the baseline came
        # earlier than the streak.
        return []

    timestamp = utc_iso8601(now)
    payload = {
        "detector": DETECTOR_NAME,
        "signal": (
            f"test failure spike: {trailing_failures} consecutive non-zero "
            f"pytest exits after baseline (threshold={threshold})"
        ),
        "threshold": {
            "consecutive_failure_threshold": threshold,
            "trailing_failures": trailing_failures,
            "total_observations": len(cleaned),
        },
        "recommended_action": RECOMMENDED_ACTION,
        "evidence": {
            "exit_codes": list(cleaned),
            "trailing_failures": trailing_failures,
            "baseline_index": baseline_index,
            "session_id": session_id,
            "project_slug": project_slug,
        },
        "session_id": session_id,
        "project_slug": project_slug,
        "timestamp": timestamp,
    }
    errors, _warnings = validate_payload(EVENT_TYPE, payload)
    if errors:
        raise AssertionError(
            f"test-failure-spike detector built an invalid payload: {errors}"
        )
    return [payload]


def _last_zero_index(codes: Sequence[int]) -> Optional[int]:
    """Return index of the rightmost 0 in ``codes``, or ``None`` if absent."""
    for i in range(len(codes) - 1, -1, -1):
        if codes[i] == 0:
            return i
    return None


# ---------------------------------------------------------------------------
# Public API — emitter
# ---------------------------------------------------------------------------

def emit_test_failure_spike_events(payloads: Sequence[dict]) -> int:
    """Emit each payload to wicked-bus as ``wicked.steer.escalated``."""
    return emit_validated_payloads(
        payloads,
        event_type=EVENT_TYPE,
        subdomain=EVENT_SUBDOMAIN,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_exit_codes_arg(raw: str) -> List[int]:
    """Parse ``--exit-codes`` — comma-separated ints (e.g. ``1,1,1,0``)."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out: List[int] = []
    for part in parts:
        try:
            out.append(int(part))
        except ValueError as exc:
            raise ValueError(
                f"--exit-codes entry {part!r} is not an int: {exc}"
            )
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_standard_arg_parser(
        prog="test_failure_spike",
        description=(
            "Detect test-failure spikes (N consecutive non-zero pytest "
            "exits after a green baseline) and emit wicked.steer.escalated "
            "events. Until the framework wires a signal source, callers "
            "supply --exit-codes explicitly."
        ),
    )
    parser.add_argument(
        "--exit-codes",
        required=True,
        help=(
            "Chronological pytest exit codes as a comma-separated list, "
            "oldest first (e.g. '0,1,1,1'). 0 = pass, non-zero = fail. "
            "Until the framework wires the signal source automatically, "
            "this is the canonical input."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=CONSECUTIVE_FAILURE_THRESHOLD,
        help=(
            f"Consecutive trailing failures required to fire (default "
            f"{CONSECUTIVE_FAILURE_THRESHOLD})."
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        codes = _parse_exit_codes_arg(args.exit_codes)
        payloads = detect_test_failure_spike(
            exit_codes=codes,
            session_id=args.session_id,
            project_slug=args.project_slug,
            threshold=args.threshold,
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    for event_record in payloads:
        sys.stdout.write(json.dumps(event_record, separators=(",", ":")) + "\n")
    sys.stdout.flush()

    sys.stderr.write(
        f"detector: {len(payloads)} steering event(s) from "
        f"{len(codes)} exit code(s)\n"
    )

    if args.dry_run:
        return 0

    emitted = emit_test_failure_spike_events(payloads)
    sys.stderr.write(
        f"emitted: {emitted}/{len(payloads)} event(s) to wicked-bus\n"
    )
    return 0


__all__ = [
    "DETECTOR_NAME",
    "EVENT_TYPE",
    "EVENT_SUBDOMAIN",
    "CONSECUTIVE_FAILURE_THRESHOLD",
    "RECOMMENDED_ACTION",
    "detect_test_failure_spike",
    "emit_test_failure_spike_events",
]


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
