"""wicked-garden#1533: the card read "nothing left to map" with placeholders a second ask resolves.

The fixtures are the `coverage-report.json` files `extract-apply` wrote into the worktrees of the
train-12 CardDemo certification runs (the report `wicked-core coverage` returns, published by
`scripts/domain/apply_rules.py` through `rules_file.write_json_file(base, coverage_rel, after)`),
copied unchanged:

  * coverage_carddemo_run1_page2.json — run f88faa2f after its second page: 434 of 697 real,
    263 placeholders, 0 unmapped. Every unit had been asked once, and the card offered only
    "Lower the minimum" ("nothing left to map in the files the repository tracks").
  * coverage_carddemo_run2_page1.json — the next run (92cf8547) after asking those 263 again:
    535 real, 162 placeholders (a subset of the 263).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from domain import generation, next_page  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MIN = 60_000
RUN1 = json.loads((FIXTURES / "coverage_carddemo_run1_page2.json").read_text())
RUN2 = json.loads((FIXTURES / "coverage_carddemo_run2_page1.json").read_text())
HELD1 = [n["symbol_id"] for n in RUN1["placeholder_nodes"]]
RUN3 = json.loads((FIXTURES / "coverage_carddemo_run3_page1.json").read_text())
HELD2 = [n["symbol_id"] for n in RUN2["placeholder_nodes"]]


class _FixtureCore:
    """`wicked-core coverage` answers the recorded report; the daemon's minimum is 80%."""

    def __init__(self, doc):
        self.doc = doc

    def coverage(self, db, out):
        Path(out).write_text(json.dumps(self.doc))
        return self.doc

    def requirements_target(self, db, set_pct=None):
        assert set_pct is None, "nothing here lowers the minimum"
        return 80, "daemon"


def _repo(tmp_path):
    from tests.domain.test_extraction_files import _git_repo
    files = sorted({n["file"] for n in RUN1["placeholder_nodes"]})
    return _git_repo(tmp_path, tracked=files)


def _next(db, repo, doc, minute, **env):
    run_env = {"WICKED_RUN_ID": "run-1", **{k: str(v) for k, v in env.items()}}
    return next_page.run(db, repo, core=_FixtureCore(doc), env=run_env, now=minute * MIN)


def _first_run_asked_everything(tmp_path):
    """Run 1: one page framed every behaviour (434 now real, 263 left placeholders) and closed."""
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    repo = _repo(tmp_path)
    generation.open_record(str(db), "run-1", {"behavior_bearing": 697, "resolved": 0},
                           "carddemo-t12", at=0)
    page = [f"real::{i}" for i in range(434)] + HELD1
    generation.frame_page(str(db), "run-1", page)
    generation.record_answered(str(db), "run-1", page)
    return str(db), repo


def test_every_unit_asked_once_offers_to_ask_the_placeholders_again(tmp_path, capsys):
    db, repo = _first_run_asked_everything(tmp_path)
    d = _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)
    assert d["next"] == "ask"
    assert [c["id"] for c in d["choices"]] == ["again", "lower"]
    assert d["choices"][0]["label"] == "Ask the 263 placeholders again"
    # a second ask is likely to help: it is the recommendation, not lowering the minimum
    assert d["recommended"] == "again"
    assert "nothing left to map" not in d["line"], d["line"]
    assert ("263 placeholders this run asked about once, unresolved: asking again can help"
            in d["line"]), d["line"]
    assert "real requirements 0% → 62%" in d["line"]


