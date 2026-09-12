#!/usr/bin/env python3
"""self_check.py — the ONE command a document author runs before saying "done".

Runs the three floors of the `wicked-garden-draft` skill over a self-contained HTML deliverable
and prints one verdict:

  * contrast  — every text/background pair ≥ 4.5:1 (3:1 large text); print text ≥ 7pt
                (`contrast_check.py`);
  * pages     — the RENDERED page count meets the brief's budget (`page_count.py`); when neither a
                PDF nor a Chrome render is available the count is UNVERIFIED and the verdict says so;
  * claims    — no placeholders, every number/URL cited or visibly labelled illustrative, no
                dangling `data-source` paths, no URL the sources never mention (`claims_scan.py`).

Exit: 0 = every floor met (and verified); 1 = a floor failed — fix the document and re-run;
3 = no floor failed but the page count could not be verified — disclose it in the notes;
2 = usage / unreadable input. Stdlib only.

CLI:
    self_check.py <file.html> [--pdf <exported.pdf>] [--pages N [--exact]] [--render]
                  [--repo <dir> …] [--min-contrast 4.5] [--min-font-pt 7] [--mode print|screen|both]
                  [--no-pages] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from draft import claims_scan, contrast_check, page_count  # noqa: E402


def run(html: str, pdf: str | None = None, pages: int | None = None, exact: bool = False,
        render: bool = False, repos: list[str] | None = None, min_contrast: float = 4.5,
        min_font_pt: float = 7.0, mode: str = "print", check_pages: bool = True) -> dict:
    checks: dict[str, dict] = {}
    checks["contrast"] = contrast_check.run(html, min_contrast, min_font_pt, mode)
    checks["claims"] = claims_scan.run(html, repos)
    unverified = False
    if check_pages:
        checks["pages"] = page_count.run(html, pdf=pdf, budget=pages, exact=exact, render=render)
        unverified = not checks["pages"]["verified"]
    failed = [name for name, rep in checks.items()
              if rep.get("ok") is False or (name == "pages" and rep.get("within_budget") is False)]
    verdict = "FAIL" if failed else ("UNVERIFIED" if unverified else "PASS")
    lines = [rep["summary"] for rep in checks.values()]
    return {
        "check": "draft-self-check",
        "file": html,
        "verdict": verdict,
        "ok": verdict == "PASS",
        "failed": failed,
        "unverified": [n for n, rep in checks.items() if rep.get("verified") is False],
        "checks": checks,
        "summary": lines,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("html", help="the self-contained HTML deliverable")
    ap.add_argument("--pdf", help="an exported PDF of the deliverable (authoritative page count)")
    ap.add_argument("--pages", type=int, help="the page budget the brief asks for")
    ap.add_argument("--exact", action="store_true", help="the budget must be met exactly")
    ap.add_argument("--render", action="store_true", help="print with headless Chrome when no PDF is given")
    ap.add_argument("--repo", action="append", default=[], help="repository snapshot(s) claims must trace to")
    ap.add_argument("--min-contrast", type=float, default=4.5)
    ap.add_argument("--min-font-pt", type=float, default=7.0, help="0 disables the print size floor")
    ap.add_argument("--mode", choices=("print", "screen", "both"), default="print")
    ap.add_argument("--no-pages", action="store_true", help="skip the page check (web pages, prose docs)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = run(args.html, pdf=args.pdf, pages=args.pages, exact=args.exact, render=args.render,
                     repos=args.repo, min_contrast=args.min_contrast, min_font_pt=args.min_font_pt,
                     mode=args.mode, check_pages=not args.no_pages)
    except (OSError, ValueError) as exc:
        print(json.dumps({"check": "draft-self-check", "verdict": "ERROR", "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"draft self-check: {report['verdict']}")
        for line in report["summary"]:
            print(f"  {line}")
        for name in ("contrast", "claims"):
            for f in report["checks"][name]["findings"][:40]:
                if name == "contrast":
                    what = (f"{f['ratio']}:1 < {f['required']}:1" if f["kind"] == "contrast"
                            else f"{f['font_pt']}pt < {f['required']}pt")
                    print(f"    [{f['kind']}] {f['path']}  fg {f['fg']} on {f['bg']}  {what}  “{f['text']}”")
                else:
                    print(f"    [{f['kind']}] {f['path']}  “{f['text']}”  — {f['detail']}")
            extra = len(report["checks"][name]["findings"]) - 40
            if extra > 0:
                print(f"    … {extra} more {name} findings (use --json for all)")
        for note in report["checks"].get("pages", {}).get("notes", []):
            print(f"    note: {note}")
    if report["verdict"] == "FAIL":
        return 1
    if report["verdict"] == "UNVERIFIED":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
