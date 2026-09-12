"""Unit tests for scripts/draft/page_count.py — the rendered page count vs the brief's budget.

F-RECON-008: two ``.page`` wrappers, four printed pages. The counter must read the RENDERED
count (PDF page tree, object streams included), fall back to a Chrome print when it can, and
otherwise report the structural estimate as UNVERIFIED (exit 3) — never as a pass.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from draft import page_count as pc

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "recon-brochure-v1.html"
SCRIPT = REPO / "scripts" / "draft" / "page_count.py"


def make_pdf(n_pages: int, object_streams: bool = False) -> bytes:
    """A minimal PDF with `n_pages` pages. With `object_streams`, the page dictionaries AND the
    page tree root are packed into one FlateDecode object stream (as PDF 1.5 writers do)."""
    if not object_streams:
        objs = ["<< /Type /Catalog /Pages 2 0 R >>"]
        kids = " ".join(f"{3 + i} 0 R" for i in range(n_pages))
        objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>")
        for _ in range(n_pages):
            objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>")
        out = ["%PDF-1.4"]
        for i, body in enumerate(objs, start=1):
            out.append(f"{i} 0 obj\n{body}\nendobj")
        out.append("trailer\n<< /Root 1 0 R >>\n%%EOF")
        return "\n".join(out).encode("latin-1")
    kids = " ".join(f"{3 + i} 0 R" for i in range(n_pages))
    packed = [f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"]
    packed += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>"] * n_pages
    offsets, cur = [], 0
    for i, body in enumerate(packed):
        offsets.append(f"{2 + i} {cur}")
        cur += len(body) + 1
    header = " ".join(offsets) + "\n"
    payload = (header + "\n".join(packed) + "\n").encode("latin-1")
    stream = zlib.compress(payload)
    pdf = b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pdf += (f"9 0 obj\n<< /Type /ObjStm /N {len(packed)} /First {len(header)} /Length {len(stream)} "
            f"/Filter /FlateDecode >>\nstream\n").encode("latin-1") + stream + b"\nendstream\nendobj\n"
    pdf += b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    return pdf


@pytest.mark.parametrize("n", [1, 2, 4, 12])
def test_count_pdf_pages_plain(tmp_path: Path, n: int):
    p = tmp_path / "doc.pdf"
    p.write_bytes(make_pdf(n))
    assert pc.count_pdf_pages(p) == n


@pytest.mark.parametrize("n", [1, 3, 7])
def test_count_pdf_pages_inside_object_streams(tmp_path: Path, n: int):
    p = tmp_path / "doc.pdf"
    p.write_bytes(make_pdf(n, object_streams=True))
    assert pc.count_pdf_pages(p) == n


def test_count_pdf_pages_falls_back_to_page_objects(tmp_path: Path):
    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n2 0 obj\n<< /Type /Page >>\nendobj\n%%EOF"
    p = tmp_path / "nocount.pdf"
    p.write_bytes(pdf)
    assert pc.count_pdf_pages(p) == 2


def test_count_pdf_pages_rejects_non_pdf(tmp_path: Path):
    p = tmp_path / "x.pdf"
    p.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError):
        pc.count_pdf_pages(p)


def test_estimate_counts_breaks_and_wrappers():
    html = ("<style>@page{size:A4 portrait;margin:18mm} .page-1{page-break-after:always} .cut{break-after:page}</style>"
            "<body><section class='page page-1'>a</section><section class='page page-2'>b</section>"
            "<div class='cut'>c</div><div style='break-before: page'>d</div></body>")
    est = pc.estimate_html_pages(html)
    assert est == {"breaks": 3, "wrappers": 2, "estimate": 4, "page_size": "A4 portrait"}


def test_recon_fixture_estimate_is_two_but_pdf_says_four(tmp_path: Path):
    """The lesson itself: the estimate sees 2 wrappers; the render is the truth."""
    est = pc.estimate_html_pages(FIXTURE.read_text(encoding="utf-8"))
    assert est["wrappers"] == 2 and est["estimate"] == 2
    exported = tmp_path / "export.pdf"
    exported.write_bytes(make_pdf(4))
    report = pc.run(str(FIXTURE), pdf=str(exported), budget=2)
    assert report["pages"] == 4 and report["source"] == "pdf" and report["verified"] is True
    assert report["within_budget"] is False and report["ok"] is False
    assert "EXCEEDED" in report["summary"]


def test_estimate_only_is_unverified_never_a_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pc, "find_chrome", lambda env=None: None)
    report = pc.run(str(FIXTURE), budget=2, render=True)
    assert report["source"] == "html-estimate" and report["verified"] is False
    assert report["ok"] is None and report["within_budget"] is True
    assert any("UNVERIFIED" in n for n in report["notes"])
    assert any("no Chrome" in n for n in report["notes"])
    assert pc.main([str(FIXTURE), "--budget", "2", "--render"]) == 3


def test_exact_budget(tmp_path: Path):
    p = tmp_path / "three.pdf"
    p.write_bytes(make_pdf(3))
    assert pc.run(str(p), budget=4)["within_budget"] is True
    assert pc.run(str(p), budget=4, exact=True)["within_budget"] is False
    assert pc.run(str(p), budget=3, exact=True)["within_budget"] is True


@pytest.mark.skipif(os.name != "posix", reason="fake chrome is a POSIX shell script")
def test_render_path_uses_the_chrome_binary_it_is_given(tmp_path: Path):
    """A fake Chrome that honours --print-to-pdf=<path> proves the render → count → verdict path
    without a real browser."""
    canned = tmp_path / "canned.pdf"
    canned.write_bytes(make_pdf(4))
    fake = tmp_path / "chrome"
    fake.write_text(
        "#!/bin/sh\nfor a in \"$@\"; do case \"$a\" in --print-to-pdf=*) out=\"${a#--print-to-pdf=}\";; esac; done\n"
        f"cp '{canned}' \"$out\"\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    report = pc.run(str(FIXTURE), budget=2, render=True, chrome=str(fake))
    assert report["source"] == "chrome-render" and report["pages"] == 4 and report["verified"] is True
    assert report["within_budget"] is False


def test_find_chrome_prefers_env_override(tmp_path: Path):
    fake = tmp_path / "mychrome"
    fake.write_text("", encoding="utf-8")
    assert pc.find_chrome({"WICKED_CHROME": str(fake)}) == str(fake)
    assert pc.find_chrome({"WICKED_CHROME": str(tmp_path / "nope")}) in (None, pc.find_chrome({}))


def test_cli(tmp_path: Path):
    p = tmp_path / "four.pdf"
    p.write_bytes(make_pdf(4))
    assert pc.main([str(p), "--budget", "4"]) == 0
    assert pc.main([str(p), "--budget", "2"]) == 1
    assert pc.main([str(tmp_path / "missing.pdf")]) == 2
    proc = subprocess.run([sys.executable, str(SCRIPT), str(p), "--budget", "2", "--json"], capture_output=True, text=True)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["pages"] == 4
