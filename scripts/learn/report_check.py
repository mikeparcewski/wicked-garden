#!/usr/bin/env python3
"""The mechanical floor of learn's report mode (the `sourced-report` workflow's six cards).

    wicked-garden run scripts/learn/report_check.py preflight --lens <lens> [--records <dir>]
    wicked-garden run scripts/learn/report_check.py check --packet <file|-> [--records <dir>] [--repo <dir>]

Deterministic and read-only: it writes nothing and makes no network call. The packet contract is the
learn skill's refs/report-claims.md. Pass every folder as an absolute path.

``preflight`` runs at the start of ``gather``. It lists the documents staged under ``--records`` and
refuses a lens that requires documents (``due-diligence``, ``analyze``) when there are none. It prints
``{ok, lens, records, documents, documents_rule, reason?}``. Exit 0: go on. Exit 3: refused, the reason
says why. Exit 2: an unknown lens.

``check`` judges a report packet. It prints ``{ok, lens, web, stopped, counts, unchecked, findings}``
and exits 0 with no findings, 1 with findings, 2 when the packet cannot be read. A finding is
``{where, rule, message}``. What it refuses:

- the packet: not an object, ``schema`` != 1, an unknown lens, no ``web`` state (or no reason when the
  web was not used), ``documents`` not a list of relative paths, documents named with no ``--records``
  to check them against (``records-missing``), too many sources or claims;
- sources: a bad or duplicate ``S<n>`` id; a record that is not exactly one of web
  ``{url, title, observed_at}``, file ``{file, page?, quote}``, code ``{path, line?, quote}`` or tool
  ``{source, tool, args, observed_at}`` (``args`` may be ``{}``, never absent); a non-http(s) url; an
  ``observed_at`` that is not an ISO-8601 time with seconds and a zone, or lies in the future; a web source while the web was not available
  (``web-not-available``), or the ``web`` source dressed as a tool (``web-as-tool``); a quote under 8
  characters once normalised (a code quote located by ``line`` is checked on that line instead); a file that is not among the staged ``documents`` (``file-not-staged``;
  ``brief`` is text pasted into the brief, checked against ``packet.brief``); a file or code path that
  resolves outside its folder (symlinks included), is missing, or whose text does not hold the quote
  (``quote-not-found``; ``quote-not-found-in-pdf-text`` when only a pdf's text derivative was searched,
  the one finding the fidelity check may clear by reading the original); code sources with no
  ``--repo``. A file the floor cannot read as text (an image, a pdf with no derivative, an empty or
  oversized file) is listed under ``unchecked`` with the reason;
- claims: a bad or duplicate ``C<n>`` id, empty text, no source (``claim-unsourced``), a source id the
  log does not hold (``claim-unknown-source``);
- the report: empty; a ``[C<n>]`` citation of an unknown claim (any length); a claim the report never
  cites; a URL (in the report or in a claim) that is not a web source in the log (``url-not-in-log``: a
  markdown destination or autolink is compared exactly, a bare URL without its closing punctuation; a
  bare URL inside emphasis marks is refused as ``url-formatted``);
- the stop rule: a lens that requires documents producing claims with none staged
  (``documents-required``); a stop that carries claims or a report (the reason is the whole output);
  a stop while something is readable: a non-empty staged document, a source in the log, or text in
  the brief (``stopped-with-documents``); no claims and no stop reason. All the text one check reads is
  budgeted (256 MiB); a file past the budget is listed as ``unchecked``.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, urlunparse

# The six lenses (refs/report-<lens>.md) and their documents rule (DES-CATALOG-002 rev 8 §3, ruling 5):
# crew's catalog holds Start for a required input; this is the same rule, checked again by the seat.
LENSES = {
    "research": "not-taken",
    "competitive": "not-taken",
    "due-diligence": "required",
    "analyze": "required",
    "critique": "optional",
    "estimate": "optional",
}
LENS_TITLES = {
    "research": "Research a question",
    "competitive": "Competitive or market analysis",
    "due-diligence": "Due diligence",
    "analyze": "Analyze documents",
    "critique": "Critique",
    "estimate": "Estimate and price",
}
WEB_STATES = ("used", "not-picked", "unavailable")
WEB_SOURCE = "web"  # crew's web source: its pages are web records, never tool records
SOURCE_ID_RE = re.compile(r"^S[1-9]\d{0,5}$")
CLAIM_ID_RE = re.compile(r"^C[1-9]\d{0,5}$")
# Any citation group, ids of any length: an id the claims cannot hold is reported, never skipped.
CITE_GROUP_RE = re.compile(r"\[\s*(C\d+(?:\s*,\s*C\d+)*)\s*\]")
# Parentheses may belong to a URL (``/wiki/X_(y)``); an unbalanced closing one is the text's, not the URL's.
URL_RE = re.compile(r"""https?://[^\s<>\[\]{}"'`|\\^]+""", re.IGNORECASE)
URL_TRAILING = ".,;:!?"
# A markdown link's destination and an autolink are taken exactly as written: no punctuation is trimmed.
MD_LINK_RE = re.compile(r"\]\(\s*(<?)(https?://)", re.IGNORECASE)
AUTOLINK_RE = re.compile(r"<(https?://[^\s<>]+)>", re.IGNORECASE)
# Seconds required: Python 3.10's fromisoformat refuses a time without them.
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d{1,9}))?(?:Z|[+-]\d{2}:\d{2})$")
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
                 ".html", ".htm", ".xml", ".log", ".rst", ".ini", ".toml"}
