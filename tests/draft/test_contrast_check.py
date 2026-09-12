"""Unit tests for scripts/draft/contrast_check.py — the WCAG contrast + print-size floor.

The regression anchor is the RECON brochure (F-RECON-007): ``tests/draft/fixtures/
recon-brochure-v1.html`` is the governed draft as landed (instrumented, with the injected
theme block and NO <html>/<head> open tags). Its footer requirements and KPI label were
``rgba(255,255,255,0.14)`` on ``#1a1a26`` — invisible in the PNG and PDF — and its hero fact
strip was 6.8pt monospace. The checker must find exactly that class of defect and must PASS
the same document once the tokens are lifted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from draft import contrast_check as cc

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "recon-brochure-v1.html"
SCRIPT = REPO / "scripts" / "draft" / "contrast_check.py"


def _doc(css: str, body: str, head_extra: str = "") -> str:
    return f"<!doctype html><html><head><style>{css}</style>{head_extra}</head><body>{body}</body></html>"


# ── colour maths ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("#fff", (255, 255, 255, 1.0)),
    ("#09090f", (9, 9, 15, 1.0)),
    ("#ffffff80", (255, 255, 255, 128 / 255)),
    ("rgb(255, 255, 255)", (255, 255, 255, 1.0)),
    ("rgba(255,255,255,0.48)", (255, 255, 255, 0.48)),
    ("rgb(255 255 255 / 14%)", (255, 255, 255, 0.14)),
    ("hsl(0, 0%, 100%)", (255, 255, 255, 1.0)),
    ("hsl(258 72% 62% / 0.5)", None),  # checked below for channel ranges only
    ("white", (255, 255, 255, 1.0)),
    ("rebeccapurple", (102, 51, 153, 1.0)),
    ("transparent", (0, 0, 0, 0.0)),
])
def test_parse_color(value, expected):
    got = cc.parse_color(value)
    assert got is not None
    if expected is None:
        assert 0 <= got[0] <= 255 and abs(got[3] - 0.5) < 1e-9
        return
    assert tuple(round(c) for c in got[:3]) == expected[:3]
    assert abs(got[3] - expected[3]) < 1e-6


def test_parse_color_rejects_non_colours():
    assert cc.parse_color("var(--x)") is None
    assert cc.parse_color("inherit") is None
    assert cc.parse_color("linear-gradient(90deg, #000, #fff)") is None
    assert cc.parse_color("") is None


def test_contrast_ratio_known_values():
    white, black = cc.parse_color("#fff"), cc.parse_color("#000")
    assert abs(cc.contrast_ratio(white, black) - 21.0) < 1e-6
    assert abs(cc.contrast_ratio(white, white) - 1.0) < 1e-9
    # #767676 on white is the classic "just passes AA" grey
    assert 4.5 <= cc.contrast_ratio(cc.parse_color("#767676"), white) < 4.6


def test_alpha_composite_reproduces_the_recon_pair():
    """14 % white over the brochure surface is what nobody could read (≈1.4:1); the 48 % tint
    just clears 4.5:1 — the checker must tell them apart by the COMPOSITED pair."""
    surface = cc.parse_color("#09090f")
    faint = cc.composite(cc.parse_color("rgba(255,255,255,0.14)"), surface)
    muted = cc.composite(cc.parse_color("rgba(255,255,255,0.48)"), surface)
    assert cc.contrast_ratio(faint, surface) < 1.6
    assert cc.contrast_ratio(muted, surface) > 4.5


def test_find_colors_collects_every_gradient_stop():
    cols = cc.find_colors("linear-gradient(145deg, #0d0d1e 0%, #111132 55%, transparent 100%)")
    assert [cc.to_hex(c) for c in cols if c[3] > 0] == ["#0d0d1e", "#111132"]


# ── cascade ───────────────────────────────────────────────────────────────────────────────────

def _findings(html: str, **kw) -> list[cc.Finding]:
    findings, _ = cc.check_document(html, **kw)
    return findings


def test_passing_document_has_no_findings():
    html = _doc(":root{--ink:#111;--paper:#fff} body{color:var(--ink);background:var(--paper);font-size:11pt}",
                "<p>Readable body copy.</p><h1>Big heading</h1>")
    assert _findings(html) == []


def test_faint_token_on_dark_surface_fails_contrast():
    html = _doc(":root{--surface:#09090f;--ink-faint:rgba(255,255,255,0.14)} body{background:var(--surface);color:#fff;font-size:10pt} .reqs{color:var(--ink-faint)}",
                "<p>Fine.</p><div class='reqs'>Node.js 22</div>")
    f = _findings(html)
    assert [x.kind for x in f] == ["contrast"]
    assert "div.reqs" in f[0].path and f[0].ratio < 1.6 and f[0].required == 4.5


def test_root_tokens_resolve_without_an_html_element():
    """The instrumented deliverable starts at <style> with only </head><body> surviving."""
    html = ("<style>:root{--surface:#09090f;--ink:rgba(255,255,255,0.14)} html,body{background:var(--surface);color:var(--ink);font-size:10pt}</style>"
            "</head><body><p>meta</p></body>")
    f = _findings(html)
    assert len(f) == 1 and f[0].kind == "contrast" and f[0].bg == "#09090f"


def test_var_fallback_and_nested_vars():
    html = _doc(":root{--a:var(--b, #000)} body{color:var(--a);background:var(--missing, #fff);font-size:12pt}",
                "<p>text</p>")
    assert _findings(html) == []


def test_inline_style_beats_stylesheet_and_important_beats_inline():
    html = _doc("p{color:#000 !important;background:#fff;font-size:12pt} span{color:#000}",
                "<p style='color:#eee'>fine because !important wins</p><span style='color:#eee;background:#fff'>inline grey</span>")
    f = _findings(html)
    assert [x.kind for x in f] == ["contrast"] and f[0].path.endswith("span")


def test_specificity_and_source_order():
    html = _doc(".x{color:#eee} p.x{color:#000} p{color:#eee} body{background:#fff;font-size:12pt}",
                "<p class='x'>black wins by specificity</p>")
    assert _findings(html) == []


def test_large_text_needs_only_three_to_one():
    # #949494 on white ≈ 3.0:1 — fails body text, passes a 24px heading
    html = _doc("body{background:#fff} h1{color:#949494;font-size:26px} p{color:#949494;font-size:12pt}",
                "<h1>Large</h1><p>small</p>")
    f = _findings(html, min_font_pt=0)
    assert [x.path.split(" > ")[-1] for x in f] == ["p"]
    assert f[0].required == 4.5


def test_bold_18pt_counts_as_large():
    html = _doc("body{background:#fff} .k{color:#949494;font-size:19px;font-weight:700}", "<div class='k'>Kicker</div>")
    assert _findings(html) == []


def test_hidden_and_display_none_are_skipped():
    html = _doc("body{background:#fff;font-size:12pt} .h{display:none;color:#fff} .v{visibility:hidden;color:#fff}",
                "<p class='h'>x</p><p class='v'>y</p><p hidden style='color:#fff'>z</p><script>var a = 1;</script>")
    assert _findings(html) == []


def test_media_print_rules_apply_only_in_print_mode():
    css = "body{background:#fff;color:#000;font-size:12pt} @media print{ p{color:#fff} } @media screen{ .s{color:#fff} }"
    body = "<p>print-white</p><div class='s'>screen-white</div>"
    print_f = _findings(_doc(css, body), mode="print")
    screen_f = _findings(_doc(css, body), mode="screen")
    assert [x.path.split(" > ")[-1] for x in print_f] == ["p"]
    assert [x.path.split(" > ")[-1] for x in screen_f] == ["div.s"]


def test_gradient_background_is_judged_at_its_worst_stop():
    html = _doc("body{font-size:12pt} .hero{background:linear-gradient(90deg,#000 0%,#fff 100%);color:#fff}",
                "<div class='hero'>text</div>")
    f = _findings(html)
    assert len(f) == 1 and f[0].bg == "#ffffff"


def test_opacity_dims_the_text():
    html = _doc("body{background:#fff;font-size:12pt} .o{color:#000;opacity:0.2}", "<p class='o'>ghost</p>")
    f = _findings(html)
    assert len(f) == 1 and f[0].kind == "contrast"


def test_translucent_card_over_dark_surface_composites():
    html = _doc("body{background:#000;font-size:12pt} .card{background:rgba(255,255,255,0.9)} .card p{color:#111}",
                "<div class='card'><p>dark on near-white card</p></div>")
    assert _findings(html) == []


def test_print_size_floor_flags_small_meta_text():
    html = _doc("body{background:#fff;color:#000} .strip{font-size:6.8pt} .ok{font-size:7pt}",
                "<div class='strip'>Works with X</div><div class='ok'>fine</div>")
    f = _findings(html)
    assert [x.kind for x in f] == ["size"] and f[0].font_pt == pytest.approx(6.8, abs=0.05)
    assert _findings(html, min_font_pt=0) == []


def test_font_size_units_and_inheritance():
    html = _doc("body{background:#fff;color:#000;font-size:16px} .em{font-size:0.5em} .rem{font-size:0.5rem} .pct{font-size:50%}",
                "<div class='em'>a</div><div class='rem'>b</div><div class='pct'>c</div>")
    f = _findings(html)  # 8px = 6pt each → three size findings
    assert len(f) == 3 and all(x.kind == "size" and abs(x.font_pt - 6.0) < 0.01 for x in f)


def test_glyph_only_spans_are_not_judged():
    html = _doc("body{background:#fff;font-size:12pt} .sep{color:#fff}", "<span class='sep'>·</span><span class='sep'>|</span>")
    assert _findings(html) == []


# ── the RECON regression fixture ──────────────────────────────────────────────────────────────

def test_recon_brochure_fails_where_the_pngs_were_unreadable():
    report = cc.run(str(FIXTURE))
    assert report["ok"] is False
    assert report["elements_checked"] > 80
    contrast = {f["path"].split(" > ")[-1]: f for f in report["findings"] if f["kind"] == "contrast"}
    # the footer requirements block and the KPI label — the ≈1.5:1 --ink-faint text
    assert contrast["div.cta-reqs"]["ratio"] < 1.6
    assert contrast["div.mockup-kpi-label"]["ratio"] < 1.6
    # the hero fact strip clears 4.5:1 numerically but is 6.8pt monospace → size floor
    sizes = [f for f in report["findings"] if f["kind"] == "size" and "fact-strip" in f["path"]]
    assert sizes and sizes[0]["font_pt"] == pytest.approx(6.8, abs=0.05)
    # a 62 %-lightness accent on the card surface is not body-text safe either
    assert contrast["div.flow-label"]["fg"] == "#8258e4" and contrast["div.flow-label"]["ratio"] < 4.5


def test_recon_brochure_passes_once_tokens_are_lifted():
    html = FIXTURE.read_text(encoding="utf-8")
    fixed = (html.replace("--ink-faint:      rgba(255,255,255,0.14);", "--ink-faint:      rgba(255,255,255,0.70);")
                 .replace("--ink-muted:      rgba(255,255,255,0.48);", "--ink-muted:      rgba(255,255,255,0.72);")
                 .replace("--accent:         hsl(258, 72%, 62%);", "--accent:         hsl(258, 72%, 78%);"))
    # the "governed" KPI span carries the accent as a LITERAL inline style, bypassing the token
    fixed = fixed.replace('style="color:hsl(258,72%,62%);"', 'style="color:hsl(258,72%,78%);"')
    for small in ("5.5pt", "5.8pt", "6pt", "6.2pt", "6.5pt", "6.8pt"):
        fixed = fixed.replace(f"font-size: {small}", "font-size: 7pt").replace(f"font-size:{small}", "font-size:7pt")
    findings, checked = cc.check_document(fixed)
    assert checked > 80
    assert [f.as_dict() for f in findings] == []


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────

def test_cli_exit_codes_and_json(tmp_path: Path):
    good = tmp_path / "good.html"
    good.write_text(_doc("body{color:#111;background:#fff;font-size:11pt}", "<p>ok</p>"), encoding="utf-8")
    bad = tmp_path / "bad.html"
    bad.write_text(_doc("body{color:#ccc;background:#fff;font-size:11pt}", "<p>faint</p>"), encoding="utf-8")
    assert cc.main([str(good)]) == 0
    assert cc.main([str(bad), "--json"]) == 1
    assert cc.main([str(tmp_path / "missing.html")]) == 2
    proc = subprocess.run([sys.executable, str(SCRIPT), str(bad), "--json"], capture_output=True, text=True)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["check"] == "contrast" and payload["contrast_failures"] == 1


# ── review follow-ups: H1 shrink-to-fit, M2 unknown colours, M3 `not` media, L1/L3/L6, M1 ──────

def test_body_zoom_shrinks_the_effective_size():
    """H1 — `body{zoom:.6}` renders 10pt text at 6pt; the floor judges the EFFECTIVE size."""
    html = _doc("body{zoom:0.6;background:#fff;color:#000;font-size:10pt}", "<p>fits now</p>")
    f = _findings(html)
    assert [x.kind for x in f] == ["size"]
    assert f[0].font_pt == pytest.approx(6.0, abs=0.01) and f[0].scale == pytest.approx(0.6)
    assert "scale" in f[0].as_dict()


@pytest.mark.parametrize("css,expected_pt", [
    (".page{transform:scale(0.5)}", 5.0),
    (".page{transform:translate(4px, 2px) scale(0.5, 0.9)}", 5.0),   # min axis
    (".page{transform:matrix(0.5,0,0,0.5,0,0)}", 5.0),
    (".page{scale: 0.6}", 6.0),
    ("html{zoom:60%}", 6.0),                                          # a REAL <html> applies once
    (".page{zoom:0.9} .inner{transform:scaleY(0.5)}", 4.5),           # factors multiply through ancestors
])
def test_transform_and_scale_ancestors_shrink_text(css, expected_pt):
    html = _doc(f"body{{background:#fff;color:#000;font-size:10pt}} {css}",
                "<section class='page'><div class='inner'><p>text</p></div></section>")
    f = _findings(html)
    assert [x.kind for x in f] == ["size"], f
    assert f[0].font_pt == pytest.approx(expected_pt, abs=0.01)


def test_zoom_up_can_lift_small_text_and_rotate_is_neutral():
    html = _doc("body{background:#fff;color:#000} .s{font-size:6pt;zoom:1.25} .r{font-size:8pt;transform:rotate(3deg) translateX(2px)}",
                "<div class='s'>lifted to 7.5pt</div><div class='r'>rotated only</div>")
    assert _findings(html) == []


def test_unevaluable_transform_makes_size_unverified_not_passed():
    html = _doc("body{background:#fff;color:#000;font-size:10pt} .w{transform:translateX(1px) unknownfn(0.3)}",
                "<div class='w'><p>who knows</p></div>")
    f = _findings(html)
    assert [x.kind for x in f] == ["unknown"] and "cannot evaluate" in f[0].detail and "cutting content" in f[0].detail


def test_recon_shrink_to_fit_bypass_fails_the_size_floor():
    """The reviewer's bypass: the fixture + `body{zoom:.62}` printed on two pages and would have
    PASSed — every text element now lands under 7pt effective and the check FAILS."""
    for placement in ("prepend", "append"):
        html = FIXTURE.read_text(encoding="utf-8")
        zoomed = ("<style>body{zoom:0.62}</style>" + html) if placement == "prepend" else (html + "<style>body{zoom:0.62}</style>")
        findings, checked = cc.check_document(zoomed)
        sizes = [f for f in findings if f.kind == "size"]
        assert checked > 80 and len(sizes) > 60, placement
        assert all(f.scale == pytest.approx(0.62) for f in sizes)
        # even the body copy (10pt declared) is now 6.2pt effective
        assert any(f.font_pt == pytest.approx(6.2, abs=0.05) for f in sizes)


def test_corrected_document_plus_zoom_still_fails():
    """Corrected tokens + zoom = the exact PASS the reviewer reproduced; it must FAIL now."""
    html = FIXTURE.read_text(encoding="utf-8")
    fixed = (html.replace("--ink-faint:      rgba(255,255,255,0.14);", "--ink-faint:      rgba(255,255,255,0.70);")
                 .replace("--ink-muted:      rgba(255,255,255,0.48);", "--ink-muted:      rgba(255,255,255,0.72);")
                 .replace("--accent:         hsl(258, 72%, 62%);", "--accent:         hsl(258, 72%, 78%);")
                 .replace('style="color:hsl(258,72%,62%);"', 'style="color:hsl(258,72%,78%);"'))
    for small in ("5.5pt", "5.8pt", "6pt", "6.2pt", "6.5pt", "6.8pt"):
        fixed = fixed.replace(f"font-size: {small}", "font-size: 7pt").replace(f"font-size:{small}", "font-size:7pt")
    assert cc.check_document(fixed)[0] == []                       # clean without zoom
    findings, _ = cc.check_document(fixed + "<style>body{zoom:0.62}</style>")
    assert findings and all(f.kind == "size" for f in findings)   # zoom alone re-fails it


@pytest.mark.parametrize("value", ["oklch(96% 0 0)", "color-mix(in srgb, #fff 95%, #000)", "lab(98% 0 0)", "light-dark(#fff, #000)"])
def test_unsupported_colour_functions_are_unverified_not_inherited(value):
    html = _doc(f"body{{background:#fff;color:#000;font-size:12pt}} p{{color:{value}}}", "<p>near white?</p><div>fine</div>")
    f = _findings(html)
    assert [x.kind for x in f] == ["unknown"]
    assert value.split("(")[0] in f[0].detail and "hex/rgb()/hsl()" in f[0].detail


def test_unsupported_colour_inherits_as_unknown_to_children():
    html = _doc("body{background:#fff;font-size:12pt} .w{color:oklch(96% 0 0)}", "<div class='w'><p>child</p></div>")
    assert [x.kind for x in _findings(html)] == ["unknown"]


def test_image_only_background_is_unverified_not_on_white():
    html = _doc("body{font-size:12pt} .hero{background:url(hero.jpg) center/cover;color:#fff}", "<div class='hero'>on a photo</div>")
    f = _findings(html)
    assert [x.kind for x in f] == ["unknown"] and "image" in f[0].detail and "background-color" in f[0].detail
    assert f[0].bg == "?" and f[0].fg == "#ffffff"


def test_image_background_with_colour_fallback_is_judged():
    html = _doc("body{font-size:12pt} .hero{background:#000 url(hero.jpg) center/cover;color:#fff} .bad{background:#fff url(x.png);color:#fff}",
                "<div class='hero'>fine</div><div class='bad'>white on white</div>")
    f = _findings(html)
    assert [(x.kind, x.path.split(' > ')[-1]) for x in f] == [("contrast", "div.bad")]


def test_media_not_print_applies_only_off_print():
    """M3 — false positive: a `not print` rule must NOT apply in print mode."""
    html = _doc("body{background:#fff;color:#000;font-size:12pt} @media not print { p{color:#fff} }", "<p>black in print</p>")
    assert _findings(html, mode="print") == []
    assert [x.kind for x in _findings(html, mode="screen")] == ["contrast"]


def test_media_not_print_false_negative_is_caught():
    """M3 — false negative: white text fixed only for `not print` is still white when printed."""
    html = _doc("body{background:#fff;font-size:12pt} p{color:#fff} @media not print { p{color:#000} }", "<p>white in print</p>")
    assert [x.kind for x in _findings(html, mode="print")] == ["contrast"]
    assert _findings(html, mode="screen") == []


def test_media_lists_and_only_screen():
    html = _doc("body{background:#fff;color:#000;font-size:12pt} @media only screen and (min-width: 1px), print and (color) { p{color:#fff} } @media not screen, (min-width:1px) { .a{color:#fff} }",
                "<p>both listed</p><div class='a'>feature query applies</div>")
    assert sorted(x.path.split(" > ")[-1] for x in _findings(html, mode="print")) == ["div.a", "p"]


def test_inline_important_beats_more_specific_stylesheet_important():
    """L3 — inline !important is the top of the cascade."""
    html = _doc("body{background:#fff;font-size:12pt} #a #b{color:#fff !important}",
                "<div id='a'><p id='b' style='color:#000 !important'>black</p></div>")
    assert _findings(html) == []


def test_mode_both_reports_a_pair_once(tmp_path: Path):
    """L1 — a pair failing in print AND screen is one finding tagged with both modes."""
    p = tmp_path / "x.html"
    p.write_text(_doc("body{background:#fff;font-size:12pt} p{color:#eee}", "<p>faint</p>"), encoding="utf-8")
    report = cc.run(str(p), mode="both")
    assert report["contrast_failures"] == 1 and len(report["findings"]) == 1
    assert report["findings"][0]["mode"] == "print+screen"


def test_unsupported_selector_colour_rules_are_noted_not_silent():
    """L6 — a rule this matcher skips must leave a trace in the report."""
    html = _doc("body{background:#fff;color:#000;font-size:12pt} li:nth-child(2){color:#fff} .x:is(.y){background:#000}",
                "<ul><li>a</li><li>b</li></ul>")
    notes: list[str] = []
    cc.check_document(html, notes=notes)
    assert len(notes) == 1 and "2 colour-declaring rule" in notes[0] and "li:nth-child(2)" in notes[0]


def test_cli_exit_3_when_only_unverified(tmp_path: Path):
    p = tmp_path / "u.html"
    p.write_text(_doc("body{background:#fff;font-size:12pt} p{color:oklch(96% 0 0)}", "<p>near white</p>"), encoding="utf-8")
    assert cc.main([str(p)]) == 3
    report = cc.run(str(p))
    assert report["ok"] is True and report["verified"] is False and report["unverified"] == 1


def test_cli_survives_a_cp1252_console():
    """M1 — Windows piped stdout: summaries with ≤/—/curly quotes and echoed document text must
    print (with `?`), never raise UnicodeEncodeError."""
    import os
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE)], capture_output=True, env=env)
    assert proc.returncode == 1, proc.stderr[-400:]
    assert b"Traceback" not in proc.stderr and b"UnicodeEncodeError" not in proc.stderr
    assert b"[contrast]" in proc.stdout and b"[size]" in proc.stdout
