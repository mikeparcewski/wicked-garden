#!/usr/bin/env python3
"""page_count.py — the RENDERED page count of a print deliverable against the brief's budget.

F-RECON-008: a brief asked for "two pages"; the draft had two ``.page`` wrappers, each taller than
one A4 sheet, so the PDF export was four pages — two of them 85 % blank. Wrappers are not pages;
only a render knows. This module therefore counts pages from, in order of authority:

1. a PDF you already have (``--pdf``): the page tree's ``/Count`` (falling back to ``/Type /Page``
   objects, including those packed into compressed object streams);
2. a Chrome/Chromium headless print of the HTML (``--render``; the binary is looked up on PATH,
   in the usual install locations, or via ``$WICKED_CHROME`` / ``$CHROME_BIN``);
3. otherwise a STRUCTURAL ESTIMATE from the HTML (explicit page breaks + page wrappers) — reported
   as unverified, never as a pass.

Exit codes: 0 = the rendered count meets the budget; 1 = it exceeds the budget (or misses an
``--exact`` budget); 3 = nothing could render and the estimate is all there is — say so in the
deliverable's notes instead of claiming the count; 2 = usage / unreadable input. Stdlib only.

CLI:
    page_count.py <file.html|file.pdf> [--pdf out.pdf] [--budget N] [--exact] [--render] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draft._dom import parse  # noqa: E402

# ── PDF ───────────────────────────────────────────────────────────────────────────────────────

_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.DOTALL)
_PAGES_TYPE_RE = re.compile(rb"/Type\s*/Pages\b")
_PAGE_TYPE_RE = re.compile(rb"/Type\s*/Page\b(?!s)")
_PARENT_RE = re.compile(rb"/Parent\s+\d+\s+\d+\s+R")
_COUNT_RE = re.compile(rb"/Count\s+(\d+)")
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


def _inflate_object_streams(data: bytes) -> bytes:
    """Concatenate the decompressed payload of every FlateDecode object stream (where a PDF
    writer may have packed the page dictionaries)."""
    out = []
    for m in _OBJ_RE.finditer(data):
        body = m.group(3)
        if b"/ObjStm" not in body or b"FlateDecode" not in body:
            continue
        sm = _STREAM_RE.search(body)
        if not sm:
            continue
        try:
            out.append(zlib.decompress(sm.group(1)))
        except zlib.error:
            try:
                out.append(zlib.decompressobj().decompress(sm.group(1)))
            except zlib.error:
                continue
    return b"\n".join(out)


def count_pdf_pages(path: str | Path) -> int:
    """Pages in a PDF: the root page tree's ``/Count``; else the number of ``/Type /Page``
    objects (object streams inflated). Raises ValueError when the file is not a PDF."""
    data = Path(path).read_bytes()
    if not data.lstrip().startswith(b"%PDF"):
        raise ValueError(f"{path}: not a PDF (no %PDF header)")
    haystacks = [data]
    inflated = _inflate_object_streams(data)
    if inflated:
        haystacks.append(inflated)
    # 1. root /Pages node = a /Type /Pages dictionary without a /Parent
    root_counts: list[int] = []
    for hay in haystacks:
        for m in _OBJ_RE.finditer(hay):
            body = m.group(3)
            if _PAGES_TYPE_RE.search(body) and not _PARENT_RE.search(body):
                cm = _COUNT_RE.search(body)
                if cm:
                    root_counts.append(int(cm.group(1)))
        # object streams carry bare dictionaries (no `N 0 obj` wrapper)
        if hay is inflated:
            for dict_body in re.findall(rb"<<(?:(?!<<).)*?/Type\s*/Pages\b(?:(?!<<).)*?>>", hay, re.DOTALL):
                if not _PARENT_RE.search(dict_body):
                    cm = _COUNT_RE.search(dict_body)
                    if cm:
                        root_counts.append(int(cm.group(1)))
    if root_counts:
        return max(root_counts)  # an incremental update may leave an older root behind
    # 2. fall back to counting page objects
    total = 0
    for hay in haystacks:
        total += len(_PAGE_TYPE_RE.findall(hay))
    if total == 0:
        raise ValueError(f"{path}: no page tree found")
    return total


# ── Chrome render ─────────────────────────────────────────────────────────────────────────────

_CHROME_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
                 "microsoft-edge", "msedge", "brave-browser"]
_CHROME_MAC = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]
_CHROME_WIN = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome(env: dict[str, str] | None = None) -> str | None:
    """A Chrome/Chromium/Edge binary, or None. ``$WICKED_CHROME`` / ``$CHROME_BIN`` win."""
    env = os.environ if env is None else env
    for var in ("WICKED_CHROME", "CHROME_BIN"):
        cand = env.get(var)
        if cand and Path(cand).exists():
            return cand
    for name in _CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    system = platform.system()
    candidates = _CHROME_MAC if system == "Darwin" else _CHROME_WIN if system == "Windows" else []
    for cand in candidates:
        if Path(cand).exists():
            return cand
    return None


def render_pdf(html_path: str | Path, out_pdf: str | Path, chrome: str | None = None,
               timeout: float = 90.0) -> tuple[bool, str]:
    """Print `html_path` to `out_pdf` with headless Chrome. Returns (ok, detail)."""
    chrome = chrome or find_chrome()
    if chrome is None:
        return False, "no Chrome/Chromium/Edge binary found (set WICKED_CHROME to one to enable rendering)"
    src = Path(html_path).resolve()
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
           "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
           f"--print-to-pdf={Path(out_pdf).resolve()}", src.as_uri()]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"chrome failed to run: {exc}"
    if not Path(out_pdf).exists() or Path(out_pdf).stat().st_size == 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return False, f"chrome exited {proc.returncode} without writing a PDF: {' | '.join(tail)}"
    return True, chrome


# ── HTML estimate ─────────────────────────────────────────────────────────────────────────────

_BREAK_PROP_RE = re.compile(
    r"(?:page-)?break-(after|before)\s*:\s*(always|page|left|right|recto|verso)\b", re.IGNORECASE)
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def estimate_html_pages(html: str) -> dict:
    """A STRUCTURAL estimate: 1 + the number of elements that force a page break (via a class
    rule or inline style), or the number of ``.page`` wrappers when that is larger. It cannot
    see overflow — a wrapper taller than the sheet still spills onto another page."""
    doc = parse(html)
    css = doc.inline_style_text()
    breaking_selectors: list[str] = []
    for sel, body in _RULE_RE.findall(re.sub(r"/\*.*?\*/", " ", css, flags=re.DOTALL)):
        if _BREAK_PROP_RE.search(body):
            breaking_selectors.extend(s.strip() for s in sel.split(",") if s.strip())
    class_names = {s.lstrip(".") for s in breaking_selectors if s.startswith(".") and "." not in s[1:] and " " not in s}
    breaks = 0
    wrappers = 0
    for el in doc.elements():
        classes = set(el.classes())
        if classes & class_names:
            breaks += 1
        elif _BREAK_PROP_RE.search(el.attrs.get("style", "")):
            breaks += 1
        if "page" in classes or el.attrs.get("data-page") is not None:
            wrappers += 1
    at_page = re.findall(r"@page[^{]*\{[^}]*\}", css)
    size = None
    for block in at_page:
        m = re.search(r"size\s*:\s*([^;]+);", block)
        if m:
            size = m.group(1).strip()
    return {"breaks": breaks, "wrappers": wrappers, "estimate": max(breaks + 1, wrappers, 1),
            "page_size": size}


# ── verdict ───────────────────────────────────────────────────────────────────────────────────

def run(target: str, pdf: str | None = None, budget: int | None = None, exact: bool = False,
        render: bool = False, chrome: str | None = None) -> dict:
    report: dict = {"check": "pages", "file": target, "budget": budget, "exact": exact,
                    "pages": None, "source": None, "verified": False, "ok": None, "notes": []}
    path = Path(target)
    if not path.exists():
        raise OSError(f"{target}: no such file")
    is_pdf = path.suffix.lower() == ".pdf" or path.read_bytes()[:5] == b"%PDF-"
    html = None if is_pdf else path.read_text(encoding="utf-8", errors="replace")

    if is_pdf:
        report["pages"], report["source"], report["verified"] = count_pdf_pages(path), "pdf", True
    elif pdf and Path(pdf).exists():
        report["pages"], report["source"], report["verified"] = count_pdf_pages(pdf), "pdf", True
        report["pdf"] = pdf
    elif render or pdf:
        with tempfile.TemporaryDirectory(prefix="wg-draft-pages-") as tmp:
            out = Path(pdf) if pdf else Path(tmp) / "render.pdf"
            ok, detail = render_pdf(path, out, chrome=chrome)
            if ok:
                report["pages"], report["source"], report["verified"] = count_pdf_pages(out), "chrome-render", True
                report["renderer"] = detail
                if pdf:
                    report["pdf"] = str(out)
            else:
                report["notes"].append(detail)
    if html is not None:
        est = estimate_html_pages(html)
        report["estimate"] = est
        if report["pages"] is None:
            report["pages"], report["source"] = est["estimate"], "html-estimate"
            report["notes"].append(
                "UNVERIFIED — structural estimate only (page breaks/wrappers); it cannot see a wrapper "
                "that overflows its sheet. Render to PDF (--render, or --pdf <exported file>) to verify.")

    if budget is not None and report["pages"] is not None:
        within = report["pages"] == budget if exact else report["pages"] <= budget
        report["ok"] = bool(within) if report["verified"] else None
        report["within_budget"] = bool(within)
    elif report["pages"] is not None and budget is None:
        report["ok"] = True if report["verified"] else None
    summary = f"pages: {report['pages']} ({report['source']})"
    if budget is not None:
        summary += f" vs budget {'= ' if exact else '≤ '}{budget}"
        if report["pages"] is not None:
            summary += " — " + ("within" if report.get("within_budget") else "EXCEEDED")
    if not report["verified"]:
        summary += " — UNVERIFIED (no render)"
    report["summary"] = summary
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", help="the HTML deliverable (or an exported PDF)")
    ap.add_argument("--pdf", help="an exported PDF of the deliverable (authoritative when present); "
                                  "with --render, where to write the rendered PDF")
    ap.add_argument("--budget", type=int, help="the page budget from the brief")
    ap.add_argument("--exact", action="store_true", help="the budget must be met exactly, not just not exceeded")
    ap.add_argument("--render", action="store_true", help="print the HTML with headless Chrome when no PDF is given")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = run(args.target, pdf=args.pdf, budget=args.budget, exact=args.exact, render=args.render)
    except (OSError, ValueError) as exc:
        print(json.dumps({"check": "pages", "ok": False, "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["summary"])
        for note in report["notes"]:
            print(f"  note: {note}")
    if not report["verified"]:
        return 3
    if args.budget is not None and not report.get("within_budget", False):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
