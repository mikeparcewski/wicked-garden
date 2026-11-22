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
| ``process-word`` | a drafting check's verdict or its running ("UNVERIFIED", "self-check: PASS", "keep_check.py: PASS", "I ran the self-check"); a subject's own check ("The device self-check: PASS means …") is prose | text, notes, attributes, comments, CSS strings |
| ``source-marker`` | a bare source marker such as ``[S]`` or ``[S2]`` | text, notes, attributes, comments, CSS strings |
| ``narration`` | first-person narration of the drafting ("I used SearchEntity…", "I ran keep_check.py…", "the brief says…") | text, notes, attributes, comments, CSS strings |

Text is read per block with its inline children joined in (``I used <em>SearchEntity</em>`` is caught), and
script/style bodies are read for paths and run ids. CSS is read by a tokenizer: every string token is decoded
(``"\\5b S\\5d "`` renders ``[S]``), ``var()`` references are replaced by their custom properties' strings, and
each rule block's strings are joined (``content``, ``quotes`` and the rest all render strings).

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
# The drafting tools by their script names: a verdict after one is always the drafting check's.
_TOOL_CHECKS = r"(?:(?:self_check|keep_check|contrast_check|claims_scan|notes_check|leak_scan|page_count)(?:\.py)?|self[- ]check\.py)"
_VERDICT = r"\W{0,3}(?:(?i:verdict)\W{0,3})?(?:PASS|FAIL|UNVERIFIED)\b"
_PROCESS_WORD = re.compile(
    r"\bUNVERIFIED\b"  # the verdict word, in capitals only ("unverified claims" is prose)
    # the check named in any case, its verdict in the capitals the checks print ("the self-check passed" is prose)
    r"|(?i:\b" + _TOOL_CHECKS + r")" + _VERDICT +
    r"|(?i:\b(?:I|we) (?:ran|re-ran|reran|have run|re-run) (?:the |a |my )?(?:draft )?" + _CHECKS + r")"
    r"|(?i:\bdraft self[- ]check\b)")
# A bare "self-check" verdict is the drafting check's printed form ("Self-check: PASS", "Final self-check: PASS")
# unless a named subject owns the check, written as a determiner and a noun ("The device self-check: PASS means
# the motor may start", "each pump's self-check") or a possessive ("the pump's self-check"). A drafting
# qualifier in the noun's place ("The final self-check") does not make it the subject's.
_BARE_SELF_CHECK = re.compile(r"(?i:\bself[- ]check\b)(?!\.py)" + _VERDICT)
_QUALIFIERS = r"(?:draft|drafting|final|last|latest|full|first|second|automated|required|initial|my|our|this)"
_OWNED = re.compile(
    r"(?i:(?:\b(?:the|a|an|its|their|each|every|your|his|her)\s+(?!" + _QUALIFIERS + r"\b)[^\W\d_][\w-]*(?:['’]s)?"
    r"|\b(?!" + _QUALIFIERS + r"\b)[^\W\d_][\w-]*['’]s))\s*$")
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
_HEX = frozenset("0123456789abcdefABCDEF")
_CSS_IDENT_CHAR = re.compile(r"[\w-]|[^\x00-\x7f]")


def _css_escape(css: str, i: int) -> tuple[str, int]:
    """The code point of the escape whose backslash is at ``css[i]`` (CSS Syntax 3 §4.3.7), and the index after it."""
    j = i + 1
    if j >= len(css):
        return "\ufffd", j
    if css[j] in _HEX:
        k = j
        while k < len(css) and k - j < 6 and css[k] in _HEX:
            k += 1
        cp = int(css[j:k], 16)
        if k < len(css) and css[k] in " \t\n":
            k += 1  # one whitespace after a hex escape belongs to it
        return ("\ufffd" if cp == 0 or 0xD800 <= cp <= 0xDFFF or cp > 0x10FFFF else chr(cp)), k
    return css[j], j + 1


def _css_string(css: str, i: int) -> tuple[str, int]:
    """The decoded value of the string token opening at ``css[i]`` (CSS Syntax 3 §4.3.5), and the index after it.
    An escaped newline continues the string; an unescaped one ends it (a bad string: what was read is kept)."""
    quote, out, j = css[i], [], i + 1
    while j < len(css):
        c = css[j]
        if c == quote:
            return "".join(out), j + 1
        if c == "\n":
            return "".join(out), j
        if c == "\\":
            if j + 1 < len(css) and css[j + 1] == "\n":
                j += 2
                continue
            ch, j = _css_escape(css, j)
            out.append(ch)
            continue
        out.append(c)
        j += 1
    return "".join(out), j


def _css_ident(css: str, i: int) -> tuple[str, int]:
    """The decoded ident-like run starting at ``css[i]`` (escapes decoded, so ``cont\\65nt`` is ``content``)."""
    out, j = [], i
    while j < len(css):
        if css[j] == "\\" and j + 1 < len(css) and css[j + 1] != "\n":
            ch, j = _css_escape(css, j)
            out.append(ch)
        elif _CSS_IDENT_CHAR.match(css[j]):
            out.append(css[j])
            j += 1
        else:
            break
    return "".join(out), j


