#!/usr/bin/env python3
"""The mechanical floor of learn's report mode (the `sourced-report` workflow's six cards).

    wicked-garden run scripts/learn/report_check.py preflight --lens <lens> [--records <dir>]
    wicked-garden run scripts/learn/report_check.py check --packet <file|-> [--records <dir>]

Deterministic and read-only: it writes nothing and makes no network call. The packet contract is the
learn skill's refs/report-claims.md.

``preflight`` runs at the start of ``gather``. It lists the documents staged under ``--records`` and
refuses a lens that requires documents (``due-diligence``, ``analyze``) when there are none. It prints
``{ok, lens, documents, documents_rule, reason?}``. Exit 0: go on. Exit 3: refused, the reason says
why. Exit 2: an unknown lens.

``check`` judges a report packet. It prints ``{ok, lens, web, stopped, counts, unchecked, findings}``
and exits 0 with no findings, 1 with findings, 2 when the packet cannot be read. A finding is
``{where, rule, message}``. What it refuses:

- the packet: not an object, ``schema`` != 1, an unknown lens, no ``web`` state (or a missing reason
  when the web was not used), ``documents`` not a list of relative paths;
- sources: a bad or duplicate ``S<n>`` id; a record that is not exactly one of web
  ``{url, title, observed_at}``, file ``{file, page?, quote}`` or tool ``{source, tool,
  observed_at}``; a non-http(s) url; an ``observed_at`` that is not ISO-8601 or lies in the future;
  a web source while the web was not available (``web-not-available``); a file that is not among the
  staged ``documents`` (``file-not-staged``; ``brief`` is the text pasted into the brief, checked against
  ``packet.brief``); with ``--records``: a file outside it or missing, and a
  quote not found in the file's text (a pdf is read through its text derivative ``<name>.txt``; a
  pdf without one, or an image, is listed as ``unchecked`` for the fidelity check to read);
- claims: a bad or duplicate ``C<n>`` id, empty text, no source (``claim-unsourced``), a source id
  the log does not hold (``claim-unknown-source``);
- the report: empty; a ``[C<n>]`` citation of an unknown claim; a claim the report never cites; a
  URL (in the report or in a claim) that is not a web source in the log (``url-not-in-log``);
- the stop rule: a lens that requires documents producing claims with none staged
  (``documents-required``); a stop that still carries claims; no claims and no stop reason.

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
SOURCE_ID_RE = re.compile(r"^S[1-9]\d*$")
CLAIM_ID_RE = re.compile(r"^C[1-9]\d*$")
CITE_GROUP_RE = re.compile(r"\[(C[1-9]\d*(?:\s*,\s*C[1-9]\d*)*)\]")
URL_RE = re.compile(r"""https?://[^\s<>()\[\]{}"'`|]+""", re.IGNORECASE)
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
                 ".html", ".htm", ".xml", ".log", ".rst", ".ini", ".toml"}
PACKET_MAX_BYTES = 8 * 1024 * 1024
DOC_MAX_BYTES = 64 * 1024 * 1024
FUTURE_SKEW = timedelta(minutes=10)
WEB_KEYS, FILE_KEYS, TOOL_KEYS = {"url"}, {"file"}, {"source", "tool"}
# A critique of a pasted claim cites the brief: ``{"file": "brief", "quote": ...}``, against ``packet.brief``.
BRIEF_FILE = "brief"


def _f(where: str, rule: str, message: str) -> dict:
    return {"where": where, "rule": rule, "message": message}


def _nonempty(v: object) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _iso(v: object) -> datetime | None:
    if not isinstance(v, str) or not ISO_RE.match(v):
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def norm_url(url: str) -> str | None:
    """Scheme and host lowercased, the fragment dropped, one trailing slash ignored."""
    try:
        p = urlparse(url.strip())
        p.port  # noqa: B018  (raises ValueError on a malformed authority)
    except ValueError:
        return None
    if p.scheme.lower() not in ("http", "https") or not p.netloc:
        return None
    path = p.path[:-1] if p.path.endswith("/") else p.path
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, p.params, p.query, ""))


def urls_in(text: str) -> list[str]:
    """Every http(s) URL in the text, without the sentence punctuation that follows it."""
    out = []
    for m in URL_RE.finditer(text or ""):
        out.append(m.group(0).rstrip(".,;:!?*_"))
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


