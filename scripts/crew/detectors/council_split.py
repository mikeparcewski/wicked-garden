#!/usr/bin/env python3
"""
crew/detectors/council_split.py — Council vote-split detector.

PR-4 of the steering detector epic (#679). Fires
``wicked.steer.escalated`` when the most recent council gate produced no
clear majority — e.g. a 2-2 tie on a 4-voter panel, or a 2-1-1 split with no
verdict reaching the configured ``quorum_threshold``.

Recommended action: ``require-council-review`` — the next gate is forced
into council mode regardless of the project's normal dispatch tier.

Subdomain: ``crew.detector.council-split``.

Threshold logic (per epic brainstorm):

  * Take the most recent gate-finding records (caller filters / orders
    them — typically the latest single gate's voter records).
  * Tally verdict counts across the panel (``APPROVE``, ``CONDITIONAL``,
    ``REJECT`` — or any caller-supplied verdict labels).
  * If the maximum vote count is ``< quorum_threshold`` (default 3), the
    gate failed to reach quorum → fires.
  * Single-voter panels are no-op (can't have a split).
  * Empty input is no-op.

Input shape (``gate_findings``)::

    [
        {"verdict": "APPROVE",    "reviewer": "senior-engineer", ...},
        {"verdict": "REJECT",     "reviewer": "security-engineer", ...},
        {"verdict": "APPROVE",    "reviewer": "product-manager", ...},
        {"verdict": "REJECT",     "reviewer": "risk-assessor", ...},
    ]

Only ``verdict`` is required by this detector — extra keys are passed
through into the emitted ``evidence`` dict for the audit trail. Records
without a ``verdict`` field are skipped with a stderr warning (we never
silently invent a vote).

Design constraints (mirror PR-2 ``sensitive_path.py``):

  * Pure stdlib.
  * Detector and emitter are separate.
  * Every emitted payload is re-validated against the schema.
  * Fail-open if bus unreachable.

Usage (programmatic)::

    from crew.detectors.council_split import (
        detect_council_split,
        emit_council_split_events,
    )

    payloads = detect_council_split(
        gate_findings=[
            {"verdict": "APPROVE", "reviewer": "a"},
            {"verdict": "APPROVE", "reviewer": "b"},
            {"verdict": "REJECT",  "reviewer": "c"},
            {"verdict": "REJECT",  "reviewer": "d"},
        ],
        session_id="sess-001",
        project_slug="demo",
    )
    # -> [{"detector": "council-split", ...}]  (one event)

Usage (CLI)::

    # Pass voter records as a JSON literal or @path/to/file.json
    python3 scripts/crew/detectors/council_split.py \\
        --gate-findings '[{"verdict":"APPROVE"},{"verdict":"REJECT"},
                          {"verdict":"APPROVE"},{"verdict":"REJECT"}]' \\
        --session-id sess-001 --project-slug demo --dry-run
"""

from __future__ import annotations

import json
import sys
from collections import Counter
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

DETECTOR_NAME = "council-split"
EVENT_TYPE = "wicked.steer.escalated"
EVENT_SUBDOMAIN = f"crew.detector.{DETECTOR_NAME}"

assert DETECTOR_NAME in KNOWN_DETECTORS, (
    f"detector {DETECTOR_NAME!r} not in KNOWN_DETECTORS — "
    "schema (steering_event_schema.py) and detector are out of sync"
)

#: Default quorum — vote count required for a "clear" verdict. A panel of 4
#: where the leading verdict has only 2 votes (max < 3) is a split. Callers
#: tune this for non-default panel sizes.
DEFAULT_QUORUM_THRESHOLD: int = 3

#: Minimum voters required to consider a split. 1 voter is never a split.
MIN_VOTERS_FOR_SPLIT: int = 2

RECOMMENDED_ACTION = "require-council-review"


# ---------------------------------------------------------------------------
# Public API — detector
# ---------------------------------------------------------------------------

