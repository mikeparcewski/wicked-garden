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
script/style bodies are read for paths and run ids. CSS is read by a tokenizer, one declaration at a time, from
every ``<style>`` and ``style=""`` of the document together: its string tokens are decoded and joined
(``"\\5b S\\5d "`` renders ``[S]``), and a ``var(--x)`` is read as each text it can render, with every
declaration of ``--x`` in the document and its fallback (the cascade picks one; each is read). A composition too
deep or too wide to read is a ``css-unread`` finding: the scan does not pass what it could not read.

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
# A bare "self-check" verdict is the drafting check's printed form ("Self-check: PASS", "The completed self-check:
# PASS") unless BOTH hold: a named subject owns the check, written as a determiner and one to three words ("The
# control unit self-check") or a possessive ("each pump's self-check"), none of them a drafting qualifier; and the
# sentence goes on after the verdict ("... PASS means the motor may start"). A verdict that ends its sentence, a
# drafting qualifier ("Final", "The completed", "My") or a clause break ("Done, self-check: PASS") stays flagged.
_BARE_SELF_CHECK = re.compile(r"(?i:\bself[- ]check\b)(?!\.py)" + _VERDICT)
_QUALIFIERS = (r"(?:draft|drafting|final|last|latest|full|first|second|automated|required|initial|completed|complete"
               r"|overall|current|previous|manual|quick|local|new|updated|my|our|this|that"
               r"|document|doc|deck|page|slide|report|artifact)")
_SUBJECT_WORD = r"(?!" + _QUALIFIERS + r"\b)[^\W\d_][\w-]*"
_OWNED = re.compile(
    r"(?i:(?:\b(?:the|a|an|its|their|each|every|your|his|her)(?:\s+" + _SUBJECT_WORD + r"){1,3}(?:['’]s)?"
    r"|\b" + _SUBJECT_WORD + r"['’]s))\s*$")
_GOES_ON = re.compile(r"\s*[a-z]")

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


_CSS_WS = " \t\n"
_CSS_VAR_DEPTH = 8
_CSS_NEST_MAX = 32       # var() nested inside var() fallbacks; past it the stylesheet is not read
_CSS_ALTS_MAX = 32       # distinct texts one value may render through var(); past it the value is not read
_CSS_TEXT_MAX = 100_000  # characters one rendered alternative may hold; past it the value is not read


def _css_comment_end(css: str, i: int) -> int:
    end = css.find("*/", i + 2)
    return len(css) if end < 0 else end + 2


def _css_value(css: str, i: int, in_var: bool, nest: int = 0) -> tuple[list, int]:
    """The parts of a declaration value from ``css[i]``: decoded strings and ``("var", name, fallback)``
    references. Ends at ``;``, ``{``, ``}`` or ``!`` outside parentheses (index left on it), or for a ``var()``
    fallback at its closing ``)`` (index after it). An unquoted ``url(...)`` is one token whose characters
    are data (a ``/*`` or a quote inside it opens nothing; CSS Syntax 3 §4.3.6). Raises :class:`_Unread` past
    :data:`_CSS_NEST_MAX` nested ``var()`` fallbacks."""
    if nest > _CSS_NEST_MAX:
        raise _Unread
    parts: list = []
    depth = 0
    n = len(css)
    while i < n:
        if css.startswith("/*", i):
            i = _css_comment_end(css, i)
            continue
        c = css[i]
        if c in "\"'":
            text, i = _css_string(css, i)
            parts.append(text)
            continue
        if c == "\\" or _CSS_IDENT_CHAR.match(c):
            name, j = _css_ident(css, i)
            if j == i:
                i += 1
                continue
            i = j
            if i < n and css[i] == "(":
                low = name.lower()
                k = i + 1
                while k < n and css[k] in _CSS_WS:  # whitespace only: a comment here is URL data
                    k += 1
                if low == "url" and not (k < n and css[k] in "\"'"):
                    i = _css_url(css, i + 1)
                    continue
                if low == "var":
                    k = i + 1
                    while k < n and (css[k] in _CSS_WS or css.startswith("/*", k)):
                        k = _css_comment_end(css, k) if css.startswith("/*", k) else k + 1
                    ref, k = _css_ident(css, k)
                    fallback, i = _css_value(css, k, True, nest + 1)  # the rest up to the matching ")"
                    # the tokens between the name and its comma are not text; the fallback follows the comma
                    parts.append(("var", ref, fallback if _css_has_comma(css, k, i) else None))
                    continue
                depth += 1
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0 and in_var:
                return parts, i + 1
            depth = max(0, depth - 1)
        elif depth == 0 and not in_var and c in ";{}!":
            return parts, i
        i += 1
    return parts, i


def _css_has_comma(css: str, start: int, end: int) -> bool:
    """Whether the ``var()`` arguments between ``start`` and ``end`` carry a fallback (a top-level comma)."""
    i = start
    while i < end:
        if css.startswith("/*", i):
            i = _css_comment_end(css, i)
            continue
        if css[i] in "\"'":
            _, i = _css_string(css, i)
            continue
        if css[i] == ",":
            return True
        if css[i] in "()":
            return False
        i += 1
    return False


