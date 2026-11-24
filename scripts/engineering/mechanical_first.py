#!/usr/bin/env python3
"""mechanical_first.py — the deterministic half of the `wicked-garden-codemod-first` skill.

    mechanical_first.py check <file | ->     # does the text hold one valid mechanical-first decision?
    mechanical_first.py applies "<request>"  # is the request upgrade/modernization-shaped?

``check`` reads the decision shape `skills/codemod-first/refs/decision-block.md` defines (the
contract the wicked-core `mechanical_first` plan step also reads): a fenced block whose first
non-blank line is exactly ``mechanical-first:`` with the six keys ``inventory``, ``count``,
``recipe_checked``, ``codemod``, ``gate`` and ``residue``, or the single line
``mechanical-first: rejected — <reason>`` outside a code block. It prints
``{"ok", "form", "errors", "block"}`` and exits 0 when the text holds exactly one valid decision,
1 when it does not, 2 on a usage error.

``applies`` is the trigger list the skill's description states, as a word match: it prints
``{"applies", "matched"}`` and always exits 0. It is a hint for a seat that is unsure, not a gate.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KEYS = ("inventory", "count", "recipe_checked", "codemod", "gate", "residue")
HEADER = "mechanical-first:"
REJECTION_RE = re.compile(r"^\s*mechanical-first: rejected — (?P<reason>.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
KEY_RE = re.compile(r"^\s*(?P<key>[a-z_]+)\s*:\s?(?P<value>.*?)\s*$")

# The skill's trigger families (its description says the same in words). Each pattern is matched
# case-insensitively against the request as a whole word or phrase.
TRIGGERS: dict[str, str] = {
    "upgrade": r"\bupgrad(?:e|es|ed|ing)\b",
    "bump": r"\bbump(?:s|ed|ing)?\b",
    "version-move": r"\bv?\d+(?:\.\d+)*\s*(?:→|->|to)\s*v?\d+(?:\.\d+)*\b",
    "migrate": r"\bmigrat(?:e|es|ed|ing|ion)\b",
    "deprecated": r"\bdeprecat(?:ed|ion|ions)\b",
    "rename": r"\brenam(?:e|es|ed|ing)\b.*\b(?:everywhere|across|all)\b|\bapi rename\b",
    "replace-library": r"\breplac(?:e|es|ed|ing)\b\s+\S+\s+with\b|\bmove off\b|\bswitch from\b",
    "lint-rollout": r"\b(?:lint|format(?:ting)?|eslint|ruff|clippy)\s+rules?\b|\badopt the new\b",
    "modernize": r"\bmoderni[sz](?:e|es|ed|ing|ation)\b",
    "port": r"\bport(?:s|ed|ing)?\b\s+(?:this|the|our|a|an)?\s*(?:module|app|service|codebase|library)\b",
}


def _decisions(text: str) -> tuple[list[dict], list[str]]:
    """Every decision in ``text``: ``(forms, errors)``. A block that is present but malformed
    is an error, never silently skipped."""
    forms: list[dict] = []
    errors: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        fence = FENCE_RE.match(lines[i])
        if not fence:
            m = REJECTION_RE.match(lines[i])
            if m:
                if m.group("reason"):
                    forms.append({"form": "rejected", "reason": m.group("reason")})
                else:
                    errors.append(f"line {i + 1}: the rejection has no reason")
            i += 1
            continue
        marker = fence.group(1)
        body: list[tuple[int, str]] = []
        j = i + 1
        while j < len(lines) and not lines[j].lstrip().startswith(marker):
            body.append((j + 1, lines[j]))
            j += 1
        i = j + 1
        content = [(n, ln) for n, ln in body if ln.strip()]
        if not content or content[0][1].strip() != HEADER:
            continue                    # some other code block
        forms.append(_block(content, errors))
    return forms, errors


def _block(content: list[tuple[int, str]], errors: list[str]) -> dict:
    start = content[0][0]
    values: dict[str, str] = {}
    for n, line in content[1:]:
        m = KEY_RE.match(line)
        if not m or m.group("key") not in KEYS:
            errors.append(f"line {n}: not one of the keys {', '.join(KEYS)}: {line.strip()[:60]}")
            continue
        key = m.group("key")
        if key in values:
            errors.append(f"line {n}: `{key}` is given twice")
            continue
        values[key] = m.group("value")
    for key in KEYS:
        if key not in values:
            errors.append(f"block at line {start}: `{key}` is missing")
        elif not values[key]:
            errors.append(f"block at line {start}: `{key}` is empty")
    numbers: dict[str, int] = {}
    for key in ("count", "residue"):
        if values.get(key):
            if re.fullmatch(r"\d+", values[key]):
                numbers[key] = int(values[key])
            else:
                errors.append(f"block at line {start}: `{key}` must be a whole number, not {values[key]!r}")
    if len(numbers) == 2 and numbers["residue"] > numbers["count"]:
        errors.append(f"block at line {start}: `residue` ({numbers['residue']}) is more than `count` ({numbers['count']})")
    return {"form": "block", "line": start, **values}


def check(text: str) -> dict:
    forms, errors = _decisions(text)
    if not forms and not errors:
        errors.append("no mechanical-first decision: add the block or the one-line rejection "
                      "(skills/codemod-first/refs/decision-block.md)")
    if len(forms) > 1:
        errors.append(f"{len(forms)} mechanical-first decisions: write exactly one")
    ok = not errors
    return {"ok": ok, "form": forms[0]["form"] if ok else None, "errors": errors,
            "block": forms[0] if ok and forms[0]["form"] == "block" else None}


def applies(request: str) -> dict:
    matched = [name for name, pattern in TRIGGERS.items() if re.search(pattern, request, re.IGNORECASE)]
    return {"applies": bool(matched), "matched": matched}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check", help="check a plan, phase output or PR description for the decision")
    c.add_argument("path", help="the file to read, or - for stdin")
    a = sub.add_parser("applies", help="is this request upgrade/modernization-shaped?")
    a.add_argument("request")
    args = ap.parse_args(argv)
    if args.action == "applies":
        print(json.dumps(applies(args.request)))
        return 0
    try:
        text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(json.dumps({"ok": False, "form": None, "errors": [f"cannot read {args.path}: {exc}"], "block": None}))
        return 2
    report = check(text)
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