PACKET_MAX_BYTES = 8 * 1024 * 1024
DOC_MAX_BYTES = 64 * 1024 * 1024
MAX_SOURCES = 2000
MAX_CLAIMS = 2000
QUOTE_MIN_CHARS = 8
TEXT_BUDGET_BYTES = 256 * 1024 * 1024  # all the text one check reads, over every file
FUTURE_SKEW = timedelta(minutes=10)
# A critique of a pasted claim, or an estimate's scope from the intent, cites the brief:
# ``{"file": "brief", "quote": ...}``, checked against ``packet.brief``.
BRIEF_FILE = "brief"


def _f(where: str, rule: str, message: str) -> dict:
    return {"where": where, "rule": rule, "message": message}


def _nonempty(v: object) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _iso(v: object) -> datetime | None:
    m = ISO_RE.match(v) if isinstance(v, str) else None
    if not m:
        return None
    # Python 3.10's fromisoformat takes 3 or 6 fraction digits only: compare at microseconds.
    frac = m.group(1)
    t = v if frac is None else v.replace("." + frac, "." + (frac + "000000")[:6], 1)
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def norm_url(url: str) -> str | None:
    """Scheme and host lowercased and the fragment dropped; the path and query are kept as written."""
    try:
        p = urlparse(url.strip())
        p.port  # noqa: B018  (raises ValueError on a malformed authority)
    except ValueError:
        return None
    if p.scheme.lower() not in ("http", "https") or not p.netloc:
        return None
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path, p.params, p.query, ""))


def _trim_bare(u: str) -> str:
    """A bare URL without the sentence punctuation or the unbalanced ``)`` after it. Formatting marks
    (``_``, ``*``) are never trimmed: a URL wrapped in them does not match, and the seat rewrites it as a
    link. One backward scan: the work is linear in the URL's length."""
    opens, closes = u.count("("), u.count(")")
    end = len(u)
    while end:
        ch = u[end - 1]
        if ch in URL_TRAILING:
            pass
        elif ch == ")" and opens < closes:
            closes -= 1
        else:
            break
        end -= 1
    return u[:end]


def _md_destination(text: str, i: int, angle: bool) -> tuple[str, int] | None:
    """The markdown link destination starting at ``text[i]``, exactly as a renderer reads it, or ``None``
    when it is not a complete destination (then its text stays for the bare-URL scan). ``<…>`` form: up
    to the ``>`` on the same line, parentheses kept. Bare form: up to the ``)`` that closes the link
    (nested parens kept) or the whitespace before a title."""
    if angle:
        j = text.find(">", i)
        if j < 0 or "\n" in text[i:j] or "<" in text[i:j]:
            return None
        return text[i:j], j
    depth, j = 0, i
    while j < len(text):
        ch = text[j]
        if ch.isspace():
            return text[i:j], j  # a title may follow; whatever follows is scanned on its own
        if ch in "<>":
            return None
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return text[i:j], j
            depth -= 1
        j += 1
    return None


