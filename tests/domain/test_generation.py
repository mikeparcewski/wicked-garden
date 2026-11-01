"""A generation keeps mapping page by page until the target or the operator's word (domain-graph-3).

`generation.py` holds the record and the pure decision; `next_page.py` is the host step that
measures, records and prints the engine's `wicked-repeat` line.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from domain import _clients, extract_loop, generation, next_page  # noqa: E402

MIN = 60_000


def _pt(page, mapped, at_min, behaviours=1000):
    return {"page": page, "pct": generation.real_pct(mapped, behaviours), "real": mapped,
            "behaviours": behaviours, "at": at_min * MIN}


def _doc(*points, grant=(0, 0)):
    pts = [dict(p) for p in points]
    for prev, p in zip(pts, pts[1:]):  # each page ran from the previous one's end
        p.setdefault("took", p["at"] - prev["at"])
    return {"schema": generation.SCHEMA, "run_id": "r1", "repo": "crew", "points": pts,
            "grant": {"page": grant[0], "at": grant[1] * MIN}}


def _decide(doc, target=80, now_min=None, max_pages=20, max_minutes=240, left=5000):
    now = (now_min if now_min is not None else doc["points"][-1]["at"] // MIN) * MIN
    return generation.decide(doc, repo="crew", target=target, now=now, max_pages=max_pages,
                             max_minutes=max_minutes, left_to_map=left)


def test_below_the_target_with_budget_left_the_run_maps_the_next_page_and_says_so():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 120, 15), _pt(2, 190, 30)))
    assert d["next"] == "continue"
    # one line: the repo, the curve, the target, the next page, and an ETA from its own pace
    # (80 behaviours/page, 15 min/page: 800 - 190 = 610 → 8 pages → 2 h)
    assert d["line"] == ("Mapping crew · real requirements 3% → 12% → 19% · minimum 80% · "
                         "page 3 · about 2 h left")


def test_at_the_target_the_loop_is_done_and_the_line_says_how_long_it_took():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 500, 20), _pt(2, 801, 50)))
    assert d == {"next": "done", "line": "Mapped crew · real requirements 3% → 50% → 80% · "
                                         "minimum 80% reached · 2 pages in 50 min"}


@pytest.mark.parametrize("pages,minutes,spent", [(20, 100, "20 pages"), (5, 240, "240 minutes")])
def test_a_spent_budget_asks_map_more_or_lower_the_target(pages, minutes, spent):
    pts = [_pt(0, 30, 0)] + [_pt(i, 30 + 10 * i, minutes * i // pages) for i in range(1, pages + 1)]
    d = _decide(_doc(*pts), now_min=minutes)
    assert d["next"] == "ask" and d["recommended"] == "continue"
    assert [c["id"] for c in d["choices"]] == ["continue", "lower"]
    assert f"budget reached ({spent};" in d["line"]
    low = generation.real_pct(30 + 10 * pages, 1000)
    assert d["choices"][1]["label"] == f"Lower the minimum to {low}% for crew and build the graph"


def test_a_fresh_grant_restarts_the_budget():
    pts = [_pt(i, 30 + 10 * i, 10 * i) for i in range(0, 22)]
    assert _decide(_doc(*pts), now_min=210)["next"] == "ask"
    assert _decide(_doc(*pts, grant=(21, 210)), now_min=210)["next"] == "continue"


def test_two_pages_that_map_nothing_new_ask_instead_of_looping():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 90, 10), _pt(2, 90, 20), _pt(3, 90, 30)))
    assert d["next"] == "ask" and d["recommended"] == "lower"
    assert "the last two pages added no real requirement" in d["line"]


def test_map_more_after_a_stall_tries_again():
    """codex/agy r1 on #1369: a fresh grant after a stall must run another page, not re-ask."""
    pts = (_pt(0, 30, 0), _pt(1, 90, 10), _pt(2, 90, 20), _pt(3, 90, 30))
    assert _decide(_doc(*pts, grant=(3, 31)), now_min=31)["next"] == "continue"
    # …and stalls again only after two more pages map nothing.
    more = (*pts, _pt(4, 90, 40))
    assert _decide(_doc(*more, grant=(3, 31)))["next"] == "continue"
    assert _decide(_doc(*more, _pt(5, 90, 50), grant=(3, 31)))["next"] == "ask"


