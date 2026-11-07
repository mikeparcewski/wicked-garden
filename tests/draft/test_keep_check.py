"""Tests for scripts/draft/keep_check.py — a refine keeps the person's own edits (DES-CHAT-ARTIFACTS-001 §6.2, §13 A5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from draft import keep_check as kc

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "draft" / "keep_check.py"


def deck(slides: list[tuple[str, str, str]], styles: dict[str, str] | None = None) -> str:
    """A deck: (slide id, title, body) per slide, each anchored like interactive instruments it."""
    styles = styles or {}
    out = []
    for sid, title, body in slides:
        st = f' style="{styles[sid]}"' if sid in styles else ""
        out.append(f'<section data-slide-id="{sid}" data-wid="sec-{sid}"{st}><h2 data-wid="{sid}-h">{title}</h2>'
                   f'<p data-wid="{sid}-p">{body}</p></section>')
    return "<!doctype html><html><body>" + "".join(out) + "</body></html>"


BASE = [("s1", "Intro", "Hello"), ("s2", "Plan", "Steps"), ("s3", "Risks", "Few"), ("s4", "Ask", "Budget")]


class Lineage:
    def __init__(self, tmp: Path, root_html: str) -> None:
        self.tmp = tmp
        self.steps: list[dict] = []
        self.add("root", root_html)

    def add(self, step: str, html: str, allow: list[str] | None = None) -> "Lineage":
        p = self.tmp / f"_v{len(self.steps)}.html"
        p.write_text(html, encoding="utf-8")
        self.steps.append({"version": len(self.steps), "html": str(p), "step": step, **({"allow": allow} if allow else {})})
        return self

    def map(self) -> dict:
        m, _ = kc.build_map(self.steps)
        return m


def verdict(m: dict, html: str, allow: list[str] | None = None) -> dict:
    return kc.check(m, kc.Version(html), allow or [])


def test_a_retitle_by_hand_is_kept_byte_for_byte(tmp_path: Path):
    v1 = deck(BASE)
    lin = Lineage(tmp_path, v1).add("job", v1).add("hand", deck([("s1", "Release 0.17 — what changed", "Hello"), *BASE[1:]]))
    m = lin.map()
    assert m["texts"] == {"s1-h": "Release 0.17 — what changed"}
    kept = deck([("s1", "Release 0.17 — what changed", "Hello, engineers"), *BASE[1:]])
    assert verdict(m, kept)["ok"] is True
    lost = deck([("s1", "Release 0.17: what changed", "Hello, engineers"), *BASE[1:]])
    r = verdict(m, lost)
    assert r["ok"] is False and r["violations"][0]["kind"] == "changed" and r["violations"][0]["wid"] == "s1-h"


def test_let_this_change_it_releases_exactly_that_value(tmp_path: Path):
    lin = Lineage(tmp_path, deck(BASE)).add("hand", deck([("s1", "Mine", "Hello"), *BASE[1:]]))
    m = lin.map()
    entry = next(e for e in kc.entry_ids(m) if e["wid"] == "s1-h")
    changed = deck([("s1", "Theirs", "Hello"), *BASE[1:]])
    assert verdict(m, changed, [entry["id"]])["ok"] is True
    # The same title edited again by hand is a new value: the old "let it change" no longer releases it.
    lin.add("hand", deck([("s1", "Mine again", "Hello"), *BASE[1:]]))
    assert verdict(lin.map(), changed, [entry["id"]])["ok"] is False


def test_a_moved_slide_holds_through_two_refines(tmp_path: Path):
    moved = [BASE[2], BASE[0], BASE[1], BASE[3]]
    lin = Lineage(tmp_path, deck(BASE)).add("hand", deck(moved))
    m = lin.map()
    assert m["order"] == ["s3", "s1", "s2", "s4"]
    refined = deck([(s, t, b + " tightened") for s, t, b in moved])
    lin.add("job", refined)
    assert verdict(lin.map(), refined)["ok"] is True
    again = deck([(s, t, b + " again") for s, t, b in moved] + [("s9", "New", "Slide")])
    assert verdict(lin.map(), again)["ok"] is True, "a new slide anywhere is fine"
    assert verdict(lin.map(), deck(BASE))["violations"][0]["kind"] == "order"


def test_move_a_then_move_b_keeps_the_latest_order(tmp_path: Path):
    a = [BASE[1], BASE[0], BASE[2], BASE[3]]
    b = [BASE[1], BASE[0], BASE[3], BASE[2]]
    m = Lineage(tmp_path, deck(BASE)).add("hand", deck(a)).add("hand", deck(b)).map()
    assert verdict(m, deck(b))["ok"] is True
    assert verdict(m, deck(a))["ok"] is False


def test_reorder_then_delete_keeps_the_slide_gone_and_the_survivors_order(tmp_path: Path):
    reordered = [BASE[3], BASE[0], BASE[1], BASE[2]]
    deleted = [BASE[3], BASE[0], BASE[2]]
    lin = Lineage(tmp_path, deck(BASE)).add("hand", deck(reordered)).add("hand", deck(deleted))
    m = lin.map()
    assert "sec-s2" in m["gone"] and m["order"] == ["s4", "s1", "s3"]
    lin.add("job", deck(deleted))
    lin.add("job", deck(deleted))
    assert verdict(lin.map(), deck(deleted))["ok"] is True
    back = verdict(lin.map(), deck(reordered))
    assert back["ok"] is False and {v["kind"] for v in back["violations"]} >= {"reappeared"}


def test_a_removed_section_stays_removed(tmp_path: Path):
    m = Lineage(tmp_path, deck(BASE)).add("hand", deck(BASE[:3])).map()
    assert verdict(m, deck(BASE[:3]))["ok"] is True
    assert verdict(m, deck(BASE))["violations"][0]["kind"] == "reappeared"


def test_styled_then_removed_section_protects_nothing_but_its_absence(tmp_path: Path):
    m = (Lineage(tmp_path, deck(BASE)).add("hand", deck(BASE, {"s2": "color:#c00"}))
         .add("hand", deck([BASE[0], BASE[2], BASE[3]])).map())
    assert m["attrs"] == {} and "sec-s2" in m["gone"]
    assert verdict(m, deck([BASE[0], BASE[2], BASE[3]]))["ok"] is True


def test_retitle_twice_protects_the_second_title(tmp_path: Path):
    m = (Lineage(tmp_path, deck(BASE)).add("hand", deck([("s1", "First", "Hello"), *BASE[1:]]))
         .add("hand", deck([("s1", "Second", "Hello"), *BASE[1:]])).map())
    assert m["texts"]["s1-h"] == "Second"


def test_undo_follows_the_parent_chain_so_the_undone_value_is_not_protected(tmp_path: Path):
    # v0 root, v1 the draft, v2 a hand retitle; Undo forks v1 → v3 (parent v1): the chain is v0, v1, v3.
    v1 = deck(BASE)
    lin = Lineage(tmp_path, v1).add("job", v1)
    lin.add("hand", v1)  # the fork of v1, as the host walks it (v2 is not on the chain)
    m = lin.map()
    assert kc.entry_ids(m) == []


def test_a_theme_step_protects_nothing(tmp_path: Path):
    themed = deck(BASE).replace("<body>", "<body style='background:#000'>")
    m = Lineage(tmp_path, deck(BASE)).add("theme", themed).map()
    assert kc.entry_ids(m) == []


def test_a_pre_provenance_version_is_never_claimed_as_kept(tmp_path: Path):
    m = Lineage(tmp_path, deck(BASE)).add("unknown", deck([("s1", "Someone", "Hello"), *BASE[1:]])).map()
    assert kc.entry_ids(m) == []


def test_a_job_step_releases_only_its_accepted_allow(tmp_path: Path):
    lin = Lineage(tmp_path, deck(BASE)).add("hand", deck([("s1", "Mine", "Mine too"), *BASE[1:]]))
    ids = {e["wid"]: e["id"] for e in kc.entry_ids(lin.map())}
    lin.add("job", deck([("s1", "Theirs", "Mine too"), *BASE[1:]]), allow=[ids["s1-h"]])
    m = lin.map()
    assert "s1-h" not in m["texts"] and m["texts"]["s1-p"] == "Mine too"


def test_an_added_slide_must_stay_with_its_initial_text(tmp_path: Path):
    added = BASE + [("s5", "Extra", "Notes")]
    m = Lineage(tmp_path, deck(BASE)).add("hand", deck(added)).map()
    assert "sec-s5" in m["added"] and m["texts"]["s5-h"] == "Extra"
    assert verdict(m, deck(BASE))["violations"][0]["kind"] == "missing"


def test_touched_entries_overlap_the_anchor_by_subtree(tmp_path: Path):
    lin = Lineage(tmp_path, deck(BASE)).add("hand", deck([("s1", "Mine", "Mine too"), ("s2", "Ours", "Steps"), *BASE[2:]]))
    m, head = kc.build_map(lin.steps)
    touched = {e["wid"]: e["touched"] for e in kc.entries_for(m, head, ["sec-s1"])}
    assert touched == {"s1-h": True, "s1-p": True, "s2-h": False}


def test_cli_map_then_check(tmp_path: Path):
    lin = Lineage(tmp_path, deck(BASE)).add("hand", deck([("s1", "Mine", "Hello"), *BASE[1:]]))
    lineage = tmp_path / "lineage.json"
    lineage.write_text(json.dumps({"steps": lin.steps}), encoding="utf-8")
    out = subprocess.run([sys.executable, str(SCRIPT), "map", "--lineage", str(lineage), "--json"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    mapped = json.loads(out.stdout)
    assert [e["label"] for e in mapped["entries"]] == ["slide 1 · heading “Mine”"]
    mp = tmp_path / "map.json"
    mp.write_text(json.dumps(mapped["map"]), encoding="utf-8")
    bad = tmp_path / "bad.html"
    bad.write_text(deck(BASE), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "check", "--map", str(mp), str(bad), "--json"], capture_output=True, text=True)
    assert proc.returncode == 1 and json.loads(proc.stdout)["violations"][0]["wid"] == "s1-h"


def doc(body: str) -> str:
    return f"<!doctype html><html><body>{body}</body></html>"


def test_r1_text_around_an_anchored_child_is_the_parents(tmp_path: Path):
    m = Lineage(tmp_path, doc('<p data-wid="p">Hi <a data-wid="a">world</a></p>')).add(
        "hand", doc('<p data-wid="p">Bye <a data-wid="a">world</a></p>')).map()
    assert m["texts"] == {"p": "Bye"}
    assert verdict(m, doc('<p data-wid="p">Hi <a data-wid="a">world</a></p>'))["ok"] is False


def test_r1_an_unwrapped_descendant_keeps_its_protection(tmp_path: Path):
    v0 = doc('<div data-wid="w"><p data-wid="p">Old</p></div>')
    lin = Lineage(tmp_path, v0).add("hand", doc('<div data-wid="w"><p data-wid="p">Mine</p></div>')).add("hand", doc('<p data-wid="p">Mine</p>'))
    m = lin.map()
    assert m["texts"]["p"] == "Mine" and "w" in m["gone"]
    assert verdict(m, doc('<p data-wid="p">Theirs</p>'))["ok"] is False


def test_r1_the_unchanged_head_always_satisfies_its_own_map(tmp_path: Path):
    head = doc('<p data-wid="p">Mine <b data-wid="b">new</b></p><pre data-wid="c">a    b</pre>')
    m = (Lineage(tmp_path, doc('<p data-wid="p">Old</p><pre data-wid="c">a b</pre>'))
         .add("hand", doc('<p data-wid="p">Mine</p><pre data-wid="c">a b</pre>')).add("hand", head).map())
    assert verdict(m, head)["ok"] is True
    assert m["texts"]["c"] == "a    b", "spacing inside pre is content"
    assert verdict(m, head.replace("a    b", "a b"))["ok"] is False


def test_r1_words_are_not_split_or_joined_by_markup(tmp_path: Path):
    m = Lineage(tmp_path, doc('<p data-wid="p">any where</p>')).add("hand", doc('<p data-wid="p">any<b>where</b></p>')).map()
    assert m["texts"]["p"] == "anywhere"


def test_r1_a_repeated_anchor_never_satisfies_the_check(tmp_path: Path):
    m = Lineage(tmp_path, doc('<p data-wid="p">Old</p>')).add("hand", doc('<p data-wid="p">Mine</p>')).map()
    sneaky = doc('<template><p data-wid="p">Mine</p></template><p data-wid="p">Changed</p>')
    assert verdict(m, sneaky)["ok"] is False
    assert verdict(m, doc('<p data-wid="p">Mine</p><p data-wid="p">Changed</p>'))["violations"][0]["kind"] == "duplicate"


def test_r1_an_attribute_edit_on_a_surviving_node_is_kept_exactly(tmp_path: Path):
    m = (Lineage(tmp_path, doc('<p data-wid="p" class="a" title="t">x</p>'))
         .add("hand", doc('<p data-wid="p" class="b">x</p>')).map())
    assert m["attrs"]["p"] == {"class": "b", "title": None}
    assert verdict(m, doc('<p data-wid="p" class="b">x</p>'))["ok"] is True
    assert verdict(m, doc('<p data-wid="p" class="a">x</p>'))["ok"] is False
    assert verdict(m, doc('<p data-wid="p" class="b" title="t">x</p>'))["ok"] is False
    entry = next(e for e in kc.entry_ids(m) if e.get("name") == "class")
    assert verdict(m, doc('<p data-wid="p" class="c">x</p>'), [entry["id"]])["ok"] is True


def test_r1_a_protected_ancestor_is_touched_too(tmp_path: Path):
    lin = Lineage(tmp_path, doc('<div data-wid="w"><p data-wid="p">x</p></div>')).add("hand", doc('<div data-wid="w" style="color:red"><p data-wid="p">x</p></div>'))
    m, head = kc.build_map(lin.steps)
    assert [e["touched"] for e in kc.entries_for(m, head, ["p"])] == [True]


def test_r1_the_lineage_starts_at_its_root_and_a_malformed_map_is_an_error(tmp_path: Path):
    p = tmp_path / "h.html"
    p.write_text(doc("<p>x</p>"), encoding="utf-8")
    with pytest.raises(kc.KeepError):
        kc.build_map([{"html": str(p), "step": "hand"}])
    with pytest.raises(kc.KeepError):
        kc.validate_map({**kc.empty_map(), "order": ""})
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({**kc.empty_map(), "order": ""}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "check", "--map", str(bad), str(p)], capture_output=True, text=True)
    assert proc.returncode == 2


def test_r2_descendants_removed_with_a_tombstone_stay_removed(tmp_path: Path):
    m = (Lineage(tmp_path, doc('<div data-wid="parent"><p data-wid="child">Remove me</p></div><p data-wid="k">Keep</p>'))
         .add("hand", doc('<p data-wid="k">Keep</p>')).map())
    assert m["gone"] == ["parent"] and m["gone_with"] == {"parent": ["child"]}
    assert verdict(m, doc('<p data-wid="child">Remove me</p><p data-wid="k">Keep</p>'))["ok"] is False
    gone = next(e for e in kc.entry_ids(m) if e["kind"] == "gone")
    assert verdict(m, doc('<p data-wid="child">Remove me</p><p data-wid="k">Keep</p>'), [gone["id"]])["ok"] is True


def test_r2_spacing_in_an_unanchored_pre_is_content(tmp_path: Path):
    m = Lineage(tmp_path, doc('<div data-wid="p"><pre>a b</pre></div>')).add("hand", doc('<div data-wid="p"><pre>a    b</pre></div>')).map()
    assert "a    b" in m["texts"]["p"]
    assert verdict(m, doc('<div data-wid="p"><pre>a b</pre></div>'))["ok"] is False


def test_r2_an_added_empty_cell_stays_empty(tmp_path: Path):
    m = Lineage(tmp_path, doc('<p data-wid="a">x</p>')).add("hand", doc('<p data-wid="a">x</p><p data-wid="p"></p>')).map()
    assert m["texts"]["p"] == ""
    assert verdict(m, doc('<p data-wid="a">x</p><p data-wid="p">Changed</p>'))["ok"] is False


def test_r2_a_template_or_repeated_slide_never_satisfies_the_order(tmp_path: Path):
    m = Lineage(tmp_path, deck(BASE[:2])).add("hand", deck([BASE[1], BASE[0]])).map()
    real = deck(BASE[:2])
    tricked = real.replace("<body>", '<body><template><section data-slide-id="s2" data-wid="t2"></section><section data-slide-id="s1" data-wid="t1"></section></template>')
    assert verdict(m, tricked)["ok"] is False
    assert any(v["kind"] == "duplicate" for v in verdict(m, deck([BASE[1], BASE[0], BASE[1]]).replace('data-wid="sec-s2"', 'data-wid="x"', 1))["violations"])


def test_r2_a_repeated_attribute_reads_as_the_browser_reads_it(tmp_path: Path):
    m = Lineage(tmp_path, doc('<p data-wid="p" class="a">x</p>')).add("hand", doc('<p data-wid="p" class="mine">x</p>')).map()
    assert verdict(m, doc('<p data-wid="p" class="changed" class="mine">x</p>'))["ok"] is False


def test_r3_re_adding_a_container_keeps_its_removed_children_removed(tmp_path: Path):
    m = (Lineage(tmp_path, doc('<div data-wid="parent"><p data-wid="child">x</p></div>'))
         .add("hand", doc('<p data-wid="k">k</p>')).add("hand", doc('<div data-wid="parent"></div><p data-wid="k">k</p>')).map())
    assert "child" in m["gone"]
    assert verdict(m, doc('<div data-wid="parent"><p data-wid="child">x</p></div><p data-wid="k">k</p>'))["ok"] is False


def test_r3_indentation_around_a_pre_is_not_content(tmp_path: Path):
    m = Lineage(tmp_path, doc('<div data-wid="p"><pre>a b</pre></div>')).add("hand", doc('<div data-wid="p"><pre>a    b</pre></div>')).map()
    assert verdict(m, doc('<div data-wid="p">\n  <pre>a    b</pre>\n</div>'))["ok"] is True


def test_r3_a_revision_that_repeats_any_anchor_is_refused(tmp_path: Path):
    m = Lineage(tmp_path, doc('<p data-wid="a">x</p><p data-wid="b">y</p>')).map()
    assert verdict(m, doc('<p data-wid="a">x</p><p data-wid="b">y</p><p data-wid="b">z</p>'))["violations"][0]["kind"] == "duplicate"


def test_unreadable_input_is_an_error_never_a_pass(tmp_path: Path):
    with pytest.raises(kc.KeepError):
        kc.build_map([{"html": str(tmp_path / "nope.html"), "step": "root"}])
    proc = subprocess.run([sys.executable, str(SCRIPT), "check", "--map", str(tmp_path / "none.json"), str(tmp_path / "x.html")],
                          capture_output=True, text=True)
    assert proc.returncode == 2
