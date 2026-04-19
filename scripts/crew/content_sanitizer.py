"""Content sanitizer (#471) — codepoint allow-list + injection pattern scan.

Two-mode design (challenge-phase mutation CH-03 / design-addendum-2 § CH-03):

  - ``sanitize_strict(s)``      — for machine-generated fields
    (reviewer, verdict, result, recorded_at, phase/gate slugs).
    Allow-list = Basic Latin printable + tab/LF/CR. Anything else
    rejects.

  - ``sanitize_permissive(s)``  — for authored-text fields
    (reason, conditions[i], rubric_breakdown.<dim>.notes, summary).
    Unicode-category-based allow: L*/N*/P*/M*/S*/Zs + tab/LF/CR.
    Denies Cc / Cf (includes bidi-overrides + zero-width),
    Cn / Co / Cs. Legitimate i18n (CJK, Cyrillic, Greek, math,
    currency, em/en dash, curly quotes) continues to load.

Both modes additionally scan for injection-intent substrings
(case-insensitive) after the codepoint check, so a payload that
squeaks past the category check still trips a suspect pattern.

Framing (CH-01): this is a FLOOR against content drift and trivial
prompt-injection — not a wall against a capable attacker.

Stdlib-only. No I/O side effects — caller writes the audit entry.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_THIS_DIR)
for _p in (_SCRIPTS_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gate_result_schema import (  # noqa: E402
    GateResultSchemaError,
    _excerpt,
)


# ---------------------------------------------------------------------------
# Strict-mode allow-list: Basic Latin printable + tab/LF/CR
# ---------------------------------------------------------------------------

_STRICT_ALLOWED = frozenset(range(0x20, 0x7F)) | frozenset({0x09, 0x0A, 0x0D})


# ---------------------------------------------------------------------------
# Permissive-mode allow / deny
# ---------------------------------------------------------------------------

_DENIED_CODEPOINTS_EXPLICIT: frozenset = frozenset({
    # Zero-width family
    0x200B,  # ZWSP
    0x200C,  # ZWNJ
    0x200D,  # ZWJ
    0x200E,  # LRM
    0x200F,  # RLM
    # Bidi isolate / overrides
    0x2028,  # LINE SEPARATOR
    0x2029,  # PARAGRAPH SEPARATOR
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # LRE/RLE/PDF/LRO/RLO
    0x2066, 0x2067, 0x2068, 0x2069,  # LRI/RLI/FSI/PDI
    0xFEFF,  # BOM
})

# Explicit allow of whitespace controls that general Cc category would deny.
_WHITESPACE_CONTROL_ALLOW: frozenset = frozenset({0x09, 0x0A, 0x0D})

# Permissive allow-list Unicode category prefixes. ``unicodedata.category(ch)``
# returns two-letter codes; we allow any whose first letter is in this set.
_PERMISSIVE_ALLOWED_MAJOR = frozenset({"L", "N", "P", "M", "S"})
# Separator-space is the Z-category subset we allow (U+0020 etc.).
_PERMISSIVE_ALLOWED_MINOR = frozenset({"Zs"})


# ---------------------------------------------------------------------------
# Suspect-pattern catalogue (applied after codepoint check on both modes)
# ---------------------------------------------------------------------------

_TEMPLATE_ONLY_RE = re.compile(r"^\s*\$\{[A-Za-z_][A-Za-z0-9_]*\}\s*$")


def _dollar_brace_matcher(value: str) -> bool:
    """Match ``${`` presence with the design §7 Decision-2 carve-out.

    If the *entire field* is one ``${identifier}`` token, allow it;
    otherwise any ``${`` occurrence is suspect. The carve-out reduces
    false-positives on legitimate template-string conditions like
    ``"Fix ${module}.py line 42"`` — but the carve-out requires the
    *whole* field to be the template; embedded ``${`` still matches.
    """
    if "${" not in value:
        return False
    return not bool(_TEMPLATE_ONLY_RE.match(value))


_SUSPECT_PATTERNS: tuple = (
    ("ignore-previous",
     re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE)),
    ("disregard-above",
     re.compile(r"disregard\s+the\s+above", re.IGNORECASE)),
    ("system-prompt-tag",
     re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE)),
    ("system-pipe-tag",
     re.compile(r"<\|\s*system\s*\|>", re.IGNORECASE)),
    ("system-markdown-header",
     re.compile(r"(?m)^\s*#{1,6}\s*SYSTEM\b", re.IGNORECASE)),
    ("system-html-comment",
     re.compile(r"<!--\s*system\s*:", re.IGNORECASE)),
    ("system-prose-prefix",
     re.compile(r"(?m)^\s*system\s*:", re.IGNORECASE)),
    ("human-tag", re.compile(r"<\s*human\s*>", re.IGNORECASE)),
    ("assistant-tag", re.compile(r"<\s*assistant\s*>", re.IGNORECASE)),
    ("code-fence-system",
     re.compile(r"```[^`]{0,64}?system", re.IGNORECASE | re.DOTALL)),
    ("shell-subst-dollar-paren", re.compile(r"\$\(")),
    # NOTE: ``${`` uses the dedicated matcher to honor the carve-out.
    ("shell-backtick-rm", re.compile(r"`[^`]*\brm\s+")),
)


# ---------------------------------------------------------------------------
# Feature-flag (design-addendum-1 D-1)
# ---------------------------------------------------------------------------


def _sanitization_disabled() -> bool:
    """Return True when ``WG_GATE_RESULT_CONTENT_SANITIZATION=off`` is set.

    Emits a stderr WARN on every invocation. Auto-expires at
    ``WG_GATE_RESULT_STRICT_AFTER`` (default 2026-06-18).
    """
    raw = os.environ.get("WG_GATE_RESULT_CONTENT_SANITIZATION", "")
    if raw.strip().lower() != "off":
        return False

    strict_after = os.environ.get("WG_GATE_RESULT_STRICT_AFTER", "2026-06-18")
    try:
        expires = datetime.strptime(strict_after, "%Y-%m-%d").date()
    except ValueError:
        expires = datetime.strptime("2026-06-18", "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    if today >= expires:
        sys.stderr.write(
            "[wicked-garden:gate-result] WG_GATE_RESULT_CONTENT_SANITIZATION=off "
            f"is EXPIRED (strict-after={expires.isoformat()}). Flag ignored; "
            "content sanitization remains ACTIVE.\n"
        )
        return False

    sys.stderr.write(
        "[wicked-garden:gate-result] WARN: content sanitization DISABLED via "
        "WG_GATE_RESULT_CONTENT_SANITIZATION=off. This bypasses #471 "
        f"injection defense; auto-expires {expires.isoformat()}.\n"
    )
    return True


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------


def _raise_nonallowlist(
    *, field: str, offset: int, codepoint: int, mode: str, value: str
) -> None:
    tag_suffix = "strict" if mode == "strict" else "permissive"
    raise GateResultSchemaError(
        f"content-nonallowlist-{tag_suffix}:{field}:{offset}:U+{codepoint:04X}",
        offending_field=field,
        offending_value_excerpt=_excerpt(value),
        violation_class="content",
    )


def _raise_injection(*, field: str, pattern_id: str, value: str) -> None:
    raise GateResultSchemaError(
        f"content-injection:{pattern_id}:{field}",
        offending_field=field,
        offending_value_excerpt=_excerpt(value),
        violation_class="content",
    )


def _scan_suspect_patterns(value: str, *, field: str) -> None:
    """Run the injection-pattern scan. Raises on first hit."""
    for pattern_id, pattern in _SUSPECT_PATTERNS:
        if pattern.search(value):
            _raise_injection(field=field, pattern_id=pattern_id, value=value)
    # Dollar-brace carve-out check — separate because it has custom logic.
    if _dollar_brace_matcher(value):
        _raise_injection(field=field, pattern_id="shell-subst-dollar-brace",
                         value=value)


def sanitize_strict(value: str, *, field: str = "<field>") -> str:
    """Validate ``value`` under the strict allow-list. Returns ``value``
    unchanged on success; raises on violation.

    Scope: machine-generated / structured fields (reviewer, verdict,
    result, recorded_at, phase, gate). Rejects everything outside
    Basic Latin printable + tab/LF/CR.
    """
    if _sanitization_disabled():
        return value
    if not isinstance(value, str):
        return value  # non-string: schema validator already rejected
    for offset, ch in enumerate(value):
        cp = ord(ch)
        if cp not in _STRICT_ALLOWED:
            _raise_nonallowlist(
                field=field, offset=offset, codepoint=cp,
                mode="strict", value=value,
            )
    _scan_suspect_patterns(value, field=field)
    return value


def sanitize_permissive(value: str, *, field: str = "<field>") -> str:
    """Validate ``value`` under the permissive allow-list. Returns
    ``value`` unchanged on success; raises on violation.

    Scope: authored-text fields (reason, conditions[i], notes,
    summary). Unicode-category-based:
      - ALLOW  major categories L/N/P/M/S + Zs + tab/LF/CR.
      - DENY   Cc (except whitespace), Cf (bidi / zero-width),
               Cn (unassigned), Co (private use), Cs (surrogate),
               plus an explicit deny-list for notable codepoints
               (BOM, line/paragraph separators, bidi isolates).
    """
    if _sanitization_disabled():
        return value
    if not isinstance(value, str):
        return value
    for offset, ch in enumerate(value):
        cp = ord(ch)
        if cp in _DENIED_CODEPOINTS_EXPLICIT:
            _raise_nonallowlist(
                field=field, offset=offset, codepoint=cp,
                mode="permissive", value=value,
            )
        if cp in _WHITESPACE_CONTROL_ALLOW:
            continue
        category = unicodedata.category(ch)
        if category[0] in _PERMISSIVE_ALLOWED_MAJOR:
            continue
        if category in _PERMISSIVE_ALLOWED_MINOR:
            continue
        # Anything else (Cc/Cf/Cn/Co/Cs, other Z* variants) — reject.
        _raise_nonallowlist(
            field=field, offset=offset, codepoint=cp,
            mode="permissive", value=value,
        )
    _scan_suspect_patterns(value, field=field)
    return value


# ---------------------------------------------------------------------------
# Recursive walker hooked into validate_gate_result
# ---------------------------------------------------------------------------


_STRICT_FIELDS = ("reviewer", "verdict", "result", "recorded_at",
                  "phase", "gate")
_PERMISSIVE_FIELDS = ("reason", "summary")


def sanitize_gate_result(parsed: Any) -> None:
    """Walk a parsed gate-result dict and apply the appropriate mode to
    every string field in scope (per challenge-phase § CH-03 mapping).

    Raises :class:`GateResultSchemaError` on the first violation.
    """
    if _sanitization_disabled():
        return
    if not isinstance(parsed, dict):
        return  # schema layer already caught it

    for key in _STRICT_FIELDS:
        if key in parsed and isinstance(parsed[key], str):
            sanitize_strict(parsed[key], field=key)

    for key in _PERMISSIVE_FIELDS:
        if key in parsed and isinstance(parsed[key], str):
            sanitize_permissive(parsed[key], field=key)

    # conditions[] — each entry is permissive. dict entries scan
    # description only (matching schema-layer shape).
    conditions = parsed.get("conditions") or []
    if isinstance(conditions, list):
        for idx, entry in enumerate(conditions):
            if isinstance(entry, str):
                sanitize_permissive(entry, field=f"conditions[{idx}]")
            elif isinstance(entry, dict):
                desc = entry.get("description")
                if isinstance(desc, str):
                    sanitize_permissive(
                        desc, field=f"conditions[{idx}].description"
                    )

    # rubric_breakdown.<dim>.notes — permissive.
    rubric = parsed.get("rubric_breakdown") or {}
    if isinstance(rubric, dict):
        for dim, entry in rubric.items():
            if isinstance(entry, dict):
                notes = entry.get("notes")
                if isinstance(notes, str):
                    sanitize_permissive(
                        notes, field=f"rubric_breakdown.{dim}.notes"
                    )

    # per_reviewer_verdicts[].(reviewer|verdict|reason|conditions)
    prvs = parsed.get("per_reviewer_verdicts") or []
    if isinstance(prvs, list):
        for idx, entry in enumerate(prvs):
            if not isinstance(entry, dict):
                continue
            path = f"per_reviewer_verdicts[{idx}]"
            for sk in ("reviewer", "verdict"):
                val = entry.get(sk)
                if isinstance(val, str):
                    sanitize_strict(val, field=f"{path}.{sk}")
            reason_val = entry.get("reason")
            if isinstance(reason_val, str):
                sanitize_permissive(reason_val, field=f"{path}.reason")
            sub_conditions = entry.get("conditions") or []
            if isinstance(sub_conditions, list):
                for sidx, sentry in enumerate(sub_conditions):
                    if isinstance(sentry, str):
                        sanitize_permissive(
                            sentry, field=f"{path}.conditions[{sidx}]"
                        )


__all__ = [
    "sanitize_strict",
    "sanitize_permissive",
    "sanitize_gate_result",
]