def test_nothing_left_to_map_offers_only_to_lower_the_target():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 600, 10)), left=0)
    assert d["next"] == "ask" and [c["id"] for c in d["choices"]] == ["lower"]
    assert d["line"].endswith("nothing left to map in the files the repository tracks")


def test_below_one_percent_no_target_can_be_lowered_to():
    """codex/agy r1 on #1369: "lower to 1%" at 0.5% mapped could never be met."""
    stuck = _doc(_pt(0, 2, 0, behaviours=1000), _pt(1, 5, 10, behaviours=1000))
    d = _decide(stuck, left=0)
    assert d["next"] == "done", "nothing can change; the coverage step says the share"
    budget = _decide(stuck, max_pages=1)
    assert budget["next"] == "ask" and [c["id"] for c in budget["choices"]] == ["continue"]


def test_a_long_curve_keeps_its_start_and_its_last_four():
    pts = [_pt(i, 10 * (i + 1), i) for i in range(9)]
    assert generation.curve_text(pts) == "1% → … → 6% → 7% → 8% → 9%"


def test_the_budget_comes_from_the_settings_and_a_bad_value_is_the_default():
    assert generation.budget_from_env({}) == (20, 240)
    assert generation.budget_from_env({"WICKED_DOMAIN_MAX_PAGES": "6",
                                       "WICKED_DOMAIN_MAX_MINUTES": "90"}) == (6, 90)
    assert generation.budget_from_env({"WICKED_DOMAIN_MAX_PAGES": "-1",
                                       "WICKED_DOMAIN_MAX_MINUTES": "lots"}) == (20, 240)


def test_the_record_lives_beside_the_store_never_in_the_worktree(tmp_path):
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    path = generation.record_path(str(db), "run-1")
    assert path == (tmp_path / "graphs" / "domain-generations" / "run-1.json").resolve()
    with pytest.raises(ValueError):
        generation.record_path(str(db), "../escape")
    cov = {"behavior_bearing": 100, "resolved": 3, "risk_flagged": 0}
    first = generation.open_record(str(db), "run-1", cov, "crew")
    again = generation.open_record(str(db), "run-1", {**cov, "resolved": 50}, "crew")
    assert again == first, "a later page keeps the record its first page opened"
    path.write_text("{not json")
    assert generation.load(str(db), "run-1") is None


class _Core:
    """`coverage` over a mapped count; `requirements-target` with the repository's own value."""

    def __init__(self, mapped, behaviours=1000, unmapped=None, target=80):
        self.mapped, self.behaviours, self.target, self.own = mapped, behaviours, target, None
        self.unmapped = unmapped if unmapped is not None else [
            {"symbol_id": "s::x", "name": "x", "file": "f.py", "kind": "Function"}]
        self.set_calls = []

    def coverage(self, db, out):
        doc = {"behavior_bearing": self.behaviours, "resolved": self.mapped, "risk_flagged": 0,
               "unaccounted": self.behaviours - self.mapped, "unaccounted_nodes": self.unmapped}
        Path(out).write_text(json.dumps(doc))
        return doc

    def requirements_target(self, db, set_pct=None):
        if set_pct is not None:
            self.own = set_pct
            self.set_calls.append(set_pct)
        return (self.own, "repository") if self.own else (self.target, "daemon")


def _repo(tmp_path):
    from tests.domain.test_extraction_files import _git_repo
    if (tmp_path / "repo").exists():
        return str(tmp_path / "repo")
    return _git_repo(tmp_path)


def _env(**kw):
    return {"WICKED_RUN_ID": "run-1", **{k: str(v) for k, v in kw.items()}}


def _run(tmp_path, core, env, now_min, capsys):
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir(exist_ok=True)
    d = next_page.run(str(db), _repo(tmp_path), core=core, env=env, now=now_min * MIN)
    out = capsys.readouterr().out.splitlines()
    return d, out, str(db)


def test_next_page_prints_the_line_then_the_engines_decision(tmp_path, capsys):
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    generation.open_record(str(db), "run-1", {"behavior_bearing": 1000, "resolved": 30}, "repo")
    d, out, _ = _run(tmp_path, _Core(120), _env(WICKED_REPEAT_PASS=1), 15, capsys)
    assert d["next"] == "continue"
    assert out[0].startswith("[extract-next] Mapping repo · real requirements 3% → 12% · minimum 80%")
    assert out[-1].startswith("wicked-repeat ")
    assert json.loads(out[-1][len("wicked-repeat "):]) == d
    rec = generation.load(str(db), "run-1")
    assert [p["page"] for p in rec["points"]] == [0, 1]


