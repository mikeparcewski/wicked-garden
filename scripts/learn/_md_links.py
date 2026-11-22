"""Read CommonMark 0.31.2 links, with GFM autolinks, without rendering HTML.

Blocks are separated before inlines; references are resolved in a second pass.
Only syntax that affects destinations is interpreted. Emphasis needs no tree.
Ambiguous HTML is deliberately reported conservatively, including duplicate attrs.
"""

from array import array
from dataclasses import dataclass, replace
from html import unescape
from html.entities import html5
import re
import string

try:
    from scripts.learn._md_blocks import blocks
except ModuleNotFoundError:  # Direct script imports, including report_check's CLI.
    from _md_blocks import blocks


@dataclass(frozen=True)
class Link:
    kind: str
    destination: str
    raw: str
    start: int
    end: int
    image: bool = False
    # Syntax metadata used by the report floor, not part of URL normalisation.
    title: bool = False
    angle: bool = False


def normalise(text: str) -> str:
    """CommonMark input preprocessing, preserving all other characters."""
    return text.replace('\r\n', '\n').replace('\r', '\n').replace('\0', '\ufffd')


_ENTITY = re.compile(r'&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});')
_ESCAPE = re.compile(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])')
# One substitution pass: escaped ampersands must not be decoded again.
_DECODE = re.compile(_ESCAPE.pattern + '|' + _ENTITY.pattern)
_SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+.-]{1,31}:')
_EMAIL = re.compile(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*")
_TICKS = re.compile(r'`+')
_WS = ' \t\n'
_ATTR_NAME = re.compile(r'[A-Za-z_:][A-Za-z0-9_.:-]*')
_TAG_NAME = re.compile(r'[A-Za-z][A-Za-z0-9-]*')
_LINK_ATTRS = {'href', 'src', 'action', 'formaction', 'data', 'poster', 'cite'}
_GFM_START = re.compile(r'https?://|www\.|@', re.I)
_EMAIL_LOCAL = frozenset(string.ascii_letters + string.digits + '._+-')
_GFM_DOMAIN = re.compile(r'[\w-]+(?:\.[\w-]+)*')
_GFM_EMAIL = re.compile(r'[A-Za-z0-9._+-]+@[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+')


def _entity(m: re.Match) -> str:
    raw = m.group()
    if raw.startswith('&#') or raw[1:] in html5:
        return unescape(raw)
    return raw


def _decode(raw: str) -> str:
    return _DECODE.sub(lambda m: m.group(1) if m.group(1) is not None else _entity(m), raw)


def _label(raw: str) -> str:
    # Labels are matched before backslash/entity decoding (CommonMark §4.7).
    return ' '.join(raw.casefold().split())


def _label_end(s: str, i: int) -> int | None:
    """Read at most 999 label characters; escaped brackets are ordinary text."""
    p = i + 1
    limit = min(len(s), p + 1000)
    while p < limit:
        if s[p] == '\\' and p + 1 < len(s) and s[p + 1] in string.punctuation:
            p += 2
        elif s[p] == ']':
            return p if p > i + 1 and s[i + 1:p].strip() else None
        elif s[p] == '[':
            return None
        else:
            p += 1
    return None


def _space(s: str, i: int) -> int:
    while i < len(s) and s[i] in _WS:
        i += 1
    return i


class _Destinations:
    """Memoise bare-destination grammar and angle ends in one backward pass."""

    def __init__(self, s: str):
        n = len(s)
        self.bare = array('i', [n]) * (n + 1)
        self.angle = array('i', [-1]) * (n + 1)
        self.autolinks: dict[int, int] = {}
        boundary = n
        for p in range(n - 1, -1, -1):
            c = s[p]
            if c == '<' and boundary < n and s[boundary] == '>':
                self.autolinks[p] = boundary
            if ord(c) <= 32 or c in '<>':
                boundary = p
            if c == '>':
                self.angle[p] = p
            elif c not in '<\n':
                self.angle[p] = self.angle[p + 1]
            if c == '\\' and p + 1 < n and s[p + 1] in string.punctuation:
                self.bare[p] = self.bare[p + 2]
                self.angle[p] = self.angle[p + 2]
            elif c == '(':
                close = self.bare[p + 1]
                self.bare[p] = self.bare[close + 1] if 0 <= close < n and s[close] == ')' else -1
            elif c == ')' or ord(c) <= 32 or ord(c) == 127:
                self.bare[p] = p
            else:
                self.bare[p] = self.bare[p + 1]


def _destination(s: str, i: int, index: _Destinations) -> tuple[int, int, int, bool] | None:
    """Return raw start/end, cursor after destination, and angle-form flag."""
    if i < len(s) and s[i] == '<':
        end = index.angle[i + 1]
        return (i + 1, end, end + 1, True) if end >= 0 else None
    end = index.bare[i]
    return (i, end, end, False) if end >= 0 else None


def _title(s: str, i: int) -> int | None:
    if i >= len(s) or s[i] not in '\"\'(':
        return None
    close = ')' if s[i] == '(' else s[i]
    p = i + 1
    while p < len(s):
        if s[p] == '\\' and p + 1 < len(s) and s[p + 1] in string.punctuation:
            p += 2
        elif s[p] == close:
            return p + 1
        elif s[p] == '(' and close == ')':
            return None
        elif s[p] == '\n' and re.match(r'[ \t]*\n', s[p + 1: p + 1001]):
            return None
        else:
            p += 1
    return None


def _inline_destination(s: str, i: int, index: _Destinations):
    p = _space(s, i + 1)
    dest = _destination(s, p, index)
    if dest is None:
        return None
    a, b, p, angle = dest
    q = _space(s, p)
    title = False
    if q > p and q < len(s) and s[q] in '\"\'(':
        end = _title(s, q)
        if end is None:
            return None
        title, q = True, _space(s, end)
    if q < len(s) and s[q] == ')':
        return a, b, q + 1, angle, title
    return None


def _link(s: str, offsets: list[int], kind: str, a: int, b: int, *,
          image: bool = False, title: bool = False, angle: bool = False,
          destination: str | None = None) -> Link:
    start = offsets[a] if a < len(offsets) else (offsets[-1] + 1 if offsets else 0)
    end = offsets[b - 1] + 1 if b > a else start
    raw = s[a:b]
    return Link(kind, _decode(raw) if destination is None else destination, raw,
                start, end, image, title, angle)


def _definitions(s: str, offsets: list[int], refs: dict[str, Link], definitions: list[Link],
                 index: _Destinations) -> int:
    """Consume definitions only at the start of a paragraph; first label wins."""
    i = 0
    while i < len(s):
        p = i
        while p < len(s) and s[p] in ' \t':
            p += 1
        if p >= len(s) or s[p] != '[':
            break
        end = _label_end(s, p)
        if end is None or s[end + 1:end + 2] != ':':
            break
        dest = _destination(s, _space(s, end + 2), index)
        if dest is None:
            break
        a, b, q, angle = dest
        if a == b and not angle:
            break
        line_end = s.find('\n', q)
        if line_end < 0:
            line_end = len(s)
        after = q
        while after < line_end and s[after] in ' \t':
            after += 1
        title = False
        consumed = line_end + (line_end < len(s))
        # An optional title can start on the next line. A failed next-line title
        # leaves the destination-only definition valid.
        t = _space(s, q)
        if t > q and t < len(s) and s[t] in '\"\'(':
            te = _title(s, t)
            if te is not None:
                tail = te
                while tail < len(s) and s[tail] in ' \t':
                    tail += 1
                if tail == len(s) or s[tail] == '\n':
                    title, consumed = True, tail + (tail < len(s))
                elif t <= line_end:
                    break
            elif t <= line_end:
                break
        if not title and after != line_end:
            break
        link = _link(s, offsets, 'reference', a, b, title=title, angle=angle)
        definitions.append(link)
        refs.setdefault(_label(s[p + 1:end]), link)
        i = consumed
    return i


def _closing(s: str, token: str, start: int, missing: set[str]) -> int:
    if token in missing:
        return -1
    end = s.find(token, start)
    if end < 0:
        missing.add(token)
    return end


def _html_token(s: str, i: int, missing: set[str]) -> int | None:
    """Recognise CommonMark raw HTML; quoted > characters do not end tags."""
    n = len(s)
    for short_comment in ('<!-->', '<!--->'):
        if s.startswith(short_comment, i):
            return i + len(short_comment)
    for prefix, close in (('<!--', '-->'), ('<?', '?>'), ('<![CDATA[', ']]>')):
        if s.startswith(prefix, i):
            end = _closing(s, close, i + len(prefix), missing)
            return end + len(close) if end >= 0 else None
    if s.startswith('<!', i) and i + 2 < n and s[i + 2].isalpha() and s[i + 2].isascii():
        end = _closing(s, '>', i + 3, missing)
        return end + 1 if end >= 0 else None
    p = i + 1
    closing = p < n and s[p] == '/'
    p += closing
    m = _TAG_NAME.match(s, p)
    if not m:
        return None
    p = m.end()
    while p < n:
        q = _space(s, p)
        if s.startswith('/>', q) and not closing:
            return q + 2
        if q < n and s[q] == '>':
            return q + 1
        if closing or q == p:
            return None
        attr = _ATTR_NAME.match(s, q)
        if not attr:
            return None
        p = _space(s, attr.end())
        if p >= n or s[p] != '=':
            p = attr.end()
            continue
        p = _space(s, p + 1)
        if p >= n:
            return None
        if s[p] in '\"\'':
            end = _closing(s, s[p], p + 1, missing)
            if end < 0:
                return None
            p = end + 1
        else:
            a = p
            while p < n and s[p] not in ' \t\n\"\'=<>`':
                p += 1
            if a == p:
                return None
    return None


def _html_links(s: str, offsets: list[int]) -> list[Link]:
    """Read URL attributes on every tag, also repeated and unfamiliar tags."""
    out = []
    missing: set[str] = set()
    i = 0
    while i < len(s):
        i = s.find('<', i)
        if i < 0:
            break
        end = _html_token(s, i, missing)
        if end is None:
            # A malformed tag in a raw HTML block can still be browser-repaired.
            # Keep reading attributes across lines, bounded by the next tag.
            next_tag = s.find('<', i + 1)
            end = next_tag if next_tag >= 0 else len(s)
        if s.startswith(('<!--', '<?', '<!'), i):
            i = end
            continue
        m = _TAG_NAME.match(s, i + 1)
        if m:
            p = m.end()
            while p < end:
                if s[p].isspace() or s[p] == '/':
                    p += 1
                    continue
                attr = _ATTR_NAME.match(s, p)
                if not attr:
                    p += 1
                    continue
                name = attr.group().lower()
                p = _space(s, attr.end())
                if p >= end or s[p] != '=':
                    continue
                p = _space(s, p + 1)
                if p < end and s[p] in '\"\'':
                    a = p + 1
                    b = s.find(s[p], a, end)
                    if b < 0:
                        b = end
                    p = b + 1
                else:
                    a = p
                    while p < end and not s[p].isspace() and s[p] != '>':
                        p += 1
                    b = p
                if name in _LINK_ATTRS:
                    out.append(_link(s, offsets, 'html', a, b, destination=unescape(s[a:b])))
        i = end
    return out


def _gfm(s: str, offsets: list[int], a: int, b: int) -> list[Link]:
    """Read GFM text autolinks, retaining only their rendered destination span."""
    out = []
    i = a
    while i < b:
        m = _GFM_START.search(s, i, b)
        if not m:
            break
        p = m.start()
        www = s[p:p + 4].lower() == 'www.'
        email = s[m.end() - 1] == '@'
        if email:
            while p > a and s[p - 1] in _EMAIL_LOCAL:
                p -= 1
            e = _GFM_EMAIL.match(s, p, b)
            if e:
                raw = e.group()
                if raw[-1] not in '-_':
                    out.append(_link(s, offsets, 'gfm-autolink', p, p + len(raw), destination='mailto:' + raw))
                i = e.end()
            else:
                i = m.end()
            continue
        if p > 0 and not (s[p - 1].isspace() or s[p - 1] in '*_~('):
            i = m.end()
            continue
        domain = _GFM_DOMAIN.match(s, p if www else m.end(), b)
        parts = domain.group().split('.') if domain is not None else []
        if (domain is None or (www and len(parts) < 2)
                or any('_' in part for part in parts[-2:])):
            # Later www. prefixes within this same domain have the same invalid
            # final two labels. Do not rescan a long rejected domain per prefix.
            i = domain.end() if domain is not None else m.end()
            continue
        q = m.end()
        while q < b and not s[q].isspace() and s[q] != '<':
            q += 1
        end = q
        # Trimming a close can expose punctuation, and vice versa. Each character
        # is visited once, including in adversarial runs of closing parentheses.
        opens = s.count('(', p, end)
        closes = s.count(')', p, end)
        while end > m.end():
            if s[end - 1] in '?!.,:*_~':
                end -= 1
            elif s[end - 1] == ')' and closes > opens:
                end -= 1
                closes -= 1
            else:
                break
        if end > p and s[end - 1] == ';':
            amp = s.rfind('&', p, end)
            if amp >= p and re.fullmatch(r'&[A-Za-z0-9]+;', s[amp:end]):
                end = amp
        if end >= domain.end():
            raw = s[p:end]
            out.append(_link(s, offsets, 'gfm-autolink', p, end,
                             destination=('http://' if www else '') + raw))
        i = max(q, m.end())
    # GFM email detection runs on consolidated text nodes, after CommonMark
    # decoding. A character reference can create the @ or any other email part.
    # Retain a map to source spans so these destinations still have exact raw text.
    if s.find('&', a, b) >= 0 or s.find('\\', a, b) >= 0:
        pieces = []
        starts, ends = array('i'), array('i')
        cursor = a
        for match in _DECODE.finditer(s, a, b):
            pieces.append(s[cursor:match.start()])
            starts.extend(range(cursor, match.start()))
            ends.extend(range(cursor + 1, match.start() + 1))
            replacement = match.group(1) if match.group(1) is not None else _entity(match)
            pieces.append(replacement)
            if replacement == match.group():
                starts.extend(range(match.start(), match.end()))
                ends.extend(range(match.start() + 1, match.end() + 1))
            else:
                starts.extend([match.start()] * len(replacement))
                ends.extend([match.end()] * len(replacement))
            cursor = match.end()
        pieces.append(s[cursor:b])
        starts.extend(range(cursor, b))
        ends.extend(range(cursor + 1, b + 1))
        decoded = ''.join(pieces)
        protected = [link for link in out if not link.destination.startswith('mailto:')]
        added = []
        protected_index = 0
        decoded_cursor = 0
        while decoded_cursor < len(decoded):
            at = decoded.find('@', decoded_cursor)
            if at < 0:
                break
            local = at
            while local > decoded_cursor and decoded[local - 1] in _EMAIL_LOCAL:
                local -= 1
            email_match = _GFM_EMAIL.match(decoded, local)
            decoded_cursor = email_match.end() if email_match is not None else at + 1
            if email_match is None:
                continue
            address = email_match.group()
            left, right = starts[email_match.start()], ends[email_match.end() - 1]
            if address[-1] in '-_' or s[left:right] == address:
                continue
            link = _link(s, offsets, 'gfm-autolink', left, right, destination='mailto:' + address)
            while protected_index < len(protected) and protected[protected_index].end <= link.start:
                protected_index += 1
            if (protected_index < len(protected)
                    and protected[protected_index].start < link.end):
                continue
            added.append(link)
        # A decoded address can encompass a shorter raw-source email found above.
        # Merge once, rather than repeatedly filtering the accumulated output.
        if added:
            retained = []
            added_index = 0
            for link in out:
                while added_index < len(added) and added[added_index].end <= link.start:
                    added_index += 1
                if (added_index < len(added) and added[added_index].start < link.end
                        and link.destination.startswith('mailto:')):
                    continue
                retained.append(link)
            out = sorted(retained + added, key=lambda link: link.start)
    return out


def _inlines(s: str, offsets: list[int], refs: dict[str, Link]) -> list[Link]:
    index = _Destinations(s)
    missing: set[str] = set()
    # Precompute equal-length backtick successors, avoiding rescans on unmatched runs.
    runs = list(_TICKS.finditer(s))
    next_tick, last = {}, {}
    for m in reversed(runs):
        size = m.end() - m.start()
        if size in last:
            next_tick[m.start()] = last[size]
        # A backslash can escape the first tick of a run, leaving its suffix as
        # an opener. Inside a code span the full original run is the closer.
        if size > 1 and size - 1 in last:
            next_tick[m.start() + 1] = last[size - 1]
        last[size] = (m.start(), m.end())
    tick_end = {m.start() + delta: m.end() for m in runs
                for delta in range(min(2, m.end() - m.start()))}
    out: list[tuple[int, Link]] = []
    # opener position, image, activation epoch, output index
    stack: list[tuple[int, bool, int, int]] = []
    epoch = 0
    i = 0
    excluded: list[tuple[int, int]] = []

    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s) and s[i + 1] in string.punctuation:
            i += 2
            continue
        if c == '`':
            end = tick_end[i]
            if i in next_tick:
                end = next_tick[i][1]
                excluded.append((i, end))
                i = end
            else:
                i = end
            continue
        if c == '<':
            auto = _SCHEME.match(s, i + 1)
            end = index.autolinks.get(i, -1)
            # Reject whitespace/control/< before the close without crossing tokens.
            if end >= 0:
                raw = s[i + 1:end]
                email = _EMAIL.fullmatch(raw) if not auto else None
                if auto or email:
                    link = _link(s, offsets, 'autolink' if auto else 'email-autolink', i + 1, end,
                                 destination=_ENTITY.sub(_entity, raw) if auto else 'mailto:' + _ENTITY.sub(_entity, raw),
                                 angle=True)
                    out.append((offsets[i], link))
                    epoch += 1
                    excluded.append((i, end + 1))
                    i = end + 1
                    continue
            end = _html_token(s, i, missing)
            if end is not None:
                out.extend((offsets[i], link) for link in _html_links(s[i:end], offsets[i:end]))
                excluded.append((i, end))
                i = end
                continue
        image = c == '!' and s[i + 1:i + 2] == '['
        if c == '[' or image:
            p = i + 1 if image else i
            stack.append((p, image, epoch, len(out)))
            i = p + 1
            continue
        if c == ']' and stack:
            opener, image, active, output_index = stack.pop()
            found = None
            end = i + 1
            if image or active == epoch:
                if s[i + 1:i + 2] == '(':
                    dest = _inline_destination(s, i + 1, index)
                    if dest:
                        a, b, end, angle, title = dest
                        found = _link(s, offsets, 'inline', a, b, image=image, title=title, angle=angle)
                if found is None:
                    label_end = _label_end(s, i + 1) if s[i + 1:i + 2] == '[' else None
                    collapsed = s[i + 1:i + 3] == '[]'
                    if label_end is not None:
                        label = s[i + 2:label_end]
                    else:
                        label = s[opener + 1:i] if i - opener <= 1000 else ''
                    ref = refs.get(_label(label)) if len(label) <= 999 else None
                    if ref:
                        found = replace(ref, image=image)
                        end = label_end + 1 if label_end is not None else i + 3 if collapsed else i + 1
            if found:
                if image:
                    del out[output_index:]  # Images render their description as plain alt text.
                else:
                    epoch += 1  # Earlier link openers become inactive; image openers remain active.
                out.append((offsets[opener], found))
                excluded.append((opener - int(image), end))
                i = end
            else:
                i += 1
            continue
        i += 1
    # Extended autolinks run on remaining text nodes. Unmatched brackets stay
    # in those nodes, including brackets that are part of an autolink path.
    cursor = 0
    for a, b in sorted(excluded):
        if a > cursor:
            out.extend((link.start, link) for link in _gfm(s, offsets, cursor, a))
        cursor = max(cursor, b)
    out.extend((link.start, link) for link in _gfm(s, offsets, cursor, len(s)))
    out.sort(key=lambda item: item[0])
    return [link for _, link in out]


def _read(text: str) -> tuple[list[Link], list[Link]]:
    text = normalise(text)
    parsed = blocks(text)
    refs: dict[str, Link] = {}
    definitions: list[Link] = []
    pending = []
    for kind, content, offsets in parsed:
        consumed = _definitions(content, offsets, refs, definitions, _Destinations(content)) if kind == 'inline' else 0
        pending.append((kind, content[consumed:], offsets[consumed:]))
    out = []
    for kind, content, offsets in pending:
        out.extend(_html_links(content, offsets) if kind == 'html' else _inlines(content, offsets, refs))
    # A multiline attribute may cross stripped container markers. raw describes
    # the contiguous source span; destination describes what the reader opens.
    raw_spans: dict[tuple[int, int], str] = {}

    def source_raw(link: Link) -> Link:
        key = (link.start, link.end)
        if key not in raw_spans:
            raw_spans[key] = text[link.start:link.end]
        return replace(link, raw=raw_spans[key])
    return [source_raw(link) for link in out], [source_raw(link) for link in definitions]


def rendered_links(text: str) -> list[Link]:
    """Extract destinations in rendered order; spans address normalise(text)."""
    return _read(text)[0]
