"""Block boundaries and source maps for the learn link reader."""

from __future__ import annotations

import re


_LIST = re.compile(r"(?:[*+-]|[0-9]{1,9}[.)])(?=[ \t\n]|$)")
_FENCE = re.compile(r"(`{3,}|~{3,})([^\n]*)")
_ATX = re.compile(r"#{1,6}(?:[ \t]|$)")
_SETEXT = re.compile(r"(?:=+|-+)[ \t]*(?:\n)?$")
_THEMATIC = re.compile(r"(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})(?:\n)?$")
_HTML_TAGS = (
    "address article aside base basefont blockquote body caption center col colgroup dd details "
    "dialog dir div dl dt fieldset figcaption figure footer form frame frameset h1 h2 h3 h4 h5 h6 "
    "head header hr html iframe legend li link main menu menuitem nav noframes ol optgroup option "
    "p param search section summary table tbody td tfoot th thead title tr track ul"
)
_HTML_BLOCK_TAG = re.compile(
    r"</?(?:" + "|".join(_HTML_TAGS.split()) + r")(?=[ \t\n>]|/>|$)", re.I
)
_ATTR = r"[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t\n]*=[ \t\n]*(?:[^ \t\n\"'=<>`]+|'[^']*'|\"[^\"]*\"))?"
_COMPLETE_TAG = re.compile(
    r"(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t\n]+" + _ATTR + r")*[ \t\n]*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*[ \t\n]*>)[ \t]*(?:\n)?$"
)
_RAW_START = re.compile(r"<(script|pre|style|textarea)(?=[ \t\n>]|$)", re.I)
_RAW_ENDS = {tag: re.compile(r"</" + tag + r">", re.I)
             for tag in ("script", "pre", "style", "textarea")}
_STRUCTURAL_PREFIX = re.compile(r"[ \t>*+0-9().-]*")


def _structural_tabs(line: str, offset: int) -> tuple[str, list[int] | None]:
    """Expand structural tabs with a source map, retaining partial-tab spaces.

    Stop before inline syntax so tabs inside destinations and HTML attributes
    remain literal. Every expanded space maps to its original tab character.
    """
    end = _STRUCTURAL_PREFIX.match(line).end()
    if "\t" not in line[:end]:
        return line, None
    chars: list[str] = []
    offsets: list[int] = []
    column = 0
    for index in range(end):
        char = line[index]
        width = 4 - column % 4 if char == "\t" else 1
        chars.append(" " * width if char == "\t" else char)
        offsets.extend([offset + index] * width)
        column += width
    chars.append(line[end:])
    offsets.extend(range(offset + end, offset + len(line)))
    return "".join(chars), offsets


def _indent(line: str, pos: int) -> tuple[int, int]:
    """Return the end and width of structural whitespace."""
    width = 0
    column = pos
    while pos < len(line) and line[pos] in " \t":
        width += 1 if line[pos] == " " else 4 - (column + width) % 4
        pos += 1
    return pos, width


def _up_to(line: str, pos: int, width: int) -> int:
    used = 0
    column = pos
    while pos < len(line) and line[pos] in " \t" and used < width:
        used += 1 if line[pos] == " " else 4 - (column + used) % 4
        pos += 1
    return pos


def _prefix(line: str, previous: list[tuple[str, int]], paragraph: bool,
            open_containers: bool = True):
    """Continue containers, then open explicit quotes and list items."""
    pos = 0
    containers = []
    for kind, indent in previous:
        end, width = _indent(line, pos)
        if kind == "quote":
            if width > 3 or end == len(line) or line[end] != ">":
                break
            pos = end + 1
            if pos < len(line) and line[pos] in " \t":
                pos += 1
        else:
            if width < indent:
                break
            pos = _up_to(line, pos, indent)
        containers.append((kind, indent))
    continued = len(containers) == len(previous)
    added = False
    if not open_containers:
        return pos, containers, continued, added
    while pos < len(line):
        end, width = _indent(line, pos)
        if width > 3 or end == len(line):
            break
        if line[end] == ">":
            pos = end + 1
            if pos < len(line) and line[pos] in " \t":
                pos += 1
            containers.append(("quote", 0))
            added = True
            continue
        if _THEMATIC.match(line, end):
            break
        marker = _LIST.match(line, end)
        if not marker:
            break
        list_kind = "list:" + (line[marker.end() - 1] if line[end].isdigit() else line[end])
        sibling = (len(containers) < len(previous)
                   and previous[len(containers)][0].startswith("list:"))
        # An ordered list can interrupt a paragraph only when it starts at 1.
        # A sibling item continues its existing list, so its number is unrestricted.
        if paragraph and not sibling and line[end].isdigit() and line[end:marker.end() - 1] != "1":
            break
        after, padding = _indent(line, marker.end())
        if paragraph and not sibling and after >= len(line.rstrip("\n")):
            break
        pad = padding if 1 <= padding <= 4 else 1
        pos = _up_to(line, marker.end(), pad)
        containers.append((list_kind, width + marker.end() - end + pad))
        added = True
    return pos, containers, continued, added