def detect_council_split(
    *,
    gate_findings: Sequence[dict],
    session_id: str,
    project_slug: str,
    quorum_threshold: int = DEFAULT_QUORUM_THRESHOLD,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Return zero or one validated payload depending on vote tally.

    Args:
        gate_findings: Voter records from the most recent council gate. Each
            entry MUST be a dict with at least a ``verdict`` key (string).
            Records missing/with non-string ``verdict`` are skipped with a
            stderr warning. Order does not matter.
        session_id: Session id (required by schema).
        project_slug: Crew project slug (required by schema).
        quorum_threshold: Vote count needed for a clear verdict. Defaults to
            3. Must be ``>= 2`` (1 means any single vote wins, which is not
            a split scenario the caller intended). Raises ``ValueError`` on
            non-int / < 2.
        now: Override for the timestamp source — only used by tests.

    Returns:
        A list with at most one payload. Empty list = no split detected
        (or input was too small to consider).

    Raises:
        ValueError: bad ``quorum_threshold``, or empty
            ``session_id`` / ``project_slug``.
    """
    require_non_empty_string(session_id, "session_id")
    require_non_empty_string(project_slug, "project_slug")
    if (
        not isinstance(quorum_threshold, int)
        or isinstance(quorum_threshold, bool)
        or quorum_threshold < MIN_VOTERS_FOR_SPLIT
    ):
        raise ValueError(
            f"quorum_threshold must be int >= {MIN_VOTERS_FOR_SPLIT}, "
            f"got {quorum_threshold!r}"
        )

    if not gate_findings:
        return []

    # Extract verdicts, dropping malformed entries with a warning.
    verdicts: List[str] = []
    for record in gate_findings:
        if not isinstance(record, dict):
            sys.stderr.write(
                f"warn: council-split detector skipping non-dict finding: "
                f"{type(record).__name__}\n"
            )
            continue
        v = record.get("verdict")
        if not isinstance(v, str) or not v.strip():
            sys.stderr.write(
                "warn: council-split detector skipping finding without "
                f"valid verdict: {record!r}\n"
            )
            continue
        verdicts.append(v.strip())

    voter_count = len(verdicts)
    if voter_count < MIN_VOTERS_FOR_SPLIT:
        # Single voter (or zero after filtering) — not a split scenario.
        return []

    tally = Counter(verdicts)
    leading_count = max(tally.values())

    # Fires when no verdict reaches quorum. This catches:
    #   - 2-2 ties on a 4-voter panel (leading=2 < 3)
    #   - 2-1-1 splits on a 4-voter panel (leading=2 < 3)
    # Does NOT fire on:
    #   - 3-1 majority (leading=3 >= 3)
    #   - any verdict with quorum_threshold votes
    if leading_count >= quorum_threshold:
        return []

    timestamp = utc_iso8601(now)
    payload = {
        "detector": DETECTOR_NAME,
        "signal": (
            f"council split: {voter_count} voters, leading verdict has "
            f"{leading_count} votes (< quorum {quorum_threshold})"
        ),
        "threshold": {
            "quorum_threshold": quorum_threshold,
            "voter_count": voter_count,
            "leading_count": leading_count,
        },
        "recommended_action": RECOMMENDED_ACTION,
        "evidence": {
            "vote_tally": dict(tally),
            "voter_count": voter_count,
            "leading_count": leading_count,
            # Pass through the raw findings (without nested non-serializable
            # values) so the audit trail keeps the reviewer attribution.
            "gate_findings": [
                _safe_finding(f) for f in gate_findings if isinstance(f, dict)
            ],
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
            f"council-split detector built an invalid payload: {errors}"
        )
    return [payload]


def _safe_finding(record: dict) -> dict:
    """Return a JSON-serializable subset of a gate-finding record.

    We pass through ``verdict``, ``reviewer``, ``score``, and ``min_score``
    when present — these are the audit-relevant fields. Anything else is
    dropped to keep the evidence payload bounded.
    """
    out: dict = {}
    for key in ("verdict", "reviewer", "score", "min_score"):
        if key in record:
            out[key] = record[key]
    return out


# ---------------------------------------------------------------------------
# Public API — emitter
# ---------------------------------------------------------------------------

def emit_council_split_events(payloads: Sequence[dict]) -> int:
    """Emit each payload to wicked-bus as ``wicked.steer.escalated``."""
    return emit_validated_payloads(
        payloads,
        event_type=EVENT_TYPE,
        subdomain=EVENT_SUBDOMAIN,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_findings_arg(raw: str) -> List[dict]:
    """Parse ``--gate-findings`` — accepts JSON literal or ``@path``."""
    if raw.startswith("@"):
        path = Path(raw[1:])
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read gate-findings file {path}: {exc}")
    else:
        text = raw
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--gate-findings must be valid JSON: {exc}")
    if not isinstance(parsed, list):
        raise ValueError(
            f"--gate-findings must be a JSON list, got {type(parsed).__name__}"
        )
    return parsed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_standard_arg_parser(
        prog="council_split",
        description=(
            "Detect council vote splits and emit wicked.steer.escalated "
            "events recommending council mode for the next gate."
        ),
    )
    parser.add_argument(
        "--gate-findings",
        required=True,
        help=(
            "Voter records as JSON list, e.g. "
            "'[{\"verdict\":\"APPROVE\"},{\"verdict\":\"REJECT\"}]'. "
            "Use @path/to/file.json to read from a file."
        ),
    )
    parser.add_argument(
        "--quorum-threshold",
        type=int,
        default=DEFAULT_QUORUM_THRESHOLD,
        help=(
            f"Vote count needed for a clear verdict (default "
            f"{DEFAULT_QUORUM_THRESHOLD}). Must be >= "
            f"{MIN_VOTERS_FOR_SPLIT}."
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        findings = _parse_findings_arg(args.gate_findings)
        payloads = detect_council_split(
            gate_findings=findings,
            session_id=args.session_id,
            project_slug=args.project_slug,
            quorum_threshold=args.quorum_threshold,
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    for event_record in payloads:
        sys.stdout.write(json.dumps(event_record, separators=(",", ":")) + "\n")
    sys.stdout.flush()

    sys.stderr.write(
        f"detector: {len(payloads)} steering event(s) from "
        f"{len(findings)} finding(s)\n"
    )

    if args.dry_run:
        return 0

    emitted = emit_council_split_events(payloads)
    sys.stderr.write(
        f"emitted: {emitted}/{len(payloads)} event(s) to wicked-bus\n"
    )
    return 0


__all__ = [
    "DETECTOR_NAME",
    "EVENT_TYPE",
    "EVENT_SUBDOMAIN",
    "DEFAULT_QUORUM_THRESHOLD",
    "MIN_VOTERS_FOR_SPLIT",
    "RECOMMENDED_ACTION",
    "detect_council_split",
    "emit_council_split_events",
]


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
