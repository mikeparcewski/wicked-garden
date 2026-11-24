#!/usr/bin/env python3
"""claims_scan.py — claims discipline for a document deliverable: no placeholders, every number
and URL traceable to a source, every mock visibly labelled.

F-RECON-009: a governed brochure shipped a visible ``[PLACEHOLDER: Customer validation]`` box, a
"live instance" URL claim the sources contradict, and a command-center mock whose KPIs were called
"illustrative" only inside an HTML comment. Grounding prose in the prompt did not prevent any of
it; a scan of the *visible text* before "done" would have caught all three.

What counts as CITED (the convention the `wicked-garden-draft` skill asks the author to follow):
  * the element — or an ancestor — carries ``data-source="<repo-relative path>[:line]"``
    (several sources: separate with spaces or commas);
  * or the same text block names a repo path inline, e.g. ``(README.md:87)``;
  * or the block carries a footnote marker (``[3]``, ``<sup>``) AND the document has a sources
    block (``data-sources``, or a heading/element whose text starts with "Sources") that lists
    repo paths.
A MOCK/ILLUSTRATION is fine when its container carries ``data-illustrative`` AND a reader can see
the label (the word "illustrative", "example", "mock", "sample" or "hypothetical" inside that
container). A label that lives only in an HTML comment is the F-RECON-009 defect and is reported.

Findings (all fail the floor): ``placeholder`` · ``uncited-number`` · ``mock-label-hidden`` ·
``mock-unlabelled`` · ``dangling-source`` (``data-source`` path missing under ``--repo``) ·
``escaped-source`` (``data-source`` path that leaves every ``--repo`` folder: an absolute path, a
``..`` that climbs out, or a link inside the folder that leads out of it — never read, never a pass) ·
``cite-off`` (``data-source path:N`` exists but the cited lines share no tokens with the block's
own text — the author read a different line than they cited — or they do not state a figure the
text claims, or an inherited ``path:N`` is out of range or does not state the figures it alone
cites) ·
``unsourced-url`` (a URL in the visible text that no file under ``--repo`` mentions) ·
``uncited-url`` (a URL with no ``--repo`` to check against and no ``data-source``).
Exit: 0 clean, 1 findings, 2 usage / unreadable input. Stdlib only.

THE CITATION RULE (#1184) — what text a ``data-source="path:N"`` is verified against:

  **A citation asserts the text of the element that carries it, and is verified against that
  element's own text (its inline children included) — never a sibling's text, never a wider
  block.** So:

  * on the element itself → that element's text;
  * on an inline wrapper (``<b>``, ``<span>``, …) or on the enclosing block → that wrapper's or
    that block's text, because a citation on a block asserts the whole block;
  * on an ancestor ABOVE the block (a ``<section>``) → *inherited*: never checked for word
    overlap, because a section-level citation covers many descendants whose text cannot all
    appear on those lines. Its line must exist (out of range is ``cite-off``), and a block whose
    figures it is the ONLY citation of must find each figure on one of its lines (#1551);
  * path-only (no ``:N``) → provenance only, checked only for existence.

  One check per (source, carrier): the carrier IS the unit of verification, so two inline
  siblings that carry the same source are two checks against two different texts, and a
  block-level citation is one check against the block.

  A citation is VERIFIED when both hold: the cited text shares at least one CONTENT token with
  the claim (an overlap of common words verifies nothing), and no other span of the SAME WIDTH
  in the file shares MORE of them (so a range is judged against the best range of its own width —
  scoring a multi-line union against single lines let any wide range tie — and both sides are
  scored on content tokens, so a line rich in common words cannot outscore the cited one), and
  every FIGURE the claim states is on the cited span, with its unit when it has one (#1551: the
  figure IS the claim, so ``80%`` on the line never verifies ``99%``). Tokens are ``\\W+``
  split, so unicode variants like ``≥`` and ``>=`` produce the same tokens. A verified range is
  a weaker assertion than a verified line, and the summary says how many there were
  (``cited_ranges``).

CLI:
    claims_scan.py <file.html> [--repo <dir> …] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draft._dom import Document, Node, is_rendered, parse  # noqa: E402

PLACEHOLDER_RE = re.compile(
    r"\[\s*PLACEHOLDER\b|\bPLACEHOLDER\s*:|\bTODO\b|\bTBD\b|\bFIXME\b|\bTK\b(?![\w-])|"
    r"\blorem\s+ipsum\b|\bLorem\b|\{\{[^}]*\}\}|\[\s*INSERT\b|<\s*insert\b|\[\s*(?:add|your|company|client)\s+[^\]]{0,40}(?:here|name)\s*\]",
    re.IGNORECASE)
# a repo path: at least one slash or a known doc/code extension, optional :line
PATH_RE = re.compile(
    r"(?<![\w/@:.-])((?:[\w.-]+/)*[\w.-]+\.(?:md|mdx|txt|rst|adoc|json|ya?ml|toml|ts|tsx|js|mjs|cjs|py|rs|go|java|kt|cs|rb|php|sh|html|css|sql|proto|csv|ipynb|lock)(?::\d+(?:-\d+)?)?)(?![\w/])",
    re.IGNORECASE)
# a URL with a scheme, or a bare domain on a common TLD (`ws.wickedagile.com`) — a file name's
# extension (README.md, server.ts) is not a TLD in this list, so paths never match.
URL_RE = re.compile(
    r"https?://[^\s<>\"')\]]+|"
    r"(?<![\w@/.-])(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|ai|app|co|cloud|sh|tech|info|biz|eu|uk|de|fr|us|ca|au)\b"
    r"(?:/[^\s<>\"')\]]*)?",
    re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<![\w.,:/#-])(\d+(?:[.,]\d+)*)(?![\w/:-])")
FOOTNOTE_RE = re.compile(r"\[\d{1,3}\]|[†‡§¶]|\^\d{1,3}")
LABEL_RE = re.compile(r"\b(illustrative|illustration|example|mock(?:-?up)?|sample|hypothetical|not (?:real|measured)|for illustration)\b", re.IGNORECASE)
COPYRIGHT_YEAR_RE = re.compile(r"(?:©|\(c\)|copyright)\s*\d{4}", re.IGNORECASE)
ORDINAL_RE = re.compile(r"^0\d$")  # "01", "02" — section numbering, not a claim
# L2 — number tokens that are structure, not claims: prose dates ("September 12, 2026", "Sep 2026",
# "2026 roadmap" → the year next to a month word), numbered headings ("1. Readable"), "Step 1",
# page footers ("Page 1 of 2", "1 / 2"), and a lone 1–2 digit number that is an element's whole text
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
STRUCTURE_RES = [
    re.compile(rf"\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.IGNORECASE),  # September 12, 2026
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH},?\s+\d{{4}}\b", re.IGNORECASE),   # 12 Sep 2026
    re.compile(rf"\b{_MONTH}\s+\d{{4}}\b", re.IGNORECASE),                                # Sep 2026
    re.compile(r"\b(?:19|20)\d{2}\s+(?:roadmap|edition|release|plan|report|review|q[1-4])\b", re.IGNORECASE),
    re.compile(r"\b(?:q[1-4]|h[12]|fy)\s*(?:19|20)?\d{2}\b", re.IGNORECASE),               # Q3 2026 / FY26
    re.compile(r"^\s*\d{1,3}[.)]\s+(?=\S)"),                                                # "1. Readable"
    re.compile(r"\b(?:step|phase|part|chapter|section|figure|fig\.|table|slide|page|pg\.)\s+\d{1,3}(?:\s+of\s+\d{1,3})?\b", re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}\s*/\s*\d{1,3}\s*$"),                                            # "1 / 2" footer
]
LONE_ORDINAL_RE = re.compile(r"^\d{1,2}$")
SOURCE_ATTRS = ("data-source", "data-sources", "data-src-path", "data-cite")
SKIP_DIRS = {".git", "node_modules", ".venv", "target", "dist", "build", "__pycache__", ".next"}
# matches path:N or path:N-M at end of a source string; group 1 = path, group 2 = line spec
_LINE_SPEC_RE = re.compile(r'^(.*?):(\d+(?:-\d+)?)$')
# sentinel returned by _check_cite_off: file found but could not verify → treated as cite-off
_UNVERIFIABLE = object()
# Common words carry no evidence: a citation whose only overlap with the claim is drawn from this
# set has verified nothing (#1184-B). Digits are never stopwords — a figure IS the claim.
STOPWORDS = frozenset("""
a about across after again all also an and any are as at be been before being between both but by
can could did do does down during each every few for from had has have how if in into is it its
just may might more most much must no not of off on once one only or other our out over per same
should since so some still such than that the their them then there these they this those through
to too under until up us very was we were what when where which while who will with within would
you your
""".split())

# The figure IS the claim (#1551): a line citation verifies a figure only when the cited span
# states it, with its unit when it has one. Both sides are read by ONE tokenizer: a number with its
# sign, decimals and exponent, then the unit after it (attached, or after spaces), every spelling
# of a unit mapped to one canonical form. Byte/bit case is kept (MB is not Mb); words are not.
_UNIT_SPELLINGS = {
    "%": "% percent pct",
    "x": "x ×",
    "ns": "ns nanosecond nanoseconds",
    "us": "us µs μs microsecond microseconds",
    "ms": "ms msec msecs millisecond milliseconds",
    "s": "s sec secs second seconds",
    "min": "min mins minute minutes",
    "h": "h hr hrs hour hours",
    "d": "d day days",
    "wk": "wk wks week weeks",
    "k": "k thousand",
    "million": "million mn",
    "billion": "billion bn",
}
_DATA_UNIT_RE = re.compile(r"^[kmgtp]i?b$", re.IGNORECASE)
_DATA_WORDS = {"kilobyte": "kB", "megabyte": "mB", "gigabyte": "gB", "terabyte": "tB", "petabyte": "pB"}  # canonical: prefix lowercased, B kept
_UNIT_CANON = {sp: canon for canon, spellings in _UNIT_SPELLINGS.items() for sp in spellings.split()}
_UNIT_ALTS = sorted([*_UNIT_CANON, *_DATA_WORDS, *(w + "s" for w in _DATA_WORDS),
                     r"[kKmMgGtTpP]i?[bB]"], key=len, reverse=True)
_UNIT_PATTERN = "|".join(a if a.startswith("[") else re.escape(a) for a in _UNIT_ALTS)
# A figure starts at a word boundary that is not inside another number ("v12", "1.5", "4xx" are
# not figures of their own); a sign counts only there ("80-90" is a range, " -80" is negative).
FIGURE_RE = re.compile(
    r"(?<![\w.,])(?P<sign>[-\u2212+]?)(?P<num>\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?)"
    rf"(?:[ \t\u00a0]*(?P<unit>{_UNIT_PATTERN})(?![A-Za-z0-9_]))?(?![A-Za-z0-9_])")


def _canon_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    if _DATA_UNIT_RE.match(unit):        # kB/KB = kB, but MB (bytes) is not Mb (bits)
        return unit[0].lower() + ("i" if len(unit) == 3 else "") + unit[-1]
    word = unit.lower()
    if word.rstrip("s") in _DATA_WORDS:
        return _DATA_WORDS[word.rstrip("s")]
    return _UNIT_CANON.get(word, _UNIT_CANON.get(unit, word))


def _canon_number(sign: str, number: str) -> str:
    """One spelling per value: 1,200 = 1200, 80.0 = 80, 1e3 = 1000, -80 is not 80. A dotted
    version (12.64.0) or a comma that is not a thousands separator stays as written."""
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", number):
        number = number.replace(",", "")
    if re.fullmatch(r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", number):
        try:
            number = format(Decimal(number).normalize(), "f")
        except InvalidOperation:  # pragma: no cover - the pattern above admits only valid numbers
            pass
        if "." in number:
            number = number.rstrip("0").rstrip(".")
    return ("-" if sign in ("-", "\u2212") else "") + number


def _figures(text: str) -> list[tuple[str, tuple[str, str | None]]]:
    """(as written, (value, unit)) for every figure in ``text``."""
    return [(m.group(0).strip(), (_canon_number(m.group("sign"), m.group("num")), _canon_unit(m.group("unit"))))
            for m in FIGURE_RE.finditer(text)]


def _claim_text(text: str) -> str:
    """The text whose numbers are claims: paths, URLs, copyright years, footnote markers and the
    L2 structure numbers (dates, steps, numbered headings, page footers) removed."""
    out = PATH_RE.sub(" ", URL_RE.sub(" ", text))
    out = COPYRIGHT_YEAR_RE.sub(" ", out)
    for structure in STRUCTURE_RES:
        out = structure.sub(" ", out)
    if LONE_ORDINAL_RE.match(text.strip()):
        return ""                       # a badge / list marker whose whole text is one small number
    return out


def _claim_figures(text: str) -> list[tuple[str, tuple[str, str | None]]]:
    """The figures ``text`` claims (structure numbers, footnote markers and ``01`` ordinals out)."""
    return [f for f in _figures(FOOTNOTE_RE.sub(" ", _claim_text(text))) if not ORDINAL_RE.match(f[1][0])]


def _missing_figures(figures: list[tuple[str, tuple[str, str | None]]], cited: str) -> list[str]:
    """The figures (as written) the cited text does not state: a figure with a unit needs that
    value with that unit; a figure without one needs the value."""
    pairs = {key for _, key in _figures(cited)}
    values = {v for v, _ in pairs}
    return [shown for shown, (v, u) in figures if ((v, u) not in pairs if u else v not in values)]


def _figure_detail(source: str, missing: list[str], lines: list[str], figures) -> str:
    """The cite-off detail for a figure the cited span does not state, naming the line of the file
    that does (when one line states every missing figure)."""
    want = [f for f in figures if f[0] in missing]
    at = next((i + 1 for i, line in enumerate(lines) if not _missing_figures(want, line)), None)
    hint = f" — line {at} states {'them' if len(missing) > 1 else 'it'}" if at else ""
    noun = "figures" if len(missing) > 1 else "figure"
    return (f"data-source {source} does not state the {noun} {', '.join(missing)} — cite the line that "
            f"carries it, or correct the figure to what the source says{hint}")


_FOOTNOTE_SUP_RE = re.compile(r"^\s*\[?(?:\d{1,3}|[*†‡§¶])\]?\s*$")


def _figure_text(node: Node, skip_cited: bool = False) -> str:
    """The rendered text a citation on ``node`` asserts figures of: its own text and its rendered
    INLINE descendants — never a nested block (it is judged by its own citations), never a hidden
    element, never a footnote marker (``<sup>1</sup>``). ``skip_cited`` also leaves out an inline
    descendant that carries its own ``data-source`` (that one covers its text)."""
    out: list[str] = []

    def walk(n: Node) -> None:
        for c in n.children:
            if c.tag == "#text":
                out.append(c.text)
            elif (c.tag in _INLINE_TAGS and "hidden" not in c.attrs
                  and not (c.tag == "sup" and _FOOTNOTE_SUP_RE.match(c.all_text()))
                  and not (skip_cited and _direct_sources_on(c))):
                walk(c)
    if is_rendered(node):
        walk(node)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


@dataclass
class Finding:
    kind: str
    path: str
    text: str
    detail: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "path": self.path, "text": self.text, "detail": self.detail}


def _sources_on(node: Node) -> list[str]:
    out: list[str] = []
    for n in [node, *node.ancestors()]:
        for attr in SOURCE_ATTRS:
            v = n.attrs.get(attr, "").strip()
            if v:
                out.extend(re.split(r"[\s,;]+", v))
    return [s for s in out if s]


def _direct_sources_on(node: Node) -> list[str]:
    """Sources declared directly on this element only (not inherited from ancestors)."""
    out: list[str] = []
    for attr in SOURCE_ATTRS:
        v = node.attrs.get(attr, "").strip()
        if v:
            out.extend(re.split(r"[\s,;]+", v))
    return [s for s in out if s]


def _cite_tokens(text: str) -> set[str]:
    """Token set for citation overlap — split on \\W+, keep tokens len≥2 or digit-only, lowercase —
    plus each figure's value and unit, so ``80ms`` and ``80 ms``, ``1,200`` and ``1200`` share
    tokens on both sides (#1551)."""
    tokens = {t.lower() for t in re.split(r'\W+', text) if len(t) >= 2 or t.isdigit()}
    for _, (value, unit) in _figures(text):
        tokens.add(value)
        if unit:
            tokens.add(unit.lower())
    return tokens


def _best_span(lines: list[str], content_tokens: set[str], width: int) -> tuple[int | None, int]:
    """The (1-based start, score) of the span of ``width`` lines that best matches content_tokens.

    Two rules meet here. Scoring a span against spans of its OWN width (#1184-B): a range's cited
    text is the union of its lines, so comparing it with single lines let any wide range tie or
    win; for width 1 this is the per-line scan it replaces. And scoring on CONTENT tokens only
    (codex on #1184): counting stopwords let a line that shares nothing but "it is" outscore the
    line that carries the claim's one content word, and report a correct citation as cite-off.
    """
    best_n, best_score = None, 0
    for i in range(max(1, len(lines) - width + 1)):
        score = len(content_tokens & _cite_tokens("\n".join(lines[i:i + width])))
        if score > best_score:
            best_score, best_n = score, i + 1
    return best_n, best_score


def _cited_span(source: str, repos: list[str]) -> tuple[list[str], int, int] | str | None | object:
    """Read the lines ``source`` (``path:N`` / ``path:N-M``) cites: ``(lines, start, end)`` with
    0-based inclusive bounds; a detail string for an invalid or out-of-range spec; ``None`` for a
    path-only citation; ``_UNVERIFIABLE`` when no folder holds a readable file at that path."""
    m = _LINE_SPEC_RE.match(source)
    if m is None:
        return None                     # path-only, nothing to verify
    rel_path, line_spec = m.group(1), m.group(2)
    for repo in repos:
        p = _confined(repo, rel_path)
        if p is None or not p.is_file():  # outside the folder (#1530), or a directory
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue                    # try next repo; formerly aborted the whole search
        if '-' in line_spec:
            s_int, e_int = (int(x) for x in line_spec.split('-', 1))
            if s_int > e_int:
                return f"data-source {source} has invalid range ({s_int} > {e_int})"
            if s_int < 1 or s_int > len(lines) or e_int < 1 or e_int > len(lines):
                return f"data-source {source} is past end of file ({len(lines)} lines)"
            return lines, s_int - 1, e_int - 1
        lnum = int(line_spec)
        if lnum < 1 or lnum > len(lines):
            return f"data-source {source} is past end of file ({len(lines)} lines)"
        return lines, lnum - 1, lnum - 1
    return _UNVERIFIABLE                # file not found in any repo


def _whole_file(source: str, repos: list[str]) -> str | None:
    """The text of the file a path-only ``source`` names inside a folder, or ``None``."""
    for repo in repos:
        p = _confined(repo, _source_path(source))
        if p is not None and p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return None


def _check_cite_off(source: str, claim_text: str, repos: list[str],
                    figure_text: str | None = None) -> str | None | object:
    """Check whether source's cited lines carry claim_text — the text of the element that carries
    the citation (THE RULE, see the module docstring). ``figure_text`` is the part of it whose
    figures the citation asserts (``_figure_text``: rendered inline text, no nested block, no
    footnote marker); it defaults to ``claim_text``.

    Returns:
      None            — path-only citation (no :N suffix); caller skips it.
      ""              — verified clean: a content word is shared, no same-width span elsewhere
                        in the file matches the claim better, and every figure the claim states
                        is on the cited span (#1551).
      _UNVERIFIABLE   — file unreadable, empty token set, or not found; caller treats as cite-off.
      non-empty str   — cite-off detail message; caller reports a finding.
    """
    if _LINE_SPEC_RE.match(source) is None:
        return None                     # path-only, nothing to verify
    claim_tokens = _cite_tokens(claim_text)
    if not claim_tokens:
        return _UNVERIFIABLE            # token set empty after filtering — cannot verify
    span = _cited_span(source, repos)
    if not isinstance(span, tuple):
        return span                     # a range/past-end detail, or _UNVERIFIABLE
    lines, start, end = span
    cited = "\n".join(lines[start:end + 1])
    # Only CONTENT tokens are evidence, on both sides of the comparison: an overlap of common
    # words verifies nothing, and a line rich in them must not outscore the cited one.
    content = claim_tokens - STOPWORDS
    overlap = content & _cite_tokens(cited)
    best_n, best_score = _best_span(lines, content, end - start + 1)
    hint = f" — nearest match: line {best_n}" if best_n and best_n != start + 1 else ""
    if not overlap:
        return (f"data-source {source} shares only common words with this text — a citation "
                f"verifies nothing without a content word in common{hint}")
    if best_score > len(overlap):
        return f"data-source {source} does not carry this text{hint}"
    figures = _claim_figures(claim_text if figure_text is None else figure_text)
    missing = _missing_figures(figures, cited)
    if missing:                         # the words match, the figure does not (#1551)
        return _figure_detail(source, missing, lines, figures)
    return ""                           # verified: best or tied-best span of its own width


def _illustrative_container(node: Node) -> Node | None:
    for n in [node, *node.ancestors()]:
        if "data-illustrative" in n.attrs or "data-mock" in n.attrs:
            return n
    return None


def _has_sources_block(doc: Document) -> bool:
    for el in doc.elements():
        if "data-sources" in el.attrs and PATH_RE.search(el.all_text()):
            return True
        txt = el.direct_text()
        if txt and re.match(r"^(sources?|references?|grounding)\b", txt, re.IGNORECASE):
            container = el.parent if el.parent is not None else el
            if PATH_RE.search(container.all_text()):
                return True
    return False


def _claim_blocks(doc: Document) -> list[Node]:
    """Block-level text units: the nearest element with own text whose parent is not itself a
    text-only inline wrapper — practically: every rendered element with own text, but a span's
    numbers are judged with its parent block's text so an inline citation counts."""
    return [el for el in doc.elements() if el.direct_text() and is_rendered(el) and el.tag != "br"]


_INLINE_TAGS = frozenset("span b strong i em u small sup sub code a abbr mark time s del ins q cite kbd var".split())


def _block_of(node: Node) -> Node:
    n = node
    while n.parent is not None and n.parent.tag != "" and n.tag in _INLINE_TAGS:
        n = n.parent
    return n


def _citation_carriers(el: Node, block: Node) -> list[Node]:
    """Every element that can carry a line citation covering el's text: el itself, each inline
    wrapper between el and its block, then the block. A citation on anything above the block is
    inherited: never checked for word overlap, but range- and figure-checked once per block in
    scan_document (THE RULE, see the module docstring)."""
    chain = [el]
    node = el
    while node is not block:
        parent = node.parent
        if parent is None or parent.tag == "":
            break                       # block is not an ancestor — nothing further to walk
        node = parent
        chain.append(node)
    return chain


def _nearby_comments(el: Node, block: Node) -> list[str]:
    """HTML comments a reader never sees but an author may have used as the only label of a
    mock: comments anywhere inside the block (or its parent) and comments immediately preceding
    the element or any of its ancestors up to three levels."""
    out: list[str] = [n.text for n in block.walk() if n.tag == "#comment"]
    node: Node | None = el
    for _ in range(4):
        if node is None or node.tag == "":
            break
        out.extend(node.preceding_comments())
        node = node.parent
    return out


def _repo_files(repos: list[str]) -> list[Path]:
    files: list[Path] = []
    for repo in repos:
        root = Path(repo)
        if not root.is_dir():
            continue
        real_root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            # A link out of the folder is not the folder's content (#1530): a directory that resolves
            # outside it (a Windows junction os.walk descends into) is pruned, and so is a file link.
            try:
                inside = Path(dirpath).resolve().is_relative_to(real_root)
            except (OSError, RuntimeError):
                inside = False
            if not inside:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    if p.is_symlink() and not p.resolve().is_relative_to(real_root):
                        continue
                    if p.stat().st_size <= 2_000_000:
                        files.append(p)
                except (OSError, RuntimeError):  # a link loop is RuntimeError before Python 3.13
                    continue
    return files


_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _absolute_spelling(rel_path: str) -> bool:
    """A citation is repo-relative by convention: an absolute spelling (``/etc/hosts``, ``C:\\x``)
    joined onto a folder would REPLACE it, so it is refused outright (#1530)."""
    return (not rel_path or Path(rel_path).is_absolute() or rel_path[0] in "/\\"
            or bool(_DRIVE_RE.match(rel_path)))


def _resolve_in(repo: str, rel_path: str) -> tuple[str, Path | None]:
    """Where ``rel_path`` leads from ``repo``, every ``..`` and every link followed (#1530):
    ``("in", path)`` under the resolved folder, ``("out", None)`` outside it (an absolute spelling,
    a ``..`` that climbs out, a link that leads out), ``("bad", None)`` when it cannot be resolved
    (a link loop, a NUL byte) — unresolvable is not an escape."""
    if _absolute_spelling(rel_path):
        return "out", None
    try:
        root = Path(repo).resolve()
        p = (root / rel_path).resolve()
    except (OSError, RuntimeError, ValueError):
        return "bad", None
    return ("in", p) if p.is_relative_to(root) else ("out", None)


def _confined(repo: str, rel_path: str) -> Path | None:
    """The path ``rel_path`` names inside ``repo``, resolved, or ``None`` when it does not stay inside
    it — so ``../notes.json`` and a link in the folder that points out of it are never read."""
    where, p = _resolve_in(repo, rel_path)
    return p if where == "in" else None


def _source_path(rel: str) -> str:
    """The path part of a ``data-source`` value (``path:N`` / ``path:N-M`` / ``path``)."""
    m = _LINE_SPEC_RE.match(rel)
    return m.group(1) if m else rel


def _source_status(rel: str, repos: list[str]) -> str:
    """``found`` when the cited path exists inside one of the folders; else ``escaped`` when it leads
    out of one (``escaped-source``), else ``missing`` (``dangling-source``). A folder the path is
    merely absent from never turns an escape into a missing file."""
    rel_path = _source_path(rel)
    escaped = False
    for repo in repos:
        where, p = _resolve_in(repo, rel_path)
        if where == "in" and p is not None and p.exists():
            return "found"
        escaped = escaped or where == "out"
    return "escaped" if escaped else "missing"


def _path_exists_in_repos(rel: str, repos: list[str]) -> bool:
    rel_path = _source_path(rel)
    for repo in repos:
        p = _confined(repo, rel_path)
        if p is not None and p.exists():
            return True
    return False


def _url_in_repos(url: str, files: list[Path]) -> bool:
    needle = url.rstrip("/.,;").lower()
    bare = re.sub(r"^https?://(www\.)?", "", needle)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if needle in text or bare in text:
            return True
    return False


def scan_document(html: str, repos: list[str] | None = None) -> tuple[list[Finding], dict]:
    repos = [r for r in (repos or []) if Path(r).is_dir()]
    doc = parse(html)
    findings: list[Finding] = []
    seen: set[tuple] = set()
    has_sources = _has_sources_block(doc)
    repo_files = _repo_files(repos) if repos else []
    stats = {"blocks": 0, "numbers": 0, "urls": 0, "cited_numbers": 0, "cited_lines": 0,
             "cited_ranges": 0, "cite_off": 0, "sources_block": has_sources, "repos": repos}

    def add(kind: str, node: Node, text: str, detail: str) -> None:
        # The key is the NODE (identity, not `path()` — which carries no sibling index) plus the
        # detail: two sibling carriers with the same tag, text and bad source are two findings, and
        # two different bad citations on one element are two findings, so the findings list and
        # stats["cite_off"] can never disagree (#1184; codex review).
        key = (kind, id(node), text[:60], detail)
        if key in seen:
            return
        seen.add(key)
        findings.append(Finding(kind, node.path(), text[:100], detail))

    checked_sources: set[str] = set()
    # (source, id(carrier)) — one check per source per carrying element: two inline siblings that
    # carry the same source are two distinct checks, a block-level citation is checked once (#1184)
    checked_cite_off: set[tuple] = set()
    checked_blocks: set[int] = set()    # blocks whose inherited citations were checked (#1551)
    for el in _claim_blocks(doc):
        stats["blocks"] += 1
        own = el.direct_text()
        if PLACEHOLDER_RE.search(own):
            add("placeholder", el, own, "placeholder text is visible in the deliverable — move the gap to the notes/reply, never into the document")
        block = _block_of(el)
        block_text = block.all_text()
        sources = _sources_on(el)
        for s in sources:
            if repos and s not in checked_sources:
                checked_sources.add(s)
                status = _source_status(s, repos)
                if status == "escaped":
                    add("escaped-source", el, s,
                        "data-source points outside the folders the document is checked against (an absolute "
                        "path, a '..' or a link that leads out) — cite a file inside the project, by its path from the project root")
                elif status == "missing":
                    add("dangling-source", el, s, "data-source names a path that does not exist under --repo")
        # cite-off: every carrier of a line citation — el, its inline wrappers, its block — is
        # verified against ITS OWN text (THE RULE, #1184; the block carrier covers #1181-A)
        if repos:
            for carrier in _citation_carriers(el, block):
                carrier_text = carrier.all_text()
                for s in _direct_sources_on(carrier):
                    m = _LINE_SPEC_RE.match(s)
                    if not (m and _path_exists_in_repos(m.group(1), repos)):
                        continue
                    cite_key = (s, id(carrier))
                    if cite_key in checked_cite_off:
                        continue
                    checked_cite_off.add(cite_key)
                    detail = _check_cite_off(s, carrier_text, repos, _figure_text(carrier))
                    if detail is None:
                        pass                        # path-only: not a line citation, count nothing
                    elif detail is _UNVERIFIABLE:
                        stats["cite_off"] += 1
                        add("cite-off", carrier, carrier_text, f"data-source {s} could not be verified")
                    elif detail:
                        stats["cite_off"] += 1
                        add("cite-off", carrier, carrier_text, detail)
                    else:
                        stats["cited_lines"] += 1
                        if "-" in m.group(2):
                            stats["cited_ranges"] += 1
        inline_paths = PATH_RE.findall(block_text)
        footnoted = has_sources and bool(FOOTNOTE_RE.search(block_text))
        cited = bool(sources) or bool(inline_paths) or footnoted
        # An inherited line citation (on an ancestor above the block, #1551): its line must exist,
        # and when inherited citations are the ONLY citation of the block's figures, each figure
        # must be on one of the inherited lines (or in a file an ancestor cites whole). Word
        # overlap stays unchecked: a section's descendants say many different things. Once per block.
        if repos and id(block) not in checked_blocks:
            checked_blocks.add(id(block))
            inherited = [(s, anc) for anc in block.ancestors() for s in _direct_sources_on(anc)]
            spans: list[str] = []
            whole: list[str] = []
            for s, anc in inherited:
                if not _path_exists_in_repos(s, repos):
                    continue                # dangling-source / escaped-source already reported
                if not _LINE_SPEC_RE.match(s):
                    whole.append(s)         # path-only: provenance; holds figures only beside a line
                    continue
                span = _cited_span(s, repos)
                if isinstance(span, tuple):
                    lines, start, end = span
                    spans.append("\n".join(lines[start:end + 1]))
                elif (s, id(anc)) not in checked_cite_off:
                    checked_cite_off.add((s, id(anc)))
                    stats["cite_off"] += 1
                    add("cite-off", anc, anc.all_text(),
                        span if isinstance(span, str) else f"data-source {s} could not be verified")
            own_cite = bool(_direct_sources_on(block)) or bool(inline_paths) or footnoted
            figures = _claim_figures(_figure_text(block, skip_cited=True)) if spans and not own_cite else []
            texts = spans + [t for t in (_whole_file(w, repos) for w in whole) if t is not None]
            missing = [f for f in figures if all(_missing_figures([f], t) for t in texts)]
            if missing:
                stats["cite_off"] += 1
                cited_by = ", ".join(s for s, _ in inherited)
                add("cite-off", block, block_text,
                    f"the citation this text inherits ({cited_by}) does not state the "
                    f"{'figures' if len(missing) > 1 else 'figure'} {', '.join(f[0] for f in missing)} — "
                    "put a data-source on this element naming the line that carries it, or correct the figure")
        illustrative = _illustrative_container(el)
        labelled = illustrative is not None and bool(LABEL_RE.search(illustrative.all_text()))

        # URLs
        for url in URL_RE.findall(own):
            stats["urls"] += 1
            if repos:
                if not _url_in_repos(url, repo_files):
                    add("unsourced-url", el, url, "no file under --repo mentions this URL — an invented or misremembered address")
            elif not cited:
                add("uncited-url", el, url, "URL with no data-source and no repo to check it against")

        # numbers
        numbers = [n for n in NUMBER_RE.findall(_claim_text(own)) if not ORDINAL_RE.match(n)]
        if not numbers:
            continue
        stats["numbers"] += len(numbers)
        if cited:
            stats["cited_numbers"] += len(numbers)
            continue
        if illustrative is not None:
            if labelled:
                continue
            add("mock-unlabelled", el, own, "data-illustrative container has no visible label — a reader cannot tell the figures are not real")
            continue
        if any(LABEL_RE.search(c) for c in _nearby_comments(el, block)):
            add("mock-label-hidden", el, own,
                "figures are called illustrative only in an HTML comment — label the mock visibly and mark its container data-illustrative")
        else:
            add("uncited-number", el, own,
                f"number(s) {', '.join(numbers[:5])} with no data-source, inline repo path or footnote — cite the file (path:line) or remove the figure")
    return findings, stats


def run(path: str, repos: list[str] | None = None) -> dict:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    findings, stats = scan_document(html, repos)
    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    return {
        "check": "claims",
        "file": path,
        "ok": not findings,
        "stats": stats,
        "by_kind": by_kind,
        "findings": [f.as_dict() for f in findings],
        "summary": (
            f"claims: {stats['blocks']} text blocks, {stats['numbers']} numbers ({stats['cited_numbers']} cited), "
            f"{stats['urls']} URLs, {stats['cited_lines']} cited lines "
            # a range verifies a span, not a line — a weaker assertion, so it is named (#1184)
            f"({stats['cited_ranges']} by line range, {stats['cite_off']} cite-off) — "
            + ("clean" if not findings else ", ".join(f"{v} {k}" for k, v in sorted(by_kind.items())))
        ),
    }


def safe_console() -> None:
    """M1 — never crash on a code-page console (Windows piped stdout is cp1252 on Python < 3.15)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def format_finding(f: dict) -> str:
    return f"  [{f['kind']}] {f['path']}  \"{f['text']}\"  — {f['detail']}"


def main(argv: list[str] | None = None) -> int:
    safe_console()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("html", help="the self-contained HTML deliverable")
    ap.add_argument("--repo", action="append", default=[],
                    help="a repository snapshot the claims must trace to (repeatable)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = run(args.html, args.repo)
    except OSError as exc:
        print(json.dumps({"check": "claims", "ok": False, "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["summary"])
        for f in report["findings"]:
            print(format_finding(f))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
