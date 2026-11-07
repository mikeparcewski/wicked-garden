#!/usr/bin/env python3
"""notes_check.py — the drafting run's ``notes.json`` exists and has the one shape a host reads.

What a draft could not confirm is listed BESIDE the artifact, never inside it (DES-CHAT-ARTIFACTS-001
§11.2). The writer saves ``notes.json`` next to its output, under that fixed name:

    {"left_out": [{"claim": "...", "why": "..."}],
     "sources": [{"token": "run:1a2b3c4d", "used": true}],
     "assumptions": ["..."]}

All three keys are required (an empty list is a real answer: nothing left out). Nothing else may be
in it: a host shows these fields as the writer's notes, labelled, and reads nothing else from it.

Exit: 0 = valid; 1 = missing or invalid (fix it, re-run); 2 = usage. Stdlib only.

CLI:
    notes_check.py <notes.json> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MAX_BYTES = 256 * 1024
MAX_ITEMS = 200
MAX_TEXT = 1000
MAX_TOKEN = 300
KEYS = ("left_out", "sources", "assumptions")


def _text(v: object, cap: int) -> bool:
    return isinstance(v, str) and 0 < len(v.strip()) and len(v) <= cap


def validate(data: object) -> list[str]:
    """Every problem with the parsed notes, as sentences; ``[]`` = valid."""
    if not isinstance(data, dict):
        return ["notes.json must be one JSON object"]
    problems: list[str] = []
    extra = sorted(k for k in data if k not in KEYS)
    if extra:
        problems.append(f"unknown key(s) {', '.join(extra)}: only left_out, sources and assumptions are read")
    for key in KEYS:
        if key not in data:
            problems.append(f"missing `{key}` (an empty list is fine)")
        elif not isinstance(data[key], list):
            problems.append(f"`{key}` must be a list")
        elif len(data[key]) > MAX_ITEMS:
            problems.append(f"`{key}` has {len(data[key])} items (at most {MAX_ITEMS})")
    if problems:
        return problems
    for i, item in enumerate(data["left_out"]):
        if not isinstance(item, dict) or set(item) != {"claim", "why"} or not _text(item.get("claim"), MAX_TEXT) or not _text(item.get("why"), MAX_TEXT):
            problems.append(f"left_out[{i}] must be {{claim, why}}, each 1-{MAX_TEXT} characters")
    for i, item in enumerate(data["sources"]):
        if not isinstance(item, dict) or set(item) != {"token", "used"} or not _text(item.get("token"), MAX_TOKEN) or not isinstance(item.get("used"), bool):
            problems.append(f"sources[{i}] must be {{token (1-{MAX_TOKEN} characters), used (true or false)}}")
    for i, item in enumerate(data["assumptions"]):
        if not _text(item, MAX_TEXT):
            problems.append(f"assumptions[{i}] must be a sentence of 1-{MAX_TEXT} characters")
    return problems


def run(path: str) -> dict:
    p = Path(path)
    problems: list[str]
    if not p.is_file():
        problems = [f"notes.json is missing at {p.name}: write it beside the document, even with empty lists"]
    elif p.stat().st_size > MAX_BYTES:
        problems = [f"notes.json is over {MAX_BYTES // 1024} KB"]
    else:
        try:
            problems = validate(json.loads(p.read_text(encoding="utf-8")))
        except (ValueError, UnicodeDecodeError) as exc:
            problems = [f"notes.json is not valid JSON: {exc}"]
    ok = not problems
    return {"check": "notes", "ok": ok, "findings": problems,
            "summary": "notes: notes.json is valid" if ok else f"notes: {len(problems)} problem(s) — {problems[0]}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("notes")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = run(args.notes)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["summary"])
        for f in report["findings"][1:]:
            print("  " + f)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
