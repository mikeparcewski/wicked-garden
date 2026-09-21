"""Unit tests for scripts/draft/claims_scan.py — placeholders, uncited numbers/URLs, hidden mock
labels, dangling sources.

The regression anchor is the RECON brochure (F-RECON-009): a visible ``[PLACEHOLDER: Customer
validation]`` box, a command-center mock whose KPIs ("3 active · 1 needs you") were called
illustrative only inside an HTML comment, and the SC-S02/SC-S03 latencies ("within 2 s",
"within 3 s") stated without a source.
"""

from __future__ import annotations

import json
import os
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
    # README.md:1 ("# studio") shares no tokens with "Live at https://…" → cite-off
    assert kinds == [
        ("cite-off", "Live at https://live.example.com/app"),
        ("dangling-source", "docs/missing.md:4"),
        ("unsourced-url", "https://live.example.com/app"),
    ]
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
    import re
    html = FIXTURE.read_text(encoding="utf-8")
    # the placeholder is REMOVED (the skill says "never in the deliverable") — hiding it would be the bypass
    fixed, n = re.subn(r'<div class="placeholder-note">.*?</div>', "", html, count=1, flags=re.DOTALL)
    from draft._dom import text_elements
    visible = " ".join(el.direct_text() for el in text_elements(cs.parse(fixed)))
    assert n == 1 and "PLACEHOLDER" not in visible
    fixed = fixed.replace('<section class="page page-1"', '<section data-source="README.md:5 .product/REQ-001-application-overview.md:82" class="page page-1"', 1)
    fixed = fixed.replace('<section class="page page-2"', '<section data-source="README.md:60 .product/REQ-001-application-overview.md:83" class="page page-2"', 1)
    fixed = fixed.replace('<div class="mockup-kpi">', '<div class="mockup-kpi" data-illustrative><div>Illustrative — not measured data</div>', 1)
    findings, _ = cs.scan_document(fixed)
    assert [f.as_dict() for f in findings] == []


# ── cite-off (line-level citation verification) ───────────────────────────────────────────────

BROCHURE_FIXTURE = Path(__file__).parent / "fixtures" / "brochure-cite-off.html"
# README used by the brochure fixture: text is on line 4, fixture cites line 7
_BROCHURE_README = (
    "# studio\n"
    "Node >= 22\n"
    "Install: npm install\n"
    "Fast: sub-second execution\n"
    "More details here.\n"
    "Another detail line.\n"
    "Extended detail line here\n"
)