def test_again_reopens_the_asked_placeholders_for_the_next_page(tmp_path, capsys):
    db, repo = _first_run_asked_everything(tmp_path)
    _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)
    # the engine re-runs the step at the same pass with the operator's choice
    d = _next(db, repo, RUN1, 61, WICKED_REPEAT_PASS=1, WICKED_REPEAT_CHOICE="again")
    assert d["next"] == "continue", d
    rec = generation.load(db, "run-1")
    # prepare frames every placeholder no closed page holds in `visited`
    # (scripts/domain/prepare_worklist.py: candidates not in `seen`)
    assert not set(HELD1) & generation.visited(rec)
    assert generation.asked_again(rec) == set(HELD1)
    assert rec["grant"] == {"page": 1, "at": 61 * MIN}, "the operator's answer grants a budget"
    assert [p["page"] for p in rec["points"]] == [0, 1], "an answer is not another page"


def test_a_second_ask_that_resolved_some_still_recommends_asking_again(tmp_path, capsys):
    """wicked-garden#1536: after re-asks that resolved 11 and 14 units (run 37e5f9da) the card
    recommended "Lower the minimum to 74%". While a re-ask still moves the share, asking again
    stays the recommendation; lowering is offered and says what it gives up."""
    db, repo = _first_run_asked_everything(tmp_path)
    _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)
    _next(db, repo, RUN1, 61, WICKED_REPEAT_PASS=1, WICKED_REPEAT_CHOICE="again")
    # page 2 asks the 263 again; 101 resolve (run 92cf8547's yield), 162 stay placeholders
    generation.frame_page(db, "run-1", HELD1)
    generation.record_answered(db, "run-1", HELD1)
    d = _next(db, repo, RUN2, 120, WICKED_REPEAT_PASS=2)
    assert d["next"] == "ask"
    assert [c["id"] for c in d["choices"]] == ["again", "lower"]
    assert d["recommended"] == "again", "the second ask resolved 101 of the 263"
    assert d["choices"][1]["label"] == ("Lower the minimum to 76% for repo and build the "
                                        "graph with 162 behaviours left without a requirement")
    assert "162 placeholders asked again and still unresolved" in d["line"], d["line"]
    assert "real requirements 0% → 62% → 76%" in d["line"]
    assert set(HELD2) <= generation.visited(generation.load(db, "run-1"))


def test_a_near_empty_second_ask_still_says_what_is_left_and_offers_it(tmp_path, capsys):
    db, repo = _first_run_asked_everything(tmp_path)
    _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)
    _next(db, repo, RUN1, 61, WICKED_REPEAT_PASS=1, WICKED_REPEAT_CHOICE="again")
    generation.frame_page(db, "run-1", HELD1)
    generation.record_answered(db, "run-1", HELD1)
    _next(db, repo, RUN2, 120, WICKED_REPEAT_PASS=2)
    d = _next(db, repo, RUN2, 121, WICKED_REPEAT_PASS=2, WICKED_REPEAT_CHOICE="again")
    assert d["next"] == "continue"
    # page 3 asks the 162 once more; 8 resolve (run b6e2a946's yield)
    generation.frame_page(db, "run-1", HELD2)
    generation.record_answered(db, "run-1", HELD2)
    d = _next(db, repo, RUN3, 180, WICKED_REPEAT_PASS=3)
    assert d["next"] == "ask"
    # 8 of 162 resolved: under 1 in 20, but a re-ask still moves the share (wicked-garden#1536)
    assert [c["id"] for c in d["choices"]] == ["again", "lower"] and d["recommended"] == "again"
    assert d["line"].endswith("the last page resolved under 1 in 20 of its units: read its review"
                              " · 154 placeholders asked again and still unresolved"), d["line"]
    assert "nothing is left to map" not in d["line"]


def test_a_re_ask_that_resolved_none_recommends_lowering_and_says_what_it_gives_up(tmp_path,
                                                                                    capsys):
    """wicked-garden#1536: only a re-ask page that resolved none of its units leaves lowering
    as the recommendation, and its label names the behaviours left without a requirement."""
    db, repo = _first_run_asked_everything(tmp_path)
    _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)
    _next(db, repo, RUN1, 61, WICKED_REPEAT_PASS=1, WICKED_REPEAT_CHOICE="again")
    generation.frame_page(db, "run-1", HELD1)
    generation.record_answered(db, "run-1", HELD1)
    # the 263 asked again and not one resolved: the same report as before the page
    d = _next(db, repo, RUN1, 120, WICKED_REPEAT_PASS=2)
    assert d["next"] == "ask" and [c["id"] for c in d["choices"]] == ["again", "lower"]
    assert d["recommended"] == "lower", d
    assert d["choices"][1]["label"] == ("Lower the minimum to 62% for repo and build the "
                                        "graph with 263 behaviours left without a requirement")


