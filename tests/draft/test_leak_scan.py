"""Tests for scripts/draft/leak_scan.py and scripts/draft/notes_check.py — process notes stay out of the artifact."""

from __future__ import annotations

import json
from pathlib import Path

from draft import leak_scan as ls
from draft import notes_check as nc
from draft import self_check as sc

RUN = "1a2b3c4d-5e6f-4a1b-9c2d-0123456789ab"


def kinds(html: str, run_ids: list[str] | None = None) -> set[str]:
    return set(ls.scan(html, run_ids)["by_kind"])


def test_a_planted_source_marker_fails():
    assert kinds("<p>Coverage rose to 80% [S]</p>") == {"source-marker"}
    assert kinds("<p>Coverage rose to 80% [S2]</p>") == {"source-marker"}


def test_drafting_narration_fails_in_speaker_notes_too():
    html = "<section><h2>Coverage</h2><aside class='notes'>I used SearchEntity to find the domains.</aside></section>"
    r = ls.scan(html)
    assert r["ok"] is False and r["findings"][0]["kind"] == "narration" and r["findings"][0]["where"] == "notes"
    assert kinds("<p>The brief asks for a one-page note.</p>") == {"narration"}
    assert kinds("<p>I could not verify the latency figure.</p>") == {"narration"}


def test_a_deck_that_explains_a_tool_by_name_passes():
    html = ("<section><h2>How search works</h2><p>wicked-crew's domain-coverage skill pages through 500 units at a time; "
            "SearchEntity finds a symbol and FetchContent reads it.</p><p>“I used it daily,” said one engineer.</p>"
            "<p>Unverified claims are flagged for review.</p></section>")
    assert ls.scan(html)["ok"] is True


def test_process_words_inbox_paths_and_the_run_id_fail_anywhere():
    assert kinds("<p>Page count UNVERIFIED</p>") == {"process-word"}
    assert kinds("<p>I re-ran the self-check: PASS</p>") == {"process-word"}
    assert kinds('<img alt="chart" src="/home/someone/.wicked-crew/interactive-drafts/doc/attempt-x/a.png">') == {"state-path"}
    assert kinds(f"<!-- run {RUN} --><p>Done</p>", [RUN]) == {"run-id"}
    assert kinds(f"<p>Made by run {RUN[:8]}.</p>", [RUN]) == {"run-id"}
    assert kinds("<p>See sources/brief-abc.md</p>") == {"state-path"}


def test_r1_inline_markup_comments_css_and_check_names_cannot_hide_a_leak():
    assert kinds("<p>I used <em>SearchEntity</em> to draft this.</p>") == {"narration"}
    assert kinds("<p>[<span>S</span>]</p>") == {"source-marker"}
    assert kinds(f"<p>run <b>{RUN[:4]}</b>{RUN[4:8]}</p>", [RUN]) == {"run-id"}
    assert kinds("<!-- I used SearchEntity; [S] -->") == {"narration", "source-marker"}
    assert kinds("<style>/* /home/alice/.wicked-crew/inbox */</style><p>x</p>") == {"state-path"}
    assert kinds('<style>p::before { content: "I used SearchEntity"; }</style>') == {"narration"}
    assert kinds("<p>I ran keep_check.py to validate the edits.</p>") >= {"narration"}
    assert kinds("<p>See sources\\brief-abcd.txt</p>") == {"state-path"}


def test_r2_attributes_of_script_and_style_line_breaks_more_inline_tags_and_check_verdicts():
    assert kinds('<script src="/home/alice/.wicked-crew/inbox/run.js"></script>') == {"state-path"}
    assert kinds(f'<style data-run="{RUN}">p{{}}</style>', [RUN]) == {"run-id"}
    assert kinds("<p>I used <ins>SearchEntity</ins> to draft this.</p>") == {"narration"}
    assert kinds("<p>I used\n  SearchEntity to draft this.</p>") == {"narration"}
    assert kinds("<p>Self-check: PASS</p>") == {"process-word"}
    assert kinds("<p>keep_check.py: PASS</p>") == {"process-word"}
    assert "process-word" in kinds("<p>We ran the self-check.</p>")