def test_cite_off_wrong_line_produces_finding(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(_BROCHURE_README, encoding="utf-8")
    html = '<body><p data-source="README.md:7">Fast: sub-second execution</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    cite_offs = [f for f in findings if f.kind == "cite-off"]
    assert len(cite_offs) == 1
    assert "README.md:7" in cite_offs[0].detail
    assert "nearest match" in cite_offs[0].detail
    assert stats["cite_off"] == 1
    assert stats["cited_lines"] == 0


def test_cite_off_correct_line_is_clean(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(_BROCHURE_README, encoding="utf-8")
    html = '<body><p data-source="README.md:4">Fast: sub-second execution</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert all(f.kind != "cite-off" for f in findings)
    assert stats["cited_lines"] == 1
    assert stats["cite_off"] == 0


def test_cite_off_path_only_is_clean(tmp_path: Path):
    """A path-only data-source (no :N) is always valid — no cite-off check."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\n", encoding="utf-8")
    html = '<body><p data-source="README.md">Fast: sub-second execution 3 s</p></body>'
    findings, _ = cs.scan_document(html, [str(repo)])
    assert all(f.kind != "cite-off" for f in findings)


def test_cite_off_frontmatter_delimiter_for_absent_prose(tmp_path: Path):
    """A --- frontmatter line cited for prose that isn't in that line → cite-off."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("---\nname: my-skill\n---\n# Title\n", encoding="utf-8")
    html = '<body><p data-source="README.md:1">Processes 1000 requests per second</p></body>'
    findings, _ = cs.scan_document(html, [str(repo)])
    cite_offs = [f for f in findings if f.kind == "cite-off"]
    assert len(cite_offs) == 1
    assert "README.md:1" in cite_offs[0].detail


def test_cite_off_inherited_citation_not_checked(tmp_path: Path):
    """A data-source on an ancestor section is NOT checked for cite-off."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\nSomething else entirely\n", encoding="utf-8")
    # section data-source="README.md:2" — child p text has no overlap with line 2
    html = ('<body><section data-source="README.md:2">'
            '<p>Fast: sub-second execution 3 s</p></section></body>')
    findings, _ = cs.scan_document(html, [str(repo)])
    assert all(f.kind != "cite-off" for f in findings)


def test_cite_off_line_range_passes_when_text_in_range(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\nLine two\nFast: sub-second execution\nLine four\n", encoding="utf-8")
    html = '<body><p data-source="README.md:2-4">Fast: sub-second execution</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert all(f.kind != "cite-off" for f in findings)
    assert stats["cited_lines"] == 1


def test_brochure_fixture_fails_then_passes_once_citation_corrected(tmp_path: Path):
    """The checked-in fixture cites line 7 for text that lives on line 4 → cite-off.
    Correcting the citation to :4 makes the scan clean."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(_BROCHURE_README, encoding="utf-8")

    # RED: fixture has the wrong line citation
    report_wrong = cs.run(str(BROCHURE_FIXTURE), repos=[str(repo)])
    assert report_wrong["ok"] is False
    assert report_wrong["by_kind"].get("cite-off", 0) >= 1
    cite_off_findings = [f for f in report_wrong["findings"] if f["kind"] == "cite-off"]
    assert any("nearest match" in f["detail"] for f in cite_off_findings)

    # GREEN: correct the citation in-memory → clean
    fixed_html = BROCHURE_FIXTURE.read_text(encoding="utf-8").replace(
        'data-source="README.md:7"', 'data-source="README.md:4"'
    )
    fixed_findings, _ = cs.scan_document(fixed_html, repos=[str(repo)])
    assert all(f.kind != "cite-off" for f in fixed_findings)


# ── cite-off new bug fixes (#1178, #1179, #1181) ─────────────────────────────────────────────


def test_out_of_range_line_spec_is_cite_off(tmp_path: Path):
    """#1178 — a line number past EOF must fail, not clamp to the last line.

    Red on main: max(0, min(9999-1, 2)) = 2 → reads line 3 "last words here" → overlap → None →
    cited_lines=1, findings=[]. Green after fix: 9999 > 3 → detail "past end of file (3 lines)" →
    cite-off finding, cited_lines=0.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("line1\nline2\nlast words here\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:9999">last words here</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "past end of file (3 lines)" in coffs[0].detail
    assert stats["cited_lines"] == 0


def test_out_of_range_range_spec_end_is_cite_off(tmp_path: Path):
    """#1178 — a range whose end exceeds EOF must fail, not clamp.

    Red on main: end clamped to min(2, 998)=2 → reads line 3 → overlap → None → cited_lines=1.
    Green after fix: e_int=999 > 3 → detail "past end of file (3 lines)" → cite-off, cited_lines=0.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("line1\nline2\nlast words here\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:3-999">last words here</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "past end of file (3 lines)" in coffs[0].detail
    assert stats["cited_lines"] == 0


def test_stopword_only_shared_token_is_cite_off(tmp_path: Path):
    """#1179 — a citation whose text is on a different line than cited must fail even when the
    two lines share stopwords.

    Red on main: block_tokens ∩ line2_tokens = {"for", "the"} → nonzero → None → cited_lines=1.
    Green after fix: cited_score=2, best_score=line1=7 → best_score > cited_score → cite-off.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "Fast sub-second execution for the enterprise\nfor the document\n",
        encoding="utf-8")
    # text lives on line 1; cited at line 2 which shares only "for", "the"
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:2">Fast sub-second execution for the enterprise</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "nearest match" in coffs[0].detail
    assert stats["cited_lines"] == 0


def test_inline_wrapped_citation_is_checked(tmp_path: Path):
    """#1181-A — a citation on a block whose text is wrapped in an inline tag must still be checked.

    Red on main: span has no data-source; li.direct_text()="" so li is not in _claim_blocks;
    citation is invisible → findings=[], cited_lines=0 (neither verified nor flagged).
    Green after fix: block=li is found via block_sources; cite-off produced for wrong line.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("nothing here\nfast execution\n", encoding="utf-8")
    # data-source on li (line 1 doesn't match "fast execution")
    html = '<body><ul><li data-source="README.md:1"><span>fast execution</span></li></ul></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1


def test_inline_wrapped_citation_guard_no_false_positive(tmp_path: Path):
    """#1181-A guard — <p data-source="README.md:4">Requirement: <strong>v22</strong></p> must NOT
    produce cite-off when line 4 = "v22" (inline child text IS on the cited line).

    Red on main: el=<p>, own="Requirement: ", _cite_tokens("Requirement: ")={"requirement"},
    line 4 "v22" has no "requirement" → cite-off (false positive, cite_off=1).
    Green after fix: block_text="Requirement: v22" → {"requirement","v22"} ∩ {"v22"} = {"v22"} → verified;
    dedup prevents the p element from re-checking the same (source, block) pair.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("intro\nsomething\nelse\nv22\n", encoding="utf-8")
    html = '<body><p data-source="README.md:4">Requirement: <strong>v22</strong></p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert all(f.kind != "cite-off" for f in findings)
    assert stats["cited_lines"] == 1


def test_single_digit_token_is_not_vacuously_verified(tmp_path: Path):
    """#1181-B — a block whose text is a single digit must not cite any line vacuously.

    Red on main: _cite_tokens("7")={} → if not block_tokens: return None → cited_lines=1 (BUG).
    Green after fix: "7".isdigit() → block_tokens={"7"}; line 999>4 → past-end-of-file cite-off.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:999">7</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert stats["cited_lines"] == 0


def test_directory_as_file_fails_closed(tmp_path: Path):
    """#1181-C — a data-source that names a directory must be treated as unverifiable.

    Red on main: _path_exists_in_repos("docs") True (dir); p.read_text() → IsADirectoryError →
    return None → cited_lines=1 (BUG). Green after fix: p.is_file() False → _UNVERIFIABLE → cite-off.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()          # docs is a directory, not a file
    findings, stats = cs.scan_document(
        '<body><p data-source="docs:5">some words here</p></body>',
        [str(repo)])
    assert any(f.kind == "cite-off" for f in findings)
    assert stats["cited_lines"] == 0


def test_oserror_continues_to_next_repo(tmp_path: Path, monkeypatch):
    """#1181-C — an OSError reading one repo must try the next repo, not abort.

    repo1/README.md raises PermissionError (monkeypatched — works at every euid including root).
    repo2/README.md = file that does NOT carry the block text → cite-off produced.

    Red on original: p.exists() True → p.read_text() → PermissionError → return None →
    cited_lines=1 (aborted at repo1, reported verified despite never reading the file).
    Green after fix: PermissionError → continue → repo2 tried → no match → cite_off=1.
    """
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    readme1 = repo1 / "README.md"
    readme1.write_text("fast execution sub-second\n", encoding="utf-8")
    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    (repo2 / "README.md").write_text("unrelated content here\n", encoding="utf-8")
    _orig_read_text = Path.read_text

    def _failing_read_text(self, *args, **kwargs):
        if self.resolve() == readme1.resolve():
            raise PermissionError("permission denied")
        return _orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _failing_read_text)
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:1">fast execution sub-second</p></body>',
        [str(repo1), str(repo2)])
    assert stats["cite_off"] == 1
    assert stats["cited_lines"] == 0


# ── PR #1183 review follow-ups ────────────────────────────────────────────────────────────────


def test_sibling_elements_each_checked_for_cite_off(tmp_path: Path):
    """PR #1183 review item 1 — silent sibling skip: two sibling <li> with the same source
    must each be independently checked. Previously checked_cite_off keyed on (s, block.path()),
    but path() has no sibling index — both <li> shared a key and the second was never checked.
    Fix: key on (s, id(block)) so each node is distinct regardless of path().

    Two-sibling <li> shape: first element matches line 1 (verified); second element has no
    token overlap with line 1 (genuine cite-off, was silently skipped before the fix).

    Red on b868483a: cite_off=0, cited_lines=1 — second <li> key-collides with first, skipped.
    Green after fix: cite_off=1, cited_lines=1 — first verified, second independently checked.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("fast execution\n", encoding="utf-8")
    html = (
        '<body><ul>'
        '<li data-source="README.md:1">fast execution</li>'
        '<li data-source="README.md:1">slow throughput</li>'
        '</ul></body>'
    )
    findings, stats = cs.scan_document(html, [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert stats["cite_off"] == 1
    assert stats["cited_lines"] == 1


def test_check_cite_off_path_only_returns_none_and_is_skipped():
    """PR #1183 review item 2 — latent contract: _check_cite_off with a path-only source
    returns None; the caller's explicit branch treats None as skip (no cited_lines increment).
    This branch is currently unreachable from scan_document (the :307 _LINE_SPEC_RE guard
    filters path-only sources before calling _check_cite_off), so this test pins the contract
    directly. It passes before and after the latent-contract fix; that is correct and expected.
    """
    assert cs._check_cite_off("README.md", "some text", []) is None


def test_inverted_range_is_invalid(tmp_path: Path):
    """PR #1183 review item 4 — inverted range: README.md:3-1 previously passed both bounds
    checks (3≥1, 1≥1, both ≤3), produced an empty slice, and mischaracterised as
    'does not carry this text'. Fix: add s_int > e_int guard with a distinct 'invalid range'
    detail, distinct from past-end-of-file and does-not-carry-this-text.

    Red on b868483a: detail contains 'does not carry this text — nearest match: line 1'.
    Green after fix: detail contains 'invalid range (3 > 1)'.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("line one\nline two\nline three\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:3-1">line three</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "invalid range" in coffs[0].detail
    assert "3 > 1" in coffs[0].detail
    assert stats["cite_off"] == 1
    assert stats["cited_lines"] == 0


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


# ── review follow-ups: L2 false-positive classes, M1 ───────────────────────────────────────────

@pytest.mark.parametrize("html", [
    "<p>Published September 12, 2026 by the team.</p>",
    "<p>Updated 12 Sep 2026.</p>",
    "<p>Roadmap for Sep 2026 and Q3 2026.</p>",
    "<p>The 2026 roadmap in one page.</p>",
    "<h2>1. Readable</h2><h2>2) Sized to the brief</h2>",
    "<h3>Step 1 — outline</h3><p>Figure 2 shows the flow. See Table 3 and Section 4.</p>",
    "<footer>Page 1 of 2</footer><footer>1 / 2</footer>",
    "<span class='badge'>10</span><span class='num'>7</span>",
])
def test_structural_numbers_are_not_claims(html):
    assert _kinds(f"<body>{html}</body>") == []


@pytest.mark.parametrize("html", [
    "<p>Gate events appear within 2 seconds.</p>",
    "<p>Node ≥ 22 · npm ≥ 10</p>",
    "<p>3 active runs · 1 needs you</p>",
    "<p>Success rate 94% over 12 months.</p>",
])
def test_real_figures_are_still_claims(html):
    assert "uncited-number" in _kinds(f"<body>{html}</body>")


def test_cli_survives_a_cp1252_console():
    """M1 — echoed document text carries ≥ · — and curly quotes; must print, not raise."""
    import os
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE)], capture_output=True, env=env)
    assert proc.returncode == 1 and b"Traceback" not in proc.stderr
    assert b"[placeholder]" in proc.stdout
