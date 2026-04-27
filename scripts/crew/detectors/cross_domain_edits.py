#!/usr/bin/env python3
"""
crew/detectors/cross_domain_edits.py — Cross-domain edits ADVISORY detector.

PR-4 of the steering detector epic (#679). Per the brainstorm decision
this detector is **advisory, NOT escalating** — it emits
``wicked.steer.advised`` (NOT ``wicked.steer.escalated``). The audit log
and tail subscriber will see the event, but the rigor-escalator does NOT
mutate rigor on ``advised`` events.

Recommended action: ``notify-only``.

Subdomain: ``crew.detector.cross-domain-edits``.

Threshold (per epic brainstorm — escalated to 4 from the original 3):

  * Distinct domain count ``>= MIN_DISTINCT_DOMAINS=4`` fires the event.
  * Domains are inferred from the second path segment under ``scripts/``,
    ``agents/``, ``skills/``, ``commands/``, or ``tests/``. Other top-level
    paths are ignored (e.g. ``README.md``, ``CHANGELOG.md``).

So::

    scripts/crew/x.py       → domain "crew"
    scripts/jam/y.py        → domain "jam"
    agents/qe/reviewer.md   → domain "qe"
    tests/crew/test_foo.py  → domain "crew" (same as scripts/crew/*)
    README.md               → ignored (no recognized parent)

Design constraints (mirror PR-2 ``sensitive_path.py``):

  * Pure stdlib.
  * Detector and emitter are separate.
  * Every emitted payload is re-validated against the schema as
    ``wicked.steer.advised``.
  * Fail-open if bus unreachable.

Usage (programmatic)::

    from crew.detectors.cross_domain_edits import (
        detect_cross_domain_edits,
        emit_cross_domain_edits_events,
    )

    payloads = detect_cross_domain_edits(
        changed_paths=[
            "scripts/crew/a.py",
            "scripts/jam/b.py",
            "agents/qe/c.md",
            "tests/platform/d.py",
        ],
        session_id="sess-001",
        project_slug="demo",
    )
    # -> [{"detector": "cross-domain-edits", ...}]  (one event, advisory)

Usage (CLI)::

    python3 scripts/crew/detectors/cross_domain_edits.py \\
        --paths scripts/crew/a.py scripts/jam/b.py agents/qe/c.md tests/platform/d.py \\
        --session-id sess-001 --project-slug demo --dry-run
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

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

DETECTOR_NAME = "cross-domain-edits"

#: ADVISORY — not escalating. The brainstorm explicitly demoted this from
#: escalating because cross-domain edits are common in refactors and the
#: signal isn't strong enough to mutate rigor by itself.
EVENT_TYPE = "wicked.steer.advised"
EVENT_SUBDOMAIN = f"crew.detector.{DETECTOR_NAME}"

assert DETECTOR_NAME in KNOWN_DETECTORS, (
    f"detector {DETECTOR_NAME!r} not in KNOWN_DETECTORS — "
    "schema (steering_event_schema.py) and detector are out of sync"
)

#: Distinct-domain threshold. Brainstorm escalated this from the original
#: 3 to 4 — refactors commonly touch 3 domains and the noise wasn't worth
#: the signal.
MIN_DISTINCT_DOMAINS: int = 4

#: Top-level path roots whose second segment counts as the "domain".
#: Anything outside this set is ignored by the domain extractor.
DOMAIN_ROOTS: frozenset = frozenset({
    "scripts",
    "agents",
    "skills",
    "commands",
    "tests",
})

RECOMMENDED_ACTION = "notify-only"


# ---------------------------------------------------------------------------
# Public API — detector
# ---------------------------------------------------------------------------

def _normalize_path(path: str) -> str:
    """Forward slashes, no leading ``./`` — matches sensitive_path conventions."""
    p = path.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def _extract_domain(path: str) -> Optional[str]:
    """Return the domain (second path segment) for ``path``, or ``None``.

    A path is considered domain-attributable if its first segment is in
    ``DOMAIN_ROOTS`` AND it has at least two segments.
    """
    p = _normalize_path(path)
    if not p:
        return None
    parts = p.split("/")
    if len(parts) < 2:
        return None
    if parts[0] not in DOMAIN_ROOTS:
        return None
    domain = parts[1].strip()
    if not domain:
        return None
    return domain


def detect_cross_domain_edits(
    changed_paths: Iterable[str],
    *,
    session_id: str,
    project_slug: str,
    min_distinct_domains: int = MIN_DISTINCT_DOMAINS,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Return zero or one validated ``wicked.steer.advised`` payload.

    Args:
        changed_paths: File paths edited in the current task. Empty/blank
            entries are skipped. Paths whose top-level segment is not in
            ``DOMAIN_ROOTS`` (e.g. ``README.md``) are ignored.
        session_id: Session id (required by schema).
        project_slug: Crew project slug (required by schema).
        min_distinct_domains: Threshold for how many distinct domains must
            be touched before firing. Defaults to ``MIN_DISTINCT_DOMAINS=4``.
            Must be ``>= 1``.
        now: Override for the timestamp source — only used by tests.

    Returns:
        A list with at most one payload. The payload is an
        ``advised`` event (severity intentionally below ``escalated``).

    Raises:
        ValueError: bad ``min_distinct_domains``, or empty
            ``session_id`` / ``project_slug``.
    """
    require_non_empty_string(session_id, "session_id")
    require_non_empty_string(project_slug, "project_slug")
    if (
        not isinstance(min_distinct_domains, int)
        or isinstance(min_distinct_domains, bool)
        or min_distinct_domains < 1
    ):
        raise ValueError(
            f"min_distinct_domains must be int >= 1, got {min_distinct_domains!r}"
        )

    distinct_domains: Set[str] = set()
    contributing_paths: List[str] = []
    for raw_path in changed_paths:
        if not raw_path or not str(raw_path).strip():
            continue
        domain = _extract_domain(str(raw_path))
        if domain is None:
            continue
        distinct_domains.add(domain)
        contributing_paths.append(_normalize_path(str(raw_path)))

    if len(distinct_domains) < min_distinct_domains:
        return []

    timestamp = utc_iso8601(now)
    payload = {
        "detector": DETECTOR_NAME,
        "signal": (
            f"task touches {len(distinct_domains)} distinct domains "
            f"(threshold >= {min_distinct_domains})"
        ),
        "threshold": {
            "min_distinct_domains": min_distinct_domains,
            "observed_distinct_domains": len(distinct_domains),
        },
        "recommended_action": RECOMMENDED_ACTION,
        "evidence": {
            "distinct_domains": sorted(distinct_domains),
            "contributing_paths": contributing_paths,
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
            f"cross-domain-edits detector built an invalid payload: {errors}"
        )
    return [payload]


# ---------------------------------------------------------------------------
# Public API — emitter
# ---------------------------------------------------------------------------

def emit_cross_domain_edits_events(payloads: Sequence[dict]) -> int:
    """Emit each payload to wicked-bus as ``wicked.steer.advised`` (advisory)."""
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
        prog="cross_domain_edits",
        description=(
            "Detect cross-domain edits (>= N distinct domains touched in "
            "one task) and emit wicked.steer.advised events. ADVISORY — "
            "does not mutate rigor."
        ),
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Explicit list of changed file paths.",
    )
    parser.add_argument(
        "--min-distinct-domains",
        type=int,
        default=MIN_DISTINCT_DOMAINS,
        help=(
            f"Distinct-domain threshold (default {MIN_DISTINCT_DOMAINS}, "
            "per epic brainstorm)."
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        payloads = detect_cross_domain_edits(
            args.paths,
            session_id=args.session_id,
            project_slug=args.project_slug,
            min_distinct_domains=args.min_distinct_domains,
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    for event_record in payloads:
        sys.stdout.write(json.dumps(event_record, separators=(",", ":")) + "\n")
    sys.stdout.flush()

    sys.stderr.write(
        f"detector: {len(payloads)} advisory event(s) from "
        f"{len(args.paths)} path(s)\n"
    )

    if args.dry_run:
        return 0

    emitted = emit_cross_domain_edits_events(payloads)
    sys.stderr.write(
        f"emitted: {emitted}/{len(payloads)} advisory event(s) to wicked-bus\n"
    )
    return 0


__all__ = [
    "DETECTOR_NAME",
    "EVENT_TYPE",
    "EVENT_SUBDOMAIN",
    "MIN_DISTINCT_DOMAINS",
    "DOMAIN_ROOTS",
    "RECOMMENDED_ACTION",
    "detect_cross_domain_edits",
    "emit_cross_domain_edits_events",
]


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
