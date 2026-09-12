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
``unsourced-url`` (a URL in the visible text that no file under ``--repo`` mentions) ·
``uncited-url`` (a URL with no ``--repo`` to check against and no ``data-source``).
Exit: 0 clean, 1 findings, 2 usage / unreadable input. Stdlib only.

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
SOURCE_ATTRS = ("data-source", "data-sources", "data-src-path", "data-cite")
SKIP_DIRS = {".git", "node_modules", ".venv", "target", "dist", "build", "__pycache__", ".next"}


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
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    if p.stat().st_size <= 2_000_000:
                        files.append(p)
                except OSError:
                    continue
    return files


def _path_exists_in_repos(rel: str, repos: list[str]) -> bool:
    rel_path = rel.split(":")[0]
    for repo in repos:
        if (Path(repo) / rel_path).exists():
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
    stats = {"blocks": 0, "numbers": 0, "urls": 0, "cited_numbers": 0, "sources_block": has_sources,
             "repos": repos}

    def add(kind: str, node: Node, text: str, detail: str) -> None:
        key = (kind, node.path(), text[:60])
        if key in seen:
            return
        seen.add(key)
        findings.append(Finding(kind, node.path(), text[:100], detail))

    checked_sources: set[str] = set()
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
                if not _path_exists_in_repos(s, repos):
                    add("dangling-source", el, s, "data-source names a path that does not exist under --repo")
        inline_paths = PATH_RE.findall(block_text)
        cited = bool(sources) or bool(inline_paths) or (has_sources and bool(FOOTNOTE_RE.search(block_text)))
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
        text_wo_paths = PATH_RE.sub(" ", URL_RE.sub(" ", own))
        text_wo_paths = COPYRIGHT_YEAR_RE.sub(" ", text_wo_paths)
        numbers = [n for n in NUMBER_RE.findall(text_wo_paths) if not ORDINAL_RE.match(n)]
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
            f"{stats['urls']} URLs — "
            + ("clean" if not findings else ", ".join(f"{v} {k}" for k, v in sorted(by_kind.items())))
        ),
    }


def main(argv: list[str] | None = None) -> int:
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
            print(f"  [{f['kind']}] {f['path']}  “{f['text']}”  — {f['detail']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
