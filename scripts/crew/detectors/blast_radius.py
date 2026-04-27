#!/usr/bin/env python3
"""
crew/detectors/blast_radius.py — Blast-radius explosion detector.

PR-4 of the steering detector epic (#679). Fires ``wicked.steer.escalated``
when the observed file-edit count blows past the original facilitator
estimate by a significant margin AND crosses an absolute floor (so a 1-file
plan that turns into 3 files doesn't spam events).

Threshold (per epic brainstorm):

    fires iff  observed > (RATIO_MULTIPLIER * estimated)  AND  observed > FLOOR

with ``RATIO_MULTIPLIER = 2`` and ``FLOOR = 8``. The absolute floor is the
flow-protector concession — small estimates with small overruns stay quiet.

Recommended action: ``force-full-rigor``.

Subdomain: ``crew.detector.blast-radius``.

Design constraints (mirror PR-2 ``sensitive_path.py``):

  * Pure stdlib.
  * Detector and emitter are separate. ``detect_blast_radius_explosion``
    returns a list of validated payloads; ``emit_blast_radius_events``
    pushes them to wicked-bus.
  * Every emitted payload is re-validated against
    ``crew.steering_event_schema.validate_payload`` — invalid payloads are
    dropped, never blocked.
  * Fail-open if bus unreachable.

Usage (programmatic)::

    from crew.detectors.blast_radius import (
        detect_blast_radius_explosion,
        emit_blast_radius_events,
    )

    payloads = detect_blast_radius_explosion(
        observed_files=12,
        estimated_files=2,
        session_id="sess-001",
        project_slug="demo",
    )
    # -> [{"detector": "blast-radius", ...}]  (one event)

    emit_blast_radius_events(payloads)
    # -> 1

Usage (CLI)::

    python3 scripts/crew/detectors/blast_radius.py \\
        --observed 12 --estimated 2 \\
        --session-id sess-001 --project-slug demo --dry-run
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

DETECTOR_NAME = "blast-radius"
EVENT_TYPE = "wicked.steer.escalated"
EVENT_SUBDOMAIN = f"crew.detector.{DETECTOR_NAME}"

assert DETECTOR_NAME in KNOWN_DETECTORS, (
    f"detector {DETECTOR_NAME!r} not in KNOWN_DETECTORS — "
    "schema (steering_event_schema.py) and detector are out of sync"
)

#: Fire when ``observed > RATIO_MULTIPLIER * estimated``.
RATIO_MULTIPLIER: int = 2

#: Absolute floor — even a >2x ratio stays quiet below this many observed
#: files. Avoids "1 estimated, 3 observed" noise on small tasks.
ABSOLUTE_FLOOR: int = 8

#: When the caller passes ``estimated_files=0`` we substitute this floor to
#: avoid divide-by-zero AND avoid silently treating 0 as an infinite budget.
#: 1 means even 9 observed files (1 * 2 = 2, AND 9 > 8) will fire — the
#: caller should fix their estimate, but until they do, we err on the side
#: of escalation.
ZERO_ESTIMATE_FLOOR: int = 1

RECOMMENDED_ACTION = "force-full-rigor"


# ---------------------------------------------------------------------------
# Public API — detector
# ---------------------------------------------------------------------------

def detect_blast_radius_explosion(
    *,
    observed_files: int,
    estimated_files: int,
    session_id: str,
    project_slug: str,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Return zero or one validated payload depending on the threshold.

    Args:
        observed_files: Actual count of files edited in the current task.
            Negative inputs raise ``ValueError`` — they're a caller bug, not
            a runtime condition.
        estimated_files: Original estimate from the facilitator
            (``process-plan.json`` or task metadata). ``0`` is accepted with
            a stderr warning and floored to ``ZERO_ESTIMATE_FLOOR=1`` to
            avoid divide-by-zero. Negative inputs raise.
        session_id: Session id (required by schema).
        project_slug: Crew project slug (required by schema).
        now: Override for the timestamp source — only used by tests.

    Returns:
        A list with at most one payload. Empty list = below threshold.

    Raises:
        ValueError: ``observed_files`` or ``estimated_files`` is negative,
            or ``session_id`` / ``project_slug`` is empty.
    """
    require_non_empty_string(session_id, "session_id")
    require_non_empty_string(project_slug, "project_slug")

    if not isinstance(observed_files, int) or isinstance(observed_files, bool):
        raise ValueError(
            f"observed_files must be int, got {type(observed_files).__name__}"
        )
    if not isinstance(estimated_files, int) or isinstance(estimated_files, bool):
        raise ValueError(
            f"estimated_files must be int, got {type(estimated_files).__name__}"
        )
    if observed_files < 0:
        raise ValueError(
            f"observed_files must be >= 0, got {observed_files}"
        )
    if estimated_files < 0:
        raise ValueError(
            f"estimated_files must be >= 0, got {estimated_files}"
        )

    effective_estimate = estimated_files
    if estimated_files == 0:
        sys.stderr.write(
            "warn: blast-radius detector got estimated_files=0; "
            f"flooring to {ZERO_ESTIMATE_FLOOR} to avoid divide-by-zero\n"
        )
        effective_estimate = ZERO_ESTIMATE_FLOOR

    ratio_threshold = RATIO_MULTIPLIER * effective_estimate
    if not (observed_files > ratio_threshold and observed_files > ABSOLUTE_FLOOR):
        return []

    timestamp = utc_iso8601(now)
    payload = {
        "detector": DETECTOR_NAME,
        "signal": (
            f"observed file-edit count {observed_files} exceeds estimate "
            f"{estimated_files} by >{RATIO_MULTIPLIER}x and crosses "
            f"absolute floor {ABSOLUTE_FLOOR}"
        ),
        "threshold": {
            "ratio_multiplier": RATIO_MULTIPLIER,
            "absolute_floor": ABSOLUTE_FLOOR,
            "estimated_files": estimated_files,
            "effective_estimate": effective_estimate,
        },
        "recommended_action": RECOMMENDED_ACTION,
        "evidence": {
            "observed_files": observed_files,
            "estimated_files": estimated_files,
            "ratio": (
                round(observed_files / effective_estimate, 2)
                if effective_estimate
                else None
            ),
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
            f"blast-radius detector built an invalid payload: {errors}"
        )
    return [payload]


# ---------------------------------------------------------------------------
# Public API — emitter
# ---------------------------------------------------------------------------

def emit_blast_radius_events(payloads: Sequence[dict]) -> int:
    """Emit each payload to wicked-bus as ``wicked.steer.escalated``.

    Thin wrapper over :func:`crew.detectors._common.emit_validated_payloads`
    that pins the event_type and subdomain. Fails open on bus unreachable.
    """
    return emit_validated_payloads(
        payloads,
        event_type=EVENT_TYPE,
        subdomain=EVENT_SUBDOMAIN,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_standard_arg_parser(
        prog="blast_radius",
        description=(
            "Detect blast-radius explosions (observed files >> estimated) "
            "and emit wicked.steer.escalated events."
        ),
    )
    parser.add_argument(
        "--observed",
        type=int,
        required=True,
        help="Actual file-edit count for the current task.",
    )
    parser.add_argument(
        "--estimated",
        type=int,
        required=True,
        help="Original facilitator estimate (process-plan.json / metadata).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        payloads = detect_blast_radius_explosion(
            observed_files=args.observed,
            estimated_files=args.estimated,
            session_id=args.session_id,
            project_slug=args.project_slug,
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    for event_record in payloads:
        sys.stdout.write(json.dumps(event_record, separators=(",", ":")) + "\n")
    sys.stdout.flush()

    sys.stderr.write(
        f"detector: {len(payloads)} steering event(s) "
        f"(observed={args.observed}, estimated={args.estimated})\n"
    )

    if args.dry_run:
        return 0

    emitted = emit_blast_radius_events(payloads)
    sys.stderr.write(
        f"emitted: {emitted}/{len(payloads)} event(s) to wicked-bus\n"
    )
    return 0


__all__ = [
    "DETECTOR_NAME",
    "EVENT_TYPE",
    "EVENT_SUBDOMAIN",
    "RATIO_MULTIPLIER",
    "ABSOLUTE_FLOOR",
    "ZERO_ESTIMATE_FLOOR",
    "RECOMMENDED_ACTION",
    "detect_blast_radius_explosion",
    "emit_blast_radius_events",
]


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