def urls_in(text: str) -> list[tuple[str, bool]]:
    """Every http(s) URL in the text. A markdown destination or an autolink is exact; a bare URL loses
    the punctuation that ends its sentence. Returns ``(url, ambiguous)``: a bare URL right after an
    emphasis mark (``_``, ``*``) is ambiguous, since what the reader sees is not what is written. Each
    character is scanned a bounded number of times."""
    text = text or ""
    out: list[str] = []
    masked = list(text)
    consumed = 0
    for m in MD_LINK_RE.finditer(text):
        start = m.start(2)
        if start < consumed:
            continue  # inside a destination already read
        got = _md_destination(text, start, bool(m.group(1)))
        if got is None:
            continue
        dest, end = got
        out.append((dest, False))
        masked[start:end] = " " * (end - start)
        consumed = end
    rest = "".join(masked)
    masked = list(rest)
    for m in AUTOLINK_RE.finditer(rest):
        out.append((m.group(1), False))
        masked[m.start(1):m.end(1)] = " " * (m.end(1) - m.start(1))
    rest = "".join(masked)
    for m in URL_RE.finditer(rest):
        u = _trim_bare(m.group(0))
        if u:
            out.append((u, m.start() > 0 and rest[m.start() - 1] in "_*"))
    return out


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                                   "–": "-", "—": "-", "­": ""}))
    return " ".join(s.casefold().split())


def _rel_ok(p: object) -> bool:
    if not _nonempty(p):
        return False
    pp = PurePosixPath(str(p).replace("\\", "/"))
    return not pp.is_absolute() and ".." not in pp.parts and not re.match(r"^[A-Za-z]:", str(p))


def _inside(path: Path, root: Path) -> Path | None:
    """``path`` resolved (symlinks followed), or ``None`` when that lands outside ``root``."""
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (ValueError, OSError, RuntimeError):
        return None
    return resolved


def staged_files(records: Path | None) -> list[str]:
    """Every file under the records dir but dotfiles and the MANIFEST, relative, sorted."""
    if records is None or not records.is_dir():
        return []
    return sorted(p.relative_to(records).as_posix() for p in records.rglob("*")
                  if p.is_file() and not p.name.startswith(".") and not p.name.upper().startswith("MANIFEST"))


def staged_documents(records: Path | None) -> list[str]:
    """The documents a person staged: a pdf's text derivative (``<name>.txt`` or ``<name>.pdf.txt``
    beside it) is the same document, so it is not counted twice."""
    rel = staged_files(records)
    derivatives = set()
    for r in rel:
        if r.lower().endswith(".pdf"):
            derivatives |= {r[:-4] + ".txt", r + ".txt"}
    return [r for r in rel if r not in derivatives]


class Texts:
    """The normalised text of each confined file, read once however many sources quote it, within one
    budget for the whole check. A repository file keeps its raw text too, for quotes located by line."""

    def __init__(self) -> None:
        self._cache: dict[tuple[Path, bool], tuple[str | None, str, bool, str | None]] = {}
        self._budget = TEXT_BUDGET_BYTES

    def _entry(self, path: Path, root: Path, code: bool):
        if (path, code) not in self._cache:
            got = self._read(path, root, code, self._budget)
            if got[0] is not None:
                self._budget -= len(got[0].encode("utf-8")) + len((got[3] or "").encode("utf-8"))
            self._cache[(path, code)] = got
        return self._cache[(path, code)]

    def get(self, path: Path, root: Path, code: bool = False) -> tuple[str | None, str, bool]:
        """(normalised text or None, why it is None, whether it came from a pdf's derivative).

        A repository file (``code``) is read as text whatever its suffix."""
        return self._entry(path, root, code)[:3]

    def lines(self, path: Path, root: Path, wanted: set[int]) -> dict[int, str]:
        """The wanted lines (from 1) of a repository file, normalised, in one forward scan that stops at
        the last one wanted. A line past the end is ``""``."""
        raw = self._entry(path, root, True)[3] or ""
        out: dict[int, str] = {}
        last, n, pos = max(wanted), 1, 0
        while n <= last and pos <= len(raw):
            nl = raw.find("\n", pos)
            end = len(raw) if nl < 0 else nl
            if n in wanted:
                out[n] = norm_text(raw[pos:end])
            if nl < 0:
                break
            pos, n = nl + 1, n + 1
        return {k: out.get(k, "") for k in wanted}

    @staticmethod
    def _read(path: Path, root: Path, code: bool = False, budget: int = TEXT_BUDGET_BYTES):
        suffix = path.suffix.lower()
        if code:
            candidates, from_pdf = [path], False
        elif suffix == ".pdf":
            candidates, from_pdf = [path.with_suffix(".txt"), path.with_name(path.name + ".txt")], True
        elif suffix in TEXT_SUFFIXES:
            candidates, from_pdf = [path], False
        else:
            return None, "not a text format (an image or another binary): read the original", False, None
        why = "a pdf with no text derivative: read the original" if from_pdf else "empty"
        for c in candidates:
            if not c.is_file():
                continue
            real = _inside(c, root)
            if real is None:
                return None, f"{c.name} resolves outside the folder: not read", from_pdf, None
            size = real.stat().st_size
            if size > DOC_MAX_BYTES:
                return None, f"over {DOC_MAX_BYTES // (1024 * 1024)} MiB: read the original", from_pdf, None
            if size * (2 if code else 1) > budget:
                return None, (f"this check already read {TEXT_BUDGET_BYTES // (1024 * 1024)} MiB of text: "
                              "read the original"), from_pdf, None
            raw = real.read_text(encoding="utf-8", errors="replace")
            text = norm_text(raw)
            if text:
                return text, "", from_pdf, (raw if code else None)
            why = "its text is empty: read the original"
        return None, why, from_pdf, None