def test_a_page_whose_share_did_not_move_recommends_lowering_whatever_its_yield_says():
    """codex r1: a page's yield also counts a changed mapped unit that was real before the page;
    whether asking again helps is read from the share itself."""
    pts = [{"page": 0, "at": 0, "pct": 74, "real": 520, "behaviours": 697, "placeholders": 177},
           {"page": 1, "at": MIN, "took": MIN, "pct": 74, "real": 520, "behaviours": 697,
            "placeholders": 177, "framed": 178, "page_real": 1}]
    d = generation.decide({"points": pts, "grant": {"page": 0, "at": 0}}, repo="r", target=80,
                          now=2 * MIN, max_pages=20, max_minutes=240, left_to_map=0,
                          asked_left=177, asked_once=0)
    assert [c["id"] for c in d["choices"]] == ["again", "lower"] and d["recommended"] == "lower"
    moved = [pts[0], {**pts[1], "real": 521, "placeholders": 176}]
    d = generation.decide({"points": moved, "grant": {"page": 0, "at": 0}}, repo="r", target=80,
                          now=2 * MIN, max_pages=20, max_minutes=240, left_to_map=0,
                          asked_left=176, asked_once=0)
    assert d["recommended"] == "again"


def test_the_lower_label_keeps_what_it_gives_up_inside_the_label_limit():
    last = {"pct": 74, "real": 520, "behaviours": 697}
    assert generation._lower_label("carddemo-t12r3", last) == (
        "Lower the minimum to 74% for carddemo-t12r3 and build the graph with 177 behaviours "
        "left without a requirement")
    long = generation._lower_label("r" * 64, last)
    assert len(long) <= generation.MAX_LABEL and long.endswith("177 behaviours left without a "
                                                               "requirement"), long
    assert "1 behaviour left" in generation._lower_label("r", {"pct": 99, "real": 99,
                                                              "behaviours": 100})


def test_a_minimum_the_placeholders_asked_again_can_reach_is_not_out_of_reach():
    """codex r1: 450 of 1,000 real, 200 units never asked and 350 asked placeholders: resolving
    the 200 and 150 of the reopened 350 reaches 80%, so the line gives no "out of reach"."""
    doc = {"points": [{"page": 0, "at": 0, "pct": 30, "real": 300, "behaviours": 1000,
                       "placeholders": 0},
                      {"page": 1, "at": 10 * MIN, "took": 10 * MIN, "pct": 45, "real": 450,
                       "behaviours": 1000, "placeholders": 350}],
           "grant": {"page": 0, "at": 0}}
    d = generation.decide(doc, repo="r", target=80, now=11 * MIN, max_pages=20, max_minutes=240,
                          left_to_map=200, asked_left=350, asked_once=350)
    assert d["next"] == "continue" and "out of reach" not in d["line"], d["line"]
    short = generation.decide(doc, repo="r", target=80, now=11 * MIN, max_pages=20,
                              max_minutes=240, left_to_map=200)
    assert "minimum out of reach in this run" in short["line"], "without them it is"