def _css_declarations(css: str) -> list[tuple[str, list]]:
    """Every declaration ``(property, parts)`` in a stylesheet or a ``style`` attribute, read by tokenizing
    (CSS Syntax 3), never by pattern. Strings are decoded (``"\\5b S\\5d "`` is ``[S] ``); a ``;`` or an escaped
    quote inside a string, comments, and nested blocks (``@media``) change nothing. Outside declarations, a
    string or an unquoted ``url(...)`` body (an ``@import`` prelude, a selector) is one URL token, never a
    comment opener, and its text is returned as ``("", [text])`` so an inline ``data:`` stylesheet is read."""
    css = css.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n").replace("\x00", "�")
    out: list[tuple[str, list]] = []
    n = len(css)
    i = 0
    expect_name = True
    while i < n:
        if css.startswith("/*", i):
            i = _css_comment_end(css, i)
            continue
        c = css[i]
        if c in "\"'":
            text, i = _css_string(css, i)  # a selector or prelude string: read, it may be a data: stylesheet
            if text:
                out.append(("", [text]))
            continue
        if c in ";{}":
            expect_name = True
            i += 1
            continue
        if c == "\\" or _CSS_IDENT_CHAR.match(c):
            name, j = _css_ident(css, i)
            if j == i:
                i += 1
                continue
            i = j
            if name.lower() == "url" and i < n and css[i] == "(":
                k = i + 1
                while k < n and css[k] in _CSS_WS:  # whitespace only: a comment here is URL data
                    k += 1
                if not (k < n and css[k] in "\"'"):
                    end = _css_url(css, i + 1)
                    body = css[i + 1:end - 1 if css[end - 1:end] == ")" else end]
                    if body.strip(_CSS_WS):
                        out.append(("", [body]))
                    i = end
                    expect_name = False
                    continue
            if expect_name:
                k = i
                while k < n and (css[k] in _CSS_WS or css.startswith("/*", k)):
                    k = _css_comment_end(css, k) if css.startswith("/*", k) else k + 1
                if k < n and css[k] == ":":
                    parts, i = _css_value(css, k + 1, False)
                    out.append((name, parts))
                    expect_name = False
            continue
        i += 1
    return out


class _Unread(Exception):
    """A value whose rendered text could not be read within the bounds: the scan does not pass it."""


def _css_rendered(parts: list, custom: dict[str, list[list]], depth: int = 0, seen: frozenset = frozenset()) -> list[str]:
    """Every text a value can render: a ``var(--x)`` stands for each declaration of ``--x`` anywhere in the
    document (which one applies is the cascade's call, so each is read), or its fallback, or nothing. Raises
    :class:`_Unread` past the depth, alternatives or size bounds."""
    alts = [""]
    for part in parts:
        if isinstance(part, str):
            choices = [part]
        else:
            _, ref, fallback = part
            choices = [""]
            if ref in seen:
                pass  # a reference cycle renders nothing (invalid at computed-value time)
            elif depth >= _CSS_VAR_DEPTH:
                raise _Unread
            else:
                for definition in custom.get(ref, []):
                    choices += _css_rendered(definition, custom, depth + 1, seen | {ref})
            if fallback is not None:
                choices += _css_rendered(fallback, custom, depth + 1, seen)
            choices = list(dict.fromkeys(choices))
        alts = list(dict.fromkeys(a + c for a in alts for c in choices))
        if len(alts) > _CSS_ALTS_MAX or any(len(a) > _CSS_TEXT_MAX for a in alts):
            raise _Unread
    return alts


def _css_units(sources: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """The CSS units of a document from its ``(locator, css)`` sources (every ``<style>`` body and ``style``
    attribute): each declaration's own strings joined (always read, whatever else happens), and, for a
    declaration that uses ``var()``, each text it can render with the document's custom properties
    substituted. A value that cannot be read within the bounds is a ``css-unread`` unit."""
    decls: list[tuple[str, str, list]] = []
    units: list[tuple[str, str, str]] = []
    for loc, css in sources:
        try:
            decls += [(loc, prop, parts) for prop, parts in _css_declarations(css)]
        except (_Unread, RecursionError):
            units.append(("css-unread", loc, "a CSS value nests var() too deeply to read"))
    custom: dict[str, list[list]] = {}
    for _, prop, parts in decls:
        if prop.startswith("--"):
            custom.setdefault(prop, []).append(parts)
    for loc, _, parts in decls:
        literal = "".join(p for p in parts if isinstance(p, str))
        if literal:
            units.append(("css", loc, literal))
        if any(not isinstance(p, str) for p in parts):
            try:
                for text in _css_rendered(parts, custom):
                    if text and text != literal:
                        units.append(("css", loc, text))
            except (_Unread, RecursionError):
                units.append(("css-unread", loc, "a CSS value composed through var() is too deep or too wide to read"))
    return units


def _units(html: str) -> list[tuple[str, str, str]]:
    """Every scannable unit: (where, locator, text). `where` is text | notes | attr:<name> | comment | code | css.
    Text is read per block, with its inline children joined in, so markup inside a sentence cannot split a leak."""
    doc = parse(html)
    units: list[tuple[str, str, str]] = []
    css_sources: list[tuple[str, str]] = []  # read together: a custom property set in one is used in another

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
                    css_sources.append((locator, value))
        if node.tag in ("script", "style"):
            body = "".join(c.text for c in node.children if c.tag == "#text")
            units.append(("code", locator, body))
            if node.tag == "style":
                css_sources.append((locator, body))
            continue
        if node.tag in _INLINE and node.parent is not None and node.parent.tag not in ("", None):
            continue  # its words are read with the block it sits in
        text = block_text(node)
        if text.strip():
            units.append(("notes" if _in_notes(node) else "text", locator, text))
    return units + _css_units(css_sources)


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
        if where == "css-unread":
            findings.append({"kind": "css-unread", "where": "css", "path": locator, "excerpt": raw})
            continue
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
            if not (_OWNED.search(before) and _GOES_ON.match(text, m.end())):
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