def preflight(lens: str, records: Path | None) -> tuple[int, dict]:
    if lens not in LENSES:
        return 2, {"ok": False, "lens": lens, "reason": f"unknown lens {lens!r}: one of {', '.join(LENSES)}"}
    docs = staged_documents(records)
    rule = LENSES[lens]
    out = {"ok": True, "lens": lens, "records": str(records.resolve()) if records else None,
           "documents": docs, "documents_rule": rule}
    if rule == "required" and not docs:
        out["ok"] = False
        out["reason"] = (f"{LENS_TITLES[lens]} needs documents and none were staged for this job: "
                         "attach the documents and start it again.")
        return 3, out
    return 0, out


def _quote_finding(w: str, quote: str, text: str | None, why: str, from_pdf: bool, label: str,
                   sid: str | None, unchecked: list[dict]) -> list[dict]:
    if text is None:
        unchecked.append({"source": sid or w, "file": label, "why": why})
        return []
    if norm_text(quote) in text:
        return []
    if from_pdf:
        return [_f(w, "quote-not-found-in-pdf-text", f"the quote is not in {label}'s extracted text: "
                   "read the pdf page; extraction may have lost it")]
    return [_f(w, "quote-not-found", f"the quote is not in {label}'s text")]


class Ctx:
    def __init__(self, web_state, documents, records, repo, now, brief):
        self.web_state = web_state
        self.documents = documents
        self.records = records.resolve() if records else None
        self.repo = repo.resolve() if repo else None
        self.now = now
        self.brief = brief
        self.texts = Texts()
        self.unchecked: list[dict] = []
        # Repository quotes located by line, checked after the log in one scan per file.
        self.located: dict[Path, list[tuple[str, int, str, str]]] = {}

    def located_findings(self) -> list[dict]:
        out = []
        for real, asks in self.located.items():
            got = self.texts.lines(real, self.repo, {line for _, line, _, _ in asks})
            for w, line, quote, p in asks:
                if quote not in got[line]:
                    out.append(_f(w, "quote-not-found", f"the quote is not on line {line} of {p}"))
        return out