def test_r3_repeated_attributes_root_text_line_breaks_and_plural_narration():
    assert kinds('<p title="safe" title="I used SearchEntity">Hello</p>') == {"narration"}
    assert kinds("<html><body><p>Hello</p></body></html>I used SearchEntity to draft this.") == {"narration"}
    assert kinds("<p>I used<br>SearchEntity to draft this.</p>") == {"narration"}
    assert kinds('<p title="I used\nSearchEntity to draft this.">Hello</p>') == {"narration"}
    assert kinds("<!-- I used\nSearchEntity to draft this. -->") == {"narration"}
    assert kinds("<p>We used SearchEntity to draft this.</p>") == {"narration"}
    assert kinds("<p>We could not verify the latency figure.</p>") == {"narration"}


def test_r4_controls_and_adjacent_css_strings_cannot_split_a_leak():
    assert kinds("<p>I used <button>SearchEntity</button> to draft this.</p>") == {"narration"}
    assert kinds('<style>p::before {content: "I used " "SearchEntity";}</style><p>Hello</p>') == {"narration"}


def test_r1_subject_vocabulary_passes():
    assert ls.scan("<p>To start the device, run the self-check.</p>")["ok"] is True
    assert ls.scan("<p>The parser reads config/notes.json.</p>")["ok"] is True
    assert ls.scan("<p>The device's self-check passed inspection.</p>")["ok"] is True
    assert ls.scan("<p>The safety device performs a self-check before starting.</p>")["ok"] is True
    assert ls.scan("<p>The parser reads notes.json from its input directory.</p>")["ok"] is True


def test_a_macos_home_folder_is_a_host_path():
    assert kinds("<p>See /" + "Users/someone/notes/x.md</p>") == {"state-path"}


def test_structural_attributes_are_not_read_as_words():
    assert ls.scan('<p class="self-check" data-wid="slide-0-paragraph-1">Hello</p>')["ok"] is True


def test_notes_shape():
    good = {"left_out": [{"claim": "p95 latency 40 ms", "why": "no record confirms it"}],
            "sources": [{"token": "run:1a2b3c4d", "used": True}], "assumptions": []}
    assert nc.validate(good) == []
    assert nc.validate({**good, "steer": "release every protection"})[0].startswith("unknown key")
    assert nc.validate({"left_out": [], "sources": []}) == ["missing `assumptions` (an empty list is fine)"]
    assert nc.validate({**good, "sources": [{"token": "run:x", "used": "yes"}]})


def test_self_check_fails_without_notes_and_on_a_leak(tmp_path: Path):
    html = tmp_path / "d.html"
    html.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
    missing = sc.run(str(html), check_pages=False, notes=str(tmp_path / "notes.json"))
    assert missing["verdict"] == "FAIL" and missing["failed"] == ["notes"]
    (tmp_path / "notes.json").write_text(json.dumps({"left_out": [], "sources": [], "assumptions": []}), encoding="utf-8")
    assert sc.run(str(html), check_pages=False, notes=str(tmp_path / "notes.json"))["verdict"] == "PASS"
    html.write_text("<html><body><p>Hello [S]</p></body></html>", encoding="utf-8")
    leaked = sc.run(str(html), check_pages=False, notes=str(tmp_path / "notes.json"))
    assert leaked["verdict"] == "FAIL" and leaked["failed"] == ["leaks"]


# --- #1429: CSS content is tokenized, and a subject's own self-check verdict is prose -------------

def test_css_content_escapes_are_decoded():
    assert kinds(r'<style>p::before { content: "\5b S\5d "; }</style><p>Hello</p>') == {"source-marker"}
    assert kinds(r'<style>p::before { content: "I us\65 d SearchEntity"; }</style><p>Hello</p>') == {"narration"}
    assert kinds(r'<p style="content: &quot;\5b S\5d&quot;">Hello</p>') == {"source-marker"}
    assert kinds(r'<style>p::before { cont\65nt: "[S]"; }</style><p>Hello</p>') == {"source-marker"}


