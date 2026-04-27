#!/usr/bin/env python3
"""
crew/steering_event_schema.py — Schema validator for the wicked.steer.* event family.

The steering detector registry (epic) emits two event types on the bus:

  * ``wicked.steer.escalated`` — a detector recommends a rigor change
  * ``wicked.steer.advised``   — a detector observed something but is informational only

Both share the same payload shape. This module is the single source of truth for
that shape so that emitters, the reference tail subscriber, and any future
behavior subscriber (e.g. ``crew:rigor-escalator``) all agree on what valid
looks like.

Pure stdlib. Importable from any other crew script.

Usage::

    from crew.steering_event_schema import (
        KNOWN_DETECTORS,
        KNOWN_EVENT_TYPES,
        KNOWN_ACTIONS,
        validate_payload,
    )

    errors = validate_payload("wicked.steer.escalated", payload_dict)
    if errors:
        # reject — see errors list for details
        ...

PR-1 of the steering detector epic ships ONLY the event family wiring. No
detectors, no behavior subscribers — see ``docs/steering-detectors.md``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Allowlists — locked at PR-1, intentionally narrow.
# ---------------------------------------------------------------------------

#: Event types in the wicked.steer.* family. Locked by ``wicked-bus:naming``.
KNOWN_EVENT_TYPES: frozenset = frozenset({
    "wicked.steer.escalated",
    "wicked.steer.advised",
})

#: Detectors planned for v1 of the registry. New detectors require a PR that
#: adds the name here AND ships the detector implementation.
KNOWN_DETECTORS: frozenset = frozenset({
    "sensitive-path",
    "blast-radius",
    "council-split",
    "test-failure-spike",
    "cross-domain-edits",
})

#: Recommended actions a detector may suggest. This set is loose — unknown
#: values produce a warning string, not a hard error, so we don't have to gate
#: action vocabulary growth on a schema bump.
KNOWN_ACTIONS: frozenset = frozenset({
    "force-full-rigor",
    "regen-test-strategy",
    "require-council-review",
    "notify-only",
})

#: Required top-level payload keys.
_REQUIRED_FIELDS: tuple = (
    "detector",
    "signal",
    "threshold",
    "recommended_action",
    "evidence",
    "session_id",
    "project_slug",
    "timestamp",
)

# ISO8601 — accept the common subset:
#   - 2026-04-27T10:00:00Z
#   - 2026-04-27T10:00:00+00:00
#   - 2026-04-27T10:00:00.123456+00:00
# Intentionally strict-ish: we don't accept space separator or naive timestamps.
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def validate_payload(event_type: str, payload: Dict[str, Any]) -> List[str]:
    """Validate a steering event payload.

    Returns a list of error strings. Empty list = valid.

    Unknown ``recommended_action`` values are reported as warning strings
    (prefix ``warning:``) rather than hard errors — actions are loose by
    design (see ``KNOWN_ACTIONS`` docstring). Callers that want to treat
    warnings as errors can do so explicitly.

    Args:
        event_type: Bus event_type (e.g. ``wicked.steer.escalated``).
        payload: The payload dict.

    Returns:
        List of error/warning strings. Empty if fully valid.
    """
    errors: List[str] = []

    # event_type validation is independent of payload shape.
    if event_type not in KNOWN_EVENT_TYPES:
        errors.append(
            f"unknown event_type: {event_type!r} "
            f"(known: {sorted(KNOWN_EVENT_TYPES)})"
        )

    if not isinstance(payload, dict):
        errors.append(f"payload must be a dict, got {type(payload).__name__}")
        return errors  # nothing more we can validate

    # Required field presence.
    for field in _REQUIRED_FIELDS:
        if field not in payload:
            errors.append(f"missing required field: {field!r}")

    # Type checks for present fields.
    if "detector" in payload:
        detector = payload["detector"]
        if not isinstance(detector, str):
            errors.append(f"detector must be a string, got {type(detector).__name__}")
        elif detector not in KNOWN_DETECTORS:
            errors.append(
                f"unknown detector: {detector!r} "
                f"(known: {sorted(KNOWN_DETECTORS)})"
            )

    if "signal" in payload and not isinstance(payload["signal"], str):
        errors.append(
            f"signal must be a string, got {type(payload['signal']).__name__}"
        )

    if "threshold" in payload and not isinstance(payload["threshold"], dict):
        errors.append(
            f"threshold must be a dict, got {type(payload['threshold']).__name__}"
        )

    if "recommended_action" in payload:
        action = payload["recommended_action"]
        if not isinstance(action, str):
            errors.append(
                f"recommended_action must be a string, got {type(action).__name__}"
            )
        elif action not in KNOWN_ACTIONS:
            # WARNING, not error — actions are loose by design.
            errors.append(
                f"warning: unknown recommended_action: {action!r} "
                f"(known: {sorted(KNOWN_ACTIONS)}; loose set, will not block)"
            )

    if "evidence" in payload:
        evidence = payload["evidence"]
        if not isinstance(evidence, dict):
            errors.append(
                f"evidence must be a dict, got {type(evidence).__name__}"
            )
        elif not evidence:
            errors.append("evidence must contain at least one key")

    if "session_id" in payload:
        sid = payload["session_id"]
        if not isinstance(sid, str) or not sid.strip():
            errors.append("session_id must be a non-empty string")

    if "project_slug" in payload:
        slug = payload["project_slug"]
        if not isinstance(slug, str) or not slug.strip():
            errors.append("project_slug must be a non-empty string")

    if "timestamp" in payload:
        ts = payload["timestamp"]
        if not isinstance(ts, str):
            errors.append(
                f"timestamp must be a string, got {type(ts).__name__}"
            )
        elif not _ISO8601_RE.match(ts):
            errors.append(
                f"timestamp must be ISO8601 (e.g. 2026-04-27T10:00:00Z), got {ts!r}"
            )

    return errors


__all__ = [
    "KNOWN_DETECTORS",
    "KNOWN_EVENT_TYPES",
    "KNOWN_ACTIONS",
    "validate_payload",
]
