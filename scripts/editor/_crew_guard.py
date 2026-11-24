"""Third-party served form, ported from wicked-crew 2eab5eb's webrtc-guard.ts and csp.ts.

Keep the scanner and prologue reader in step with crew; the golden vectors are crew's own answers.
The raw guard has crew's unlimited default; the serving route explicitly applies MAX_INLINE_SCRIPTS.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
import re
from collections.abc import Sequence


WEBRTC_GLOBALS = (
    "RTCPeerConnection", "webkitRTCPeerConnection", "mozRTCPeerConnection", "RTCDataChannel",
    "RTCIceTransport", "RTCDtlsTransport", "RTCSctpTransport", "RTCRtpSender", "RTCRtpReceiver",
    "RTCRtpTransceiver", "RTCIceCandidate", "RTCSessionDescription", "RTCCertificate",
)
WEBRTC_PRELUDE_REFUSAL = "WebRTC is not available in an editor frame"
_REFUSAL = json.dumps(WEBRTC_PRELUDE_REFUSAL, separators=(",", ":"))
WEBRTC_PRELUDE = (
    '(function(w,o){if(typeof w!=="object"||w===null||w.window!==w)throw ' + _REFUSAL + ';var n='
    + json.dumps(WEBRTC_GLOBALS, separators=(",", ":"))
    + ',k=o.getOwnPropertyNames(w),i,d;for(i=0;i!==k.length;i++)if(/^(webkit|moz)?RTC/.test(k[i])'
    + '&&(d=o.getOwnPropertyDescriptor(w,k[i]))&&d.configurable)n.push(k[i]);'
    + 'for(i=0;i!==n.length;i++){o.defineProperty(w,n[i],{value:void 0,writable:false,configurable:false});'
    + 'if(w[n[i]]!==void 0)throw ' + _REFUSAL + '}})(window,({}).constructor);\n'
)
MAX_INLINE_SCRIPTS = 200

_LINE_END = frozenset("\n\r\u2028\u2029")
# ECMAScript \s, not Python's broader Unicode whitespace set (which also includes U+0085 and U+001C–1F).
_SPACE = frozenset("\t\n\v\f\r \u00a0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff" + "".join(map(chr, range(0x2000, 0x200b))))


def _identifier_part(c: str) -> bool:
    # JS \w is ASCII. Every non-ASCII UTF-16 unit matches crew's [\u0080-\uFFFF], including astral pairs.
    return bool(c) and ("a" <= c <= "z" or "A" <= c <= "Z" or "0" <= c <= "9" or c in "_$\\" or ord(c) >= 0x80)


def _char(text: str, i: int) -> str:
    """JS indexed access at end of text, represented by an empty non-matching character."""
    return text[i] if i < len(text) else ""


def _ends_by_asi(text: str, i: int) -> bool:
    if i >= len(text):
        return True
    c = text[i]
    if c in "\"'{~" or "0" <= c <= "9":
        return True
    if c == "!":
        return _char(text, i + 1) != "="
    if c == ".":
        return "0" <= _char(text, i + 1) <= "9"
    if c == "\\":
        return True
    if c in "+-":
        return _char(text, i + 1) == c
    if not _identifier_part(c):
        return False
    j = i
    while j < len(text) and _identifier_part(text[j]) and text[j] not in _SPACE:
        j += 1
    return text[i:j] not in ("in", "instanceof")


@dataclass(frozen=True)
class PrologueEnd:
    at: int
    after_hashbang: bool
    semicolon: bool


def prologue_end(text: str) -> PrologueEnd:
    """Past the hashbang and inert directive prologue, as crew's JavaScript lexer reads them."""
    n = len(text)
    i = at = 0
    after_hashbang = semicolon = False
    if text.startswith("#!"):
        while i < n and text[i] not in _LINE_END:
            i += 1
        at = i
        after_hashbang = True
    crossed = False
    line_start = before_directives = True

    def skip() -> bool:
        nonlocal i, crossed, line_start
        while True:
            while i < n and text[i] in _SPACE:
                if text[i] in _LINE_END:
                    crossed = line_start = True
                i += 1
            if before_directives and line_start and text.startswith("-->", i):
                while i < n and text[i] not in _LINE_END:
                    i += 1
                continue
            if text.startswith("/*", i):
                close = text.find("*/", i + 2)
                if close < 0:
                    return False
                if any(c in _LINE_END for c in text[i:close]):
                    crossed = line_start = True
                i = close + 2
            elif text.startswith("//", i) or (before_directives and text.startswith("<!--", i)):
                while i < n and text[i] not in _LINE_END:
                    i += 1
            else:
                return True

    while skip():
        quote = _char(text, i)
        if quote not in ('"', "'"):
            break
        before_directives = False
        j = i + 1
        closed = False
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == quote:
                closed = True
                j += 1
                break
            if c in "\n\r":
                break
            j += 1
        if not closed:
            break
        line_start = False
        end = i = j
        crossed = False
        if not skip():
            break
        if _char(text, i) == ";":
            i += 1
            line_start = False
            at = i
            semicolon = False
        elif text.startswith("<!--", i):
            at = end
            semicolon = True
            after_hashbang = False
            break
        elif (crossed or i >= n) and _ends_by_asi(text, i):
            at = end
            semicolon = True
        else:
            break
        after_hashbang = False
    return PrologueEnd(at, after_hashbang, semicolon)