def test_the_low_yield_ask_keeps_its_review_instruction_inside_the_line_limit():
    """codex r1: a 404-character line was clipped by wicked-core (repeat.rs MAX_LINE_CHARS 400)
    through "read its review"; the instruction now comes before the placeholder count."""
    pts = [{"page": i, "at": i * MIN, "took": MIN, "pct": p, "real": p * 92, "behaviours": 9200,
            "placeholders": 9200} for i, p in enumerate([50, 51, 52, 53, 54])]
    pts.append({"page": 5, "at": 5 * MIN, "took": MIN, "pct": 54, "real": 54 * 92,
                "behaviours": 9200, "placeholders": 9200, "framed": 500, "page_real": 0})
    d = generation.decide({"points": pts, "grant": {"page": 0, "at": 0}}, repo="r" * 64,
                          target=80, now=6 * MIN, max_pages=20, max_minutes=240, left_to_map=0,
                          asked_left=9200, asked_once=9200)
    assert "read its review" in d["line"][:399], d["line"]
    assert all(len(c["label"]) <= 120 for c in d["choices"])


def test_lowering_after_an_ask_still_ends_the_mapping(tmp_path, capsys):
    """"Lower the minimum ... and build the graph" ends the mapping as its label says."""
    db, repo = _first_run_asked_everything(tmp_path)
    _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)

    class Lowering(_FixtureCore):
        def requirements_target(self, db, set_pct=None):
            return (set_pct or 62), "repository"

    d = next_page.run(db, repo, core=Lowering(RUN1),
                      env={"WICKED_RUN_ID": "run-1", "WICKED_REPEAT_PASS": "1",
                           "WICKED_REPEAT_CHOICE": "lower"}, now=61 * MIN)
    assert d["next"] == "done", d


def test_outside_a_run_nothing_was_asked_so_nothing_is_offered_again():
    held = set(HELD1)
    assert generation.asked_unresolved(None, held) == set()
    doc = {"visited": HELD1[:10]}
    assert generation.reopen(doc, held) == 10
    assert doc["visited"] == [] and doc["asked_again"] == sorted(HELD1[:10])


def test_the_extractor_states_every_worklist_unit_whatever_the_request_names():
    """The extract seat of run b6e2a946 stated 1 of 162 units: "none of CBTRN02C, CBACT04C or
    CBTRN03C is in the 162-unit page" (the request named those three programs), and left the rest
    empty as "CICS screen send/receive/init paragraphs ... file open/close" plumbing; run 92cf8547
    left 224 of 263 out as "screen plumbing, which the skill says to leave empty". The page's
    critique then failed screen-setup paragraphs that decide what is shown. Both instruction
    paths now say a deciding screen, step or I/O unit states its rule, and the skill says the
    request never takes a unit off the page."""
    from tests.domain.test_extraction_files import _extractor_texts
    skill, prompt = _extractor_texts()
    assert "The page is the worklist, whatever the job's request names." in skill
    assert "it never takes a worklist unit off the page" in skill
    for text in (skill, prompt):
        assert "a paragraph that only moves control or data with no condition" in text
        assert ("A screen, step or I/O unit that decides something (what is shown or protected "
                "under which condition, which input is refused, what a failed open or read "
                "stops) states that rule") in text