def test_the_operators_continue_grants_a_fresh_budget(tmp_path, capsys):
    env = _env(WICKED_DOMAIN_MAX_PAGES=1)
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    generation.open_record(str(db), "run-1", {"behavior_bearing": 1000, "resolved": 30}, "repo")
    d, _, _ = _run(tmp_path, _Core(120), {**env, "WICKED_REPEAT_PASS": "1"}, 15, capsys)
    assert d["next"] == "ask"
    # the engine re-runs the step at the same pass with the choice: the page is not counted twice
    d, _, _ = _run(tmp_path, _Core(120), {**env, "WICKED_REPEAT_PASS": "1",
                                          "WICKED_REPEAT_CHOICE": "continue"}, 16, capsys)
    assert d["next"] == "continue"
    rec = generation.load(str(db), "run-1")
    assert [p["page"] for p in rec["points"]] == [0, 1]
    assert rec["grant"] == {"page": 1, "at": 16 * MIN}


def test_a_retried_or_answered_step_records_the_same_page_and_keeps_its_time(tmp_path, capsys):
    """codex r1 on #1369: the engine's pass names the page; an answer is not mapping time."""
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    generation.open_record(str(db), "run-1", {"behavior_bearing": 1000, "resolved": 30}, "repo",
                           at=0)
    _run(tmp_path, _Core(120), _env(WICKED_REPEAT_PASS=1, WICKED_DOMAIN_MAX_PAGES=1), 15, capsys)
    _run(tmp_path, _Core(120), _env(WICKED_REPEAT_PASS=1, WICKED_DOMAIN_MAX_PAGES=1), 16, capsys)
    rec = generation.load(str(db), "run-1")
    assert [p["page"] for p in rec["points"]] == [0, 1], "a retry is the same page"
    # the operator answers a day later: page 1 keeps the 15 minutes it ran
    d, _, _ = _run(tmp_path, _Core(120), _env(WICKED_REPEAT_PASS=1, WICKED_DOMAIN_MAX_PAGES=1,
                                              WICKED_REPEAT_CHOICE="continue"), 24 * 60, capsys)
    rec = generation.load(str(db), "run-1")
    assert rec["points"][1]["took"] == 16 * MIN and d["next"] == "continue"
    assert rec["grant"] == {"page": 1, "at": 24 * 60 * MIN}
    # page 2 ran 15 minutes after the grant: the ETA counts runs, never the wait
    many = [{"symbol_id": f"s::{i}", "name": "x", "file": "f.py", "kind": "Function"}
            for i in range(800)]  # enough left to ask that the target is in reach
    d, _, _ = _run(tmp_path, _Core(200, unmapped=many),
                   _env(WICKED_REPEAT_PASS=2, WICKED_DOMAIN_MAX_PAGES=5), 24 * 60 + 15, capsys)
    rec = generation.load(str(db), "run-1")
    assert rec["points"][2]["took"] == 15 * MIN
    assert "about 2 h 4 min left" in d["line"], d["line"]  # 15.5 min a page, 85 a page


def test_lowering_the_target_sets_the_repositorys_own_and_finishes(tmp_path, capsys):
    core = _Core(230)
    d, out, _ = _run(tmp_path, core, _env(WICKED_REPEAT_PASS=3, WICKED_REPEAT_CHOICE="lower"),
                     60, capsys)
    assert core.set_calls == [23]
    assert d["next"] == "done"
    assert "minimum lowered to 23% for repo" in d["line"]
    assert "(minimum from the repository)" in out[0]


def test_untracked_unmapped_behaviours_do_not_count_as_left_to_map(tmp_path, capsys):
    core = _Core(300, unmapped=[{"symbol_id": "s::g", "name": "g", "file": "gen/out.py"}])
    d, _, _ = _run(tmp_path, core, _env(WICKED_REPEAT_PASS=1), 10, capsys)
    assert d["next"] == "ask" and [c["id"] for c in d["choices"]] == ["lower"]


