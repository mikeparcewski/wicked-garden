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
    assert ("every unit in the files the repository tracks was asked once; 263 placeholders not "
            "resolved yet, and asking again can raise the share") in d["line"], d["line"]
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


def test_placeholders_asked_again_and_still_unresolved_recommend_no_third_ask(tmp_path, capsys):
    db, repo = _first_run_asked_everything(tmp_path)
    _next(db, repo, RUN1, 60, WICKED_REPEAT_PASS=1)
    _next(db, repo, RUN1, 61, WICKED_REPEAT_PASS=1, WICKED_REPEAT_CHOICE="again")
    # page 2 asks the 263 again; 101 resolve (run 92cf8547's yield), 162 stay placeholders
    generation.frame_page(db, "run-1", HELD1)
    generation.record_answered(db, "run-1", HELD1)
    d = _next(db, repo, RUN2, 120, WICKED_REPEAT_PASS=2)
    assert d["next"] == "ask"
    assert [c["id"] for c in d["choices"]] == ["again", "lower"]
    assert d["recommended"] == "lower", "every one of them was asked twice"
    assert "162 placeholders asked again and still not resolved" in d["line"], d["line"]
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
    assert [c["id"] for c in d["choices"]] == ["again", "lower"] and d["recommended"] == "lower"
    assert "the last page resolved under 1 in 20 of its units" in d["line"], d["line"]
    assert "154 placeholders asked again and still not resolved" in d["line"], d["line"]
    assert "nothing is left to map" not in d["line"]


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
