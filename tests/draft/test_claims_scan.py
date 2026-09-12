"""Unit tests for scripts/draft/claims_scan.py — placeholders, uncited numbers/URLs, hidden mock
labels, dangling sources.

The regression anchor is the RECON brochure (F-RECON-009): a visible ``[PLACEHOLDER: Customer
validation]`` box, a command-center mock whose KPIs ("3 active · 1 needs you") were called
illustrative only inside an HTML comment, and the SC-S02/SC-S03 latencies ("within 2 s",
"within 3 s") stated without a source.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from draft import claims_scan as cs

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "recon-brochure-v1.html"
SCRIPT = REPO / "scripts" / "draft" / "claims_scan.py"


def _kinds(html: str, repos=None) -> list[str]:
    findings, _ = cs.scan_document(html, repos)
    return sorted(f.kind for f in findings)


def _find(html: str, kind: str, repos=None) -> list[cs.Finding]:
    findings, _ = cs.scan_document(html, repos)
    return [f for f in findings if f.kind == kind]


# ── placeholders ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "[PLACEHOLDER: Customer validation] — a quote would go here",
    "PLACEHOLDER: add the screenshot",
    "TODO write the intro",
    "Pricing: TBD",
    "Lorem ipsum dolor sit amet",
    "Dear {{customer_name}},",
    "[INSERT LOGO]",
    "[Company name here]",
])
def test_visible_placeholders_are_findings(text):
    assert "placeholder" in _kinds(f"<body><p>{text}</p></body>")


def test_placeholder_in_comment_or_hidden_element_is_not_visible():
    html = "<body><!-- TODO: swap the hero image --><p hidden>TODO</p><p>Real copy.</p><script>// TODO</script></body>"
    assert "placeholder" not in _kinds(html)


def test_ordinary_words_are_not_placeholders():
    html = "<body><p>Total downloads to date. The plan is ready.</p></body>"
    assert _kinds(html) == []


# ── numbers and citations ─────────────────────────────────────────────────────────────────────

def test_uncited_number_is_a_finding():
    f = _find("<body><p>Gate events appear within 2 seconds.</p></body>", "uncited-number")
    assert len(f) == 1 and "2" in f[0].detail


def test_data_source_on_element_or_ancestor_cites():
    html = ("<body><section data-source='.product/REQ-001.md:82'><p>Gate events appear within 2 seconds.</p></section>"
            "<p data-source='README.md:87'>Node ≥ 22 · npm ≥ 10</p></body>")
    assert _kinds(html) == []


def test_inline_repo_path_cites_the_block():
    html = "<body><p>Requires Node ≥ 22 (<code>package.json:72</code>).</p></body>"
    assert _kinds(html) == []


def test_footnote_marker_counts_only_with_a_sources_block():
    body = "<p>Runs advance within 3 s [2].</p>"
    assert _kinds(f"<body>{body}</body>") == ["uncited-number"]
    with_sources = f"<body>{body}<footer><h4>Sources</h4><ol><li>README.md:60</li><li>.product/REQ-001.md:83</li></ol></footer></body>"
    assert _kinds(with_sources) == []


def test_ordinals_and_copyright_years_are_not_claims():
    html = "<body><span class='num'>01</span><h3>Govern</h3><footer>© 2026 wicked</footer></body>"
    assert _kinds(html) == []


def test_numbers_inside_cited_paths_and_urls_are_not_double_counted():
    html = "<body><p data-source='README.md:5'>See https://example.com/v2/docs and server.ts:1097.</p></body>"
    findings, stats = cs.scan_document(html)
    assert findings == [] and stats["numbers"] == 0


# ── mocks ─────────────────────────────────────────────────────────────────────────────────────

MOCK = ("<div class='mockup' {attr}>{label}<div class='row'>impl/auth-layer running</div>"
        "{comment}<div class='kpi'><span>3 active</span><span>1 needs you</span></div></div>")


def test_visible_label_plus_data_illustrative_is_fine():
    html = "<body>" + MOCK.format(attr="data-illustrative", label="<div class='cap'>Illustrative — not measured data</div>", comment="") + "</body>"
    assert _kinds(html) == []


def test_data_illustrative_without_a_visible_label_is_a_finding():
    html = "<body>" + MOCK.format(attr="data-illustrative", label="", comment="") + "</body>"
    assert set(_kinds(html)) == {"mock-unlabelled"}


def test_label_only_in_a_comment_is_the_hidden_label_defect():
    html = "<body>" + MOCK.format(attr="", label="", comment="<!-- KPI values are illustrative design representations -->") + "</body>"
    assert set(_kinds(html)) == {"mock-label-hidden"}


def test_hidden_label_scope_does_not_leak_to_sibling_blocks():
    """A comment inside the mock must not excuse — or re-label — an unrelated block next to it."""
    html = ("<body><header>" + MOCK.format(attr="", label="", comment="<!-- illustrative -->") +
            "<div class='fact-strip'><span>Node ≥ 22 · npm ≥ 10</span></div></header></body>")
    findings, _ = cs.scan_document(html)
    by_path = {f.path.split(" > ")[-2] if f.path.endswith("span") else f.path: f.kind for f in findings}
    assert by_path.get("div.fact-strip") == "uncited-number"
    assert any(f.kind == "mock-label-hidden" and "div.kpi" in f.path for f in findings)


# ── URLs ──────────────────────────────────────────────────────────────────────────────────────

def test_bare_domain_and_scheme_urls_are_detected():
    html = "<body><p>Production demo — ws.wickedagile.com</p><p>Docs: https://docs.example.org/x</p></body>"
    f = _find(html, "uncited-url")
    assert sorted(x.text for x in f) == ["https://docs.example.org/x", "ws.wickedagile.com"]


def test_url_with_data_source_is_cited_when_no_repo_is_given():
    html = "<body><p data-source='RAID.md:39'>Product site — ws.wickedagile.com</p></body>"
    assert _kinds(html) == []


def test_repo_check_verifies_urls_and_source_paths(tmp_path: Path):
    repo = tmp_path / "wicked-studio"
    (repo / ".product").mkdir(parents=True)
    (repo / "README.md").write_text("# studio\nNode >= 22\n", encoding="utf-8")
    (repo / ".product" / "RAID.md").write_text("marketing site at ws.wickedagile.com\n", encoding="utf-8")
    html = ("<body><p data-source='README.md:2'>Node ≥ 22</p>"
            "<p data-source='.product/RAID.md:1'>Product site — ws.wickedagile.com</p>"
            "<p data-source='docs/missing.md:4'>Latency 3 s</p>"
            "<p data-source='README.md:1'>Live at https://live.example.com/app</p></body>")
    findings, stats = cs.scan_document(html, [str(repo)])
    kinds = sorted((f.kind, f.text) for f in findings)
    assert kinds == [("dangling-source", "docs/missing.md:4"), ("unsourced-url", "https://live.example.com/app")]
    assert stats["repos"] == [str(repo)]


def test_file_names_are_paths_not_domains():
    html = "<body><p data-source='README.md:1'>See server.ts and package.json for details.</p></body>"
    findings, stats = cs.scan_document(html)
    assert findings == [] and stats["urls"] == 0


# ── the RECON regression fixture ──────────────────────────────────────────────────────────────

def test_recon_brochure_reproduces_f_recon_009():
    report = cs.run(str(FIXTURE))
    assert report["ok"] is False
    kinds = report["by_kind"]
    assert kinds["placeholder"] == 1
    placeholder = [f for f in report["findings"] if f["kind"] == "placeholder"][0]
    assert "PLACEHOLDER: Customer validation" in placeholder["text"]
    hidden = [f for f in report["findings"] if f["kind"] == "mock-label-hidden"]
    assert sorted(f["text"] for f in hidden) == ["1 needs you", "3 active"]
    uncited = [f for f in report["findings"] if f["kind"] == "uncited-number"]
    texts = " | ".join(f["text"] for f in uncited)
    assert "within 2 seconds" in texts and "within 3 s" in texts
    assert any("Node ≥ 22" in f["text"] for f in uncited)  # the fact strip is uncited, not a mock


def test_recon_brochure_passes_once_claims_are_disciplined():
    html = FIXTURE.read_text(encoding="utf-8")
    fixed = html.replace('<div class="placeholder-note">', '<div class="placeholder-note" hidden>')
    fixed = fixed.replace('<section class="page page-1"', '<section data-source="README.md:5 .product/REQ-001-application-overview.md:82" class="page page-1"', 1)
    fixed = fixed.replace('<section class="page page-2"', '<section data-source="README.md:60 .product/REQ-001-application-overview.md:83" class="page page-2"', 1)
    fixed = fixed.replace('<div class="mockup-kpi">', '<div class="mockup-kpi" data-illustrative><div>Illustrative — not measured data</div>', 1)
    findings, _ = cs.scan_document(fixed)
    assert [f.as_dict() for f in findings] == []


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────

def test_cli(tmp_path: Path):
    good = tmp_path / "good.html"
    good.write_text("<body><p data-source='README.md:1'>Node ≥ 22</p></body>", encoding="utf-8")
    bad = tmp_path / "bad.html"
    bad.write_text("<body><p>TODO: 3 things</p></body>", encoding="utf-8")
    assert cs.main([str(good)]) == 0
    assert cs.main([str(bad)]) == 1
    assert cs.main([str(tmp_path / "missing.html")]) == 2
    proc = subprocess.run([sys.executable, str(SCRIPT), str(bad), "--json"], capture_output=True, text=True)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["by_kind"] == {"placeholder": 1, "uncited-number": 1}