def _css_skip(css: str, j: int) -> int:
    """Past whitespace and comments."""
    while j < len(css):
        if css[j] in " \t\n":
            j += 1
        elif css.startswith("/*", j):
            end = css.find("*/", j + 2)
            j = len(css) if end < 0 else end + 2
        else:
            break
    return j


def _css_url(css: str, i: int) -> int:
    """Past the unquoted URL token whose body starts at ``css[i]`` (after ``url(``), CSS Syntax 3 §4.3.6: its
    characters are data, so a ``/*`` or a quote inside it opens nothing. A bad URL is skipped to its ``)``."""
    j = i
    while j < len(css):
        c = css[j]
        if c == ")":
            return j + 1
        if c == "\\" and j + 1 < len(css) and css[j + 1] != "\n":
            _, j = _css_escape(css, j)
            continue
        j += 1
    return j


_CSS_VAR_DEPTH = 8
_CSS_EXPAND_MAX = 1_000_000  # parts + characters one stylesheet may expand to; past it the rest is not expanded


def _css_texts(css: str) -> list[str]:
    """The text a stylesheet (or a ``style`` attribute) can render, read by tokenizing (CSS Syntax 3), never by
    pattern. Every string token is decoded (``"\\5b S\\5d "`` is ``[S] ``) whatever property holds it:
    ``content``, ``quotes``, ``list-style-type`` and custom properties all render strings. A ``var(--x)`` is
    replaced by the strings of ``--x`` (its last declaration; nested references bounded, cycles cut), so a
    leak composed through custom properties is read whole. One unit per rule block: its declarations'
    strings joined in order (``content: "I used " var(--tool)``). A ``;`` or an escaped quote inside a string,
    a comment between strings, and ``/*`` or a quote inside an unquoted ``url(...)`` change nothing."""
    css = css.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n").replace("\x00", "\ufffd")
    blocks: list[list[list]] = []        # every closed block: its declarations, each a list of parts
    stack: list[list[list]] = [[[]]]     # open blocks; the root holds a style attribute's declarations
    custom: dict[str, list] = {}         # --name -> the parts of its last declaration
    prop, expect_name = "", True
    i = 0

    def end_decl() -> None:
        nonlocal prop, expect_name
        if prop.startswith("--"):
            custom[prop] = stack[-1][-1]
        if stack[-1][-1]:
            stack[-1].append([])
        prop, expect_name = "", True

    while i < len(css):
        c = css[i]
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end < 0 else end + 2
        elif c in "\"'":
            text, i = _css_string(css, i)
            stack[-1][-1].append(text)
        elif c == "\\" or _CSS_IDENT_CHAR.match(c):
            name, j = _css_ident(css, i)
            if j == i:
                i += 1
                continue
            i = j
            if i < len(css) and css[i] == "(":
                low = name.lower()
                k = _css_skip(css, i + 1)
                if low == "url" and not (k < len(css) and css[k] in "\"'"):
                    i = _css_url(css, i + 1)
                elif low == "var" and k < len(css) and css[k] == "-":
                    ref, i = _css_ident(css, k)
                    stack[-1][-1].append(("var", ref))
                continue
            if expect_name:
                k = _css_skip(css, i)
                if k < len(css) and css[k] == ":":
                    prop, expect_name, i = name, False, k + 1
        elif c == ";":
            end_decl()
            i += 1
        elif c == "{":
            end_decl()
            stack.append([[]])
            i += 1
        elif c == "}":
            end_decl()
            blocks.append(stack.pop() if len(stack) > 1 else stack[0])
            if len(stack) == 0 or blocks[-1] is stack[0]:
                stack[:] = [[[]]]
            i += 1
        else:
            i += 1
    end_decl()
    blocks.extend(stack)

    budget = [_CSS_EXPAND_MAX]  # one budget for the whole stylesheet: every part visited costs at least 1

    def expand(parts: list, depth: int, seen: frozenset, out: list[str]) -> None:
        for part in parts:
            if budget[0] <= 0:
                return
            if isinstance(part, str):
                out.append(part)
                budget[0] -= len(part) + 1
            else:
                budget[0] -= 1
                if depth < _CSS_VAR_DEPTH and part[1] not in seen and part[1] in custom:
                    expand(custom[part[1]], depth + 1, seen | {part[1]}, out)

    texts: list[str] = []
    for block in blocks:
        out: list[str] = []
        for decl in block:
            expand(decl, 0, frozenset(), out)
        if out:
            texts.append("".join(out))
    return texts


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
                    for text in _css_texts(value):
                        units.append(("css", locator, text))
        if node.tag in ("script", "style"):
            body = "".join(c.text for c in node.children if c.tag == "#text")
            units.append(("code", locator, body))
            if node.tag == "style":
                for text in _css_texts(body):
                    units.append(("css", locator, text))
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
        for m in _BARE_SELF_CHECK.finditer(text):
            # the clause it sits in (a bounded look-back: the owner sits right before the check)
            before = re.split(r"[.!?:;,]\s", text[max(0, m.start() - 120):m.start()])[-1]
            if not _OWNED.search(before):
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