def with_prelude(text: str) -> str:
    end = prologue_end(text)
    return (text[:end.at] + (";" if end.semicolon else "") + ("\n" if end.after_hashbang else "")
            + WEBRTC_PRELUDE + text[end.at:])


@dataclass(frozen=True)
class GuardedBundle:
    body: bytes
    script_hashes: list[str]
    too_many: int | None = None


_JS_TYPES = frozenset((
    "application/ecmascript", "application/javascript", "application/x-ecmascript", "application/x-javascript",
    "text/ecmascript", "text/javascript", "text/javascript1.0", "text/javascript1.1", "text/javascript1.2",
    "text/javascript1.3", "text/javascript1.4", "text/javascript1.5", "text/jscript", "text/livescript",
    "text/x-ecmascript", "text/x-javascript",
))
_RAW_TEXT = frozenset(("style", "xmp", "iframe", "noembed", "noframes", "noscript", "textarea", "title"))
_WS = frozenset("\t\n\f\r ")
_TAG_END = _WS | frozenset("/>")
_NAMED_REFS = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "sol": "/", "period": ".",
               "plus": "+", "lowbar": "_", "colon": ":", "semi": ";", "comma": ",", "Tab": "\t", "NewLine": "\n"}


@dataclass(frozen=True)
class InlineScript:
    start: int
    end: int
    runs: bool


def decode_attribute(value: str) -> str:
    def numeric(match: re.Match) -> str:
        digits = match[1] if match[1] is not None else match[2]
        # JS parseInt produces Infinity for huge input; no need to build an unbounded Python int.
        significant = digits.lstrip("0")
        cp = int(significant or "0", 16 if match[1] is not None else 10) if len(significant) <= 7 else 0x110000
        return chr(cp) if 0 < cp <= 0x10ffff and not 0xd800 <= cp <= 0xdfff else "\ufffd"
    value = re.sub(r"&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));?", numeric, value)
    return re.sub(r"&([A-Za-z]+);", lambda m: _NAMED_REFS.get(m[1], m[0]), value)


def _runs_inline(attrs: dict[str, str], svg: bool) -> bool:
    if ("href" in attrs or "xlink:href" in attrs) if svg else "src" in attrs:
        return False
    language = None if svg else attrs.get("language")
    raw = attrs["type"] if "type" in attrs else "text/" + language if language not in (None, "") else ""
    if raw == "" or raw.lower() == "module":
        return True
    return raw.strip("\t\n\f\r ").lower() in _JS_TYPES


