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
| ``state-path`` | the run's inbox or state paths (``.wicked-crew``, ``attempt-<id>``, ``refine-<id>``, ``sources/brief-…``, a home directory) | everything |
| ``run-id`` | the drafting run's own id (``--run-id``) | everything |
| ``process-word`` | a drafting check's verdict or its running ("UNVERIFIED", "self-check: PASS", "keep_check.py: PASS", "I ran the self-check") | text, notes, attributes, comments, CSS ``content`` |
| ``source-marker`` | a bare source marker such as ``[S]`` or ``[S2]`` | text, notes, attributes, comments, CSS ``content`` |
| ``narration`` | first-person narration of the drafting ("I used SearchEntity…", "I ran keep_check.py…", "the brief says…") | text, notes, attributes, comments, CSS ``content`` |

Text is read per block with its inline children joined in (``I used <em>SearchEntity</em>`` is caught), and
script/style bodies are read for paths and run ids.

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

_SEP = r"[\\/]"  # a path separator, either platform's
_STATE_PATH = re.compile(
    r"(?:\.wicked-crew\b|\.wicked-qe\b|wicked-interactive" + _SEP + r"docs\b|interactive-(?:drafts|chats|edits|reviews)\b"
    r"|\battempt-[0-9a-f]{8}-[0-9a-f-]{8,}|\b(?:sources|records)" + _SEP + r"(?:brief|conversation|message|run|doc|attachment|page|MANIFEST)-"
    r"|\brefine-[0-9a-f]{8}-[0-9a-f-]{8,}"
    # a home directory (macOS, Linux, Windows) or a temp folder of the host
    r"|/(?:Users|home)/[^/\s\"'<>]+/|[A-Za-z]:\\Users\\|/private/(?:tmp|var/folders)/|/tmp/crew-)",
    re.IGNORECASE,
)
# The self-check's own verdict words. "self-check" alone is subject vocabulary ("the device runs a self-check");
# only the drafting check's verdict or its running is execution metadata.
_CHECKS = r"(?:self[- _]check|keep_check|contrast_check|claims_scan|notes_check|leak_scan|page_count)(?:\.py)?"
_PROCESS_WORD = re.compile(
    r"\bUNVERIFIED\b"  # the verdict word, in capitals only ("unverified claims" is prose)
    # the check named in any case, its verdict in the capitals the checks print ("the self-check passed" is prose)
    r"|(?i:\b" + _CHECKS + r")\W{0,3}(?:(?i:verdict)\W{0,3})?(?:PASS|FAIL|UNVERIFIED)\b"
    r"|(?i:\b(?:I|we) (?:ran|re-ran|reran|have run|re-run) (?:the |a |my )?(?:draft )?" + _CHECKS + r")"
    r"|(?i:\bdraft self[- ]check\b)")
_SOURCE_MARKER = re.compile(r"\[(?:S\d{0,3}|src\d{0,3}|source\d{0,3})\]", re.IGNORECASE)
_TOOLS = (r"(?:SearchEntity|FetchContent|ContextBundle|RetrieveEntity|TraverseGraph|the estate|estate tools?|MCP"
          r"|the (?:repo(?:sitory)? )?snapshot|the brief|the sources?|the (?:source )?packet|the self[- ]check"
          r"|(?:self_check|keep_check|contrast_check|claims_scan|notes_check|leak_scan|page_count)(?:\.py)?)")
_NARRATION = re.compile(
    r"\b(?:I|we) (?:used|ran|called|queried|searched|checked|read)\b[^.!?\n]{0,60}?\b" + _TOOLS + r"|"
    r"\b(?:I|we) (?:could(?:n'?t| not)|was unable to|were unable to|did not|didn'?t) (?:find|verify|confirm|measure|read|reach|locate)\b|"
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


# Text inside these joins the block it sits in (``I used <em>SearchEntity</em>`` is one sentence).
_INLINE = frozenset(("a abbr b bdi bdo button cite code data del dfn em i ins kbd label mark meter option output progress q "
                     "ruby rt rp s samp select small span strong sub sup textarea time u var wbr br font").split())
_CSS_CONTENT = re.compile(r"""content\s*:\s*([^;}]*)""", re.IGNORECASE)
_CSS_STRING = re.compile(r""""([^"]*)"|'([^']*)'""")


def _css_content(value: str) -> str:
    """The text a CSS ``content`` value renders: its quoted strings, adjacent ones joined (``"I used " "X"``)."""
    return "".join(m.group(1) if m.group(1) is not None else m.group(2) for m in _CSS_STRING.finditer(value))


def _units(html: str) -> list[tuple[str, str, str]]:
    """Every scannable unit: (where, locator, text). `where` is text | notes | attr:<name> | comment | code | css.
    Text is read per block, with its inline children joined in, so markup inside a sentence cannot split a leak."""
    doc = parse(html)
    units: list[tuple[str, str, str]] = []

    def block_text(node: Node) -> str:
        out: list[str] = []
        for c in node.children:
            if c.tag == "#text":
                out.append(c.text)
            elif c.tag == "br":
                out.append(" ")  # a rendered line break is a word boundary
            elif c.tag in _INLINE:
                out.append(block_text(c))
        return "".join(out)

    for node in doc.root.walk():
        if node.tag == "#comment":
            units.append(("comment", node.parent.path() if node.parent is not None and node.parent.tag else "document", node.text))
            continue
        if node.tag == "":
            # Text outside every element (before or after the document element) still renders.
            text = block_text(node)
            if text.strip():
                units.append(("text", "document", text))
            continue
        if node.tag.startswith("#"):
            continue
        locator = node.path()
        for name, value in node.source_attrs:  # every occurrence as written: a repeated attribute ships too
            if value:
                units.append((f"attr:{name}", locator, value))
                if name == "style":
                    for m in _CSS_CONTENT.finditer(value):
                        units.append(("css", locator, _css_content(m.group(1))))
        if node.tag in ("script", "style"):
            body = "".join(c.text for c in node.children if c.tag == "#text")
            units.append(("code", locator, body))
            if node.tag == "style":
                for m in _CSS_CONTENT.finditer(body):
                    units.append(("css", locator, _css_content(m.group(1))))
            continue
        if node.tag in _INLINE and node.parent is not None and node.parent.tag not in ("", None):
            continue  # its words are read with the block it sits in
        text = block_text(node)
        if text.strip():
            units.append(("notes" if _in_notes(node) else "text", locator, text))
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

    for where, locator, raw in _units(html):
        # HTML renders a run of whitespace (a line break in the source) as one space; so is it read, on every surface.
        text = re.sub(r"\s+", " ", raw)
        for m in _STATE_PATH.finditer(text):
            hit("state-path", where, locator, text, m)
        for rx in id_res:
            m = rx.search(text)
            if m is not None:
                hit("run-id", where, locator, text, m)
                break
        if where == "code":
            continue  # script and style bodies carry paths and ids, never the reader's words
        name = where[5:] if where.startswith("attr:") else ""
        if name in _STRUCTURAL_ATTRS or name.startswith("on"):
            continue
        for m in _PROCESS_WORD.finditer(text):
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


def safe_console() -> None:
    """Never crash printing an excerpt on a code-page console (Windows piped stdout)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    safe_console()
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