def _check_source(s: object, n: int, ctx: Ctx) -> tuple[list[dict], str | None, str | None]:
    """Findings for one source record; returns (findings, its id, its kind)."""
    w = f"sources#{n}"
    if not isinstance(s, dict):
        return [_f(w, "source-shape", "a source is a JSON object")], None, None
    out: list[dict] = []
    sid = s.get("id")
    if not isinstance(sid, str) or not SOURCE_ID_RE.match(sid):
        out.append(_f(w, "source-id", "id must be S<n> (S1, S2, ...)"))
        sid = None
    else:
        w = f"sources#{sid}"
    kinds = [k for k, key in (("web", "url"), ("file", "file"), ("code", "path"), ("tool", "tool")) if key in s]
    if len(kinds) != 1:
        out.append(_f(w, "source-kind", "a source is exactly one of {url, title, observed_at}, {file, page?, quote}, "
                      "{path, line?, quote} or {source, tool, args, observed_at}"))
        return out, sid, None
    kind = kinds[0]
    if kind in ("web", "tool"):
        at = _iso(s.get("observed_at"))
        if at is None:
            out.append(_f(w, "source-observed-at", "observed_at must be an ISO-8601 time with seconds and a zone "
                          "(the fetch or call time, UTC)"))
        elif at > ctx.now + FUTURE_SKEW:
            out.append(_f(w, "source-observed-at", f"observed_at {s['observed_at']} is in the future"))
    if kind in ("file", "code"):
        q = s.get("quote")
        located = kind == "code" and isinstance(s.get("line"), int) and not isinstance(s.get("line"), bool)
        if not _nonempty(q) or not norm_text(q):
            out.append(_f(w, "source-quote", "a file or code source carries the quote the claim rests on"))
        elif not located and len(norm_text(q)) < QUOTE_MIN_CHARS:
            out.append(_f(w, "source-quote", f"the quote is under {QUOTE_MIN_CHARS} characters: too short to locate"))
    quote_ok = not any(f["rule"] == "source-quote" for f in out)
    if kind == "web":
        if norm_url(str(s.get("url") or "")) is None:
            out.append(_f(w, "source-url", "url must be http(s)"))
        if not _nonempty(s.get("title")):
            out.append(_f(w, "source-title", "a web source names the page's title"))
        if ctx.web_state is not None and ctx.web_state != "used":
            out.append(_f(w, "web-not-available", f"a web source, but the packet says the web was {ctx.web_state}: "
                          "a page this job could not fetch is not a source"))
    elif kind == "tool":
        if not _nonempty(s.get("source")) or not _nonempty(s.get("tool")):
            out.append(_f(w, "source-tool", "a tool source names its source and the tool called"))
        elif s["source"].strip().lower() == WEB_SOURCE:
            out.append(_f(w, "web-as-tool", "a page from the web source is a web record {url, title, observed_at}"))
        args = s.get("args", None)
        if not (_nonempty(args) or isinstance(args, (dict, list))):
            out.append(_f(w, "source-args", "a tool source carries the read-only arguments it was called with, "
                          "so the fidelity check can call it again"))
    elif kind == "code":
        p = s.get("path")
        line = s.get("line")
        if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
            out.append(_f(w, "source-line", "line is a whole number from 1"))
        if not _rel_ok(p):
            out.append(_f(w, "source-path", "path is relative to the repository root"))
        elif ctx.repo is None:
            out.append(_f(w, "repo-missing", "a code source needs --repo (the repository in scope) to be checked"))
        else:
            real = _inside(ctx.repo / str(p).replace("\\", "/"), ctx.repo)
            if real is None:
                out.append(_f(w, "path-outside-repo", f"{p} resolves outside the repository"))
            elif not real.is_file():
                out.append(_f(w, "path-missing", f"{p} is not a file in the repository"))
            elif quote_ok:
                text, why, from_pdf = ctx.texts.get(real, ctx.repo, code=True)
                if text is not None and isinstance(line, int) and not isinstance(line, bool) and line >= 1:
                    ctx.located.setdefault(real, []).append((w, line, norm_text(s["quote"]), str(p)))
                else:
                    out += _quote_finding(w, s["quote"], text, why, from_pdf, str(p), sid, ctx.unchecked)
    else:  # file
        f = s.get("file")
        page = s.get("page")
        if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
            out.append(_f(w, "source-page", "page is a whole number from 1"))
        if not _rel_ok(f):
            out.append(_f(w, "source-file", "file is a path relative to the staged documents"))
            return out, sid, kind
        f = str(f).replace("\\", "/")
        if f == BRIEF_FILE:  # text pasted into the brief: checked against the packet's copy
            if quote_ok and norm_text(s["quote"]) not in norm_text(ctx.brief or ""):
                out.append(_f(w, "quote-not-found", "the quote is not in the brief's pasted text (packet.brief)"))
            return out, sid, kind
        if ctx.documents is not None and f not in ctx.documents:
            out.append(_f(w, "file-not-staged", f"{f} is not among the documents staged for this job"))
        if ctx.records is not None:
            real = _inside(ctx.records / f, ctx.records)
            if real is None:
                out.append(_f(w, "file-outside-records", f"{f} resolves outside the staged documents"))
            elif not real.is_file():
                out.append(_f(w, "file-missing", f"{f} is not under the staged documents"))
            elif quote_ok:
                text, why, from_pdf = ctx.texts.get(real, ctx.records)
                out += _quote_finding(w, s["quote"], text, why, from_pdf, f, sid, ctx.unchecked)
    return out, sid, kind


def _cid_key(cid: str) -> tuple[int, str]:
    return (len(cid), cid)


