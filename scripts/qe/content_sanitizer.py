#!/usr/bin/env python3
"""content_sanitizer.py — Strip prompt-injection patterns from reviewer
free-text fields.

Reviewer-authored content (verdict reasons, finding text, condition
descriptions) is later read by other agents. Injection patterns in
that text — `<system-reminder>`, `[Action Required]`, `IGNORE PREVIOUS
INSTRUCTIONS`, etc. — can hijack downstream agents.

This is a *floor*, not a wall. A motivated attacker writing reviewer
text can defeat any text-level sanitizer. The goal is to catch
accidental drift (e.g. a reviewer pasting the framework's own system
reminder back into their finding text) and obvious clumsy attempts.

Restored in v11 from the deleted v6 ``content_sanitizer.py``. Slimmed,
focused on patterns the v11 archetypes actually emit. No env-var
opt-out, no multi-tier configuration — the rules are the rules.

Stdlib-only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


# Patterns we strip / flag. Each entry: (pattern, replacement, severity).
# severity ∈ {"strip", "flag"}. Strip = silently remove (replaced with
# the replacement). Flag = leave intact but record a warning so the
# caller can surface it.
_PATTERNS: Tuple[Tuple[re.Pattern, str, str], ...] = (
    # Framework-specific prompt-injection vectors
    (re.compile(r"<\s*system-reminder\s*>", re.IGNORECASE),
     "<elided-system-reminder>", "strip"),
    (re.compile(r"</\s*system-reminder\s*>", re.IGNORECASE),
     "</elided-system-reminder>", "strip"),
    (re.compile(r"\[\s*Action Required\s*\]", re.IGNORECASE),
     "[elided-action-required]", "strip"),
    (re.compile(r"<\s*wg\s+archetype", re.IGNORECASE),
     "<elided-wg-archetype", "strip"),
    # Generic prompt-injection turns of phrase
    (re.compile(r"\bIGNORE\s+(PREVIOUS|ABOVE|PRIOR)\s+INSTRUCTIONS\b", re.IGNORECASE),
     "[elided-ignore-instructions]", "strip"),
    (re.compile(r"\bDISREGARD\s+(THE\s+)?(SYSTEM|PRIOR|PREVIOUS)\b", re.IGNORECASE),
     "[elided-disregard]", "strip"),
    (re.compile(r"\bYOU\s+MUST\s+IMMEDIATELY\b", re.IGNORECASE),
     "[elided-you-must-immediately]", "strip"),
    # Tool-call injection
    (re.compile(r"<\s*invoke\s+name\s*=", re.IGNORECASE),
     "<elided-invoke", "strip"),
    (re.compile(r"<\s*function_calls\s*>", re.IGNORECASE),
     "<elided-function-calls>", "strip"),
)


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------

def sanitize_text(text: str) -> Tuple[str, List[str]]:
    """Strip / flag prompt-injection patterns in a free-text field.

    Returns ``(cleaned_text, warnings)``. ``warnings`` is a list of
    one-line strings naming each pattern hit. Caller decides whether
    to display them, log them, or both.
    """
    if not isinstance(text, str) or not text:
        return text, []
    cleaned = text
    warnings: List[str] = []
    for pattern, replacement, severity in _PATTERNS:
        matches = list(pattern.finditer(cleaned))
        if not matches:
            continue
        warnings.append(
            f"sanitizer: pattern '{pattern.pattern}' matched {len(matches)}x "
            f"(severity={severity})"
        )
        if severity == "strip":
            cleaned = pattern.sub(replacement, cleaned)
    return cleaned, warnings


def sanitize_dict(
    data: Dict[str, Any],
    *,
    fields: Iterable[str] = ("reason", "summary", "description",
                              "resolution_note", "verification_evidence"),
) -> Tuple[Dict[str, Any], List[str]]:
    """Sanitise specified free-text fields in a dict in-place.

    Also recurses into ``findings: list[str]`` and ``conditions: list[dict]``
    when present, since those are the canonical reviewer-text containers
    in v11 verdict shapes.

    Returns ``(mutated_dict, all_warnings)``.
    """
    all_warnings: List[str] = []
    out = dict(data)

    for f in fields:
        if isinstance(out.get(f), str):
            cleaned, warns = sanitize_text(out[f])
            out[f] = cleaned
            all_warnings.extend(f"{f}: {w}" for w in warns)

    findings = out.get("findings")
    if isinstance(findings, list):
        new_findings: List[Any] = []
        for i, item in enumerate(findings):
            if isinstance(item, str):
                cleaned, warns = sanitize_text(item)
                new_findings.append(cleaned)
                all_warnings.extend(f"findings[{i}]: {w}" for w in warns)
            else:
                new_findings.append(item)
        out["findings"] = new_findings

    conditions = out.get("conditions")
    if isinstance(conditions, list):
        new_conditions: List[Any] = []
        for i, c in enumerate(conditions):
            if isinstance(c, dict):
                sanitized_c, warns = sanitize_dict(c, fields=fields)
                new_conditions.append(sanitized_c)
                all_warnings.extend(f"conditions[{i}].{w}" for w in warns)
            else:
                new_conditions.append(c)
        out["conditions"] = new_conditions

    return out, all_warnings


__all__ = ["sanitize_text", "sanitize_dict"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json, sys
    parser = argparse.ArgumentParser(description="v11 content sanitizer.")
    parser.add_argument("action", choices=["text", "json"])
    parser.add_argument("--input", default="-",
                        help="File path or '-' for stdin.")
    args = parser.parse_args()

    src = sys.stdin.read() if args.input == "-" \
        else open(args.input, "r", encoding="utf-8").read()

    if args.action == "text":
        cleaned, warns = sanitize_text(src)
        print(json.dumps({"cleaned": cleaned, "warnings": warns}, indent=2))
    else:
        data = json.loads(src)
        cleaned, warns = sanitize_dict(data)
        print(json.dumps({"cleaned": cleaned, "warnings": warns},
                         indent=2, default=str))
