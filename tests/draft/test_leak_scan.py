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
    assert kinds("<p>Ran the self-check: PASS</p>") == {"process-word"}
    assert kinds('<img alt="chart" src="/Users/someone/.wicked-crew/interactive-drafts/doc/attempt-x/a.png">') == {"state-path"}
    assert kinds(f"<!-- run {RUN} --><p>Done</p>", [RUN]) == {"run-id"}
    assert kinds(f"<p>Made by run {RUN[:8]}.</p>", [RUN]) == {"run-id"}
    assert kinds("<p>See sources/brief-abc.md</p>") == {"state-path"}


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