def check(packet: object, records: Path | None = None, now: datetime | None = None,
          repo: Path | None = None) -> tuple[int, dict]:
    now = now or datetime.now(timezone.utc)
    if not isinstance(packet, dict):
        return 2, {"ok": False, "reason": "the packet is not a JSON object"}
    findings: list[dict] = []
    if packet.get("schema") != 1:
        findings.append(_f("packet", "packet-schema", "schema must be 1"))
    lens = packet.get("lens")
    if not isinstance(lens, str) or lens not in LENSES:
        findings.append(_f("packet", "lens", f"lens must be one of {', '.join(LENSES)}"))
        lens = None
    web = packet.get("web")
    web_state = web.get("state") if isinstance(web, dict) else None
    if not isinstance(web_state, str) or web_state not in WEB_STATES:
        findings.append(_f("packet", "web-state", f"web.state must be one of {', '.join(WEB_STATES)}"))
        web_state = None
    elif web_state != "used" and not _nonempty(web.get("reason")):
        findings.append(_f("packet", "web-state", f"web.state {web_state} needs its reason, said in the report"))
    docs = packet.get("documents", [])
    documents: set[str] | None
    if not isinstance(docs, list) or not all(_rel_ok(d) for d in docs):
        findings.append(_f("packet", "documents", "documents is a list of paths relative to the staged documents"))
        documents = None
    else:
        documents = {str(d).replace("\\", "/") for d in docs}
    if documents and records is None:
        findings.append(_f("packet", "records-missing", "the packet names staged documents: check it with --records "
                           "(the documents folder) so each file and quote is verified"))
    if records is not None and documents is not None:
        for d in sorted(documents - set(staged_files(records))):
            findings.append(_f("packet", "file-missing", f"documents names {d}, which is not staged"))
    brief = packet.get("brief") if isinstance(packet.get("brief"), str) else None
    ctx = Ctx(web_state, documents, records, repo, now, brief)

    sources = packet.get("sources", [])
    if not isinstance(sources, list):
        findings.append(_f("packet", "sources", "sources is a list"))
        sources = []
    if len(sources) > MAX_SOURCES:
        findings.append(_f("packet", "sources", f"over {MAX_SOURCES} sources: not checked"))
        sources = []
    ids: dict[str, str | None] = {}
    web_urls: set[str] = set()
    for n, s in enumerate(sources, 1):
        fs, sid, kind = _check_source(s, n, ctx)
        findings += fs
        if sid is not None:
            if sid in ids:
                findings.append(_f(f"sources#{sid}", "source-duplicate", "duplicate source id"))
            ids[sid] = kind
        if kind == "web":
            u = norm_url(str(s.get("url") or ""))
            if u:
                web_urls.add(u)

    findings += ctx.located_findings()

    claims = packet.get("claims", [])
    if not isinstance(claims, list):
        findings.append(_f("packet", "claims", "claims is a list"))
        claims = []
    if len(claims) > MAX_CLAIMS:
        findings.append(_f("packet", "claims", f"over {MAX_CLAIMS} claims: not checked"))
        claims = []
    cids: set[str] = set()
    texts: list[tuple[str, str]] = []
    for n, c in enumerate(claims, 1):
        w = f"claims#{n}"
        if not isinstance(c, dict):
            findings.append(_f(w, "claim-shape", "a claim is a JSON object"))
            continue
        cid = c.get("id")
        if not isinstance(cid, str) or not CLAIM_ID_RE.match(cid):
            findings.append(_f(w, "claim-id", "id must be C<n> (C1, C2, ...)"))
        else:
            w = f"claims#{cid}"
            if cid in cids:
                findings.append(_f(w, "claim-duplicate", "duplicate claim id"))
            cids.add(cid)
        if not _nonempty(c.get("text")):
            findings.append(_f(w, "claim-text", "text is empty"))
        else:
            texts.append((w, c["text"]))
        refs = c.get("sources")
        if not isinstance(refs, list) or not refs:
            findings.append(_f(w, "claim-unsourced", "a claim cites at least one source from the log"))
            continue
        for r in refs:
            if not isinstance(r, str) or r not in ids:
                findings.append(_f(w, "claim-unknown-source", f"cites {str(r)[:40]!r}, which the source log does not hold"))

    report = packet.get("report")
    report = report if isinstance(report, str) else ""
    stopped = packet.get("stopped")
    stopped = stopped.strip() if isinstance(stopped, str) and stopped.strip() else None
    if stopped:
        if claims:
            findings.append(_f("packet", "stopped-with-claims", "a stopped report carries no claims"))
        if report.strip():
            findings.append(_f("packet", "stopped-with-report", "a stop delivers its reason (stopped) and no report"))
        # Every staged file counts, a pdf's text derivative included: a stop is for nothing readable.
        readable = [d for d in staged_files(records) if (records / d).stat().st_size > 0] if records else []
        read = [k for k in ids.values() if k is not None]
        if readable or read or _nonempty(brief):
            findings.append(_f("packet", "stopped-with-documents", "there is something to read (a staged document, "
                               "a source in the log, or text in the brief): a stop is only for a job with nothing "
                               "readable"))
    elif not claims:
        findings.append(_f("packet", "report-no-claims", "a report with no claims says why it stopped (stopped)"))
    if lens is not None and LENSES[lens] == "required" and documents is not None and not documents and claims:
        findings.append(_f("packet", "documents-required",
                           f"{LENS_TITLES[lens]} needs documents and none were staged: gather refuses, it does not report"))
    if not report.strip() and not stopped:
        findings.append(_f("report", "report-empty", "the report is empty"))
    cited: set[str] = set()
    for m in CITE_GROUP_RE.finditer(report):
        cited |= {x.strip()[:16] for x in m.group(1).split(",")}
    for cid in sorted(cited - cids, key=_cid_key):
        findings.append(_f("report", "report-unknown-claim", f"cites [{cid}], which the claims do not hold"))
    if not stopped:
        for cid in sorted(cids - cited, key=_cid_key):
            findings.append(_f("report", "report-uncited-claim", f"claim {cid} is not cited in the report"))
    for where, text in [("report", report)] + texts:
        for u, ambiguous in urls_in(text):
            if ambiguous:
                findings.append(_f(where, "url-formatted", f"{u[:200]} sits inside emphasis marks, so the reader "
                                   "may see a different URL: write it as a link [title](url) or <url>"))
            elif norm_url(u) not in web_urls:
                findings.append(_f(where, "url-not-in-log", f"{u[:200]} is not a web source in the log: "
                                   "cite only pages this job fetched"))
    counts = {kind: sum(1 for k in ids.values() if k == kind) for kind in ("web", "file", "code", "tool")}
    counts = {"sources": len(ids), **counts, "claims": len(cids)}
    ok = not findings
    return (0 if ok else 1), {"ok": ok, "lens": lens, "web": web_state, "stopped": stopped, "counts": counts,
                               "unchecked": ctx.unchecked, "findings": findings}