def test_next_page_main_exits_1_and_says_why_on_a_failure(tmp_path, monkeypatch, capsys):
    class Broken(_Core):
        def coverage(self, db, out):
            raise RuntimeError("wicked-core coverage exited 2: no store")
    monkeypatch.setattr(_clients, "host_core_client", lambda: Broken(0))
    assert next_page.main(["--db", str(tmp_path / "x.db"), "--repo-root", str(tmp_path)]) == 1
    assert "[extract-next] FAILED: wicked-core coverage exited 2" in capsys.readouterr().err


# --- wicked-garden#1366: the first pages start at the product's code ----------------------

class _Store:
    """A store shape `hub_first_order` reads: names/files, callers and the use adjacency."""

    def __init__(self, nodes, calls):
        self.sym_of = {i: s for i, (s, _, _) in enumerate(nodes)}
        self.sid_of = {s: i for i, s in self.sym_of.items()}
        self.node_row = {i: (name, file, "{}") for i, (_, name, file) in enumerate(nodes)}
        self.callers, self.adj = {}, {}
        for a, b in calls:
            sa, sb = self.sid_of[a], self.sid_of[b]
            self.callers.setdefault(sb, []).append(sa)
            self.adj.setdefault(sa, set()).add(sb)
            self.adj.setdefault(sb, set()).add(sa)


def _collision_store():
    nodes = [("s::startsWith", "startsWith", "src/util/strings.ts"),
             ("s::checkout", "checkout", "src/orders/checkout.ts"),
             ("s::price", "price", "src/orders/price.ts"),
             ("s::helper", "helper", "tests/helpers.test.ts")]
    callers = [(f"s::c{i}", f"c{i}", f"src/mod{i}/a.ts") for i in range(10)]
    calls = [(c, "s::startsWith") for c, _, _ in callers] + [("s::checkout", "s::price"),
                                                            ("s::helper", "s::checkout"),
                                                            ("s::checkout", "s::startsWith")]
    return _Store(nodes + callers, calls)


def test_a_builtin_name_collision_is_never_a_hub_nor_fanned_out_from():
    st = _collision_store()
    sw = st.sid_of["s::startsWith"]
    assert extract_loop.collision_sids(st) == {sw}

    class Rank:
        def rank(self, n):
            return ["s::startsWith", "s::helper", "s::checkout"]
    hubs, how = extract_loop._centrality_hubs(Rank(), st)
    assert hubs == ["s::checkout"], "a builtin-named symbol and a test file never seed a page"
    rank, hops = extract_loop.hub_first_order(st, hubs)
    # the product's code first; the test helper and the collision (reached from the hub) after it
    assert rank["s::checkout"] == 0
    assert rank["s::price"] < min(rank["s::startsWith"], rank["s::helper"])
    assert hops["s::startsWith"] == 1
    # the collision's ten "callers" are never reached THROUGH it (codex r1 on #1369): fanned out
    # from it they would all sit one layer past it; each is seeded on its own instead, one after
    # another, its distance counting on from the last layer
    first = hops["s::c0"]
    assert first > hops["s::startsWith"]
    for i in range(10):
        assert hops[f"s::c{i}"] == first + i and rank[f"s::c{i}"] > rank["s::startsWith"], i


def test_test_files_are_recognised_across_ecosystems():
    for f in ("tests/a.py", "pkg/__tests__/x.ts", "src/a.test.ts", "src/a.spec.tsx",
              "test_foo.py", "pkg/x_test.go", "e2e/flow.ts", "fixtures/data.ts"):
        assert extract_loop.is_test_path(f), f
    for f in ("src/orders/checkout.ts", "src/contest.ts", "src/latest/x.py"):
        assert not extract_loop.is_test_path(f), f


def test_a_json_document_after_an_estate_advisory_line_is_read(monkeypatch):
    import subprocess

    def fake(argv):
        return subprocess.CompletedProcess(argv, 0, stdout=(
            "STALENESS: 1 commit(s) since last index — run `wicked-estate index x`\n"
            "[\n  {\"id\": 1}\n]\n"), stderr="")
    monkeypatch.setattr(_clients, "_invoke", fake)
    assert _clients._run_json(["wicked-estate", "clusters"]) == [{"id": 1}]

    def bracketed(argv):  # an advisory line that itself opens with a bracket is skipped too
        return subprocess.CompletedProcess(argv, 0, stdout="[warn] stale\n{\"ok\": 1}\n", stderr="")
    monkeypatch.setattr(_clients, "_invoke", bracketed)
    assert _clients._run_json(["wicked-estate", "clusters"]) == {"ok": 1}

    def junk(argv):
        return subprocess.CompletedProcess(argv, 0, stdout="STALENESS only\n", stderr="")
    monkeypatch.setattr(_clients, "_invoke", junk)
    with pytest.raises(RuntimeError, match="not JSON"):
        _clients._run_json(["wicked-estate", "clusters"])


