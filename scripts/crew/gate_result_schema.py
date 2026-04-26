"""Gate-result schema validator (#479) — FLOOR against content drift.

This module defines the typed-exception contract and the recursive
schema validator called by ``phase_manager._load_gate_result``. It is
a **floor** against accidental content drift and trivial prompt-injection
in reviewer-authored free-text fields — NOT comprehensive security
against a motivated attacker with local disk write access.

Framing: **integrity + prompt-injection containment**, not "security
hardening" in the absolute sense.

Imports:
  - ``gate_result_constants`` for every byte / count cap (no magic literals)
  - ``_event_schema`` for the authoritative banned-reviewer list

Public API:
  - ``GateResultSchemaError`` — typed exception
  - ``GateResultAuthorizationError`` — subclass, raised by the dispatch-log
    cross-reference (increment 3)
  - ``validate_gate_result(data: dict) -> None`` — raises on violation

The module is stdlib-only and fail-open on env-var opt-out
(``WG_GATE_RESULT_SCHEMA_VALIDATION=off``) per design-addendum-1 § D-1.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Local imports — keep path wiring trivial so this module is hook-import safe.
_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _THIS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from gate_result_constants import (  # noqa: E402
    DEFAULT_STRING_CAP_BYTES,
    MAX_CONDITION_BYTES,
    MAX_CONDITIONS_COUNT,
    MAX_GATE_SLUG_CHARS,
    MAX_PHASE_SLUG_CHARS,
    MAX_REASON_BYTES,
    MAX_REVIEWER_NAME_CHARS,
    MAX_REVIEWER_VERDICTS_COUNT,
    MAX_RUBRIC_DIMS_COUNT,
    MAX_RUBRIC_NOTES_BYTES,
    MAX_SUMMARY_BYTES,
)

# Banned-reviewer authoritative list lives in _event_schema (hook-safe).
# Design-addendum-1 D-2 consolidation is out of scope for this increment;
# we import the current names + augment with the phase_manager superset
# to match the design-addendum-1 target list without yet renaming the
# underlying constant.
from _event_schema import (  # noqa: E402
    BANNED_REVIEWERS as _EVENT_BANNED_REVIEWERS,
    BANNED_SOURCE_AGENT_PREFIXES as _EVENT_BANNED_PREFIXES,
)

# Design-addendum-1 D-2 authoritative union (applied at-load per AC-4).
# Kept local until the cross-module consolidation lands as a follow-up.
BANNED_SOURCE_AGENTS = frozenset(_EVENT_BANNED_REVIEWERS | {
    "auto-approve-design-complete",
})
BANNED_SOURCE_AGENT_PREFIXES = tuple(set(_EVENT_BANNED_PREFIXES) | {
    "auto-approve-",
    "auto-review-",
    "self-review-",
})


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


# Issue #563: authoritative pointer to the schema source of truth. The code
# IS the schema — there is no separate JSON-Schema doc — so point callers at
# the module. Exposed via GateResultSchemaError.schema_doc and str(exc) so
# users don't have to grep to learn where the rules live.
SCHEMA_DOC = "scripts/crew/gate_result_schema.py § validate_gate_result (schema source of truth)"


class GateResultSchemaError(Exception):
    """Raised by ``validate_gate_result`` on any schema or content violation.

    Attributes:
      reason:                  short tag, e.g. ``"invalid-verdict-enum:MAYBE"``
      offending_field:         JSON-pointer-ish path, e.g.
                               ``"rubric_breakdown.user_story.notes"``
      offending_value_excerpt: first 256 bytes of the raw violating value
                               (UTF-8 lossy decoded)
      violation_class:         one of ``{"schema", "content", "authorization"}``
      schema_doc:              pointer to the schema reference (default SCHEMA_DOC)
    """

    def __init__(
        self,
        reason: str,
        *,
        offending_field: Optional[str] = None,
        offending_value_excerpt: Optional[str] = None,
        violation_class: str = "schema",
        schema_doc: Optional[str] = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.offending_field = offending_field
        self.offending_value_excerpt = offending_value_excerpt
        self.violation_class = violation_class
        self.schema_doc = schema_doc or SCHEMA_DOC

    def __str__(self) -> str:
        # Issue #563: str(exc) surfaces the schema pointer so callers that log
        # or re-raise don't need extra wiring to cite the source of truth.
        base = self.reason
        if self.offending_field:
            base = f"{base} (field: {self.offending_field})"
        return f"{base} — See: {self.schema_doc}"


class GateResultAuthorizationError(GateResultSchemaError):
    """Raised by the dispatch-log cross-reference (increment 3).

    Subclassed from ``GateResultSchemaError`` so ``except
    GateResultSchemaError:`` still catches everything, while callers
    that want to distinguish REJECT (schema / content) from
    WARN+ALLOW (orphan during deprecation window) can catch the
    subclass explicitly.
    """

    def __init__(self, reason: str, **kw: Any) -> None:
        kw.setdefault("violation_class", "authorization")
        super().__init__(reason, **kw)


# ---------------------------------------------------------------------------
# Field cap table — every cap sourced from gate_result_constants (no literals)
# ---------------------------------------------------------------------------


FIELD_CAPS: Dict[str, int] = {
    "reason": MAX_REASON_BYTES,
    "summary": MAX_SUMMARY_BYTES,
    "reviewer": MAX_REVIEWER_NAME_CHARS,
    "phase": MAX_PHASE_SLUG_CHARS,
    "gate": MAX_GATE_SLUG_CHARS,
    "conditions[]": MAX_CONDITION_BYTES,
    "per_reviewer_verdicts[].reason": MAX_REASON_BYTES,
    "per_reviewer_verdicts[].reviewer": MAX_REVIEWER_NAME_CHARS,
    "per_reviewer_verdicts[].conditions[]": MAX_CONDITION_BYTES,
    "rubric_breakdown.<dim>.notes": MAX_RUBRIC_NOTES_BYTES,
}


_VALID_VERDICTS = frozenset({"APPROVE", "CONDITIONAL", "REJECT"})
_VALID_RIGOR_TIERS = frozenset({"minimal", "standard", "full"})

# Valid dispatch-mode values for the optional ``mode`` field (#651).
# Backward-compat: absent ``mode`` is accepted (treated as unknown / legacy).
_VALID_DISPATCH_MODES = frozenset({
    "self-check", "sequential", "parallel", "council",
    "human-inline", "fast-evaluator", "advisory",
})


# ---------------------------------------------------------------------------
# Feature flag (design-addendum-1 D-1) — scoped to schema checks only
# ---------------------------------------------------------------------------


def _schema_validation_disabled() -> bool:
    """Return True when ``WG_GATE_RESULT_SCHEMA_VALIDATION=off`` is set.

    Emits a one-line stderr warning on every invocation so operators
    cannot accidentally leave the flag on. Auto-expires at the
    strict-after date (default ``2026-06-18`` — override via
    ``WG_GATE_RESULT_STRICT_AFTER``); after expiry the flag value is
    ignored and a louder warning is emitted.
    """
    raw = os.environ.get("WG_GATE_RESULT_SCHEMA_VALIDATION", "")
    if raw.strip().lower() != "off":
        return False

    # Auto-expiry check (design-addendum-1 D-1 + D-6).
    strict_after = os.environ.get("WG_GATE_RESULT_STRICT_AFTER", "2026-06-18")
    try:
        expires = datetime.strptime(strict_after, "%Y-%m-%d").date()
    except ValueError:
        expires = datetime.strptime("2026-06-18", "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    if today >= expires:
        sys.stderr.write(
            "[wicked-garden:gate-result] WG_GATE_RESULT_SCHEMA_VALIDATION=off "
            f"is EXPIRED (strict-after={expires.isoformat()}). Flag ignored; "
            "schema validation remains ACTIVE. Push "
            "WG_GATE_RESULT_STRICT_AFTER forward if ops rollback is needed.\n"
        )
        return False

    sys.stderr.write(
        "[wicked-garden:gate-result] WARN: schema validation DISABLED via "
        "WG_GATE_RESULT_SCHEMA_VALIDATION=off. This bypasses #479 "
        f"integrity floor; auto-expires {expires.isoformat()}.\n"
    )
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utf8_len(s: str) -> int:
    """Length of ``s`` encoded as UTF-8, in bytes.

    All byte caps (MAX_REASON_BYTES, MAX_CONDITION_BYTES, ...) are
    measured this way so callers and tests match enforcement exactly.
    """
    return len(s.encode("utf-8", errors="strict"))


def _excerpt(value: Any, limit: int = 256) -> str:
    """Return a short (<=limit bytes) string excerpt for audit/error messages.

    Never raises — returns ``<unrenderable>`` on any encoding trouble.
    """
    try:
        text = value if isinstance(value, str) else repr(value)
        encoded = text.encode("utf-8", errors="replace")[:limit]
        return encoded.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover — defensive
        return "<unrenderable>"


# B-2: ``GateResultSchemaError.reason`` is consumed by LLM-facing surfaces
# (gate-ingest-audit.jsonl readers, error-propagation paths). Interpolating
# raw attacker-controlled field values into that string re-introduces the
# exact prompt-injection vector #471 is defending against. Use this helper
# to produce a short, non-reversible tag of the offending value so the
# ``reason`` remains diagnostic without carrying adversarial content.
#
# Shape: ``{violation_class}:{field}:{sha256[:16]}`` (hex). The full value
# can still be inspected via the separately-passed ``offending_value_excerpt``
# (routed through the audit module, where it is ALSO hashed before disk).
def _safe_value_tag(value: Any, *, field: str,
                    violation_class: str = "content") -> str:
    """Non-reversible tag suitable for embedding in a user-visible reason.

    Never raises. Empty / unrenderable values collapse to a zero-hash tag.
    """
    try:
        if isinstance(value, str):
            encoded = value.encode("utf-8", errors="replace")
        else:
            encoded = repr(value).encode("utf-8", errors="replace")
        digest = hashlib.sha256(encoded).hexdigest()[:16]
    except Exception:  # pragma: no cover — defensive
        digest = "0" * 16
    return f"{violation_class}:{field}:{digest}"


def _is_banned_reviewer(name: str) -> bool:
    """Check ``name`` against the authoritative banned-reviewer union.

    Comparison is case-insensitive and prefix-aware, matching
    ``phase_manager._banned_reviewer_error``.
    """
    if not isinstance(name, str) or not name:
        return False
    lowered = name.lower().strip()
    if lowered in {n.lower() for n in BANNED_SOURCE_AGENTS}:
        return True
    return any(lowered.startswith(p.lower()) for p in BANNED_SOURCE_AGENT_PREFIXES)


def _parse_iso8601(value: str) -> bool:
    """Return True if ``value`` is ISO-8601 parseable.

    Python's ``fromisoformat`` is stricter than ISO-8601 proper pre-3.11,
    but it accepts everything the crew loader writes
    (``get_utc_timestamp`` emits ``YYYY-MM-DDTHH:MM:SS[.ffffff][+00:00]``).
    We also accept a trailing ``Z`` suffix for conservative interop.
    """
    if not isinstance(value, str) or not value:
        return False
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Recursive validators
# ---------------------------------------------------------------------------


def _raise_field_oversize(field: str, actual: int, cap: int) -> None:
    raise GateResultSchemaError(
        f"field-oversize:{field}:{actual}>{cap}",
        offending_field=field,
        violation_class="schema",
    )


def _check_string_cap(value: str, *, field: str, cap: int, unit: str = "bytes") -> None:
    """Length check for strings. ``unit`` is ``bytes`` or ``chars`` — the
    cap table pins the unit per field (reviewer is chars; others are bytes).
    """
    if unit == "chars":
        actual = len(value)
    else:
        actual = _utf8_len(value)
    if actual > cap:
        _raise_field_oversize(field, actual, cap)


def _check_reviewer_field(value: Any, *, field: str) -> None:
    """Validate a reviewer-name field: string, within char cap, not banned."""
    if not isinstance(value, str):
        raise GateResultSchemaError(
            f"wrong-type:{field}:expected-str:got-{type(value).__name__}",
            offending_field=field,
            violation_class="schema",
        )
    _check_string_cap(value, field=field, cap=MAX_REVIEWER_NAME_CHARS, unit="chars")
    if _is_banned_reviewer(value):
        # B-2: do not interpolate raw ``value`` into ``reason`` — a banned
        # reviewer identity can still carry prompt-injection text. Use a
        # hash-prefix tag; the excerpt is preserved on the exception for
        # in-process debugging (audit module re-hashes before write).
        raise GateResultSchemaError(
            f"banned-reviewer-at-load:{_safe_value_tag(value, field=field, violation_class='banned-reviewer')}",
            offending_field=field,
            offending_value_excerpt=_excerpt(value),
            violation_class="schema",
        )


def _check_verdict_enum(value: Any, *, field: str) -> None:
    if not isinstance(value, str):
        raise GateResultSchemaError(
            f"wrong-type:{field}:expected-str:got-{type(value).__name__}",
            offending_field=field,
            violation_class="schema",
        )
    if value not in _VALID_VERDICTS:
        # B-2: do not interpolate raw ``value`` — a crafted verdict string
        # can carry prompt-injection text that flows into LLM-readable
        # audit/error surfaces. Hash-prefix tag only.
        raise GateResultSchemaError(
            f"invalid-{field.split('.')[-1]}-enum:"
            f"{_safe_value_tag(value, field=field, violation_class='invalid-enum')}",
            offending_field=field,
            offending_value_excerpt=_excerpt(value),
            violation_class="schema",
        )


def _check_conditions_list(conditions: Any, *, field_prefix: str) -> None:
    if not isinstance(conditions, list):
        raise GateResultSchemaError(
            f"wrong-type:{field_prefix}:expected-list:got-{type(conditions).__name__}",
            offending_field=field_prefix,
            violation_class="schema",
        )
    if len(conditions) > MAX_CONDITIONS_COUNT:
        raise GateResultSchemaError(
            f"list-oversize:{field_prefix}:{len(conditions)}>{MAX_CONDITIONS_COUNT}",
            offending_field=field_prefix,
            violation_class="schema",
        )
    for idx, entry in enumerate(conditions):
        path = f"{field_prefix}[{idx}]"
        if isinstance(entry, str):
            _check_string_cap(entry, field=path, cap=MAX_CONDITION_BYTES)
        elif isinstance(entry, dict):
            desc = entry.get("description", "")
            if desc is not None:
                if not isinstance(desc, str):
                    raise GateResultSchemaError(
                        f"wrong-type:{path}.description:expected-str:"
                        f"got-{type(desc).__name__}",
                        offending_field=f"{path}.description",
                        violation_class="schema",
                    )
                _check_string_cap(
                    desc, field=f"{path}.description", cap=MAX_CONDITION_BYTES
                )
        else:
            raise GateResultSchemaError(
                f"wrong-type:{path}:expected-str-or-dict:"
                f"got-{type(entry).__name__}",
                offending_field=path,
                violation_class="schema",
            )


def _check_rubric_breakdown(rubric: Any) -> None:
    if not isinstance(rubric, dict):
        raise GateResultSchemaError(
            f"wrong-type:rubric_breakdown:expected-dict:got-{type(rubric).__name__}",
            offending_field="rubric_breakdown",
            violation_class="schema",
        )
    if len(rubric) > MAX_RUBRIC_DIMS_COUNT:
        raise GateResultSchemaError(
            f"list-oversize:rubric_breakdown:{len(rubric)}>{MAX_RUBRIC_DIMS_COUNT}",
            offending_field="rubric_breakdown",
            violation_class="schema",
        )
    for dim, entry in rubric.items():
        if not isinstance(entry, dict):
            raise GateResultSchemaError(
                f"wrong-type:rubric_breakdown.{dim}:expected-dict:"
                f"got-{type(entry).__name__}",
                offending_field=f"rubric_breakdown.{dim}",
                violation_class="schema",
            )
        notes = entry.get("notes")
        if notes is None:
            continue
        if not isinstance(notes, str):
            raise GateResultSchemaError(
                f"wrong-type:rubric_breakdown.{dim}.notes:expected-str:"
                f"got-{type(notes).__name__}",
                offending_field=f"rubric_breakdown.{dim}.notes",
                violation_class="schema",
            )
        _check_string_cap(
            notes,
            field=f"rubric_breakdown.{dim}.notes",
            cap=MAX_RUBRIC_NOTES_BYTES,
        )


def _check_per_reviewer_verdicts(verdicts: Any) -> None:
    if not isinstance(verdicts, list):
        raise GateResultSchemaError(
            f"wrong-type:per_reviewer_verdicts:expected-list:"
            f"got-{type(verdicts).__name__}",
            offending_field="per_reviewer_verdicts",
            violation_class="schema",
        )
    if len(verdicts) > MAX_REVIEWER_VERDICTS_COUNT:
        raise GateResultSchemaError(
            f"list-oversize:per_reviewer_verdicts:{len(verdicts)}>"
            f"{MAX_REVIEWER_VERDICTS_COUNT}",
            offending_field="per_reviewer_verdicts",
            violation_class="schema",
        )
    for idx, entry in enumerate(verdicts):
        path = f"per_reviewer_verdicts[{idx}]"
        if not isinstance(entry, dict):
            raise GateResultSchemaError(
                f"wrong-type:{path}:expected-dict:got-{type(entry).__name__}",
                offending_field=path,
                violation_class="schema",
            )
        if "reviewer" in entry:
            _check_reviewer_field(entry["reviewer"], field=f"{path}.reviewer")
        if "verdict" in entry:
            _check_verdict_enum(entry["verdict"], field=f"{path}.verdict")
        if "reason" in entry:
            reason_val = entry["reason"]
            if reason_val is not None:
                if not isinstance(reason_val, str):
                    raise GateResultSchemaError(
                        f"wrong-type:{path}.reason:expected-str:"
                        f"got-{type(reason_val).__name__}",
                        offending_field=f"{path}.reason",
                        violation_class="schema",
                    )
                _check_string_cap(
                    reason_val, field=f"{path}.reason", cap=MAX_REASON_BYTES
                )
        if "conditions" in entry:
            _check_conditions_list(
                entry["conditions"],
                field_prefix=f"{path}.conditions",
            )


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------


def validate_gate_result(data: Any) -> None:
    """Validate a parsed gate-result dict. Raises on any violation.

    Contract (AC-1..AC-4, AC-10 env-var bypass):

    - ``data`` must be a ``dict``. Anything else raises.
    - At least one of ``verdict`` or ``result`` must be present and a
      valid enum member.
    - ``reviewer`` required; string; within char cap; not banned.
    - ``recorded_at`` required; ISO-8601 parseable.
    - Field length caps enforced via ``FIELD_CAPS`` table.
    - ``conditions`` list cap + per-entry byte cap.
    - ``rubric_breakdown`` dict cap + per-``notes`` byte cap.
    - ``per_reviewer_verdicts`` list cap + per-entry reviewer/verdict/reason/conditions.

    When ``WG_GATE_RESULT_SCHEMA_VALIDATION=off`` is set (and not
    auto-expired), this function returns silently and emits a stderr
    warning. The flag is scoped to schema checks only — content
    sanitization and dispatch-log checks are governed by their own
    flags (see design-addendum-1 D-1).
    """
    if _schema_validation_disabled():
        return

    if not isinstance(data, dict):
        raise GateResultSchemaError(
            f"wrong-type:<root>:expected-dict:got-{type(data).__name__}",
            offending_field="<root>",
            violation_class="schema",
        )

    # AC-1: verdict / result enum. At least one must be present.
    has_verdict = "verdict" in data
    has_result = "result" in data
    if not has_verdict and not has_result:
        raise GateResultSchemaError(
            "missing-required-field:verdict-or-result",
            offending_field="verdict",
            violation_class="schema",
        )
    if has_verdict:
        _check_verdict_enum(data["verdict"], field="verdict")
    if has_result:
        _check_verdict_enum(data["result"], field="result")

    # AC-3: required fields beyond verdict/result.
    # ``score`` is required (#650) — a missing score silently became 0.0 in
    # _validate_min_gate_score and triggered a misleading threshold error.
    # Catching it here surfaces a clear schema violation at load time.
    for required in ("reviewer", "recorded_at", "score"):
        if data.get(required) is None:
            raise GateResultSchemaError(
                f"missing-required-field:{required}",
                offending_field=required,
                violation_class="schema",
            )

    # AC-2 + AC-4: top-level reviewer (string, cap, banned).
    _check_reviewer_field(data["reviewer"], field="reviewer")

    # AC-3: recorded_at must be ISO-8601.
    if not _parse_iso8601(data["recorded_at"]):
        raise GateResultSchemaError(
            "invalid-timestamp:recorded_at",
            offending_field="recorded_at",
            offending_value_excerpt=_excerpt(data["recorded_at"]),
            violation_class="schema",
        )

    # Optional scalar-string caps.
    for key, cap in (
        ("reason", MAX_REASON_BYTES),
        ("summary", MAX_SUMMARY_BYTES),
        ("phase", MAX_PHASE_SLUG_CHARS),
        ("gate", MAX_GATE_SLUG_CHARS),
    ):
        if key in data and data[key] is not None:
            value = data[key]
            if not isinstance(value, str):
                raise GateResultSchemaError(
                    f"wrong-type:{key}:expected-str:got-{type(value).__name__}",
                    offending_field=key,
                    violation_class="schema",
                )
            unit = "chars" if key in ("phase", "gate") else "bytes"
            _check_string_cap(value, field=key, cap=cap, unit=unit)

    # Optional enum: rigor_tier.
    if "rigor_tier" in data and data["rigor_tier"] is not None:
        tier = data["rigor_tier"]
        if not isinstance(tier, str) or tier not in _VALID_RIGOR_TIERS:
            # B-2: tier is attacker-controlled — same content-leak concern
            # as verdict / reviewer. Use hash-prefix tag.
            raise GateResultSchemaError(
                f"invalid-rigor_tier-enum:"
                f"{_safe_value_tag(tier, field='rigor_tier', violation_class='invalid-enum')}",
                offending_field="rigor_tier",
                offending_value_excerpt=_excerpt(tier),
                violation_class="schema",
            )

    # Optional numeric ranges.
    for key in ("score", "min_score"):
        if key in data and data[key] is not None:
            raw = data[key]
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise GateResultSchemaError(
                    f"wrong-type:{key}:expected-number:got-{type(raw).__name__}",
                    offending_field=key,
                    violation_class="schema",
                )
            if not (0.0 <= number <= 1.0):
                raise GateResultSchemaError(
                    f"out-of-range:{key}:{number}",
                    offending_field=key,
                    violation_class="schema",
                )

    # Nested structures.
    if "conditions" in data and data["conditions"] is not None:
        _check_conditions_list(data["conditions"], field_prefix="conditions")

    if "rubric_breakdown" in data and data["rubric_breakdown"] is not None:
        _check_rubric_breakdown(data["rubric_breakdown"])

    if "per_reviewer_verdicts" in data and data["per_reviewer_verdicts"] is not None:
        _check_per_reviewer_verdicts(data["per_reviewer_verdicts"])

    # Optional enum: mode (#651 — dispatch-mode field).
    # Absent mode is accepted for backward-compat (pre-#651 gate-results).
    if "mode" in data and data["mode"] is not None:
        mode_val = data["mode"]
        if not isinstance(mode_val, str) or mode_val not in _VALID_DISPATCH_MODES:
            raise GateResultSchemaError(
                f"invalid-mode-enum:"
                f"{_safe_value_tag(mode_val, field='mode', violation_class='invalid-enum')}",
                offending_field="mode",
                offending_value_excerpt=_excerpt(mode_val),
                violation_class="schema",
            )

    # Default-cap fallback for any unknown string field at the top level,
    # preventing a crafted payload in a never-documented key from slipping
    # past an un-capped path (design §1.4).
    known_top_level = {
        "verdict", "result", "reviewer", "recorded_at", "reason", "summary",
        "phase", "gate", "rigor_tier", "score", "min_score", "conditions",
        "rubric_breakdown", "per_reviewer_verdicts",
        # #651 — new fields
        "mode", "dispatch_mode", "context_ref", "mode_fallback_reason",
        "original_mode", "external_review", "recorded_at",
    }
    for key, value in data.items():
        if key in known_top_level:
            continue
        if isinstance(value, str):
            _check_string_cap(value, field=key, cap=DEFAULT_STRING_CAP_BYTES)

    # Increment 2 (#471) — content sanitization pass. Imported lazily
    # to avoid a hard load-time dependency: schema validation still
    # runs when the sanitizer module is disabled / unavailable.
    try:
        from content_sanitizer import sanitize_gate_result
    except ImportError:  # pragma: no cover — defensive
        return
    sanitize_gate_result(data)


# ---------------------------------------------------------------------------
# Increment 3 — AC-11 content-hash cache (design-addendum-2 § CH-02)
# ---------------------------------------------------------------------------


_CACHE_MAX_ENTRIES: int = 512
_VALIDATION_CACHE: Dict[Any, Dict[str, Any]] = {}


def _cache_disabled() -> bool:
    return os.environ.get("WG_GATE_RESULT_CACHE", "").strip().lower() == "off"


def _cache_key(path: str, mtime_ns: int, sha256_hex: str) -> tuple:
    return (path, mtime_ns, sha256_hex)


def _cache_get(key: tuple) -> Optional[Dict[str, Any]]:
    if _cache_disabled():
        return None
    return _VALIDATION_CACHE.get(key)


def _cache_put(key: tuple, value: Dict[str, Any]) -> None:
    if _cache_disabled():
        return
    # Simple bound — when full, drop the oldest insert (insertion order
    # is preserved by Python dicts). This is an LRU-ish bound sufficient
    # for the crew's "one project active at a time" process model.
    if len(_VALIDATION_CACHE) >= _CACHE_MAX_ENTRIES:
        try:
            first_key = next(iter(_VALIDATION_CACHE))
            _VALIDATION_CACHE.pop(first_key, None)
        except StopIteration:  # pragma: no cover — defensive
            pass  # intentional: empty cache means nothing to evict
    _VALIDATION_CACHE[key] = value


def _clear_cache_for_tests() -> None:
    """Test helper — never called from production paths."""
    _VALIDATION_CACHE.clear()


def validate_gate_result_from_file(
    gate_file: Path,
) -> Dict[str, Any]:
    """Parse + validate + sanitize a gate-result.json file, with a
    content-hash memoization cache (AC-11 perf SLO).

    Cache key is ``(abs_path, mtime_ns, sha256_of_bytes)`` — mtime
    alone is not enough (concurrent writes with identical mtime are
    possible); content-hash closes that gap. The cache short-circuits
    the entire validate + sanitize chain; it NEVER bypasses
    validation (that is what ``WG_GATE_RESULT_SCHEMA_VALIDATION=off``
    and the sanitizer flag are for).

    Raises :class:`GateResultSchemaError` on any violation. The cache
    is populated only on successful validation.
    """
    raw_bytes = gate_file.read_bytes()
    stat = gate_file.stat()
    sha_hex = hashlib.sha256(raw_bytes).hexdigest()
    key = _cache_key(str(gate_file.resolve()), stat.st_mtime_ns, sha_hex)

    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        parsed = json.loads(raw_bytes.decode("utf-8", errors="strict"))
    except json.JSONDecodeError as exc:
        raise GateResultSchemaError(
            f"malformed-json:{str(exc)[:40]}",
            offending_field="<root>",
            violation_class="schema",
        ) from exc

    validate_gate_result(parsed)
    _cache_put(key, parsed)
    return parsed


__all__ = [
    "BANNED_SOURCE_AGENTS",
    "BANNED_SOURCE_AGENT_PREFIXES",
    "FIELD_CAPS",
    "GateResultAuthorizationError",
    "GateResultSchemaError",
    "validate_gate_result",
    "validate_gate_result_from_file",
]


# ---------------------------------------------------------------------------
# #500 — DispatchLogTamperError re-export
#
# Defined in ``dispatch_log`` (closer to its detection point), re-exported
# here so callers catching ``GateResultSchemaError`` /
# ``GateResultAuthorizationError`` can reach the matching subclass from the
# schema module surface. Import lazy-guarded so a broken dispatch_log never
# breaks ``validate_gate_result``.
# ---------------------------------------------------------------------------

try:  # pragma: no cover — trivial re-export
    from dispatch_log import DispatchLogTamperError  # noqa: E402,F401
    __all__.append("DispatchLogTamperError")
except ImportError:
    pass  # intentional: dispatch_log optional; tamper-error re-export is best-effort