def _read_packet(arg: str) -> object:
    if arg == "-":
        raw = sys.stdin.buffer.read(PACKET_MAX_BYTES + 1)
    else:
        p = Path(arg)
        if not p.is_file():
            raise ValueError(f"no packet file at {arg}")
        with p.open("rb") as fh:
            raw = fh.read(PACKET_MAX_BYTES + 1)
    if len(raw) > PACKET_MAX_BYTES:
        raise ValueError(f"the packet is over {PACKET_MAX_BYTES} bytes")
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    pf = sub.add_parser("preflight", help="refuse a documents-required lens with no documents staged")
    pf.add_argument("--lens", required=True)
    pf.add_argument("--records", type=Path)
    ck = sub.add_parser("check", help="judge a report packet (refs/report-claims.md)")
    ck.add_argument("--packet", required=True, help="the packet file, or - for stdin")
    ck.add_argument("--records", type=Path, help="the staged documents folder (absolute path)")
    ck.add_argument("--repo", type=Path, help="the repository in scope, for code sources (absolute path)")
    args = parser.parse_args(argv)
    if args.cmd == "preflight":
        code, out = preflight(args.lens, args.records)
    else:
        try:
            packet = _read_packet(args.packet)
        except (ValueError, UnicodeDecodeError, OSError, RecursionError) as e:  # JSONDecodeError is a ValueError
            print(json.dumps({"ok": False, "reason": f"cannot read the packet: {e}"}, indent=2))
            return 2
        try:
            code, out = check(packet, args.records, repo=args.repo)
        except (TypeError, ValueError, OSError, RecursionError) as e:  # a shape the rules above did not foresee
            print(json.dumps({"ok": False, "reason": f"the packet could not be checked: {type(e).__name__}: {e}"}, indent=2))
            return 2
    print(json.dumps(out, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