# --- domain-real: the target counts REAL requirements only (wicked-core#1233) --------------------

def test_placeholders_never_count_toward_the_target():
    """pi-governance read "100% mapped" with 3 real requirements and 117 placeholders."""
    pt = generation.point_of({"behavior_bearing": 120, "resolved": 3, "risk_flagged": 117}, 1)
    assert (pt["pct"], pt["real"], pt["placeholders"]) == (2, 3, 117)
    d = _decide(_doc({**pt, "page": 0, "at": 0}, {**pt, "at": 10 * MIN}))
    assert d["next"] != "done"
    assert "117 placeholders" in d["line"] and "real requirements 2% → 2%" in d["line"]


def test_a_page_that_resolves_almost_nothing_asks_instead_of_mapping_on():
    """wicked-crew run 4b49cbe1: the page review passed a page that stated 3 rules of 500 units,
    and the run mapped on. Near-zero yield on a full page asks; the operator's grant goes on."""
    low = _doc(_pt(0, 100, 0), {**_pt(1, 103, 10), "framed": 500, "page_real": 3})
    d = _decide(low)
    assert d["next"] == "ask" and d["recommended"] == "continue"
    assert "last page resolved 3 of 500 units" in d["line"]
    assert "under 1 in 20 of its units" in d["line"]
    assert _decide({**low, "grant": {"page": 1, "at": 11 * MIN}}, now_min=11)["next"] == "continue"
    # 25 of 500 is 1 in 20: maps on; a small page is never judged.
    ok = _doc(_pt(0, 100, 0), {**_pt(1, 125, 10), "framed": 500, "page_real": 25})
    assert _decide(ok)["next"] == "continue"
    small = _doc(_pt(0, 100, 0), {**_pt(1, 100, 10), "framed": 19, "page_real": 0})
    assert _decide(small)["next"] == "continue"
    # codex on #1375: the last page is asked about too, before "nothing left to map" ends the run
    last = _decide(_doc(_pt(0, 300, 0), {**_pt(1, 303, 10), "framed": 500, "page_real": 3}), left=0)
    assert last["next"] == "ask" and [c["id"] for c in last["choices"]] == ["lower"]
    assert "under 1 in 20" in last["line"]
    # …and below 1%, with nothing to map or lower to, it still asks: going on is the operator's
    # word (agy/codex r2 on #1375), never a silent "done".
    floor = _decide(_doc(_pt(0, 3, 0), {**_pt(1, 3, 10), "framed": 500, "page_real": 0}), left=0)
    assert floor["next"] == "ask" and [c["id"] for c in floor["choices"]] == ["finish"]
    assert "nothing is left to map" in floor["line"] and "before mapping more" not in floor["line"]
    # …and the yield is the page's own units: 25 resolved elsewhere do not hide 3 of 500 here.
    hidden = _doc(_pt(0, 100, 0), {**_pt(1, 128, 10), "framed": 500, "page_real": 3})
    assert _decide(hidden)["next"] == "ask"


def test_next_page_closes_the_page_and_counts_only_units_no_page_asked(tmp_path, capsys):
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    generation.open_record(str(db), "run-1", {"behavior_bearing": 1000, "resolved": 30}, "repo")
    generation.frame_page(str(db), "run-1", ["s::x"])
    generation.record_answered(str(db), "run-1", ["s::x"])
    core = _Core(120, unmapped=[{"symbol_id": "s::x", "name": "x", "file": "f.py"}])
    d, out, _ = _run(tmp_path, core, _env(WICKED_REPEAT_PASS=1), 15, capsys)
    rec = generation.load(str(db), "run-1")
    assert rec["visited"] == ["s::x"] and rec["pending"] == [] and "answered" not in rec
    # this _Core is shaped like an older wicked-core (no `not_product`): no yield, not a false one
    assert rec["points"][-1]["framed"] == 1 and "page_real" not in rec["points"][-1]
    # the only unit left was asked by this page: nothing left to ask
    assert "nothing left to map" in d["line"], d