def _text_of(path: Path) -> str | None:
    """The readable text of a staged file, or ``None`` when the floor cannot read it as text."""
    suffix = path.suffix.lower()
    candidates = []
    if suffix == ".pdf":
        candidates = [path.with_suffix(".txt"), path.with_name(path.name + ".txt")]
    elif suffix in TEXT_SUFFIXES:
        candidates = [path]
    for c in candidates:
        if c.is_file() and c.stat().st_size <= DOC_MAX_BYTES:
            text = c.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                return text
    return None


def preflight(lens: str, records: Path | None) -> tuple[int, dict]:
    if lens not in LENSES:
        return 2, {"ok": False, "lens": lens, "reason": f"unknown lens {lens!r}: one of {', '.join(LENSES)}"}
    docs = staged_documents(records)
    rule = LENSES[lens]
    out = {"ok": True, "lens": lens, "documents": docs, "documents_rule": rule}
    if rule == "required" and not docs:
        out["ok"] = False
        out["reason"] = (f"{LENS_TITLES[lens]} needs documents and none were staged for this job: "
                         "attach the documents and start it again.")
        return 3, out
    return 0, out


def _check_source(s: object, n: int, web_state: str | None, documents: set[str] | None,
                  records: Path | None, now: datetime, unchecked: list[dict], brief: str | None) -> tuple[list[dict], str | None, str | None]:
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
    keys = set(s)
    kinds = [k for k, ks in (("web", WEB_KEYS), ("file", FILE_KEYS), ("tool", TOOL_KEYS)) if ks & keys]
    if len(kinds) != 1:
        out.append(_f(w, "source-kind", "a source is exactly one of {url, title, observed_at}, "
                      "{file, page?, quote} or {source, tool, observed_at}"))
        return out, sid, None
    kind = kinds[0]
    if kind in ("web", "tool"):
        at = _iso(s.get("observed_at"))
        if at is None:
            out.append(_f(w, "source-observed-at", "observed_at must be an ISO-8601 UTC time: the fetch or call time"))
        elif at > now + FUTURE_SKEW:
            out.append(_f(w, "source-observed-at", f"observed_at {s['observed_at']} is in the future"))
    if kind == "web":
        if norm_url(str(s.get("url") or "")) is None:
            out.append(_f(w, "source-url", "url must be http(s)"))
        if not _nonempty(s.get("title")):
            out.append(_f(w, "source-title", "a web source names the page's title"))
        if web_state is not None and web_state != "used":
            out.append(_f(w, "web-not-available", f"a web source, but the packet says the web was {web_state}: "
                          "a page this job could not fetch is not a source"))
    elif kind == "file":
        f = s.get("file")
        if not _rel_ok(f):
            out.append(_f(w, "source-file", "file is a path relative to the staged documents"))
            return out, sid, kind
        f = str(f).replace("\\", "/")
        if not _nonempty(s.get("quote")):
            out.append(_f(w, "source-quote", "a file source carries the quote the claim rests on"))
        if f == BRIEF_FILE:  # text the person pasted into the brief: checked against the packet's copy
            if _nonempty(s.get("quote")) and norm_text(s["quote"]) not in norm_text(brief or ""):
                out.append(_f(w, "quote-not-found", "the quote is not in the brief's pasted text (packet.brief)"))
            return out, sid, kind
        page = s.get("page")
        if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
            out.append(_f(w, "source-page", "page is a whole number from 1"))
        if documents is not None and f not in documents:
            out.append(_f(w, "file-not-staged", f"{f} is not among the documents staged for this job"))
        if records is not None:
            root = records.resolve()
            path = (root / f).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                out.append(_f(w, "file-outside-records", f"{f} resolves outside the staged documents"))
                return out, sid, kind
            if not path.is_file():
                out.append(_f(w, "file-missing", f"{f} is not under the staged documents"))
            elif _nonempty(s.get("quote")):
                text = _text_of(path)
                if text is None:
                    unchecked.append({"source": sid or w, "file": f, "why": "no text the floor can read "
                                      "(an image, or a pdf without a text derivative): read the original"})
                elif norm_text(s["quote"]) not in norm_text(text):
                    out.append(_f(w, "quote-not-found", f"the quote is not in {f}'s text"))
    else:
        if not _nonempty(s.get("source")) or not _nonempty(s.get("tool")):
            out.append(_f(w, "source-tool", "a tool source names its source and the tool called"))
    return out, sid, kind


