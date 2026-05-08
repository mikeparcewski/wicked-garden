#!/usr/bin/env python3
"""verdict_schema.py — Validate review-archetype verdict artifacts.

The v11 ``review`` archetype produces a verdict artifact:
APPROVE / CONDITIONAL / REJECT plus a remediation list. Reviewers
write it as JSON. This module validates the shape so downstream
consumers (build archetype hand-off, audit log replay, dashboards)
can trust the structure.

This is NOT a runtime gate. The review archetype's playbook decides
when to validate. Typical use:

    from verdict_schema import validate_verdict, VerdictSchemaError

    try:
        validate_verdict(parsed_dict)
    except VerdictSchemaError as exc:
        # Surface to the reviewer; they fix and re-emit.
        ...

Restored in v11 from the deleted v6 ``gate_result_schema.py``, slimmed
down (~700 LOC → ~250 LOC) with the v6 pipeline-specific cruft removed:
no rigor-tier × gate matrix, no gate-policy.json hooks, no env-var
opt-out, no banned-prefix consolidation. The validator answers one
question: *is this a structurally valid review verdict?*

Stdlib-only.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Caps + enums
# ---------------------------------------------------------------------------

VALID_VERDICTS = frozenset({"APPROVE", "CONDITIONAL", "REJECT"})

MAX_REVIEWER_NAME_CHARS = 200
MAX_REASON_BYTES = 4_000
MAX_FINDING_BYTES = 2_000
MAX_FINDINGS_COUNT = 100
MAX_CONDITIONS_COUNT = 50
MAX_CONDITION_BYTES = 2_000
MAX_SUMMARY_BYTES = 4_000

# Names that may NEVER appear as the reviewer field. Banned-reviewer
# enforcement migrated to v11 as a per-archetype check rather than a
# global gate; the review archetype's playbook is the canonical
# enforcement surface.
BANNED_REVIEWER_NAMES = frozenset({
    "auto-approve", "auto-approved", "fast-pass",
    "just-finish-auto", "yolo", "auto",
})
BANNED_REVIEWER_PREFIXES = ("auto-approve-", "fast-pass-", "yolo-")

_FIELD_ALIASES: Dict[str, str] = {
    # Issue #850 aliases preserved — older reviewer tooling emits
    # ``timestamp`` and ``decision``; both alias to the canonical
    # names. Coercion emits a one-line stderr deprecation.
    "timestamp": "recorded_at",
    "decision": "verdict",
}


class VerdictSchemaError(ValueError):
    """Raised when a verdict artifact fails validation."""

    def __init__(
        self,
        reason: str,
        *,
        offending_field: Optional[str] = None,
        offending_value_excerpt: Optional[str] = None,
    ):
        super().__init__(reason)
        self.reason = reason
        self.offending_field = offending_field
        self.offending_value_excerpt = offending_value_excerpt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$"
)


def _is_iso8601(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if not _ISO8601_RE.match(value):
        return False
    try:
        # Python 3.11+ accepts the trailing Z directly; older versions need
        # a substitution. Both supported here.
        normalized = value.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def _excerpt(value: Any, max_chars: int = 64) -> str:
    s = str(value)
    return s[:max_chars] + ("..." if len(s) > max_chars else "")


def _coerce_aliases(data: Dict[str, Any]) -> None:
    """Mutate data: copy alias -> canonical when canonical is absent.
    Stderr deprecation per coercion."""
    import sys
    for alias, canonical in _FIELD_ALIASES.items():
        if alias in data and canonical not in data:
            data[canonical] = data[alias]
            print(
                f"[verdict-schema] DEPRECATED: '{alias}' is an alias for "
                f"'{canonical}' — please update reviewer output.",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_verdict(data: Any) -> None:
    """Validate a parsed verdict dict. Raises VerdictSchemaError on any
    structural violation.

    Required fields:
      - verdict (or its alias 'decision'): one of APPROVE/CONDITIONAL/REJECT.
      - reviewer: non-empty string within char cap, not in banned list.
      - recorded_at (or its alias 'timestamp'): ISO-8601 timestamp.
      - score: numeric in [0.0, 1.0].

    Soft caps:
      - reason / summary / findings / conditions byte caps.
      - findings list ≤ MAX_FINDINGS_COUNT, conditions ≤ MAX_CONDITIONS_COUNT.

    Invariants (logical):
      - APPROVE  -> empty conditions list AND score >= 0.70.
      - CONDITIONAL -> non-empty conditions list.
      - REJECT -> non-empty findings list.
    """
    if not isinstance(data, dict):
        raise VerdictSchemaError(
            f"wrong-type:<root>:expected-dict:got-{type(data).__name__}",
            offending_field="<root>",
        )

    _coerce_aliases(data)

    # Required scalar fields
    for required in ("verdict", "reviewer", "recorded_at", "score"):
        if data.get(required) in (None, ""):
            raise VerdictSchemaError(
                f"missing-required-field:{required}",
                offending_field=required,
            )

    # verdict enum
    verdict = data["verdict"]
    if verdict not in VALID_VERDICTS:
        raise VerdictSchemaError(
            f"invalid-verdict-enum:{_excerpt(verdict)}",
            offending_field="verdict",
            offending_value_excerpt=_excerpt(verdict),
        )

    # reviewer
    reviewer = data["reviewer"]
    if not isinstance(reviewer, str):
        raise VerdictSchemaError(
            f"wrong-type:reviewer:expected-str:got-{type(reviewer).__name__}",
            offending_field="reviewer",
        )
    if len(reviewer) > MAX_REVIEWER_NAME_CHARS:
        raise VerdictSchemaError(
            f"field-oversize:reviewer:{len(reviewer)}>{MAX_REVIEWER_NAME_CHARS}",
            offending_field="reviewer",
        )
    reviewer_lower = reviewer.lower().strip()
    if reviewer_lower in BANNED_REVIEWER_NAMES:
        raise VerdictSchemaError(
            f"banned-reviewer:{reviewer}",
            offending_field="reviewer",
            offending_value_excerpt=_excerpt(reviewer),
        )
    for prefix in BANNED_REVIEWER_PREFIXES:
        if reviewer_lower.startswith(prefix):
            raise VerdictSchemaError(
                f"banned-reviewer-prefix:{reviewer}",
                offending_field="reviewer",
                offending_value_excerpt=_excerpt(reviewer),
            )

    # recorded_at
    if not _is_iso8601(data["recorded_at"]):
        raise VerdictSchemaError(
            "invalid-timestamp:recorded_at",
            offending_field="recorded_at",
            offending_value_excerpt=_excerpt(data["recorded_at"]),
        )

    # score
    score = data["score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise VerdictSchemaError(
            f"wrong-type:score:expected-number:got-{type(score).__name__}",
            offending_field="score",
        )
    if not 0.0 <= float(score) <= 1.0:
        raise VerdictSchemaError(
            f"score-out-of-range:{score}",
            offending_field="score",
            offending_value_excerpt=_excerpt(score),
        )

    # Soft caps
    for key, cap in (("reason", MAX_REASON_BYTES),
                     ("summary", MAX_SUMMARY_BYTES)):
        if key in data and isinstance(data[key], str):
            if len(data[key].encode("utf-8")) > cap:
                raise VerdictSchemaError(
                    f"field-oversize:{key}:>{cap}",
                    offending_field=key,
                )

    # findings list
    findings = data.get("findings") or []
    if not isinstance(findings, list):
        raise VerdictSchemaError(
            f"wrong-type:findings:expected-list:got-{type(findings).__name__}",
            offending_field="findings",
        )
    if len(findings) > MAX_FINDINGS_COUNT:
        raise VerdictSchemaError(
            f"too-many-findings:{len(findings)}>{MAX_FINDINGS_COUNT}",
            offending_field="findings",
        )
    for i, f in enumerate(findings):
        if isinstance(f, str) and len(f.encode("utf-8")) > MAX_FINDING_BYTES:
            raise VerdictSchemaError(
                f"field-oversize:findings[{i}]:>{MAX_FINDING_BYTES}",
                offending_field=f"findings[{i}]",
            )

    # conditions list
    conditions = data.get("conditions") or []
    if not isinstance(conditions, list):
        raise VerdictSchemaError(
            f"wrong-type:conditions:expected-list:got-{type(conditions).__name__}",
            offending_field="conditions",
        )
    if len(conditions) > MAX_CONDITIONS_COUNT:
        raise VerdictSchemaError(
            f"too-many-conditions:{len(conditions)}>{MAX_CONDITIONS_COUNT}",
            offending_field="conditions",
        )

    # Logical invariants
    if verdict == "APPROVE":
        if conditions:
            raise VerdictSchemaError(
                "invariant-violation:APPROVE-with-conditions",
                offending_field="conditions",
            )
        if float(score) < 0.70:
            raise VerdictSchemaError(
                f"invariant-violation:APPROVE-with-low-score:{score}<0.70",
                offending_field="score",
            )
    elif verdict == "CONDITIONAL":
        if not conditions:
            raise VerdictSchemaError(
                "invariant-violation:CONDITIONAL-without-conditions",
                offending_field="conditions",
            )
    elif verdict == "REJECT":
        if not findings:
            raise VerdictSchemaError(
                "invariant-violation:REJECT-without-findings",
                offending_field="findings",
            )


def validate_verdict_file(path) -> Dict[str, Any]:
    """Read + validate a verdict JSON file. Raises VerdictSchemaError."""
    from pathlib import Path
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerdictSchemaError(
            f"malformed-json:{str(exc)[:60]}",
            offending_field="<root>",
        ) from exc
    validate_verdict(data)
    return data


__all__ = [
    "VerdictSchemaError",
    "VALID_VERDICTS",
    "BANNED_REVIEWER_NAMES",
    "BANNED_REVIEWER_PREFIXES",
    "validate_verdict",
    "validate_verdict_file",
]


if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="Validate a v11 verdict JSON file.")
    parser.add_argument("path", help="Path to verdict JSON.")
    args = parser.parse_args()
    try:
        validate_verdict_file(args.path)
        print(json.dumps({"ok": True, "path": args.path}))
    except VerdictSchemaError as exc:
        print(json.dumps({
            "ok": False, "reason": exc.reason,
            "field": exc.offending_field,
            "excerpt": exc.offending_value_excerpt,
        }), file=sys.stderr)
        sys.exit(1)