def test_the_operators_finish_hands_the_share_to_the_coverage_step(tmp_path, capsys):
    db = tmp_path / "graphs" / "estate.db"
    db.parent.mkdir()
    generation.open_record(str(db), "run-1", {"behavior_bearing": 1000, "resolved": 2}, "repo",
                           at=0)
    # a page that gained one real requirement, then nothing left: the finish line claims no ETA
    # (codex r2 on #1377: it read "about 199 h 15 min left")
    _run(tmp_path, _Core(3, unmapped=[]), _env(WICKED_REPEAT_PASS=1), 15, capsys)
    d, out, _ = _run(tmp_path, _Core(3, unmapped=[]), _env(WICKED_REPEAT_PASS=1,
                                                           WICKED_REPEAT_CHOICE="finish"), 16, capsys)
    assert d["next"] == "done" and "going on as the operator chose" in d["line"]
    assert "about" not in d["line"], d["line"]


def test_a_target_the_run_cannot_reach_gets_no_time_estimate():
    """wicked-crew run 29bbbfb1 read "about 3 h 37 min left" while 2,000 more real requirements
    were needed and only 1,900 units were left to ask: no amount of time reaches the target."""
    doc = _doc(_pt(0, 100, 0), _pt(1, 300, 15), _pt(2, 450, 30))
    for left in (200, 349):  # 800 - 450 = 350 needed
        short = _decide(doc, left=left)
        assert short["next"] == "continue"
        assert (f"minimum out of reach in this run: 350 more real requirements needed, {left} "
                f"units left to ask") in short["line"] and "about" not in short["line"]
    for left in (350, 500):  # in reach if every unit left resolves
        assert "about" in _decide(doc, left=left)["line"]
    # nothing left (agy/codex r1 on #1377): the ask says why, and no ETA is claimed
    empty = _decide(doc, left=0)
    assert "nothing left to map" in empty["line"] and "about" not in empty["line"]


# --- req-list: the line says "minimum" as studio does, and counts read "2,174" -------------------

def test_the_line_says_minimum_and_formats_counts_with_thousands_separators():
    """studio reads "61% real requirements · minimum 80% · 2,174 placeholders"; the job title
    (this line, verbatim) read "target 80% · 2174 placeholders" beside it."""
    first = generation.point_of({"behavior_bearing": 5786, "resolved": 1362, "risk_flagged": 4397}, 0)
    last = generation.point_of({"behavior_bearing": 5786, "resolved": 3585, "risk_flagged": 2174}, 7)
    doc = {"points": [{**first, "at": 0}, {**last, "at": 7 * 15 * MIN, "took": 15 * MIN,
                                            "framed": 1500, "page_real": 1234}],
           "grant": {"page": 0, "at": 0}}
    d = _decide(doc, now_min=7 * 15, left=1100)
    line = d["line"]
    assert "minimum 80%" in line and "target" not in line, line
    assert "2,174 placeholders" in line and "2174" not in line, line
    assert "last page resolved 1,234 of 1,500 units" in line, line
    # 80% of 5,786 is 4,629 real; with 3,585 real, 1,044 are needed and 1,100 units are left: in reach
    assert "minimum out of reach" not in line
    far = _decide(doc, now_min=7 * 15, left=1043)
    assert "minimum out of reach in this run: 1,044 more real requirements needed, 1,043 units " \
           "left to ask" in far["line"], far["line"]
    # nothing left to ask: the gate asks, and its choice says "minimum" too
    ask = _decide(doc, now_min=7 * 15, left=0)
    assert ask["next"] == "ask" and "target" not in ask["line"], ask
    assert [c["label"] for c in ask["choices"]] == ["Lower the minimum to 61% for crew and build the graph"]
    assert generation.count(2174) == "2,174" and generation.count(7) == "7"


def test_a_large_budget_prints_its_counts_with_separators_too():
    """codex on #1378: WICKED_DOMAIN_MAX_PAGES=1000 / MAX_MINUTES=1440 printed "2000 minutes"."""
    pts = [_pt(0, 30, 0), _pt(1, 40, 2000)]
    d = _decide(_doc(*pts), now_min=2000, max_pages=1000, max_minutes=1440)
    assert d["next"] == "ask"
    assert "budget reached (2,000 minutes; the budget is 1,000 pages or 1,440 minutes)" in d["line"], d
    assert d["choices"][0]["label"] == "Map up to 1,000 more pages"
