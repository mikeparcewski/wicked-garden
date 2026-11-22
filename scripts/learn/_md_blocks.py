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
    r"</?(?:" + "|".join(_HTML_TAGS.split(" ")) + r")(?=[ \t\n>]|/>|$)", re.I | re.ASCII
)
_ATTR = r"[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t\n]*=[ \t\n]*(?:[^ \t\n\"'=<>`]+|'[^']*'|\"[^\"]*\"))?"
_COMPLETE_TAG = re.compile(
    r"(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t\n]+" + _ATTR + r")*[ \t\n]*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*[ \t\n]*>)[ \t]*(?:\n)?$"
)
_RAW_START = re.compile(r"<(script|pre|style|textarea)(?=[ \t\n>]|$)", re.I | re.ASCII)
_RAW_END = re.compile(r"</(?:script|pre|style|textarea)>", re.I | re.ASCII)
_TYPE_SEVEN_EXCLUDED = re.compile(r"<(?:script|pre|style|textarea)(?=[ \t\n/>]|$)", re.I | re.ASCII)
_STRUCTURAL_PREFIX = re.compile(r"[ \t>*+0-9().-]*")


class _Containers(list[tuple[str, int]]):
    """Append-only container path with a constant-time lists-only suffix check."""

    def __init__(self) -> None:
        super().__init__()
        self.last_quote = -1

    def append(self, container: tuple[str, int]) -> None:
        if container[0] == "quote":
            self.last_quote = len(self)
        super().append(container)


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


def _prefix(line: str, previous: _Containers, paragraph: bool,
            open_containers: bool = True):
    """Continue containers, then open explicit quotes and list items."""
    pos = 0
    containers = _Containers()
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
    # Every nested marker used to rescan the remaining suffix for a thematic
    # break and copy the whole line to locate its end. Compute both once.
    content_end = len(line) - int(line.endswith("\n"))
    suffix_start, third_last = _thematic_suffix(line, content_end)
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
            paragraph = False
            continue
        if suffix_start <= end <= third_last:
            break
        marker = _LIST.match(line, end)
        if not marker:
            break
        ordered = "0" <= line[end] <= "9"
        list_kind = "list:" + (line[marker.end() - 1] if ordered else line[end])
        sibling = (len(containers) < len(previous)
                   and previous[len(containers)][0].startswith("list:"))
        # An ordered list can interrupt a paragraph only when it starts at 1.
        # A sibling item continues its existing list, so its number is unrestricted.
        if paragraph and not sibling and ordered and int(line[end:marker.end() - 1]) != 1:
            break
        after, padding = _indent(line, marker.end())
        if paragraph and not sibling and after >= content_end:
            break
        pad = padding if 1 <= padding <= 4 else 1
        pos = _up_to(line, marker.end(), pad)
        containers.append((list_kind, width + marker.end() - end + pad))
        added = True
        paragraph = False
    return pos, containers, continued, added


def _thematic_suffix(line: str, end: int) -> tuple[int, int]:
    """Bounds where a suffix has three matching markers and only space/tab.

    Inspect the homogeneous suffix once, rather than at every list depth. A
    container can begin a thematic break only at/before its third-last marker.
    """
    p = end - 1
    while p >= 0 and line[p] in " \t":
        p -= 1
    if p < 0 or line[p] not in "*_-":
        return 0, -1
    marker = line[p]
    count, third_last = 0, -1
    while p >= 0 and (line[p] == marker or line[p] in " \t"):
        if line[p] == marker:
            count += 1
            if count == 3:
                third_last = p
        p -= 1
    return p + 1, third_last


def _html_start(line: str, pos: int, paragraph: bool) -> str | None:
    raw = _RAW_START.match(line, pos)
    if raw:
        return "raw"
    for start, end in (("<!--", "-->"), ("<?", "?>"), ("<![CDATA[", "]]>")):
        if line.startswith(start, pos):
            return end
    if re.match(r"<![A-Za-z]", line[pos:pos + 3]):
        return ">"
    if _HTML_BLOCK_TAG.match(line, pos):
        return "blank"
    if (not paragraph and not _TYPE_SEVEN_EXCLUDED.match(line, pos)
            and _COMPLETE_TAG.match(line, pos)):
        return "blank"
    return None


def _html_closed(ending: str, line: str, pos: int) -> bool:
    if ending == "raw":
        return bool(_RAW_END.search(line, pos))
    return ending != "blank" and ending in line[pos:]


def blocks(text: str, code: list[tuple[int, int]] | None = None) -> list[tuple[str, str, list[int]]]:
    """Yield inline paragraphs and raw HTML, mapped into normalised source text.

    Container continuations are consumed before leaf blocks. Ambiguous lazy
    continuation stays inline; it is never silently classified as code.
    When ``code`` is a list, each source line of a fenced or indented code
    block (fence lines included) is appended to it as a ``(start, end)`` span.
    """
    if code is None:
        code = []
    result: list[tuple[str, str, list[int]]] = []
    pieces: list[str] = []
    offsets: list[int] = []
    containers = _Containers()
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
        blank = end == len(line) or line[end:] == "\n"
        # Blank lines need no list indentation. Block quotes still require their
        # markers when their child is a fence or raw HTML rather than a paragraph.
        if (blank and not continued and not added
                and containers.last_quote < len(next_containers)):
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
            blank = end == len(line) or line[end:] == "\n"

        if fence:
            code.append((offset, offset + len(original)))
            char, count = fence
            close = _FENCE.match(line, end) if width <= 3 else None
            if (close and close[1][0] == char and len(close[1]) >= count
                    and not close[2].strip(" \t")):
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

        if added:
            # The outer paragraph ends before the new container's first leaf
            # is classified, including indented code and noninterrupting HTML.
            flush()
            indented = False

        if blank:
            flush()
            containers = next_containers if continued or added else _Containers()
            offset += len(original)
            continue

        opening = _FENCE.match(line, end) if width <= 3 else None
        if opening and (opening[1][0] != "`" or "`" not in opening[2]):
            flush()
            fence = (opening[1][0], len(opening[1]))
            code.append((offset, offset + len(original)))
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
            code.append((offset, offset + len(original)))
            containers = next_containers
            offset += len(original)
            continue
        if not continued and pieces:
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
