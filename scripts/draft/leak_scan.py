#!/usr/bin/env python3
"""leak_scan.py — no process notes inside the artifact (DES-CHAT-ARTIFACTS-001 §11.2).

A draft says what the SUBJECT is. How the draft was made (the run's inbox, its id, the self-check
it ran, which source it could not read, "I used SearchEntity") belongs in the run's ``notes.json``
and the reply, never in the document a reader gets. This scan re-derives that from the saved file.

It reads ALL of the artifact's text, not only what the screen shows: visible text, speaker notes
(``aside.notes``, a talk track and nothing else), attribute values (alt, title, aria-label, data-*)
and HTML comments (an export ships them). It rejects execution metadata, never subject vocabulary:
"wicked-crew's domain-coverage skill pages through 500 units" passes; "I used SearchEntity" fails.

| Kind | Fails | Scanned in |
|---|---|---|
| ``state-path`` | the run's inbox or state paths (``.wicked-crew``, ``attempt-<id>``, ``sources/brief-…``, ``notes.json``, a home directory) | everything |
| ``run-id`` | the drafting run's own id (``--run-id``) | everything |
| ``process-word`` | "self-check", "UNVERIFIED" | text, notes, attributes |
| ``source-marker`` | a bare source marker such as ``[S]`` or ``[S2]`` | text, notes, attributes |
| ``narration`` | first-person narration of the drafting ("I used SearchEntity…", "the brief says…") | text, notes, attributes |

Exit: 0 = clean; 1 = a leak (fix the document, re-run); 2 = usage / unreadable input. Stdlib only.

CLI:
    leak_scan.py <file.html> [--run-id <id> …] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draft._dom import Node, parse  # noqa: E402

# Attributes that are structure, never words a reader gets: their values are not scanned for words (paths and run ids
# still are — a `data-source` pointing into the inbox is a leak).
_STRUCTURAL_ATTRS = frozenset({"class", "id", "style", "data-wid", "data-slide-id", "data-wid-notes", "for", "type",
                               "rel", "lang", "dir", "role", "width", "height"})

_STATE_PATH = re.compile(
    r"(?:\.wicked-crew\b|\.wicked-qe\b|wicked-interactive/docs\b|interactive-(?:drafts|chats|edits|reviews)\b"
    r"|\battempt-[0-9a-f]{8}-[0-9a-f-]{8,}|\b(?:sources|records)/(?:brief|conversation|message|run|doc|attachment|page|MANIFEST)-"
    r"|\bnotes\.json\b|\b(?:current|revised)\.html\b"
    r"|/Users/[^/\s\"'<>]+/|/home/[^/\s\"'<>]+/|[A-Za-z]:\\Users\\|/private/(?:tmp|var/folders)/|/tmp/crew-)",
    re.IGNORECASE,
)
_PROCESS_WORD = re.compile(r"\bself[- ]check(?:s|ed)?\b|\bUNVERIFIED\b", re.IGNORECASE)
# `UNVERIFIED` only in capitals is the self-check's verdict word; "unverified" in prose is subject vocabulary.
_UNVERIFIED_CASE = re.compile(r"UNVERIFIED")
_SOURCE_MARKER = re.compile(r"\[(?:S\d{0,3}|src\d{0,3}|source\d{0,3})\]", re.IGNORECASE)
_TOOLS = r"(?:SearchEntity|FetchContent|ContextBundle|RetrieveEntity|TraverseGraph|the estate|estate tools?|MCP|the (?:repo(?:sitory)? )?snapshot|the brief|the sources?|the (?:source )?packet|the self[- ]check)"
_NARRATION = re.compile(
    r"\bI (?:used|ran|called|queried|searched|checked|read)\b[^.!?\n]{0,60}?\b" + _TOOLS + r"|"
    r"\bI (?:could(?:n'?t| not)|was unable to|did not|didn'?t) (?:find|verify|confirm|measure|read|reach|locate)\b|"
    r"\bthe brief (?:says|said|asks|asked|requests|requested|calls for|wants|wanted)\b|"
    r"\b(?:per|according to) (?:the|your) brief\b|"
    r"\bas (?:instructed|requested) (?:in|by) the (?:brief|task)\b",
    re.IGNORECASE,
)

_EXCERPT = 90


def _excerpt(text: str, start: int, end: int) -> str:
    lo = max(0, start - 30)
    hi = min(len(text), end + 30)
    out = re.sub(r"\s+", " ", text[lo:hi]).strip()
    return out[:_EXCERPT]


def _in_notes(node: Node) -> bool:
    for n in [node, *node.ancestors()]:
        if n.tag == "aside" and "notes" in n.classes():
            return True
    return False


def _units(html: str) -> list[tuple[str, str, str]]:
    """Every scannable unit: (where, locator, text). `where` is text | notes | attr:<name> | comment."""
    doc = parse(html)
    units: list[tuple[str, str, str]] = []
    for node in doc.root.walk():
        if node.tag == "#text":
            parent = node.parent
            if parent is None or parent.tag in ("script", "style"):
                continue
            if not node.text.strip():
                continue
            units.append(("notes" if _in_notes(parent) else "text", parent.path() if parent.tag else "document", node.text))
        elif node.tag == "#comment":
            units.append(("comment", node.parent.path() if node.parent is not None and node.parent.tag else "document", node.text))
        elif node.tag and not node.tag.startswith("#"):
            for name, value in node.attrs.items():
                if value:
                    units.append((f"attr:{name}", node.path(), value))
    return units


def run(html_path: str, run_ids: list[str] | None = None) -> dict:
    html = Path(html_path).read_text(encoding="utf-8", errors="replace")
    return scan(html, run_ids)


def scan(html: str, run_ids: list[str] | None = None) -> dict:
    ids = [r.strip() for r in (run_ids or []) if r and len(r.strip()) >= 8]
    id_res = [re.compile(re.escape(r), re.IGNORECASE) for r in ids]
    # The 8-character prefix a run is shown by ("run 1a2b3c4d"), as a whole hex word.
    id_res += [re.compile(r"(?<![0-9a-f])" + re.escape(r[:8]) + r"(?![0-9a-f])", re.IGNORECASE) for r in ids if len(r) > 8]
    findings: list[dict] = []

    def hit(kind: str, where: str, locator: str, text: str, m: re.Match[str]) -> None:
        findings.append({"kind": kind, "where": where, "path": locator, "excerpt": _excerpt(text, m.start(), m.end())})

    for where, locator, text in _units(html):
        for m in _STATE_PATH.finditer(text):
            hit("state-path", where, locator, text, m)
        for rx in id_res:
            m = rx.search(text)
            if m is not None:
                hit("run-id", where, locator, text, m)
                break
        if where == "comment":
            continue
        name = where[5:] if where.startswith("attr:") else ""
        if name in _STRUCTURAL_ATTRS or name.startswith("on"):
            continue
        for m in _PROCESS_WORD.finditer(text):
            # "unverified" in lower case is prose about the subject; only the verdict word in capitals fails.
            if m.group(0).lower() == "unverified" and not _UNVERIFIED_CASE.fullmatch(m.group(0)):
                continue
            hit("process-word", where, locator, text, m)
        for m in _SOURCE_MARKER.finditer(text):
            hit("source-marker", where, locator, text, m)
        for m in _NARRATION.finditer(text):
            hit("narration", where, locator, text, m)

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    ok = not findings
    summary = ("leaks: no process notes in the artifact" if ok else
               "leaks: " + ", ".join(f"{n} {k}" for k, n in sorted(by_kind.items())) +
               " — how the draft was made goes in notes.json and the reply, never in the document")
    return {"check": "leaks", "ok": ok, "findings": findings, "by_kind": by_kind, "summary": summary}


def format_finding(f: dict) -> str:
    return f"[{f['kind']}] {f['where']} at {f['path']}: “{f['excerpt']}”"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("html")
    ap.add_argument("--run-id", action="append", default=[], help="the drafting run's id (it must not appear)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = run(args.html, args.run_id)
    except (OSError, ValueError) as exc:
        print(json.dumps({"check": "leaks", "ok": False, "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["summary"])
        for f in report["findings"][:60]:
            print("  " + format_finding(f))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