def _html_start(line: str, pos: int, paragraph: bool) -> str | None:
    raw = _RAW_START.match(line, pos)
    if raw:
        return "raw:" + raw[1].lower()
    for start, end in (("<!--", "-->"), ("<?", "?>"), ("<![CDATA[", "]]>")):
        if line.startswith(start, pos):
            return end
    if re.match(r"<![A-Z]", line[pos:pos + 3]):
        return ">"
    if _HTML_BLOCK_TAG.match(line, pos):
        return "blank"
    if not paragraph and _COMPLETE_TAG.match(line, pos):
        return "blank"
    return None


def _html_closed(ending: str, line: str, pos: int) -> bool:
    if ending.startswith("raw:"):
        return bool(_RAW_ENDS[ending[4:]].search(line, pos))
    return ending != "blank" and ending in line[pos:]


def blocks(text: str) -> list[tuple[str, str, list[int]]]:
    """Yield inline paragraphs and raw HTML, mapped into normalised source text.

    Container continuations are consumed before leaf blocks. Ambiguous lazy
    continuation stays inline; it is never silently classified as code.
    """
    result: list[tuple[str, str, list[int]]] = []
    pieces: list[str] = []
    offsets: list[int] = []
    containers: list[tuple[str, int]] = []
    fence: tuple[str, int] | None = None
    html_end: str | None = None
    offset = 0
    indented = False
    source_map: list[int] | None = None

    def flush(kind: str = "inline") -> None:
        nonlocal pieces, offsets
        if pieces:
            result.append((kind, "".join(pieces), offsets))
            pieces, offsets = [], []

    def append(line: str, start: int) -> None:
        pieces.append(line[start:])
        offsets.extend(source_map[start:] if source_map is not None
                       else range(offset + start, offset + len(line)))

    # CommonMark recognises LF after normalisation, not Python's additional
    # Unicode splitlines separators (which remain ordinary inline characters).
    for line_match in re.finditer(r"[^\n]*\n|[^\n]+$", text):
        original = line_match[0]
        line, source_map = _structural_tabs(original, offset)
        pos, next_containers, continued, added = _prefix(
            line, containers, bool(pieces) and html_end is None,
            open_containers=fence is None and html_end is None,
        )
        end, width = _indent(line, pos)
        blank = not line[end:].strip("\n")
        # Blank lines need no list indentation. Block quotes still require their
        # markers when their child is a fence or raw HTML rather than a paragraph.
        if (blank and not continued and not added
                and all(kind.startswith("list:")
                        for kind, _ in containers[len(next_containers):])):
            next_containers = containers
            continued = True
        closed_leaf = False
        if fence and not continued:
            fence = None
            closed_leaf = True
        if html_end and not continued:
            flush("html")
            html_end = None
            closed_leaf = True
        if closed_leaf:
            # A new sibling container belongs to the next block, never to the
            # contents of an active fenced-code or HTML leaf.
            pos, next_containers, continued, added = _prefix(
                line, containers, bool(pieces)
            )
            end, width = _indent(line, pos)
            blank = not line[end:].strip("\n")

        if fence:
            char, count = fence
            close = _FENCE.match(line, end) if width <= 3 else None
            if (close and close[1][0] == char and len(close[1]) >= count
                    and not close[2].strip()):
                fence = None
            offset += len(original)
            continue

        if html_end:
            if html_end == "blank" and blank:
                flush("html")
                html_end = None
            else:
                append(line, pos)
                if _html_closed(html_end, line, pos):
                    flush("html")
                    html_end = None
            containers = next_containers
            offset += len(original)
            continue

        if blank:
            flush()
            containers = next_containers if continued or added else []
            offset += len(original)
            continue

        opening = _FENCE.match(line, end) if width <= 3 else None
        if opening and (opening[1][0] != "`" or "`" not in opening[2]):
            flush()
            fence = (opening[1][0], len(opening[1]))
            containers = next_containers
            indented = False
            offset += len(original)
            continue

        start_html = _html_start(line, end, bool(pieces)) if width <= 3 else None
        if start_html:
            flush()
            append(line, pos)
            html_end = start_html
            if _html_closed(start_html, line, end):
                flush("html")
                html_end = None
            containers = next_containers
            offset += len(original)
            continue

        if width <= 3 and _THEMATIC.match(line, end):
            flush()
            containers = next_containers
            indented = False
            offset += len(original)
            continue
        if width <= 3 and _SETEXT.match(line, end) and pieces:
            flush()
            containers = next_containers
            offset += len(original)
            continue
        if width <= 3 and _ATX.match(line, end):
            flush()
            # Keeping the opening hashes also prevents reference definitions in headings.
            append(line, end)
            flush()
            containers = next_containers
            indented = False
            offset += len(original)
            continue

        if width >= 4 and not pieces:
            indented = True
            containers = next_containers
            offset += len(original)
            continue
        if added:
            flush()
        elif not continued and pieces:
            # Missing container markers are legal only as lazy paragraph continuation.
            next_containers = containers
        elif indented:
            flush()
        append(line, pos)
        containers = next_containers
        indented = False
        offset += len(original)
    flush("html" if html_end else "inline")
    return result