def test_again_asks_the_seat_afresh_never_hands_back_the_earlier_pages_answers(tmp_path,
                                                                                monkeypatch):
    """codex r1 on #1533: after "again", the earlier page's rules file still held an empty entry
    for every reopened unit, and the harness resumes after any entry the worklist holds, so the
    second ask made no model call and re-applied the old empty answers. Through the real routes
    (prepare, the seat's harness, apply, next) a new page now starts with no rules file."""
    from domain import _clients, _rule_extractor, apply_rules, extract_loop, prepare_worklist
    from domain import rules_file
    from tests.domain.test_extraction_files import (_STAR, _Core, _Estate, _git_repo, _rule,
                                                    _star, _write_rules, _wt)

    class _HeldCore(_Core):
        """Coverage as wicked-core reports it: a [RISK] requirement is a placeholder."""
        def _doc(self):
            def node(s):
                return {"symbol_id": s, "name": s.split("::")[-1], "file": self.nodes[s],
                        "kind": "Function"}
            req = {s: self.estate.writes.get(s, {}).get("req") for s in self.nodes}
            left = [node(s) for s in self.nodes if req[s] is None]
            held = [node(s) for s in self.nodes if req[s] is not None and not req[s][1]]
            n, real = len(self.nodes), len(self.nodes) - len(left) - len(held)
            return {"coverage": (n - len(left)) / n, "behavior_bearing": n, "resolved": real,
                    "risk_flagged": len(held), "unaccounted": len(left), "not_product": 0,
                    "unaccounted_nodes": left, "placeholder_nodes": held}

        def requirements_target(self, db, set_pct=None):
            return 80, "daemon"

    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    db, repo, wt, estate = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path), _Estate()
    core = _HeldCore(estate, {s: "f.py" for s in _STAR})
    page1 = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 500,
                                     estate=estate, core=core)
    framed = [u["symbol_id"] for u in page1["units"]]
    assert sorted(framed) == sorted(_STAR)
    # page 1: the seat states one rule and leaves the rest empty; apply writes placeholders
    _write_rules(wt, "claude", [_rule(framed[0])] + [{"symbol_id": s, "statement": "",
                                                      "confidence": 0.0} for s in framed[1:]])
    apply_rules.apply(db, repo, wt, rules_file.RULES_REL, "coverage-report.json",
                      estate=estate, core=core)
    env = {"WICKED_RUN_ID": "run-1", "WICKED_REPEAT_PASS": "1"}
    d = next_page.run(db, repo, core=core, env=env, now=60 * MIN, worktree=wt)
    assert [c["id"] for c in d["choices"]][0] == "again", d
    d = next_page.run(db, repo, core=core, env={**env, "WICKED_REPEAT_CHOICE": "again"},
                      now=61 * MIN, worktree=wt)
    assert d["next"] == "continue", d
    # page 2 frames the reopened placeholders, and the seat's harness asks its model about each
    page2 = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 500,
                                     estate=estate, core=core)
    assert sorted(u["symbol_id"] for u in page2["units"]) == sorted(framed[1:])
    asked = []

    def model(batch, argv, **kw):
        asked.extend(c["symbol_id"] for c in batch)
        return [_rule(c["symbol_id"]) for c in batch]

    monkeypatch.setattr(_rule_extractor, "extract_rules", model)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["m"])
    assert extract_loop.run_files(wt, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=8, dry_run=False) == 0
    assert sorted(asked) == sorted(framed[1:]), "every reopened unit is asked, none replayed"
    report = apply_rules.apply(db, repo, wt, rules_file.RULES_REL, "coverage-report.json",
                               estate=estate, core=core)
    assert report["applied"]["resolved"] == len(framed) - 1


@pytest.mark.parametrize("fd_safe", [True, False])
def test_removing_an_earlier_pages_rules_file_never_follows_a_planted_link(tmp_path, monkeypatch,
                                                                           fd_safe):
    """Both paths: descriptor-relative on POSIX, the path checks where there is none (Windows)."""
    from domain import rules_file
    if fd_safe and not rules_file._FD_SAFE:
        pytest.skip("no descriptor-relative I/O on this platform")
    monkeypatch.setattr(rules_file, "_FD_SAFE", fd_safe)
    wt = tmp_path / "wt"
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    assert rules_file.remove_file(wt, rules_file.RULES_REL) is False  # nothing there yet
    (wt / ".wicked" / "domain").mkdir(parents=True)
    (wt / rules_file.RULES_REL).symlink_to(outside)
    assert rules_file.remove_file(wt, rules_file.RULES_REL) is True
    assert outside.read_text() == "{}" and not (wt / rules_file.RULES_REL).is_symlink()
    (wt / rules_file.RULES_REL).mkdir()
    try:
        rules_file.remove_file(wt, rules_file.RULES_REL)
        raise AssertionError("a directory at the leaf is refused")
    except rules_file.RulesFileRefused:
        pass
