#!/usr/bin/env python3
"""contrast_check.py — WCAG contrast (+ minimum print size) for every text-bearing element
of a self-contained HTML deliverable, resolved from the document's OWN CSS.

Why a checker and not a rule of thumb: F-RECON-007 — a brochure declared
``--ink-faint: rgba(255,255,255,0.14)`` on ``--surface: #09090f`` and shipped a footer nobody
could read (≈1.4:1). The tokens looked fine in the palette; only the *composited pair* is the
truth. So this module cascades the stylesheet the way the renderer will (specificity + source
order + inline + ``!important``), resolves ``var()`` (custom properties inherit), composites
translucent text and backgrounds over what is really beneath them, honours ``opacity``, and
judges every element that carries its own text against the nearest painted background.

Floors (WCAG 2.x AA): 4.5:1 for text, 3:1 for LARGE text (≥ 24px, or ≥ 18.66px bold). Print
deliverables add a size floor (default 7pt): thin 6–7pt type never reaches full pixel coverage,
so it reads dimmer than its computed contrast (the hero fact strip in the same brochure).

It is a static approximation, not a browser: no layout, no images/gradient geometry (every
gradient stop is judged — conservative), positioned overlaps are not seen. False negatives are
therefore possible where an element floats over an unrelated background; false positives are
rare and worth a look. Stdlib only.

CLI:
    contrast_check.py <file.html> [--min 4.5] [--min-font-pt 7|0] [--mode print|screen|both] [--json]
Exit: 0 = floor met, 1 = a text/background pair below the floor (or text under the size floor),
2 = usage / unreadable input.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

if __package__ in (None, ""):  # run as a script: make `draft._dom` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draft._dom import Document, Node, parse, text_elements  # noqa: E402

RGBA = tuple[float, float, float, float]  # 0..255, 0..255, 0..255, 0..1

# ── colours ───────────────────────────────────────────────────────────────────────────────────

NAMED_COLORS: dict[str, str] = {
    "aliceblue": "f0f8ff", "antiquewhite": "faebd7", "aqua": "00ffff", "aquamarine": "7fffd4",
    "azure": "f0ffff", "beige": "f5f5dc", "bisque": "ffe4c4", "black": "000000",
    "blanchedalmond": "ffebcd", "blue": "0000ff", "blueviolet": "8a2be2", "brown": "a52a2a",
    "burlywood": "deb887", "cadetblue": "5f9ea0", "chartreuse": "7fff00", "chocolate": "d2691e",
    "coral": "ff7f50", "cornflowerblue": "6495ed", "cornsilk": "fff8dc", "crimson": "dc143c",
    "cyan": "00ffff", "darkblue": "00008b", "darkcyan": "008b8b", "darkgoldenrod": "b8860b",
    "darkgray": "a9a9a9", "darkgrey": "a9a9a9", "darkgreen": "006400", "darkkhaki": "bdb76b",
    "darkmagenta": "8b008b", "darkolivegreen": "556b2f", "darkorange": "ff8c00",
    "darkorchid": "9932cc", "darkred": "8b0000", "darksalmon": "e9967a", "darkseagreen": "8fbc8f",
    "darkslateblue": "483d8b", "darkslategray": "2f4f4f", "darkslategrey": "2f4f4f",
    "darkturquoise": "00ced1", "darkviolet": "9400d3", "deeppink": "ff1493",
    "deepskyblue": "00bfff", "dimgray": "696969", "dimgrey": "696969", "dodgerblue": "1e90ff",
    "firebrick": "b22222", "floralwhite": "fffaf0", "forestgreen": "228b22", "fuchsia": "ff00ff",
    "gainsboro": "dcdcdc", "ghostwhite": "f8f8ff", "gold": "ffd700", "goldenrod": "daa520",
    "gray": "808080", "grey": "808080", "green": "008000", "greenyellow": "adff2f",
    "honeydew": "f0fff0", "hotpink": "ff69b4", "indianred": "cd5c5c", "indigo": "4b0082",
    "ivory": "fffff0", "khaki": "f0e68c", "lavender": "e6e6fa", "lavenderblush": "fff0f5",
    "lawngreen": "7cfc00", "lemonchiffon": "fffacd", "lightblue": "add8e6", "lightcoral": "f08080",
    "lightcyan": "e0ffff", "lightgoldenrodyellow": "fafad2", "lightgray": "d3d3d3",
    "lightgrey": "d3d3d3", "lightgreen": "90ee90", "lightpink": "ffb6c1", "lightsalmon": "ffa07a",
    "lightseagreen": "20b2aa", "lightskyblue": "87cefa", "lightslategray": "778899",
    "lightslategrey": "778899", "lightsteelblue": "b0c4de", "lightyellow": "ffffe0",
    "lime": "00ff00", "limegreen": "32cd32", "linen": "faf0e6", "magenta": "ff00ff",
    "maroon": "800000", "mediumaquamarine": "66cdaa", "mediumblue": "0000cd",
    "mediumorchid": "ba55d3", "mediumpurple": "9370db", "mediumseagreen": "3cb371",
    "mediumslateblue": "7b68ee", "mediumspringgreen": "00fa9a", "mediumturquoise": "48d1cc",
    "mediumvioletred": "c71585", "midnightblue": "191970", "mintcream": "f5fffa",
    "mistyrose": "ffe4e1", "moccasin": "ffe4b5", "navajowhite": "ffdead", "navy": "000080",
    "oldlace": "fdf5e6", "olive": "808000", "olivedrab": "6b8e23", "orange": "ffa500",
    "orangered": "ff4500", "orchid": "da70d6", "palegoldenrod": "eee8aa", "palegreen": "98fb98",
    "paleturquoise": "afeeee", "palevioletred": "db7093", "papayawhip": "ffefd5",
    "peachpuff": "ffdab9", "peru": "cd853f", "pink": "ffc0cb", "plum": "dda0dd",
    "powderblue": "b0e0e6", "purple": "800080", "rebeccapurple": "663399", "red": "ff0000",
    "rosybrown": "bc8f8f", "royalblue": "4169e1", "saddlebrown": "8b4513", "salmon": "fa8072",
    "sandybrown": "f4a460", "seagreen": "2e8b57", "seashell": "fff5ee", "sienna": "a0522d",
    "silver": "c0c0c0", "skyblue": "87ceeb", "slateblue": "6a5acd", "slategray": "708090",
    "slategrey": "708090", "snow": "fffafa", "springgreen": "00ff7f", "steelblue": "4682b4",
    "tan": "d2b48c", "teal": "008080", "thistle": "d8bfd8", "tomato": "ff6347",
    "turquoise": "40e0d0", "violet": "ee82ee", "wheat": "f5deb3", "white": "ffffff",
    "whitesmoke": "f5f5f5", "yellow": "ffff00", "yellowgreen": "9acd32",
}

_FUNC_RE = re.compile(r"(rgba?|hsla?)\(\s*([^()]*)\)", re.IGNORECASE)
_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _parse_alpha(token: str) -> float:
    token = token.strip()
    if token.endswith("%"):
        return _clamp(float(token[:-1]) / 100.0, 0.0, 1.0)
    return _clamp(float(token), 0.0, 1.0)


def _channel(token: str) -> float:
    token = token.strip()
    if token.endswith("%"):
        return _clamp(float(token[:-1]) * 2.55, 0.0, 255.0)
    return _clamp(float(token), 0.0, 255.0)


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    h = (h % 360.0) / 360.0
    if s == 0:
        v = l * 255.0
        return v, v, v

    def hue(p: float, q: float, t: float) -> float:
        t %= 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return hue(p, q, h + 1 / 3) * 255.0, hue(p, q, h) * 255.0, hue(p, q, h - 1 / 3) * 255.0


def parse_color(value: str) -> RGBA | None:
    """One CSS colour → RGBA, or None when `value` is not a single literal colour
    (``inherit``/``currentColor``/``var()``/gradients are the caller's business)."""
    v = value.strip().lower()
    if not v:
        return None
    if v == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    m = _HEX_RE.fullmatch(v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255.0 if len(h) == 8 else 1.0
        return (float(r), float(g), float(b), a)
    m = _FUNC_RE.fullmatch(v)
    if m:
        fn, body = m.group(1), m.group(2)
        body = body.replace("/", " / ")
        parts = [p for p in re.split(r"[,\s]+", body.strip()) if p]
        alpha = 1.0
        if "/" in parts:
            idx = parts.index("/")
            alpha = _parse_alpha(parts[idx + 1]) if idx + 1 < len(parts) else 1.0
            parts = parts[:idx]
        elif len(parts) == 4:
            alpha = _parse_alpha(parts[3])
            parts = parts[:3]
        if len(parts) != 3:
            return None
        try:
            if fn.startswith("rgb"):
                return (_channel(parts[0]), _channel(parts[1]), _channel(parts[2]), alpha)
            hue = float(re.sub(r"(deg|turn|rad|grad)$", "", parts[0]))
            if parts[0].endswith("turn"):
                hue *= 360.0
            elif parts[0].endswith("rad"):
                hue = math.degrees(hue)
            elif parts[0].endswith("grad"):
                hue *= 0.9
            s = _clamp(float(parts[1].rstrip("%")) / 100.0, 0.0, 1.0)
            l = _clamp(float(parts[2].rstrip("%")) / 100.0, 0.0, 1.0)
            r, g, b = _hsl_to_rgb(hue, s, l)
            return (r, g, b, alpha)
        except ValueError:
            return None
    if v in NAMED_COLORS:
        return parse_color("#" + NAMED_COLORS[v])
    return None


def find_colors(value: str) -> list[RGBA]:
    """Every literal colour inside a value — a ``background`` shorthand or a gradient yields all
    its stops (the checker judges the WORST one)."""
    out: list[RGBA] = []
    for m in _FUNC_RE.finditer(value):
        c = parse_color(m.group(0))
        if c is not None:
            out.append(c)
    stripped = _FUNC_RE.sub(" ", value)
    for m in _HEX_RE.finditer(stripped):
        c = parse_color(m.group(0))
        if c is not None:
            out.append(c)
    for word in re.findall(r"[a-zA-Z]+", stripped):
        w = word.lower()
        if w in NAMED_COLORS or w == "transparent":
            c = parse_color(w)
            if c is not None:
                out.append(c)
    return out


def composite(fg: RGBA, bg: RGBA) -> RGBA:
    """`fg` over an (assumed opaque) `bg`."""
    a = fg[3]
    return (
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1.0,
    )


def relative_luminance(c: RGBA) -> float:
    def lin(ch: float) -> float:
        s = ch / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def contrast_ratio(a: RGBA, b: RGBA) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def to_hex(c: RGBA) -> str:
    return "#%02x%02x%02x" % (int(round(c[0])), int(round(c[1])), int(round(c[2])))


# ── CSS ───────────────────────────────────────────────────────────────────────────────────────

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_ID_RE = re.compile(r"#([\w-]+)")
_CLASS_RE = re.compile(r"\.([\w-]+)")
_ATTR_RE = re.compile(r"\[([\w-]+)(?:([~|^$*]?=)\"?'?([^\]\"']*)\"?'?)?\]")
_PSEUDO_RE = re.compile(r"::?[\w-]+(?:\([^)]*\))?")
_TRACKED = {"color", "background", "background-color", "background-image", "opacity", "font-size",
            "font-weight", "font", "display", "visibility"}


@dataclass
class Rule:
    selector: str
    decls: dict[str, tuple[str, bool]]  # prop → (value, important)
    order: int
    specificity: tuple[int, int, int]
    parts: list[tuple[str, dict]]  # compiled selector: [(combinator, compound)…]


@dataclass
class Sheet:
    rules: list[Rule] = field(default_factory=list)


def _split_top(text: str, sep: str) -> list[str]:
    """Split on `sep` outside parentheses/brackets/quotes."""
    out, depth, cur, quote = [], 0, [], ""
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def parse_declarations(block: str) -> dict[str, tuple[str, bool]]:
    decls: dict[str, tuple[str, bool]] = {}
    for item in _split_top(block, ";"):
        if ":" not in item:
            continue
        prop, _, val = item.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        if not prop:
            continue
        important = False
        if val.lower().endswith("!important"):
            important, val = True, val[: -len("!important")].strip()
        if prop.startswith("--") or prop in _TRACKED:
            decls[prop] = (val, important)
    return decls


def _media_applies(query: str, mode: str) -> bool:
    q = query.lower()
    has_print, has_screen = "print" in q, "screen" in q
    if "not" in q.split():
        # `not print` / `not screen`: keep it simple and conservative — apply.
        return True
    if has_print and not has_screen:
        return mode == "print"
    if has_screen and not has_print:
        return mode == "screen"
    return True  # `all`, feature-only queries, or both media named


def _iter_blocks(css: str) -> Iterable[tuple[str, str]]:
    """Yield (prelude, body) for each top-level `prelude { body }` with balanced braces."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        body = css[j + 1 : k - 1] if depth == 0 else css[j + 1 :]
        yield prelude, body
        i = k


def _compile_selector(selector: str) -> tuple[list[tuple[str, dict]], tuple[int, int, int]] | None:
    """Compile a single (non-list) selector into [(combinator, compound)]; None when the
    selector uses something this matcher does not understand (pseudo-elements, most
    pseudo-classes) — such a rule is skipped rather than misapplied."""
    sel = re.sub(r"\s*([>+~])\s*", r" \1 ", selector.strip())
    tokens = sel.split()
    parts: list[tuple[str, dict]] = []
    comb = " "
    ids = classes = types = 0
    for tok in tokens:
        if tok in (">", "+", "~"):
            comb = tok
            continue
        compound: dict = {"tag": None, "ids": [], "classes": [], "attrs": [], "root": False, "not": []}
        rest = tok
        for m in _PSEUDO_RE.finditer(tok):
            p = m.group(0)
            if p.startswith("::"):
                return None
            name = p[1:].split("(")[0].lower()
            if name == "root":
                compound["root"] = True
                classes += 1
            elif name == "not":
                inner = p[len(":not("):-1]
                sub = _compile_selector(inner)
                if sub is None or len(sub[0]) != 1:
                    return None
                compound["not"].append(sub[0][0][1])
                classes += 1
            elif name in ("first-child", "last-child", "nth-child", "nth-of-type", "first-of-type",
                          "last-of-type", "hover", "focus", "active", "visited", "link", "empty",
                          "checked", "disabled", "focus-within", "focus-visible", "where", "is", "has"):
                return None
            else:
                return None
        rest = _PSEUDO_RE.sub("", rest)
        for m in _ATTR_RE.finditer(rest):
            compound["attrs"].append((m.group(1).lower(), m.group(2), m.group(3)))
            classes += 1
        rest = _ATTR_RE.sub("", rest)
        for m in _ID_RE.finditer(rest):
            compound["ids"].append(m.group(1))
            ids += 1
        rest = _ID_RE.sub("", rest)
        for m in _CLASS_RE.finditer(rest):
            compound["classes"].append(m.group(1))
            classes += 1
        rest = _CLASS_RE.sub("", rest).strip()
        if rest and rest != "*":
            if not re.fullmatch(r"[\w-]+", rest):
                return None
            compound["tag"] = rest.lower()
            types += 1
        parts.append((comb, compound))
        comb = " "
    if not parts:
        return None
    return parts, (ids, classes, types)


def parse_css(css: str, mode: str, start_order: int = 0) -> Sheet:
    sheet = Sheet()
    order = start_order
    css = _COMMENT_RE.sub(" ", css)

    def walk(text: str) -> None:
        nonlocal order
        for prelude, body in _iter_blocks(text):
            if not prelude:
                continue
            low = prelude.lower()
            if low.startswith("@"):
                if low.startswith("@media"):
                    if _media_applies(prelude[6:], mode):
                        walk(body)
                elif low.startswith(("@supports", "@layer", "@container")):
                    walk(body)
                # @page / @font-face / @keyframes / @import — nothing to cascade
                continue
            decls = parse_declarations(body)
            if not decls:
                continue
            for selector in _split_top(prelude, ","):
                compiled = _compile_selector(selector)
                if compiled is None:
                    continue
                parts, spec = compiled
                sheet.rules.append(Rule(selector.strip(), decls, order, spec, parts))
                order += 1

    walk(css)
    return sheet


def _compound_matches(node: Node, comp: dict) -> bool:
    if node.tag.startswith("#") or node.tag == "":
        return False
    if comp["root"] and node.tag != "html":
        return False
    if comp["tag"] and node.tag != comp["tag"]:
        return False
    if comp["ids"] and any(node.attrs.get("id") != i for i in comp["ids"]):
        return False
    if comp["classes"]:
        have = set(node.classes())
        if not all(c in have for c in comp["classes"]):
            return False
    for name, op, val in comp["attrs"]:
        if name not in node.attrs:
            return False
        actual = node.attrs[name]
        if op is None:
            continue
        if op == "=" and actual != val:
            return False
        if op == "~=" and val not in actual.split():
            return False
        if op == "^=" and not actual.startswith(val):
            return False
        if op == "$=" and not actual.endswith(val):
            return False
        if op == "*=" and val not in actual:
            return False
        if op == "|=" and not (actual == val or actual.startswith(val + "-")):
            return False
    for sub in comp["not"]:
        if _compound_matches(node, sub):
            return False
    return True


def _prev_element(node: Node) -> Node | None:
    if node.parent is None:
        return None
    sibs = node.parent.element_children()
    idx = sibs.index(node)
    return sibs[idx - 1] if idx > 0 else None


def matches(node: Node, parts: list[tuple[str, dict]]) -> bool:
    """Right-to-left selector matching with descendant/child/sibling combinators."""

    def match_from(idx: int, n: Node) -> bool:
        comb, comp = parts[idx]
        if not _compound_matches(n, comp):
            return False
        if idx == 0:
            return True
        prev_comb = comb
        if prev_comb == " ":
            anc = n.parent
            while anc is not None and anc.tag != "":
                if match_from(idx - 1, anc):
                    return True
                anc = anc.parent
            return False
        if prev_comb == ">":
            return n.parent is not None and n.parent.tag != "" and match_from(idx - 1, n.parent)
        if prev_comb == "+":
            p = _prev_element(n)
            return p is not None and match_from(idx - 1, p)
        if prev_comb == "~":
            p = _prev_element(n)
            while p is not None:
                if match_from(idx - 1, p):
                    return True
                p = _prev_element(p)
            return False
        return False

    return match_from(len(parts) - 1, node)


# ── cascade ───────────────────────────────────────────────────────────────────────────────────

@dataclass
class Computed:
    color: RGBA
    backgrounds: list[RGBA]  # this element's OWN painted background colours (empty = none)
    opacity: float
    font_px: float
    bold: bool
    hidden: bool
    custom: dict[str, str]


_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\)")
_FONT_KEYWORDS = {"xx-small": 9, "x-small": 10, "small": 13, "medium": 16, "large": 18,
                  "x-large": 24, "xx-large": 32, "xxx-large": 48}


def resolve_vars(value: str, custom: dict[str, str], depth: int = 0) -> str:
    if "var(" not in value or depth > 8:
        return value

    def sub(m: re.Match) -> str:
        name, fallback = m.group(1), m.group(2)
        if name in custom:
            return resolve_vars(custom[name], custom, depth + 1)
        return resolve_vars(fallback, custom, depth + 1) if fallback is not None else ""

    return _VAR_RE.sub(sub, value)


def _font_px(value: str, parent_px: float, root_px: float) -> float | None:
    v = value.strip().lower()
    if v in _FONT_KEYWORDS:
        return float(_FONT_KEYWORDS[v])
    if v in ("larger", "smaller"):
        return parent_px * (1.2 if v == "larger" else 1 / 1.2)
    m = re.fullmatch(rf"({_NUM})\s*(px|pt|em|rem|%|mm|cm|in|pc)?", v)
    if not m:
        return None
    num, unit = float(m.group(1)), (m.group(2) or "px")
    return {
        "px": num, "pt": num * 4 / 3, "em": num * parent_px, "rem": num * root_px,
        "%": num / 100 * parent_px, "mm": num * 96 / 25.4, "cm": num * 96 / 2.54,
        "in": num * 96, "pc": num * 16,
    }[unit]


def _is_bold(value: str, parent_bold: bool) -> bool:
    v = value.strip().lower()
    if v in ("bold", "bolder"):
        return True
    if v in ("normal", "lighter"):
        return False
    if v == "inherit":
        return parent_bold
    try:
        return float(v) >= 600
    except ValueError:
        return parent_bold


def _font_shorthand_parts(value: str) -> tuple[str | None, str | None]:
    """(font-size, font-weight) from a `font:` shorthand, best effort."""
    size = weight = None
    for tok in value.replace("/", " / ").split():
        if tok == "/":
            break
        if re.fullmatch(rf"{_NUM}(px|pt|em|rem|%|mm|cm|in|pc)", tok) or tok in _FONT_KEYWORDS:
            size = tok
        elif tok in ("bold", "bolder", "lighter", "normal") or re.fullmatch(r"[1-9]00", tok):
            if weight is None or tok != "normal":
                weight = tok
    return size, weight


ROOT_KEY = 0  # `cascade()` stores the document-level (html/:root) Computed under this key


def cascade(doc: Document, mode: str, root_px: float = 16.0) -> dict[int, Computed]:
    """Compute the tracked properties for every element (keyed by id(node)). The document-level
    values — what `:root` / `html` rules declare — live under ``ROOT_KEY``.

    An instrumented deliverable may carry no ``<html>``/``<head>`` open tags at all (the recon
    brochure did: it starts at ``<style>`` and only ``</head><body>`` survive). The custom
    properties on ``:root`` are still the document's tokens, so ``:root``/``html`` rules are
    cascaded against a synthetic root and seed every element's inherited defaults."""
    sheet = parse_css(doc.inline_style_text(), mode)
    computed: dict[int, Computed] = {}
    default = Computed(color=(0.0, 0.0, 0.0, 1.0), backgrounds=[], opacity=1.0, font_px=root_px,
                       bold=False, hidden=False, custom={})

    def declared(node: Node) -> dict[str, str]:
        """Winning value per property after specificity / order / inline / !important."""
        winners: dict[str, tuple[tuple[int, int, int, int], int, str]] = {}
        for rule in sheet.rules:
            if not matches(node, rule.parts):
                continue
            for prop, (val, imp) in rule.decls.items():
                key = (1 if imp else 0, *rule.specificity)
                cur = winners.get(prop)
                if cur is None or (key, rule.order) >= (cur[0], cur[1]):
                    winners[prop] = (key, rule.order, val)
        inline = node.attrs.get("style")
        if inline:
            for prop, (val, imp) in parse_declarations(inline).items():
                key = (1 if imp else 0, 1, 0, 0)
                cur = winners.get(prop)
                if cur is None or key >= cur[0]:
                    winners[prop] = (key, 10**9, val)
        return {p: w[2] for p, w in winners.items()}

    def visit(node: Node, parent: Computed) -> None:
        for child in node.children:
            if child.tag.startswith("#") or not child.tag:
                continue
            decl = declared(child)
            custom = dict(parent.custom)
            for prop, val in decl.items():
                if prop.startswith("--"):
                    custom[prop] = val
            res = {p: resolve_vars(v, custom) for p, v in decl.items() if not p.startswith("--")}

            # font
            font_px = parent.font_px
            bold = parent.bold
            if "font" in res:
                s, w = _font_shorthand_parts(res["font"])
                if s:
                    font_px = _font_px(s, parent.font_px, root_px) or font_px
                if w:
                    bold = _is_bold(w, parent.bold)
            if "font-size" in res:
                font_px = _font_px(res["font-size"], parent.font_px, root_px) or font_px
            if "font-weight" in res:
                bold = _is_bold(res["font-weight"], parent.bold)
            if child.tag in ("b", "strong", "th") and "font-weight" not in res and "font" not in res:
                bold = True
            if child.tag == "h1" and "font-size" not in res and "font" not in res:
                font_px, bold = 2.0 * root_px, True
            elif child.tag == "h2" and "font-size" not in res and "font" not in res:
                font_px, bold = 1.5 * root_px, True
            elif child.tag == "h3" and "font-size" not in res and "font" not in res:
                font_px, bold = 1.17 * root_px, True

            # colour (inherits)
            color = parent.color
            if "color" in res:
                cv = res["color"].strip().lower()
                if cv not in ("inherit", "currentcolor", ""):
                    parsed = parse_color(cv)
                    if parsed is not None:
                        color = parsed

            # background (does not inherit)
            backgrounds: list[RGBA] = []
            for prop in ("background", "background-color", "background-image"):
                if prop in res:
                    found = find_colors(res[prop])
                    if prop == "background-color" and found:
                        backgrounds = [found[0]]  # longhand overrides shorthand's colour
                    else:
                        backgrounds.extend(found)
            backgrounds = [c for c in backgrounds if c[3] > 0]

            opacity = parent.opacity
            if "opacity" in res:
                try:
                    opacity *= _clamp(float(res["opacity"].strip().rstrip("%")) / (100 if res["opacity"].strip().endswith("%") else 1), 0.0, 1.0)
                except ValueError:
                    pass
            hidden = parent.hidden or res.get("display", "").strip().lower() == "none" \
                or res.get("visibility", "").strip().lower() in ("hidden", "collapse")

            comp = Computed(color=color, backgrounds=backgrounds, opacity=opacity, font_px=font_px,
                            bold=bold, hidden=hidden, custom=custom)
            computed[id(child)] = comp
            visit(child, comp)

    # Seed the document-level defaults from `:root` / `html` rules (a synthetic <html> matches
    # both), so tokens resolve even when the deliverable has no <html> element of its own.
    synthetic_html = Node(tag="html", parent=doc.root)
    root_decl = declared(synthetic_html)
    root_custom = {p: v for p, v in root_decl.items() if p.startswith("--")}
    root_res = {p: resolve_vars(v, root_custom) for p, v in root_decl.items() if not p.startswith("--")}
    root_color = default.color
    if "color" in root_res:
        parsed = parse_color(root_res["color"])
        if parsed is not None:
            root_color = parsed
    root_bgs: list[RGBA] = []
    for prop in ("background", "background-color"):
        if prop in root_res:
            root_bgs.extend(c for c in find_colors(root_res[prop]) if c[3] > 0)
    root_font = default.font_px
    if "font-size" in root_res:
        root_font = _font_px(root_res["font-size"], root_px, root_px) or root_font
    root = Computed(color=root_color, backgrounds=root_bgs, opacity=1.0, font_px=root_font,
                    bold=False, hidden=False, custom=root_custom)
    computed[ROOT_KEY] = root
    # a real <html> element (when present) is visited as a child of doc.root and re-declares
    # nothing new; every other top-level element inherits from `root`.
    visit(doc.root, root)
    return computed


# ── the check ─────────────────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    kind: str  # "contrast" | "size"
    path: str
    text: str
    fg: str
    bg: str
    ratio: float
    required: float
    font_pt: float
    mode: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "path": self.path, "text": self.text, "fg": self.fg, "bg": self.bg,
                "ratio": round(self.ratio, 2), "required": self.required,
                "font_pt": round(self.font_pt, 1), "mode": self.mode}


def _effective_backgrounds(node: Node, computed: dict[int, Computed]) -> list[RGBA]:
    """Candidate opaque backgrounds beneath `node`'s text: the nearest ancestor-or-self that
    paints a background, each of its colours composited over what lies beneath it. Root = white."""
    chain = [node, *node.ancestors()]
    layers: list[list[RGBA]] = []
    opaque_found = False
    for n in chain:
        comp = computed.get(id(n))
        if comp and comp.backgrounds:
            layers.append(comp.backgrounds)
            if all(c[3] >= 1.0 for c in comp.backgrounds):
                opaque_found = True
                break
    root = computed.get(ROOT_KEY)
    if not opaque_found and root is not None and root.backgrounds and not any(
            n.tag == "html" for n in chain):
        layers.append(root.backgrounds)
    base: list[RGBA] = [(255.0, 255.0, 255.0, 1.0)]
    for colors in reversed(layers):
        nxt: list[RGBA] = []
        for c in colors:
            for b in base:
                nxt.append(composite(c, b))
        base = nxt[:16]  # bound the combinatorics for gradient-on-gradient stacks
    return base


def check_document(html: str, min_ratio: float = 4.5, min_font_pt: float = 7.0,
                   mode: str = "print") -> tuple[list[Finding], int]:
    """Judge every text-bearing element. Returns (findings, elements_checked)."""
    doc = parse(html)
    computed = cascade(doc, mode)
    findings: list[Finding] = []
    seen: set[tuple] = set()
    checked = 0
    for el in text_elements(doc):
        comp = computed.get(id(el))
        if comp is None or comp.hidden:
            continue
        text = el.direct_text()
        if not re.search(r"[A-Za-z0-9]", text):
            continue  # separators / glyph-only spans carry no words to read
        checked += 1
        fg = (comp.color[0], comp.color[1], comp.color[2], comp.color[3] * comp.opacity)
        large = comp.font_px >= 24 or (comp.font_px >= 18.66 and comp.bold)
        required = 3.0 if large else min_ratio
        font_pt = comp.font_px * 0.75
        worst: tuple[float, RGBA, RGBA] | None = None
        for bg in _effective_backgrounds(el, computed):
            fgc = composite(fg, bg)
            ratio = contrast_ratio(fgc, bg)
            if worst is None or ratio < worst[0]:
                worst = (ratio, fgc, bg)
        assert worst is not None
        ratio, fgc, bg = worst
        sig = (el.path(), to_hex(fgc), to_hex(bg), round(font_pt, 1))
        if ratio + 1e-9 < required:
            if ("contrast", *sig) not in seen:
                seen.add(("contrast", *sig))
                findings.append(Finding("contrast", el.path(), text[:80], to_hex(fgc), to_hex(bg),
                                        ratio, required, font_pt, mode))
        if min_font_pt > 0 and font_pt + 1e-9 < min_font_pt:
            if ("size", *sig) not in seen:
                seen.add(("size", *sig))
                findings.append(Finding("size", el.path(), text[:80], to_hex(fgc), to_hex(bg),
                                        ratio, min_font_pt, font_pt, mode))
    return findings, checked


def run(path: str, min_ratio: float = 4.5, min_font_pt: float = 7.0, mode: str = "print") -> dict:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    modes = ["print", "screen"] if mode == "both" else [mode]
    findings: list[Finding] = []
    checked = 0
    for m in modes:
        f, c = check_document(html, min_ratio, min_font_pt, m)
        findings.extend(f)
        checked = max(checked, c)
    contrast = [f for f in findings if f.kind == "contrast"]
    size = [f for f in findings if f.kind == "size"]
    return {
        "check": "contrast",
        "file": path,
        "mode": mode,
        "min_ratio": min_ratio,
        "min_font_pt": min_font_pt,
        "elements_checked": checked,
        "ok": not findings,
        "contrast_failures": len(contrast),
        "size_failures": len(size),
        "findings": [f.as_dict() for f in findings],
        "summary": (
            f"contrast: {checked} text elements checked in {mode} mode — "
            + ("all meet the floor" if not findings else
               f"{len(contrast)} below {min_ratio}:1 (3:1 for large text)"
               + (f", {len(size)} under {min_font_pt}pt" if min_font_pt > 0 else ""))
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("html", help="the self-contained HTML deliverable")
    ap.add_argument("--min", type=float, default=4.5, help="contrast floor for normal text (default 4.5)")
    ap.add_argument("--min-font-pt", type=float, default=7.0,
                    help="minimum text size in pt for print deliverables; 0 disables (default 7)")
    ap.add_argument("--mode", choices=("print", "screen", "both"), default="print",
                    help="which @media rules apply (default print — the PDF is the deliverable)")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args(argv)
    try:
        report = run(args.html, args.min, args.min_font_pt, args.mode)
    except OSError as exc:
        print(json.dumps({"check": "contrast", "ok": False, "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["summary"])
        for f in report["findings"]:
            what = (f"{f['ratio']}:1 < {f['required']}:1" if f["kind"] == "contrast"
                    else f"{f['font_pt']}pt < {f['required']}pt")
            print(f"  [{f['kind']}] {f['path']}  fg {f['fg']} on {f['bg']}  {what}  “{f['text']}”")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