def check(packet: object, records: Path | None = None, now: datetime | None = None) -> tuple[int, dict]:
    now = now or datetime.now(timezone.utc)
    if not isinstance(packet, dict):
        return 2, {"ok": False, "reason": "the packet is not a JSON object"}
    findings: list[dict] = []
    unchecked: list[dict] = []
    if packet.get("schema") != 1:
        findings.append(_f("packet", "packet-schema", "schema must be 1"))
    lens = packet.get("lens")
    if lens not in LENSES:
        findings.append(_f("packet", "lens", f"lens must be one of {', '.join(LENSES)}"))
    web = packet.get("web")
    web_state = web.get("state") if isinstance(web, dict) else None
    if web_state not in WEB_STATES:
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
    if records is not None and documents is not None:
        for d in sorted(documents - set(staged_files(records))):
            findings.append(_f("packet", "file-missing", f"documents names {d}, which is not staged"))

    sources = packet.get("sources", [])
    if not isinstance(sources, list):
        findings.append(_f("packet", "sources", "sources is a list"))
        sources = []
    ids: dict[str, str | None] = {}
    web_urls: set[str] = set()
    for n, s in enumerate(sources, 1):
        brief = packet.get("brief") if isinstance(packet.get("brief"), str) else None
        fs, sid, kind = _check_source(s, n, web_state, documents, records, now, unchecked, brief)
        findings += fs
        if sid is not None:
            if sid in ids:
                findings.append(_f(f"sources#{sid}", "source-duplicate", "duplicate source id"))
            ids[sid] = kind
        if kind == "web":
            u = norm_url(str(s.get("url") or ""))
            if u:
                web_urls.add(u)

    claims = packet.get("claims", [])
    if not isinstance(claims, list):
        findings.append(_f("packet", "claims", "claims is a list"))
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
                findings.append(_f(w, "claim-unknown-source", f"cites {r!r}, which the source log does not hold"))

    report = packet.get("report")
    report = report if isinstance(report, str) else ""
    stopped = packet.get("stopped")
    stopped = stopped.strip() if isinstance(stopped, str) and stopped.strip() else None
    if stopped and claims:
        findings.append(_f("packet", "stopped-with-claims", "a stopped report carries no claims"))
    if not stopped and not claims:
        findings.append(_f("packet", "report-no-claims", "a report with no claims says why it stopped (stopped)"))
    if (lens in LENSES and LENSES[lens] == "required" and documents is not None and not documents
            and claims):
        findings.append(_f("packet", "documents-required",
                           f"{LENS_TITLES[lens]} needs documents and none were staged: gather refuses, it does not report"))
    if not report.strip() and not stopped:
        findings.append(_f("report", "report-empty", "the report is empty"))
    cited: set[str] = set()
    for m in CITE_GROUP_RE.finditer(report):
        cited |= {x.strip() for x in m.group(1).split(",")}
    for cid in sorted(cited - cids, key=lambda x: int(x[1:])):
        findings.append(_f("report", "report-unknown-claim", f"cites [{cid}], which the claims do not hold"))
    if not stopped:
        for cid in sorted(cids - cited, key=lambda x: int(x[1:])):
            findings.append(_f("report", "report-uncited-claim", f"claim {cid} is not cited in the report"))
    for where, text in [("report", report)] + texts:
        for u in urls_in(text):
            if norm_url(u) not in web_urls:
                findings.append(_f(where, "url-not-in-log", f"{u} is not a web source in the log: "
                                   "cite only pages this job fetched"))
    counts = {
        "sources": len(ids),
        "web": sum(1 for k in ids.values() if k == "web"),
        "files": sum(1 for k in ids.values() if k == "file"),
        "tools": sum(1 for k in ids.values() if k == "tool"),
        "claims": len(cids),
    }
    ok = not findings
    return (0 if ok else 1), {"ok": ok, "lens": lens, "web": web_state, "stopped": stopped, "counts": counts,
                               "unchecked": unchecked, "findings": findings}


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
    ck.add_argument("--records", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "preflight":
        code, out = preflight(args.lens, args.records)
    else:
        try:
            packet = _read_packet(args.packet)
        except (ValueError, UnicodeDecodeError, OSError) as e:  # JSONDecodeError is a ValueError
            print(json.dumps({"ok": False, "reason": f"cannot read the packet: {e}"}, indent=2))
            return 2
        code, out = check(packet, args.records)
    print(json.dumps(out, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
