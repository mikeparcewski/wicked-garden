"""Tests for scripts/draft/self_check.py — the one command behind the skill's "done" line."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from draft import self_check as sc

from tests.draft.test_page_count import make_pdf

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "recon-brochure-v1.html"
SCRIPT = REPO / "scripts" / "draft" / "self_check.py"

GOOD = ("<!doctype html><html><head><style>@page{size:A4 portrait;margin:18mm} :root{--ink:#111;--paper:#fff}"
        "body{color:var(--ink);background:var(--paper);font-size:10.5pt} .page-1{break-after:page}</style></head>"
        "<body><section class='page page-1' data-source='README.md:5'><h1>Product</h1><p>Requires Node ≥ 22.</p></section>"
        "<section class='page page-2'><p data-source='README.md:60'>Start with npx wicked-crew serve — one command.</p>"
        "<footer><h4>Sources</h4><ul><li>README.md:5</li><li>README.md:60</li></ul></footer></section></body></html>")


def test_recon_brochure_fails_all_three_floors(tmp_path: Path):
    exported = tmp_path / "export.pdf"
    exported.write_bytes(make_pdf(4))
    report = sc.run(str(FIXTURE), pdf=str(exported), pages=2, exact=True)
    assert report["verdict"] == "FAIL"
    assert report["failed"] == ["contrast", "claims", "pages"]
    assert report["checks"]["pages"]["pages"] == 4
    assert report["checks"]["contrast"]["contrast_failures"] > 0
    assert report["checks"]["claims"]["by_kind"]["placeholder"] == 1


def test_good_document_passes_with_a_verified_page_count(tmp_path: Path):
    html = tmp_path / "good.html"
    html.write_text(GOOD, encoding="utf-8")
    exported = tmp_path / "good.pdf"
    exported.write_bytes(make_pdf(2))
    report = sc.run(str(html), pdf=str(exported), pages=2, exact=True)
    assert report["verdict"] == "PASS" and report["ok"] is True and report["failed"] == []
    assert sc.main([str(html), "--pdf", str(exported), "--pages", "2", "--exact"]) == 0


def test_unverified_pages_is_neither_pass_nor_fail(tmp_path: Path, monkeypatch):
    from draft import page_count as pc
    monkeypatch.setattr(pc, "find_chrome", lambda env=None: None)
    html = tmp_path / "good.html"
    html.write_text(GOOD, encoding="utf-8")
    report = sc.run(str(html), pages=2, render=True)
    assert report["verdict"] == "UNVERIFIED" and report["unverified"] == ["pages"]
    assert sc.main([str(html), "--pages", "2", "--render"]) == 3


def test_no_pages_skips_the_page_check(tmp_path: Path):
    html = tmp_path / "web.html"
    html.write_text(GOOD, encoding="utf-8")
    report = sc.run(str(html), check_pages=False, mode="screen", min_font_pt=0)
    assert report["verdict"] == "PASS" and "pages" not in report["checks"]


def test_cli_json_and_error(tmp_path: Path):
    html = tmp_path / "web.html"
    html.write_text(GOOD, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(html), "--no-pages", "--json"], capture_output=True, text=True)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["verdict"] == "PASS" and set(payload["checks"]) == {"contrast", "claims"}
    assert sc.main([str(tmp_path / "missing.html")]) == 2


# ── review follow-ups: H1 end to end, M2 → UNVERIFIED with disclosure, M1 ─────────────────────

def test_shrink_to_fit_bypass_fails_end_to_end(tmp_path: Path):
    """The reviewer's PASS: a corrected document plus `body{zoom:.62}` on a two-page render."""
    html = tmp_path / "zoomed.html"
    html.write_text(GOOD.replace("<style>", "<style>body{zoom:0.62} ", 1), encoding="utf-8")
    exported = tmp_path / "two.pdf"
    exported.write_bytes(make_pdf(2))
    report = sc.run(str(html), pdf=str(exported), pages=2, exact=True)
    assert report["verdict"] == "FAIL" and report["failed"] == ["contrast"]
    assert all(f["kind"] == "size" and f.get("scale") == 0.62 for f in report["checks"]["contrast"]["findings"])


def test_unknown_colour_is_unverified_with_a_disclosure(tmp_path: Path):
    html = tmp_path / "oklch.html"
    html.write_text(GOOD.replace(":root{--ink:#111;", ":root{--ink:oklch(20% 0 0);", 1), encoding="utf-8")
    exported = tmp_path / "two.pdf"
    exported.write_bytes(make_pdf(2))
    report = sc.run(str(html), pdf=str(exported), pages=2, exact=True)
    assert report["verdict"] == "UNVERIFIED" and report["unverified"] == ["contrast"] and report["failed"] == []
    assert len(report["disclose"]) == 1 and "contrast" in report["disclose"][0] and "by hand" in report["disclose"][0]
    assert sc.main([str(html), "--pdf", str(exported), "--pages", "2", "--exact"]) == 3


def test_unverified_pages_disclosure_names_the_verification_point(tmp_path: Path, monkeypatch):
    from draft import page_count as pc
    monkeypatch.setattr(pc, "find_chrome", lambda env=None: None)
    html = tmp_path / "good.html"
    html.write_text(GOOD, encoding="utf-8")
    report = sc.run(str(html), pages=2, render=True)
    assert report["verdict"] == "UNVERIFIED"
    assert "page_count.py --pdf" in report["disclose"][0] and "estimate 2" in report["disclose"][0]


def test_cli_survives_a_cp1252_console():
    import os
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE), "--no-pages"], capture_output=True, env=env)
    assert proc.returncode == 1 and b"Traceback" not in proc.stderr
    assert b"draft self-check: FAIL" in proc.stdout
