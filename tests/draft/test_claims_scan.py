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
    """A data-source on an ancestor section is NOT checked for word overlap (its figures are:
    #1551, see test_inherited_line_citation_must_carry_the_figures_it_cites)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\nSomething else entirely\n", encoding="utf-8")
    # section data-source="README.md:2" — child p text has no overlap with line 2
    html = ('<body><section data-source="README.md:2">'
            '<p>Fast: sub-second execution</p></section></body>')
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


def test_check_cite_off_path_only_returns_none_and_is_skipped(tmp_path, monkeypatch):
    """PR #1183 review item 2 — latent contract: _check_cite_off with a path-only source
    returns None; the caller's explicit `if detail is None: pass` arm treats None as skip
    (no cited_lines increment, no cite-off finding). The None branch is currently unreachable
    from scan_document (the :307 _LINE_SPEC_RE guard filters path-only sources first), so the
    caller arm is pinned via monkeypatch: _check_cite_off is forced to return None for a
    line-spec source so the arm IS reached and asserted. Passes before and after the
    latent-contract fix; that is correct and expected (latent-contract exemption — say so plainly).
    """
    # direct contract: path-only source → None
    assert cs._check_cite_off("README.md", "some text", []) is None

    # caller-ordering pin: _check_cite_off forced to return None → cited_lines must stay 0
    # Red when `if detail is None: pass` arm is absent (None falls to else → cited_lines=1).
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("some text here\n", encoding="utf-8")
    monkeypatch.setattr(cs, "_check_cite_off", lambda source, block_text, repos, *figure_text: None)
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:1">some text here</p></body>',
        [str(repo)])
    assert stats["cited_lines"] == 0
    assert all(f.kind != "cite-off" for f in findings)


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


# ── #1184 — the rule: a citation is verified against the text of its CARRIER ──────────────────


def test_inline_sibling_citation_is_verified_against_its_own_text(tmp_path: Path):
    """#1184 A — two inline siblings in one block, same source: each is verified against its OWN
    text, so a sibling's text can never carry an unrelated claim.

    Red on 91e2734: both spans dedup to (source, id(li)) and the one check runs against
    block.all_text() = "alpha only here zzz qqq", which satisfies line 1 on the second span's
    behalf -> cite_off=0, cited_lines=1.
    Green: span 1 verified against "alpha only here"; span 2 checked against "zzz qqq" -> cite-off.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("alpha only here\n", encoding="utf-8")
    html = ('<body><ul><li>'
            '<span data-source="README.md:1">alpha only here</span> '
            '<span data-source="README.md:1">zzz qqq</span>'
            '</li></ul></body>')
    findings, stats = cs.scan_document(html, [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "zzz qqq" in coffs[0].text
    assert stats["cite_off"] == 1
    assert stats["cited_lines"] == 1


def test_citation_on_an_inline_wrapper_is_checked(tmp_path: Path):
    """#1184 — a citation on an inline wrapper BETWEEN the text element and its block is a
    carrier like any other; it must be checked, not dropped.

    Red on 91e2734: el=<span> has no direct source and block=<li> has none either (the source is
    on the intermediate <em>), so the citation is never checked -> cite_off=0, cited_lines=0.
    Green: the <em> carrier is checked against its own text -> cite-off for the wrong line.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("nothing here\nfast execution\n", encoding="utf-8")
    html = ('<body><ul><li><em data-source="README.md:1">'
            '<span>fast execution</span></em></li></ul></body>')
    findings, stats = cs.scan_document(html, [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert stats["cite_off"] == 1


def test_range_is_scored_against_the_best_span_of_its_own_width(tmp_path: Path):
    """#1184 B — a range's cited text is the union of its lines, so scoring it against single
    lines lets a wide range tie or beat any one line. Score it against the best span of the SAME
    width instead.

    Red on 91e2734: cited 3-4 scores 2 ({alpha, beta}); best PER LINE is also 2 -> verified,
    although lines 1-2 carry the whole claim.
    Green: the best 2-line window (lines 1-2) scores 4 > 2 -> cite-off.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "alpha beta\ngamma delta\nalpha zzz\nqqq beta\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:3-4">alpha beta gamma delta</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "nearest match" in coffs[0].detail
    assert stats["cited_lines"] == 0


def test_range_whose_overlap_is_only_common_words_is_cite_off(tmp_path: Path):
    """#1184 B — a citation verifies nothing when every shared token is a common word. The cited
    span here IS the best span of its width, so width-fair scoring alone cannot catch it.

    Red on 91e2734: overlap {the, is, under} -> cited_score=3, best per line=2 -> verified.
    Green: no content word is shared -> cite-off naming the reason.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("the is under\nnothing relevant\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:1-2">Latency under the gate is 2 s</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "common words" in coffs[0].detail
    assert stats["cited_lines"] == 0


def test_single_line_overlap_of_only_common_words_is_cite_off(tmp_path: Path):
    """#1184 B — the same rule on a single line: a stopword-only overlap is not verification.

    Red on 91e2734: cited line 2 shares {the, is} (score 2) and no line scores higher -> verified.
    Green: cite-off, because no content word of the claim is on the cited line.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("zzz qqq\nthe is\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:2">The gate is 2 s</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert len(coffs) == 1
    assert "common words" in coffs[0].detail
    assert stats["cited_lines"] == 0


def test_two_bad_citations_on_one_element_are_two_findings(tmp_path: Path):
    """#1184 — add()'s dedup key must distinguish two different bad citations on one element,
    or stats["cite_off"] counts two while the reader is shown one.

    Red on 91e2734: key=(kind, path, text[:60]) collapses both -> 1 finding, cite_off=2.
    Green: 2 findings, cite_off=2.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("alpha\nbeta\ngamma delta\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:1 README.md:2">gamma delta</p></body>',
        [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert stats["cite_off"] == 2
    assert len(coffs) == 2
    assert sorted(f.detail.split()[1] for f in coffs) == ["README.md:1", "README.md:2"]


def test_a_range_citation_is_disclosed_in_the_stats(tmp_path: Path):
    """#1184 B — a range is a weaker assertion than a line; the summary says how many verified
    citations were ranges.

    Red on 91e2734: stats has no cited_ranges key (KeyError).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\nLine two\nfast execution here\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:2-3">fast execution here</p></body>',
        [str(repo)])
    assert stats["cited_lines"] == 1
    assert stats["cited_ranges"] == 1
    assert all(f.kind != "cite-off" for f in findings)


# ── #1184 codex review follow-ups ─────────────────────────────────────────────────────────────


def test_two_identical_sibling_carriers_are_two_findings(tmp_path: Path):
    """Codex on #1184 — `path()` has no sibling index, so two siblings with the same tag, text and
    bad source produced ONE finding while stats counted two.

    Red before the review fix: cite_off=2 but len(findings)=1 (the second `add` key-collided).
    Green: 2 findings, 2 cite_off — the findings list and the stats agree.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("alpha only here\n", encoding="utf-8")
    html = ('<body><ul><li>'
            '<span data-source="README.md:1">zzz qqq</span> '
            '<span data-source="README.md:1">zzz qqq</span>'
            '</li></ul></body>')
    findings, stats = cs.scan_document(html, [str(repo)])
    coffs = [f for f in findings if f.kind == "cite-off"]
    assert stats["cite_off"] == 2
    assert len(coffs) == 2


def test_a_stopword_rich_line_does_not_beat_the_cited_content_word(tmp_path: Path):
    """Codex on #1184 — the span score counted stopwords, so a line sharing only "it is" outscored
    the cited line that carries the claim's one content word, and a CORRECT citation was reported
    as cite-off.

    Red before the review fix: cited line 1 scores 1 ({fast}), line 2 "it is" scores 2 →
    best_score > overlap → cite-off (false positive).
    Green: both sides are scored on content tokens only → cited 1, best 1 → verified.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("fast\nit is\n", encoding="utf-8")
    findings, stats = cs.scan_document(
        '<body><p data-source="README.md:1">It is fast</p></body>',
        [str(repo)])
    assert all(f.kind != "cite-off" for f in findings)
    assert stats["cited_lines"] == 1


# ── #1530: a citation never leaves the --repo folders ─────────────────────────────────────────

def _escape_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """``repo/`` is the one --repo folder; ``outside.md`` sits beside it and carries the claim's
    words, so a scan that follows the citation out would VERIFY it (the defect)."""
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    (repo / "sub" / "file.md").write_text("intro\nmore\nThroughput reached 42 requests per second\n",
                                          encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("Throughput reached 42 requests per second\n", encoding="utf-8")
    return repo, outside


def test_parent_relative_citation_is_escaped(tmp_path: Path):
    repo, _ = _escape_fixture(tmp_path)
    html = '<body><p data-source="../outside.md:1">Throughput reached 42 requests per second</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert [(f.kind, f.text) for f in findings] == [("escaped-source", "../outside.md:1")]
    assert stats["cited_lines"] == 0


def test_absolute_citation_is_escaped(tmp_path: Path):
    repo, outside = _escape_fixture(tmp_path)
    html = f'<body><p data-source="{outside}:1">Throughput reached 42 requests per second</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert [f.kind for f in findings] == ["escaped-source"]
    assert stats["cited_lines"] == 0


def test_absolute_path_inside_the_repo_is_still_escaped(tmp_path: Path):
    """A citation is repo-relative: an absolute spelling is refused even when it lands inside."""
    repo, _ = _escape_fixture(tmp_path)
    html = (f'<body><p data-source="{repo / "sub" / "file.md"}:3">Throughput reached 42 requests per second</p>'
            '</body>')
    assert _kinds(html, [str(repo)]) == ["escaped-source"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_outward_symlink_citation_is_escaped(tmp_path: Path):
    repo, outside = _escape_fixture(tmp_path)
    try:
        (repo / "link.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    html = '<body><p data-source="link.md:1">Throughput reached 42 requests per second</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert [(f.kind, f.text) for f in findings] == [("escaped-source", "link.md:1")]
    assert stats["cited_lines"] == 0


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_outward_symlink_does_not_source_a_url(tmp_path: Path):
    """The URL check reads only the folder's own files: a link out of it is not one of them."""
    repo, outside = _escape_fixture(tmp_path)
    outside.write_text("docs at https://outside.example.com/x\n", encoding="utf-8")
    try:
        (repo / "link.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    html = '<body><p data-source="sub/file.md">See https://outside.example.com/x</p></body>'
    assert _kinds(html, [str(repo)]) == ["unsourced-url"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_symlink_inside_the_repo_still_verifies(tmp_path: Path):
    repo, _ = _escape_fixture(tmp_path)
    try:
        (repo / "alias.md").symlink_to(repo / "sub" / "file.md")
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    html = '<body><p data-source="alias.md:3">Throughput reached 42 requests per second</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert findings == []
    assert stats["cited_lines"] == 1


def test_ordinary_sub_path_citation_still_verifies(tmp_path: Path):
    repo, _ = _escape_fixture(tmp_path)
    html = ('<body><p data-source="sub/file.md:3">Throughput reached 42 requests per second</p>'
            '<p data-source="sub/../sub/file.md:3">Throughput reached 42 requests per second</p></body>')
    findings, stats = cs.scan_document(html, [str(repo)])
    assert findings == []
    assert stats["cited_lines"] == 2


def test_escaped_citation_fails_the_cli(tmp_path: Path):
    repo, _ = _escape_fixture(tmp_path)
    doc = tmp_path / "doc.html"
    doc.write_text('<body><p data-source="../outside.md:1">Throughput reached 42 requests per second</p></body>',
                   encoding="utf-8")
    res = subprocess.run([sys.executable, str(SCRIPT), str(doc), "--repo", str(repo), "--json"],
                         capture_output=True, text=True, check=False)
    assert res.returncode == 1
    assert json.loads(res.stdout)["by_kind"] == {"escaped-source": 1}


def _reads(monkeypatch) -> list[Path]:
    """Every file the scan reads, resolved — the boundary is "never read outside", not only "never pass"."""
    seen: list[Path] = []
    orig = Path.read_text

    def spy(self, *args, **kwargs):
        seen.append(self.resolve())
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    return seen


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_escaping_citations_never_read_the_outside_file(tmp_path: Path, monkeypatch):
    repo, outside = _escape_fixture(tmp_path)
    try:
        (repo / "link.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    outside.write_text("Throughput reached 42 requests per second, see https://outside.example.com/x\n",
                       encoding="utf-8")
    seen = _reads(monkeypatch)
    html = ('<body><p data-source="../outside.md:1">Throughput reached 42 requests per second</p>'
            f'<p data-source="{outside}:1">Throughput reached 42 requests per second</p>'
            '<p data-source="link.md:1">Throughput reached 42 requests per second</p>'
            '<p data-source="sub/file.md">See https://outside.example.com/x</p></body>')
    kinds = _kinds(html, [str(repo)])
    assert kinds == ["escaped-source", "escaped-source", "escaped-source", "unsourced-url"]
    assert outside.resolve() not in seen


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_an_outward_link_stays_escaped_beside_a_second_folder(tmp_path: Path):
    """A second --repo folder the path is merely absent from never turns an escape into a missing file."""
    repo, outside = _escape_fixture(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    try:
        (repo / "link.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    html = ('<body><p data-source="link.md:1">Throughput reached 42 requests per second</p>'
            '<p data-source="nowhere.md:1">Throughput reached 42 requests per second</p></body>')
    findings, _ = cs.scan_document(html, [str(repo), str(other)])
    assert sorted((f.kind, f.text) for f in findings) == [("dangling-source", "nowhere.md:1"),
                                                          ("escaped-source", "link.md:1")]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_a_link_loop_is_missing_not_a_crash(tmp_path: Path):
    repo, _ = _escape_fixture(tmp_path)
    try:
        (repo / "loop.md").symlink_to(repo / "loop.md")
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    html = ('<body><p data-source="loop.md:1">Throughput reached 42 requests per second</p>'
            '<p data-source="sub/file.md">See https://example.com/x</p></body>')
    assert _kinds(html, [str(repo)]) == ["dangling-source", "unsourced-url"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_a_directory_that_leads_out_is_not_walked(tmp_path: Path, monkeypatch):
    """Windows' os.walk descends a directory junction; the walk prunes a directory that resolves
    outside the folder. Simulated here by walking with followlinks=True."""
    repo, _ = _escape_fixture(tmp_path)
    away = tmp_path / "away"
    away.mkdir()
    (away / "evidence.md").write_text("docs at https://outside.example.com/x\n", encoding="utf-8")
    try:
        (repo / "linked").symlink_to(away, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks need privileges on this host")
    orig_walk = os.walk
    monkeypatch.setattr(cs.os, "walk", lambda top, **kw: orig_walk(top, followlinks=True))
    seen = _reads(monkeypatch)
    html = '<body><p data-source="sub/file.md">See https://outside.example.com/x</p></body>'
    assert _kinds(html, [str(repo)]) == ["unsourced-url"]
    assert (away / "evidence.md").resolve() not in seen


@pytest.mark.parametrize("spelling", ["C:\\outside.md:1", "C:/outside.md:1", "c:outside.md:1", "\\outside.md:1",
                                      "\\\\server\\share\\outside.md:1"])
def test_windows_absolute_spellings_are_escaped_on_every_platform(tmp_path: Path, spelling):
    repo, _ = _escape_fixture(tmp_path)
    html = f'<body><p data-source="{spelling}">Throughput reached 42 requests per second</p></body>'
    assert _kinds(html, [str(repo)]) == ["escaped-source"]


# ── #1551 — the figure is the claim: a wrong figure on the right line is cite-off ─────────────

def _record(tmp_path: Path, text: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "run-x.md").write_text(text, encoding="utf-8")
    return repo


def test_wrong_figure_on_the_right_line_is_cite_off(tmp_path: Path):
    """The issue's case 1: the words overlap, no other line scores better, the figure is wrong."""
    repo = _record(tmp_path, "Coverage reached 80%.\n")
    html = '<body><p data-source="run-x.md:1">Coverage reached 99%.</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    offs = [f for f in findings if f.kind == "cite-off"]
    assert len(offs) == 1 and "99%" in offs[0].detail
    assert stats["cited_lines"] == 0 and stats["cite_off"] == 1


def test_right_figure_on_the_right_line_still_verifies(tmp_path: Path):
    repo = _record(tmp_path, "Coverage reached 80%.\n")
    html = '<body><p data-source="run-x.md:1">Coverage reached 80%.</p></body>'
    findings, stats = cs.scan_document(html, [str(repo)])
    assert findings == [] and stats["cited_lines"] == 1


def test_wrong_figure_names_the_line_that_carries_it(tmp_path: Path):
    # line 1 ties line 3 on words (coverage, reached, march vs 99), so only the figure decides
    repo = _record(tmp_path, "Coverage reached 80% in March.\nNotes.\nCoverage reached 99% in June.\n")
    html = '<body><p data-source="run-x.md:1">Coverage reached 99% in March.</p></body>'
    offs = _find(html, "cite-off", [str(repo)])
    assert len(offs) == 1 and "line 3" in offs[0].detail


def test_the_unit_is_part_of_the_figure(tmp_path: Path):
    """80 ms on the line does not verify 80 s; a unit-less 80 on the line is not 80%."""
    repo = _record(tmp_path, "Median latency 80 ms per call.\nPass rate 80 of the suites.\n")
    wrong_unit = '<body><p data-source="run-x.md:1">Median latency 80 s per call.</p></body>'
    assert _kinds(wrong_unit, [str(repo)]) == ["cite-off"]
    no_unit_on_line = '<body><p data-source="run-x.md:2">Pass rate 80% of the suites.</p></body>'
    assert _kinds(no_unit_on_line, [str(repo)]) == ["cite-off"]
    unit_spelled = '<body><p data-source="run-x.md:1">Median latency 80ms per call.</p></body>'
    assert _kinds(unit_spelled, [str(repo)]) == []


def test_figure_spellings_that_mean_the_same_verify(tmp_path: Path):
    repo = _record(tmp_path, "Indexed 1,200 files at 94 percent coverage.\n")
    html = '<body><p data-source="run-x.md:1">Indexed 1200 files at 94% coverage.</p></body>'
    assert _kinds(html, [str(repo)]) == []


def test_every_figure_must_be_on_the_cited_span(tmp_path: Path):
    repo = _record(tmp_path, "Ran 12 suites; 3 failed.\n")
    html = '<body><p data-source="run-x.md:1">Ran 12 suites; 4 failed.</p></body>'
    offs = _find(html, "cite-off", [str(repo)])
    assert len(offs) == 1 and "figure 4 " in offs[0].detail


def test_a_range_verifies_figures_on_any_of_its_lines(tmp_path: Path):
    repo = _record(tmp_path, "Coverage report\nCoverage reached 80%\nacross 14 repos\n")
    html = '<body><p data-source="run-x.md:2-3">Coverage reached 80% across 14 repos</p></body>'
    assert _kinds(html, [str(repo)]) == []


def test_structural_numbers_are_not_figures_to_verify(tmp_path: Path):
    """Dates and step numbers are not claims (L2), so the cited line need not repeat them."""
    repo = _record(tmp_path, "Coverage reached 80%\n")
    html = '<body><p data-source="run-x.md:1">Step 2: coverage reached 80% in Sep 2026</p></body>'
    assert _kinds(html, [str(repo)]) == []


def test_inherited_line_citation_past_the_end_is_cite_off(tmp_path: Path):
    """The issue's case 2: an ancestor's out-of-range line no longer passes as a citation."""
    repo = _record(tmp_path, "Coverage reached 80%.\n")
    html = '<body><section data-source="run-x.md:999999"><p>Coverage reached 99%.</p></section></body>'
    offs = _find(html, "cite-off", [str(repo)])
    assert any("past end of file" in f.detail for f in offs)


def test_inherited_line_citation_must_carry_the_figures_it_cites(tmp_path: Path):
    repo = _record(tmp_path, "Coverage reached 80%.\nUnrelated line.\n")
    wrong = '<body><section data-source="run-x.md:1"><p>Coverage reached 99%.</p></section></body>'
    offs = _find(wrong, "cite-off", [str(repo)])
    assert len(offs) == 1 and "99%" in offs[0].detail
    right = '<body><section data-source="run-x.md:1"><p>Coverage reached 80%.</p></section></body>'
    assert _kinds(right, [str(repo)]) == []


def test_inherited_citation_still_does_not_need_word_overlap(tmp_path: Path):
    """THE RULE keeps its reason: a section citation covers descendants whose words differ."""
    repo = _record(tmp_path, "# Title\nSomething else entirely\n")
    html = ('<body><section data-source="run-x.md:2">'
            '<h2>Overview</h2><p>Fast and simple to adopt</p></section></body>')
    assert _kinds(html, [str(repo)]) == []


def test_a_block_with_its_own_citation_is_not_judged_by_the_inherited_one(tmp_path: Path):
    repo = _record(tmp_path, "Intro line\nCoverage reached 80%.\n")
    html = ('<body><section data-source="run-x.md:1">'
            '<p data-source="run-x.md:2">Coverage reached 80%.</p></section></body>')
    assert _kinds(html, [str(repo)]) == []


def test_inherited_path_only_citation_stays_provenance(tmp_path: Path):
    repo = _record(tmp_path, "Coverage reached 80%.\n")
    html = '<body><section data-source="run-x.md"><p>Coverage reached 99%.</p></section></body>'
    assert _kinds(html, [str(repo)]) == []


def test_fixtures_still_pass_once_disciplined(tmp_path: Path):
    """Guard: the brochure fixtures keep their meaning under the figure check."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(_BROCHURE_README, encoding="utf-8")
    fixed = BROCHURE_FIXTURE.read_text(encoding="utf-8").replace(
        'data-source="README.md:7"', 'data-source="README.md:4"')
    assert cs.scan_document(fixed, [str(repo)])[0] == []


# ── #1551 round-1 review folds ───────────────────────────────────────────────────────────────

def _one(tmp_path: Path, record: str, html: str) -> list[str]:
    return _kinds(html, [str(_record(tmp_path, record))])


def test_an_unreadable_inherited_citation_is_cite_off(tmp_path: Path):
    repo = _record(tmp_path, "Coverage reached 80%.\n")
    (repo / "docs").mkdir()
    html = '<body><section data-source="docs:1"><p>Coverage reached 99%.</p></section></body>'
    offs = _find(html, "cite-off", [str(repo)])
    assert any("could not be verified" in f.detail for f in offs)


def test_an_inherited_figure_split_by_inline_markup_is_still_checked(tmp_path: Path):
    html = '<body><section data-source="run-x.md:1"><p>Coverage reached <strong>99</strong>%.</p></section></body>'
    assert _one(tmp_path, "Coverage reached 80%.\n", html) == ["cite-off"]


def test_a_date_split_by_inline_markup_is_not_a_figure(tmp_path: Path):
    html = '<body><section data-source="run-x.md:1"><p>Coverage reached 80% in Sep <em>2026</em>.</p></section></body>'
    assert _one(tmp_path, "Coverage reached 80%.\n", html) == []


@pytest.mark.parametrize("claim, record", [
    ("Latency 80 s/call", "Latency 80 ms/call"),     # a unit before '/' is still a unit
    ("Latency 80ms/call", "Latency 80 s/call"),
    ("Revenue changed by 80%", "Revenue changed by -80%"),   # a sign is part of the value
    ("Latency 3 ms", "Latency 1e3 ms"),              # no figure out of the middle of another
    ("Latency 80 µs", "Latency 80 ms"),
    ("Payload 80 MB", "Payload 80 Mb"),              # bytes are not bits
    ("Ran 80-90% of suites", "Ran 10-20% of suites"),  # a range's figures are checked
    ("Window 80 days", "Window 80 s"),
])
def test_a_wrong_figure_does_not_pass_in_any_spelling(tmp_path: Path, claim, record):
    html = f'<body><p data-source="run-x.md:1">{claim}</p></body>'
    assert _one(tmp_path, record + "\n", html) == ["cite-off"]


@pytest.mark.parametrize("claim, record", [
    ("Median latency 80 ms", "Median latency 80   ms"),      # aligned source whitespace
    ("Median latency 80 ms", "Median latency 80.0 ms"),
    ("Median latency 80 ms", "Median latency 80 milliseconds"),
    ("Window 80 d", "Window 80 days"),
    ("Payload 2 GB", "Payload 2 gigabytes"),
    ("Latency 80 ms", "Latency 80ms"),                       # the word check reads 80ms too
    ("Indexed 1200 files", "Indexed 1,200 files"),
    ("Latency 1000 ms", "Latency 1e3 ms"),
])
def test_a_right_figure_passes_in_any_spelling(tmp_path: Path, claim, record):
    html = f'<body><p data-source="run-x.md:1">{claim}</p></body>'
    assert _one(tmp_path, record + "\n", html) == []


def test_a_superscript_footnote_is_not_a_figure(tmp_path: Path):
    html = '<body><p data-source="run-x.md:1">Coverage reached 80%<sup>1</sup></p></body>'
    assert _one(tmp_path, "Coverage reached 80%\n", html) == []


def test_a_hidden_descendant_is_not_a_figure(tmp_path: Path):
    html = '<body><p data-source="run-x.md:1">Coverage reached 80% <span hidden>99%</span></p></body>'
    assert _one(tmp_path, "Coverage reached 80%\n", html) == []


def test_a_nested_block_with_its_own_citation_is_not_the_ancestors_figure(tmp_path: Path):
    html = ('<body><section data-source="run-x.md:1">Overview coverage information.'
            '<p data-source="run-x.md:2">Rate 80%.</p></section></body>')
    assert _one(tmp_path, "Overview coverage information.\nRate 80%.\n", html) == []


def test_a_path_only_ancestor_does_not_switch_the_inherited_check_off(tmp_path: Path):
    html = ('<body><section data-source="run-x.md"><section data-source="run-x.md:1">'
            '<p>Coverage reached 99%</p></section></section></body>')
    assert _one(tmp_path, "Coverage reached 80%\n", html) == ["cite-off"]


def test_a_path_only_ancestor_beside_a_line_holds_the_figure_anywhere_in_its_file(tmp_path: Path):
    repo = _record(tmp_path, "Intro\nCoverage reached 80%\n")
    (repo / "notes.md").write_text("Summary line\n", encoding="utf-8")
    html = ('<body><section data-source="run-x.md notes.md:1">'
            '<p>Coverage reached 80%</p></section></body>')
    assert _kinds(html, [str(repo)]) == []


def test_a_figure_on_any_inherited_line_passes(tmp_path: Path):
    repo = _record(tmp_path, "Coverage reached 80%\nAcross 14 repos\n")
    html = ('<body><section data-source="run-x.md:1 run-x.md:2">'
            '<p>Coverage reached 80% across 14 repos</p></section></body>')
    assert _kinds(html, [str(repo)]) == []


def test_an_inline_citation_covers_its_own_figure_under_an_inherited_one(tmp_path: Path):
    repo = _record(tmp_path, "Overview\nRate 80%\n")
    html = ('<body><section data-source="run-x.md:1"><p>Overview: rate '
            '<b data-source="run-x.md:2">80%</b></p></section></body>')
    assert _kinds(html, [str(repo)]) == []


# ── #1551 round-1 delta folds ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("claim, record", [
    ("Revenue changed by -<strong>80</strong>%", "Revenue changed by 80%"),   # markup keeps the sign
    ("Coverage reached 9<strong>9</strong>%", "Coverage reached 9% and 9%"),  # and the digits
    ("Rate 80 Percent", "Rate 80 s"),                                         # unit words, any case
    ("Latency 80-90ms", "Latency 80s; 90ms"),                                 # a range shares its unit
    ("Latency 3ms", "Latency 1e−3 ms"),                                  # no suffix of an exponent
    ("Speedup 10<sup>3</sup>x", "Speedup 10x"),                               # a superscript exponent
    ("Count 10000000000000000000000000000000000000000000000000000000000000001",
     "Count 10000000000000000000000000000000000000000000000000000000000000000"),
])
def test_a_wrong_figure_does_not_pass_through_markup_case_or_notation(tmp_path: Path, claim, record):
    html = f'<body><p data-source="run-x.md:1">{claim}</p></body>'
    assert _one(tmp_path, record + "\n", html) == ["cite-off"]


@pytest.mark.parametrize("claim, record", [
    ("Rate 80%", "Rate 80 Percent"),
    ("Latency 0.001 ms", "Latency 1e−3 ms"),
])
def test_a_right_figure_passes_in_case_and_notation(tmp_path: Path, claim, record):
    html = f'<body><p data-source="run-x.md:1">{claim}</p></body>'
    assert _one(tmp_path, record + "\n", html) == []


def test_a_wrapped_source_range_keeps_the_unit(tmp_path: Path):
    html = '<body><p data-source="run-x.md:1-2">Median latency 80 ms per call</p></body>'
    assert _one(tmp_path, "Median latency 80\nms per call\n", html) == []


def test_a_leading_zero_section_number_is_not_a_figure_under_an_inherited_citation(tmp_path: Path):
    html = '<body><section data-source="run-x.md:1"><h2><span>01</span> Overview</h2></section></body>'
    assert _one(tmp_path, "Overview\n", html) == []


def test_canonical_figure_tokens_do_not_let_another_line_outscore_the_cited_one(tmp_path: Path):
    html = '<body><p data-source="run-x.md:1">Latency 80.0 ms</p></body>'
    assert _one(tmp_path, "Latency 80 ms\nLatency 8e1 s; 0 ms\n", html) == []


@pytest.mark.parametrize("hidden", ['<span hidden>run-x.md</span>', '<span hidden>[1]</span>'])
def test_a_hidden_path_or_footnote_does_not_exempt_inherited_figures(tmp_path: Path, hidden):
    html = (f'<body><section data-source="run-x.md:1"><p>Coverage reached 99%.{hidden}</p></section>'
            '<footer data-sources>Sources: run-x.md</footer></body>')
    assert "cite-off" in _one(tmp_path, "Coverage reached 80%\n", html)


def test_a_huge_exponent_never_crashes_the_scan(tmp_path: Path):
    repo = _record(tmp_path, "Unrelated 1e1000000 line\nLatency 80 ms\n")
    html = '<body><p data-source="run-x.md:2">Latency 1e1000000 ms</p></body>'
    assert _kinds(html, [str(repo)]) == ["cite-off"]
    assert _kinds('<body><p data-source="run-x.md:2">Latency 80 ms</p></body>', [str(repo)]) == []


def test_a_path_only_ancestor_file_is_read_only_when_a_figure_needs_it(tmp_path: Path, monkeypatch):
    repo = _record(tmp_path, "Coverage reached 80%\n")
    (repo / "big.md").write_text("x\n", encoding="utf-8")
    reads: list[str] = []
    monkeypatch.setattr(cs, "_whole_file", lambda s, r, c: reads.append(s) or "x")
    html = ('<body><section data-source="big.md run-x.md:1">'
            '<p>Coverage reached 80%</p><p>Also 80%</p></section></body>')
    assert _kinds(html, [str(repo)]) == [] and reads == []
