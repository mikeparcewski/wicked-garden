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
    return {"page": page, "pct": generation.mapped_pct(mapped, behaviours), "mapped": mapped,
            "behaviours": behaviours, "at": at_min * MIN}


def _doc(*points, grant=(0, 0)):
    return {"schema": generation.SCHEMA, "run_id": "r1", "repo": "crew", "points": list(points),
            "grant": {"page": grant[0], "at": grant[1] * MIN}}


def _decide(doc, target=80, now_min=None, max_pages=20, max_minutes=240, left=500):
    now = (now_min if now_min is not None else doc["points"][-1]["at"] // MIN) * MIN
    return generation.decide(doc, repo="crew", target=target, now=now, max_pages=max_pages,
                             max_minutes=max_minutes, left_to_map=left)


def test_below_the_target_with_budget_left_the_run_maps_the_next_page_and_says_so():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 120, 15), _pt(2, 190, 30)))
    assert d["next"] == "continue"
    # one line: the repo, the curve, the target, the next page, and an ETA from its own pace
    # (80 behaviours/page, 15 min/page: 800 - 190 = 610 → 8 pages → 2 h)
    assert d["line"] == ("Mapping crew · 3% → 12% → 19% · target 80% · "
                         "page 3 · about 2 h left")


def test_at_the_target_the_loop_is_done_and_the_line_says_how_long_it_took():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 500, 20), _pt(2, 801, 50)))
    assert d == {"next": "done", "line": "Mapped crew · 3% → 50% → 80% · "
                                         "target 80% reached · 2 pages in 50 min"}


@pytest.mark.parametrize("pages,minutes,spent", [(20, 100, "20 pages"), (5, 240, "240 minutes")])
def test_a_spent_budget_asks_map_more_or_lower_the_target(pages, minutes, spent):
    pts = [_pt(0, 30, 0)] + [_pt(i, 30 + 10 * i, minutes * i // pages) for i in range(1, pages + 1)]
    d = _decide(_doc(*pts), now_min=minutes)
    assert d["next"] == "ask" and d["recommended"] == "continue"
    assert [c["id"] for c in d["choices"]] == ["continue", "lower"]
    assert f"budget reached ({spent};" in d["line"]
    low = generation.mapped_pct(30 + 10 * pages, 1000)
    assert d["choices"][1]["label"] == f"Lower the target to {low}% for crew and build the graph"


def test_a_fresh_grant_restarts_the_budget():
    pts = [_pt(i, 30 + 10 * i, 10 * i) for i in range(0, 22)]
    assert _decide(_doc(*pts), now_min=210)["next"] == "ask"
    assert _decide(_doc(*pts, grant=(21, 210)), now_min=210)["next"] == "continue"


def test_two_pages_that_map_nothing_new_ask_instead_of_looping():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 90, 10), _pt(2, 90, 20), _pt(3, 90, 30)))
    assert d["next"] == "ask" and d["recommended"] == "lower"
    assert "the last two pages mapped nothing new" in d["line"]


def test_nothing_left_to_map_offers_only_to_lower_the_target():
    d = _decide(_doc(_pt(0, 30, 0), _pt(1, 600, 10)), left=0)
    assert d["next"] == "ask" and [c["id"] for c in d["choices"]] == ["lower"]
    assert d["line"].endswith("nothing left to map in the files the repository tracks")


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
    assert out[0].startswith("[extract-next] Mapping repo · 3% → 12% · target 80%")
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


def test_lowering_the_target_sets_the_repositorys_own_and_finishes(tmp_path, capsys):
    core = _Core(230)
    d, out, _ = _run(tmp_path, core, _env(WICKED_REPEAT_PASS=3, WICKED_REPEAT_CHOICE="lower"),
                     60, capsys)
    assert core.set_calls == [23]
    assert d["next"] == "done"
    assert "target lowered to 23% for repo" in d["line"]
    assert "(target from the repository)" in out[0]


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
                                                            ("s::helper", "s::checkout")]
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
    assert rank["s::checkout"] == 0 and rank["s::price"] < rank["s::startsWith"]
    # the collision's ten "callers" are not reached through it: each is seeded on its own later
    assert hops["s::c0"] != hops["s::startsWith"] + 1 or rank["s::c0"] > rank["s::price"]


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

    def junk(argv):
        return subprocess.CompletedProcess(argv, 0, stdout="STALENESS only\n", stderr="")
    monkeypatch.setattr(_clients, "_invoke", junk)
    with pytest.raises(RuntimeError, match="not JSON"):
        _clients._run_json(["wicked-estate", "clusters"])