def inline_scripts(html: str) -> list[InlineScript]:
    """Crew's HTML tokenizer: comments, attributes, raw text, and script-data escape states."""
    s, n = html, len(html)
    out: list[InlineScript] = []

    def at(p: int, word: str) -> bool:
        return s[p:p + len(word)].lower() == word

    def delimited(p: int) -> bool:
        return p < n and s[p] in _TAG_END

    def attributes(p: int) -> tuple[int, dict[str, str], bool]:
        attrs: dict[str, str] = {}
        j = p
        while j < n:
            start = j
            while j < n and (s[j] in _WS or s[j] == "/"):
                j += 1
            if j >= n:
                break
            if s[j] == ">":
                return j + 1, attrs, j > start and s[j - 1] == "/"
            k = j + 1
            while k < n and s[k] not in _TAG_END and s[k] != "=":
                k += 1
            name = s[j:k].lower()
            m = k
            while m < n and s[m] in _WS:
                m += 1
            value = ""
            if _char(s, m) == "=":
                m += 1
                while m < n and s[m] in _WS:
                    m += 1
                q = _char(s, m)
                if q in ('"', "'"):
                    close = s.find(q, m + 1)
                    if close < 0:
                        return -1, attrs, False
                    value, j = s[m + 1:close], close + 1
                else:
                    e = m
                    while e < n and s[e] not in _WS and s[e] != ">":
                        e += 1
                    value, j = s[m:e], e
            else:
                j = m
            if name not in attrs:
                attrs[name] = decode_attribute(value)
        return -1, attrs, False

    ahead = {"close": -2, "bang": -2}

    def next_from(key: str, needle: str, start: int) -> int:
        if ahead[key] == -2 or (ahead[key] != -1 and ahead[key] < start):
            ahead[key] = s.find(needle, start)
        return ahead[key]

    def script_text_end(p: int) -> int:
        state = "data"
        i = p
        while i < n:
            if state == "data":
                lt = s.find("<", i)
                if lt < 0:
                    return n
                if at(lt, "</script") and delimited(lt + 8):
                    return lt
                if at(lt, "<!--"):
                    state, i = "escaped", lt + 2
                    continue
                i = lt + 1
                continue
            lt = s.find("<", i)
            close = next_from("close", "-->", i)
            if close >= 0 and (lt < 0 or close < lt):
                state, i = "data", close + 3
                continue
            if lt < 0:
                return n
            if at(lt, "</script") and delimited(lt + 8):
                if state == "escaped":
                    return lt
                state, i = "escaped", lt + 8
                continue
            if state == "escaped" and at(lt, "<script") and delimited(lt + 7):
                state, i = "double", lt + 7
                continue
            i = lt + 1
        return n

    foreign = i = 0
    while i < n:
        lt = s.find("<", i)
        if lt < 0:
            break
        c = _char(s, lt + 1)
        if at(lt, "<!--"):
            if _char(s, lt + 4) == ">":
                i = lt + 5
                continue
            if s.startswith("->", lt + 4):
                i = lt + 6
                continue
            a = next_from("close", "-->", lt + 4)
            b = next_from("bang", "--!>", lt + 4)
            end = (-1 if b < 0 else b + 4) if a < 0 else a + 3 if b < 0 or a < b else b + 4
            if end < 0:
                break
            i = end
            continue
        if c in ("!", "?"):
            end = s.find(">", lt + 2)
            if end < 0:
                break
            i = end + 1
            continue
        if c == "/":
            if not re.fullmatch("[A-Za-z]", _char(s, lt + 2)):
                end = s.find(">", lt + 2)
                if end < 0:
                    break
                i = end + 1
                continue
            k = lt + 2
            while k < n and s[k] not in _TAG_END:
                k += 1
            closing = s[lt + 2:k].lower()
            if foreign > 0 and closing in ("svg", "math"):
                foreign -= 1
            end, _, _ = attributes(k)
            if end < 0:
                break
            i = end
            continue
        if not re.fullmatch("[A-Za-z]", c):
            i = lt + 1
            continue
        k = lt + 1
        while k < n and s[k] not in _TAG_END:
            k += 1
        name = s[lt + 1:k].lower()
        end, attrs, self_closing = attributes(k)
        if end < 0:
            break
        if name in ("svg", "math") and not self_closing:
            foreign += 1
            i = end
            continue
        if name == "script" and foreign > 0 and self_closing:
            i = end
            continue
        if name == "script":
            text_end = script_text_end(end)
            out.append(InlineScript(end, text_end, _runs_inline(attrs, foreign > 0)))
            if text_end >= n:
                break
            after_end, _, _ = attributes(text_end + 8)
            if after_end < 0:
                break
            i = after_end
            continue
        if name in _RAW_TEXT and foreign == 0:
            j = end
            while True:
                close = s.find("</", j)
                if close < 0:
                    j = n
                    break
                if at(close + 2, name) and delimited(close + 2 + len(name)):
                    j = close
                    break
                j = close + 2
            i = j
            continue
        if name == "plaintext":
            break
        i = end
    return out


def guard_bundle(body: bytes, max_scripts: int | float = math.inf) -> GuardedBundle:
    html = re.sub(r"\r\n?", "\n", body.decode("utf-8", errors="replace"))
    scripts = [s for s in inline_scripts(html) if s.runs]
    if len(scripts) > max_scripts:
        return GuardedBundle(b"", [], len(scripts))
    parts: list[str] = []
    script_hashes: list[str] = []
    last = 0
    for script in scripts:
        text = with_prelude(html[script.start:script.end].replace("\0", "\ufffd"))
        parts.extend((html[last:script.start], text))
        last = script.end
        script_hashes.append(base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii"))
    parts.append(html[last:])
    return GuardedBundle("".join(parts).encode("utf-8"), script_hashes)


BUNDLE_CSP_BASE = (
    "sandbox allow-scripts; default-src 'none'; script-src {SCRIPTS}; style-src 'unsafe-inline'; "
    "img-src data: blob:{MEDIA}; media-src blob:; font-src data:{MEDIA}; frame-src 'none'; "
    "child-src 'none'; connect-src 'none'; form-action 'none'; base-uri 'none'; "
    "worker-src 'none'; manifest-src 'none'"
)
INLINE_ONLY_POLICY = "script-src 'unsafe-inline'"


def third_party_scripts(script_hashes: Sequence[str]) -> str:
    unique = dict.fromkeys(script_hashes)
    return " ".join("'sha256-" + h + "'" for h in unique) if unique else "'none'"


def bundle_headers(script_hashes: Sequence[str] = ()) -> dict[str, str]:
    policy = BUNDLE_CSP_BASE.replace("{MEDIA}", "").replace("{SCRIPTS}", third_party_scripts(script_hashes))
    return {
        "Content-Security-Policy": policy + ", " + INLINE_ONLY_POLICY,
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Content-Type-Options": "nosniff",
        "X-DNS-Prefetch-Control": "off",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
    }


def shell_csp(origin: str) -> str:
    return f"frame-src {origin}/api/v1/editors/ {origin}/api/v1/projects/ blob: data:"
