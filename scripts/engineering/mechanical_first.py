#!/usr/bin/env python3
"""mechanical_first.py — the deterministic half of the `wicked-garden-codemod-first` skill.

    mechanical_first.py check <file | ->     # does the text hold one valid mechanical-first decision?
    mechanical_first.py applies "<request>"  # is the request upgrade/modernization-shaped?

``check`` reads the decision shape `skills/codemod-first/refs/decision-block.md` defines (the
contract the wicked-core `mechanical_first` plan step also reads): a fenced block whose first
non-blank line is exactly ``mechanical-first:`` with the six keys ``inventory``, ``count``,
``recipe_checked``, ``codemod``, ``gate`` and ``residue``, or the single line
``mechanical-first: rejected — <reason>`` outside a code block (fenced or indented). A
near-miss declaration (a rejection with the wrong dash, a block header with text after it) is an
error even beside a valid decision, never silently skipped. It prints
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
# Markdown positions (CommonMark): a fence opens with 0-3 spaces of indent and closes only on a
# bare run of the same character at least as long; 4 spaces or a tab outside a fence is indented
# code. A decision quoted as code in either form is not a decision.
REJECTION_RE = re.compile(r"^ {0,3}mechanical-first: rejected — (?P<reason>.*?)\s*$")
REJECTION_ATTEMPT_RE = re.compile(r"^ {0,3}mechanical-first\s*:\s*rejected\b", re.IGNORECASE)
OPEN_RE = re.compile(r"^ {0,3}(?P<run>`{3,}|~{3,})(?P<info>.*)$")
INDENTED_RE = re.compile(r"^(?: {4}|\t)")
MAX_DIGITS = 9
KEY_RE = re.compile(r"^\s*(?P<key>[a-z_]+)\s*:\s?(?P<value>.*?)\s*$")

# The skill's trigger families (its description says the same in words). Each pattern is matched
# case-insensitively against the request as a whole word or phrase.
TRIGGERS: dict[str, str] = {
    "upgrade": r"\bupgrad(?:e|es|ed|ing)\b",
    "bump": r"\bbump(?:s|ed|ing)?\b(?!\s+into\b)",
    # a version move needs a version shape: v1 to v2, version 2 to 3, 2.1 to 3.0, or an arrow
    "version-move": (r"\bv\d+(?:\.\d+)*\s*(?:→|->|to)\s*v?\d+|\bversion\s+\d+(?:\.\d+)*\s*(?:→|->|to)\s*v?\d+"
                     r"|\b\d+\.\d+(?:\.\d+)*\s*(?:→|->|to)\s*v?\d+|\b\d+(?:\.\d+)*\s*(?:→|->)\s*v?\d+"),
    "migrate": r"\bmigrat(?:e|es|ed|ing|ion)\b",
    "deprecated": r"\bdeprecat(?:ed|ion|ions)\b",
    "rename": (r"\brenam(?:e|es|ed|ing)\b.*\b(?:everywhere|across|all)\b|\bapi rename\b"
               r"|\brenam(?:e|es|ed|ing)\b(?:\s+\S+){0,4}?\s+(?:api|function|method|class|module|package|symbol|endpoint)s?\b"),
    # a library by name (not "this", "the" or an operator) or by the word library/package/...
    "replace-library": (r"\breplac(?:e|es|ed|ing)\s+(?!(?:this|that|these|those|it|the|a|an)\b)[a-z][\w.@/-]*\s+with\b"
                        r"|\breplac(?:e|es|ed|ing)\b(?:\s+\S+){0,3}?\s+(?:library|package|dependency|framework|sdk|client)\s+with\b"
                        r"|\bmove off\b|\bswitch from\b"),
    "lint-rollout": (r"\b(?:lint|format(?:ting)?|eslint|ruff|clippy)\s+rules?\b"
                     r"|\b(?:roll(?:s|ed|ing)?\s+out|adopt(?:s|ed|ing)?|enabl(?:e|es|ed|ing))\b.{0,40}?"
                     r"\b(?:lint(?:er|ing)?|eslint|ruff|clippy|prettier|black|formatter|biome)\b"),
    "modernize": r"\bmoderni[sz](?:e|es|ed|ing|ation)\b",
    "port": r"\bport(?:s|ed|ing)?\b\s+(?:this|the|our|a|an)?\s*(?:module|app|service|codebase|library)\b",
    # "more than about 10 similar sites": a two-digit-or-more count of sites, or dozens/hundreds
    "repeated-sites": (r"\b(?:\d{2,}|dozens of|hundreds of)\s+(?:similar|identical|matching|repeated)?\s*"
                       r"(?:sites|call\s?sites|places|occurrences|usages|files)\b"),
}


def _decisions(text: str) -> tuple[list[dict], list[str]]:
    """Every decision in ``text``: ``(forms, errors)``. A block that is present but malformed
    is an error, never silently skipped."""
    forms: list[dict] = []
    errors: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = None if INDENTED_RE.match(line) else OPEN_RE.match(line)
        if fence and fence.group("run")[0] == "`" and "`" in fence.group("info"):
            fence = None                # a backtick info string may not hold a backtick
        if fence is None:
            m = None if INDENTED_RE.match(line) else REJECTION_RE.match(line)
            if m:
                if m.group("reason"):
                    forms.append({"form": "rejected", "reason": m.group("reason")})
                else:
                    errors.append(f"line {i + 1}: the rejection has no reason")
            elif not INDENTED_RE.match(line) and REJECTION_ATTEMPT_RE.match(line):
                errors.append(f"line {i + 1}: a rejection reads exactly `mechanical-first: rejected — <reason>` "
                              f"(an em dash, —), not {line.strip()[:60]!r}")
            i += 1
            continue
        run = fence.group("run")
        closer = re.compile(rf"^ {{0,3}}{re.escape(run[0])}{{{len(run)},}}\s*$")
        body: list[tuple[int, str]] = []
        j = i + 1
        while j < len(lines) and not closer.match(lines[j]):
            body.append((j + 1, lines[j]))
            j += 1
        i = j + 1
        content = [(n, ln) for n, ln in body if ln.strip()]
        first = content[0][1].strip() if content else ""
        if first == HEADER:
            forms.append(_block(content, errors))
        elif first.startswith(HEADER) and not first[len(HEADER):].strip().lower().startswith("rejected"):
            errors.append(f"line {content[0][0]}: a decision block starts with exactly `mechanical-first:` "
                          f"on its own line, not {first[:60]!r}")
        # else: some other code block, or a rejection quoted as code
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
            if re.fullmatch(rf"\d{{1,{MAX_DIGITS}}}", values[key]):
                numbers[key] = int(values[key])
            elif re.fullmatch(r"\d+", values[key]):
                errors.append(f"block at line {start}: `{key}` is too large (more than {MAX_DIGITS} digits)")
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