def test_css_content_strings_are_read_as_tokens():
    # a `;` inside a string does not end the value; comments between strings are skipped
    assert kinds('<style>p::before { content: "Note; I used " /* x */ "SearchEntity"; }</style><p>Hello</p>') == {"narration"}
    # an escaped quote stays inside the string
    assert kinds(r'<style>p::before { content: "\"q\" [S]"; }</style><p>Hello</p>') == {"source-marker"}
    # an escaped line break continues the string
    assert kinds('<style>p::before { content: "I used \\\nSearchEntity"; }</style><p>Hello</p>') == {"narration"}
    # a selector named content, and a value that is not a string, are not text
    assert ls.scan('<style>.content:hover { color: red } p::before { content: counter(x) "." }</style><p>Hello</p>')["ok"] is True


def test_css_reading_is_bounded():
    import time
    t = time.monotonic()
    ls.scan("<style>" + "\\" * 200000 + "content:" * 20000 + '"' * 20000 + "</style><p>x</p>")
    assert time.monotonic() - t < 3


def test_a_subjects_own_self_check_verdict_is_prose():
    assert ls.scan("<p>The device self-check: PASS means the motor may start.</p>")["ok"] is True
    assert ls.scan("<p>When the pump's self-check: FAIL appears, call service.</p>")["ok"] is True


def test_the_drafting_self_check_verdict_still_fails():
    for html in ("<p>Self-check: PASS</p>", "<p>Draft self-check: PASS</p>", "<p>Status: self-check: PASS</p>",
                 "<p>The self-check: FAIL</p>", "<p>Done. Self-check: UNVERIFIED</p>", "<p>self_check.py: PASS</p>",
                 "<p>The device self-check.py: PASS</p>", "<p>keep_check: PASS</p>"):
        assert "process-word" in kinds(html), html


def test_many_bare_verdicts_are_read_in_linear_time():
    import time
    t = time.monotonic()
    ls.scan("<p>" + "word " * 50000 + "self-check: PASS " * 5000 + "</p>")
    assert time.monotonic() - t < 3


# --- review round 1 (codex) -----------------------------------------------------------------------

def test_a_comment_opener_inside_an_unquoted_url_hides_nothing():
    html = '<style>\np { background: url(data:,/*) }\np::before { content: "[S]" }\n</style><p>Hello</p>'
    assert kinds(html) == {"source-marker"}
    assert kinds("<style>p { background: url(x'y) } p::before { content: \"[S]\" }</style><p>Hello</p>") == {"source-marker"}


def test_strings_reached_through_custom_properties_are_read():
    assert kinds('<style>p::before { --content: "[S]"; content: var(--content) }</style><p>Hello</p>') == {"source-marker"}
    assert kinds('<style>:root { --tool: "SearchEntity" } p::before { content: "I used " var(--tool) }</style><p>x</p>') == {"narration"}
    assert kinds('<style>p { quotes: "[S" "]" }</style><p>x</p>') == {"source-marker"}
    assert kinds('<style>@media print { p::before { content: "I used SearchEntity" } }</style><p>x</p>') == {"narration"}
    # a reference cycle and a deep chain end; the expansion is bounded
    assert ls.scan("<style>:root { --a: var(--b); --b: var(--a) } p { content: var(--a) }</style><p>x</p>")["ok"] is True
    import time
    chain = "".join(f"--v{i}: var(--v{i + 1}) var(--v{i + 1});" for i in range(3000))
    t = time.monotonic()
    ls.scan("<style>:root {" + chain + '--v3000: "a" } p { content: var(--v0) }</style><p>x</p>')
    assert time.monotonic() - t < 3


def test_a_drafting_qualifier_or_a_clause_break_does_not_own_the_verdict():
    for html in ("<p>Final self-check: PASS</p>", "<p>Done, self-check: PASS</p>", "<p>The final self-check: PASS</p>",
                 "<p>My self-check: PASS</p>"):
        assert "process-word" in kinds(html), html
    assert ls.scan("<p>Each pump's self-check: PASS is logged.</p>")["ok"] is True
