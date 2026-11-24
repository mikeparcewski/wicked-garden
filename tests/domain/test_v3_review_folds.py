"""J6 v3 review round 1 (garden#1557): one regression per fixed finding, 0 real model calls.

Fixtures: the same small estate graphs as ``test_v3_store.py`` (``fixtures/v3``), copied per test so a case can edit
the tree; seat answers in the writer's and the checker's own output shapes (``FakeSeats``).
"""
import json
import os
import sqlite3
import time

import pytest

from domain import batches, check, extract, followups, graph, model_calls, prose, run, scope, store
from tests.domain.test_v3_store import PROG, FakeSeats, edit, fake_write, make_repo, stored


# ---------------- reading the tree ----------------
def test_no_source_read_leaves_the_tree(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    secret = tmp_path / "secret.env"
    secret.write_text("a line outside the tree\n")
    os.symlink(str(secret), os.path.join(repo.root, "app", "link.env"))
    for f in ["../secret.env", str(secret), "app/link.env", "app/../../secret.env"]:
        assert graph.flines(repo, f) is None, f
        with pytest.raises(OSError):
            graph.fbytes(repo, f)
    from domain import defs
    defs.set_root(repo.root)
    assert defs.flines("../secret.env") == [] and defs.flines("app/link.env") == []
    assert graph.flines(repo, PROG)[1].strip() == "PROGRAM-ID. PAYCALC1."


def test_a_run_reads_each_file_once_so_its_hashes_are_of_what_the_models_saw(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    before = graph.fbytes(repo, PROG)
    edit(repo, PROG, lambda L: L[:23] + [L[23].replace(b"> 40", b"> 45")] + L[24:])
    assert graph.fbytes(repo, PROG) == before and "> 40" in graph.flines(repo, PROG)[23]
    assert b"> 45" in graph.fbytes(graph.Repo(repo.root, repo.db), PROG)


# ---------------- the machine checks ----------------
def _target(repo, S, name):
    return next(t for t in S["targets"] if t.get("name") == name)


def test_a_huge_model_range_is_refused_without_being_expanded(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    t = _target(repo, S, "READ-PARA")
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    out = dict(statements=[dict(anchor=dict(file=PROG, lines=[1, 10 ** 12]),
                                claims=[dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"])])],
               not_rules=[dict(lines=f"{PROG}:1-{10 ** 12}", reason="control-only")])
    t0 = time.time()
    keep, nrs, fails, tf = extract.check_target(repo, out, t, call)
    assert time.time() - t0 < 5
    assert any("not inside the target lines" in e for e in fails[0])


def test_a_statement_anchored_in_another_file_accounts_for_no_target_line(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    t = _target(repo, S, "READ-PARA")
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    out = dict(statements=[dict(anchor=dict(file="app/cpy/PAYREC.cpy", lines=t["lines"]),
                                claims=[dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"])])],
               not_rules=[])
    _, _, _, tf = extract.check_target(repo, out, t, call)
    assert any(e.startswith("M7 target lines not accounted") for e in tf), tf


@pytest.mark.parametrize("line, decision", [
    ("  return amount > limit;", True), ("  const f = (a) => a;", False), ("  let xs: Array<string> = [];", False),
    ("  /* note */ if (x) {", True), ("  /* only a note */", False)])
def test_decision_lines(tmp_path, line, decision):
    tree = tmp_path / "t"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "a.ts").write_text(f"function f() {{\n{line}\n}}\n")
    repo = graph.Repo(str(tree), str(tmp_path / "none.db"))
    assert graph.has_decision(repo, "src/a.ts", [2]) is decision


def test_a_jcl_cond_parameter_is_a_decision(tmp_path):
    tree = tmp_path / "t"
    (tree / "jcl").mkdir(parents=True)
    (tree / "jcl" / "J.jcl").write_text("//J JOB\n//S2 EXEC PGM=X,COND=(4,LT)\n")
    repo = graph.Repo(str(tree), str(tmp_path / "none.db"))
    assert graph.has_decision(repo, "jcl/J.jcl", [2])


def test_a_failed_extract_call_stops_the_run_before_anything_is_stored(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", lambda *a, **k: ("", 1))
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    with pytest.raises(model_calls.CallFailed, match="did not answer"):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r"), write=fake_write)
    assert stored(repo.db)[store.RULE] == {}


def test_a_repair_answer_replaces_only_the_targets_that_failed(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    seats = FakeSeats(S)
    t = _target(repo, S, "READ-PARA")
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    good = json.loads(seats.claude("extract", call["id"], open(call["text_file"]).read() + "".join(
        f'"target": "{x}"' for x in call["targets"]))[0])
    first = {x["target"]: x for x in good["targets"]}
    other = next(x for x in call["targets"] if x != t["id"])
    first[other] = dict(target=other, statements=[], not_rules=[])  # fails M7: nothing accounts for its lines
    repair = dict(targets=[dict(target=other, statements=[], not_rules=first[other]["not_rules"]),
                           dict(target=t["id"], statements=[], not_rules=[])])  # the passing one, answered again, empty

    def claude(step, cid, prompt, timeout=1500, role=None, **kw):
        return json.dumps(dict(targets=list(first.values())) if step == "extract" else repair), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    model_calls.configure(str(tmp_path / "calls"))
    _, tres, repaired, _ = extract.extract_call(repo, {x["id"]: x for x in S["targets"]}, call)
    assert repaired and len(tres[t["id"]]["statements"]) == 1


def test_every_file_a_check_showed_is_in_the_statements_batch(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    _, R, _, _ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r"), write=fake_write)
    st = next(s for s in R["statements"] if s["status"] == "Checked")
    assert "app/cpy/PAYREC.cpy" in st["fetched_files"] and PROG in st["fetched_files"], st["fetched_files"]


# ---------------- reuse ----------------
def _rec(t, text_sha, file="a.ts"):
    return dict(target=t, file=file, text_sha=text_sha, statements=[], _statements=[])


def test_two_identical_targets_are_never_merged_into_one():
    by = {"id": {"A": _rec("A", "h"), "B": _rec("B", "h")}, "text": {("a.ts", "h"): [_rec("A", "h"), _rec("B", "h")]}}
    assert store.match_prior(by, dict(id="A", file="a.ts"), "h", set())["target"] == "A"
    assert store.match_prior(by, dict(id="B", file="a.ts"), "h", set())["target"] == "B"
    # a target of this scope keeps its own prior record: another target with the same text never takes it
    one_a = {"id": {"A": _rec("A", "h")}, "text": {("a.ts", "h"): [_rec("A", "h")]}}
    assert store.match_prior(one_a, dict(id="C", file="a.ts"), "h", set(), {"A", "C"}) is None
    # a renamed target whose text two prior targets share: not told apart, extracted again
    assert store.match_prior(by, dict(id="C", file="a.ts"), "h", set()) is None
    one = {"id": {"A": _rec("A", "h")}, "text": {("a.ts", "h"): [_rec("A", "h")]}}
    assert store.match_prior(one, dict(id="C", file="a.ts"), "h", set())["target"] == "A"
    assert store.match_prior(one, dict(id="C", file="a.ts"), "h", {"A"}) is None


def test_moved_text_found_twice_is_not_relocated(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    L = graph.fbytes(repo, PROG).split(b"\n")
    h = store.sha(b"\n".join(L[23:28]))
    edit(repo, PROG, lambda L: L[:2] + L[23:28] + L[2:])
    again = graph.Repo(repo.root, repo.db)
    assert store.find_window(again, PROG, 24, 5, h) is None
    edit(repo, PROG, lambda L: L[:2] + L[7:])  # the copy out again
    edit(repo, PROG, lambda L: L[:2] + L[7:])  # five lines above the text out: it moved up by five
    again = graph.Repo(repo.root, repo.db)
    assert store.find_window(again, PROG, 24, 5, h) == 19


def _run_twice(tmp_path, monkeypatch, codex_first=None, change=None):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", codex_first or seats.codex)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r1"), write=fake_write)
    if change:
        edit(repo, PROG, change)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    seats.n = 0
    lines = []
    second, R, _, _ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r2"), log=lines.append,
                              write=fake_write)
    return repo, seats, second, R


def test_a_statement_left_open_by_a_failed_check_is_checked_again_on_the_same_code(tmp_path, monkeypatch):
    def incomplete(step, cid, prompt, timeout=1500, role=None):  # answers, but with no verdict on any claim
        ns = [json.loads(ln)["n"] for ln in prompt.splitlines() if ln.startswith('{"n":')]
        return json.dumps(dict(results=[dict(n=n, claims=[]) for n in ns])), 0
    repo, seats, second, R = _run_twice(tmp_path, monkeypatch, codex_first=incomplete)
    assert second["reuse"]["revalidate"] == 1 and second["checked"] == 1, second
    assert seats.n > 0


def test_a_statement_that_failed_the_m_checks_is_extracted_again(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(repo, S, "READ-PARA")
    by = {"id": {t["id"]: dict(target=t["id"], file=PROG, text_sha="x", batch_files=[PROG], batch_hash="y",
                               pieces=[], not_rules=[], _statements=[dict(status="open", m_fail=["M2 x"])])}, "text": {}}
    monkeypatch.setattr(store, "prior_targets", lambda prior: by)
    monkeypatch.setattr(store, "match_prior", lambda by, t, h, used, ids=(): by["id"].get(t["id"]))
    monkeypatch.setattr(store, "decide", lambda repo, rec: ("carry", {}))
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    decision = run.plan_reuse(repo, S, C, store.load(repo.db))[0]
    assert decision[t["id"]] == "extract"


def test_a_revalidated_targets_not_rules_move_with_its_code():
    moves = {(PROG, 20): (10, 21)}  # the 10-line piece at line 20 is now at line 21
    n = dict(lines=f"{PROG}:22-23", reason="control-only", status="accepted")
    assert run._move_not_rule(n, moves) == dict(n, lines=f"{PROG}:23-24")
    # a not-rule in no piece cannot be moved: the target is extracted again
    assert run._move_not_rule(dict(n, lines=f"{PROG}:2-3"), moves) is None


def test_records_on_a_node_the_store_dropped_are_not_live(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    sym = _target(repo, S, "READ-PARA")["anchor_symbol"]
    fake_write(repo.db, [dict(op="annotate", symbol=sym, key="business_rule:gone#0", value=json.dumps(dict(status="Checked")),
                              type=store.RULE, replace=True)])
    assert "gone#0" in store.load(repo.db)[store.RULE]
    con = sqlite3.connect(repo.db)
    con.execute("delete from nodes where json_extract(data, '$.symbol') = ?", (sym,))
    con.commit()
    con.close()
    assert "gone#0" not in store.load(repo.db)[store.RULE]


def test_a_group_whose_every_sentence_was_withheld_is_still_stored(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(repo, S, "READ-PARA")
    rec = dict(target=t["id"], file=PROG, anchor_symbol=t["anchor_symbol"], statements=[])
    g = dict(g=1, title="Overtime", area="A", kind="business", rule=None, details=[],
             withheld=[dict(id="g1.r", layer="rule", text="x", reason="OVERREACH SCOPE: y")])
    meta = dict(text_of={"a#0": "h0"}, desc="")
    rows, _ = store.rows_for(repo, dict(statements=[]), [rec], [g], meta, [], store.load(repo.db), str, uncited=["a#0"])
    (row,) = [r for r in rows if r["type"] == store.GROUP]
    assert json.loads(row["value"]) == dict(group=g, desc="", inputs={}, uncited={"a#0": "h0"})


def test_an_empty_scope_is_refused_and_retires_nothing(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r1"), write=fake_write)
    model = stored(repo.db)
    for scope_in in (dict(intent="Extract the launch posture rules"), dict(intent="NOSUCH01")):
        with pytest.raises(run.Refused, match="nothing in the code matches"):
            run.run(repo.root, repo.db, scope_in, str(tmp_path / "r2"), write=fake_write)
    assert stored(repo.db) == model


def test_a_new_run_never_reuses_an_earlier_runs_evidence_directory(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    sc = tmp_path / "scope.json"
    sc.write_text(json.dumps(dict(intent="PAYCALC1")))
    monkeypatch.setattr(store, "write", fake_write)
    monkeypatch.setattr(run, "run", lambda root, db, s, out, log=None, write=None: outs.append(out))
    outs = []
    run.main(["--db", repo.db, "--repo-root", repo.root, "--scope", str(sc)])
    run.main(["--db", repo.db, "--repo-root", repo.root, "--scope", str(sc)])
    assert len(set(outs)) == 2 and all(o.startswith(os.path.join(".wicked", "domain", "runs")) for o in outs)


def test_the_call_count_has_every_attempt_and_no_reused_call(tmp_path):
    d = tmp_path / "calls"
    d.mkdir()
    rows = [dict(note=""), dict(note="cache hit: reused the completed call"), dict(note="TIMEOUT")]
    (d / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert run.made_calls(str(d)) == 2


# ---------------- follow-ups and prose ----------------
def test_every_open_statement_has_a_follow_up():
    sts = [dict(id="m", status="open", status1=None, m_fail=["M2 anchor.lines x"], anchor=dict(file="a.ts", lines=[1, 2]), claims=[]),
           dict(id="n", status="open", status1="noresult", m_fail=[], anchor=dict(file="a.ts", lines=[3, 4]), claims=[]),
           dict(id="bad", status="open", status1=None, m_fail=["M2 no anchor"], anchor={}, claims=[])]
    rows = followups.statement_rows(sts)
    assert [r["statement"] for r in rows] == ["m", "n", "bad"]
    assert "mechanical checks: M2 anchor.lines x" in rows[0]["unknown"] and "no verdict" in rows[1]["unknown"]
    assert rows[2]["where"] is None


def test_groups_numbered_twice_are_numbered_by_the_host(monkeypatch):
    twice = {"groups": [dict(g=1, title="A", area="x", kind="business", rule=dict(text="a", cites=["S1"]), details=[]),
                        dict(g=1, title="B", area="x", kind="business", rule=dict(text="b", cites=["S1"]), details=[])]}
    monkeypatch.setattr(model_calls, "claude", lambda *a, **k: (json.dumps(twice), 0))
    rows = [dict(sid="S1", id="a#0", text="Runs: P", file="a.ts")]
    assert [g["g"] for g in prose.write_all(rows, "d")] == [1, 2]
    monkeypatch.setattr(model_calls, "claude", lambda *a, **k: ("", 1))
    with pytest.raises(model_calls.CallFailed):
        prose.write_all(rows, "d")


# ---------------- scope ----------------
def test_a_program_id_in_two_files_is_asked_about_not_picked(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    os.makedirs(os.path.join(repo.root, "old"))
    with open(os.path.join(repo.root, PROG), "rb") as a, open(os.path.join(repo.root, "old", "PAYCALC1.CBL"), "wb") as b:
        b.write(a.read())
    S = scope.build_scope(graph.Repo(repo.root, repo.db), "PAYCALC1")
    assert S["targets"] == [] and S["ambiguous_phrases"] == ["PAYCALC1"]
    assert any("is in 2 files" in q for q in S["questions"])


def test_an_upper_case_cobol_program_is_batched_as_a_cobol_unit(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = dict(target_files=["app/cbl/PAYCALC1.CBL"], targets=[], reached_from=[])
    os.makedirs(tmp_path / "b")
    plan, files = batches.cobol_plan(repo, S, [], str(tmp_path / "b"))
    assert files == {"app/cbl/PAYCALC1.CBL"}


def test_the_scope_hash_moves_when_a_target_s_bounds_move():
    S = dict(target_files=[], targets=[dict(id="t", file="a", lines=[1, 9], anchor_symbol="s")], _repo=None)
    h = scope.scope_hash(S)
    S["targets"][0]["lines"] = [1, 12]
    assert scope.scope_hash(S) != h


def test_the_tree_is_walked_in_one_order(tmp_path):
    for n in ("b", "a", "c"):
        (tmp_path / n).mkdir()
        (tmp_path / n / "z.jcl").write_text("")
        (tmp_path / n / "y.jcl").write_text("")
    assert scope.tree_files(str(tmp_path)) == sorted(scope.tree_files(str(tmp_path)))


# ---------------- review round 2 ----------------
def test_a_target_the_writer_gave_no_answer_is_extracted_again(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(repo, S, "MAIN-PARA")
    by = {"id": {t["id"]: dict(target=t["id"], file=PROG, text_sha="x", batch_files=[PROG], batch_hash="y", pieces=[],
                               not_rules=[], state=dict(unaccounted=True), _statements=[])}, "text": {}}
    monkeypatch.setattr(store, "prior_targets", lambda prior: by)
    monkeypatch.setattr(store, "match_prior", lambda by, t, h, used, ids=(): by["id"].get(t["id"]))
    monkeypatch.setattr(store, "decide", lambda repo, rec: ("carry", {}))
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    assert run.plan_reuse(repo, S, C, store.load(repo.db))[0][t["id"]] == "extract"


def test_an_open_statement_without_a_usable_anchor_is_stored_on_its_target(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(repo, S, "READ-PARA")
    rec = dict(target=t["id"], file=PROG, anchor_symbol=t["anchor_symbol"], statements=["x#0", "x#1"], batch_hash="b",
               target_hash="t")
    sts = [dict(id="x#0", status="open", anchor={}, claims=[]), dict(id="x#1", status="open", anchor=dict(file=PROG, lines=[1]))]
    rows, unplaced = store.rows_for(repo, dict(statements=sts), [rec], [], "h", [], store.load(repo.db),
                                    lambda s: 1 / 0)
    got = [r for r in rows if r["type"] == store.RULE]
    assert unplaced == [] and [r["symbol"] for r in got] == [t["anchor_symbol"]] * 2
    assert all("could not be rendered" in json.loads(r["value"])["statement"] for r in got)


def test_a_model_range_in_a_stored_citation_is_not_expanded():
    st = dict(claims=[dict(lines=[f"{PROG}:1-{10 ** 12}", f"{PROG}:3-4"], guards="not a list")])
    t0 = time.time()
    assert store.cited(st) == {(PROG, 1), (PROG, 3), (PROG, 4)} and time.time() - t0 < 1


def test_group_numbers_never_collide_across_writer_packs(monkeypatch):
    answers = iter([{"groups": [dict(g=1, title="A", area="x", kind="business", rule=dict(text="a", cites=["S1"]), details=[])]},
                    {"groups": [dict(g=0, title="B", area="x", kind="business", rule=dict(text="b", cites=["S2"]), details=[])]}])
    monkeypatch.setattr(model_calls, "claude", lambda *a, **k: (json.dumps(next(answers)), 0))
    monkeypatch.setattr(prose, "PER_WRITE", 1)
    rows = [dict(sid="S1", id="a#0", text="Runs: P", file="a.ts"), dict(sid="S2", id="b#0", text="Runs: Q", file="b.ts")]
    assert [g["g"] for g in prose.write_all(rows, "d")] == [1, 2]


def test_an_empty_writer_answer_is_no_answer(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    monkeypatch.setattr(model_calls, "claude", lambda *a, **k: ("  \n", 0))
    with pytest.raises(model_calls.CallFailed):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r"), write=fake_write)


def test_a_checker_that_answers_no_call_stops_the_run_before_anything_is_stored(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r1"), write=fake_write)
    model = stored(repo.db)
    edit(repo, PROG, lambda L: L[:24] + [L[24].replace(b"PAY-RATE * 40", b"PAY-RATE * 41")] + L[25:])
    monkeypatch.setattr(model_calls, "codex", lambda *a, **k: ("", 4))
    with pytest.raises(model_calls.CallFailed, match="checker answered none"):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r2"), write=fake_write)
    assert stored(repo.db) == model


def test_the_cobol_lookup_reads_the_runs_snapshot(tmp_path):
    from domain import defs, lookup
    repo = make_repo(tmp_path, "mini-cobol")
    lookup.use_repo(repo)
    first = list(defs.flines(PROG))
    edit(repo, PROG, lambda L: L[:23] + [L[23].replace(b"> 40", b"> 45")] + L[24:])
    defs._fl.clear()
    assert defs.flines(PROG) == first
    lookup.use_repo(graph.Repo(repo.root, repo.db))  # a new run on the same tree starts clean
    assert "> 45" in defs.flines(PROG)[23]


def test_every_file_an_r_prompt_showed_is_in_each_of_its_statements_batch(tmp_path, monkeypatch):
    from domain import r_stage
    repo = make_repo(tmp_path, "mini-cobol")
    sts = [dict(id=f"s{k}", anchor=dict(file=PROG, lines=[20, 29]), claims=[]) for k in (1, 2)]
    monkeypatch.setattr(check.v2lib, "want", lambda repo, s, extra=None: {f"app/cpy/{s['id']}.cpy": {1}})
    monkeypatch.setattr(check.v2lib, "render_code", lambda repo, w: "")
    monkeypatch.setattr(check, "facts", lambda f: "")
    monkeypatch.setattr(r_stage, "flagged_claims", lambda r: [dict(i=0, case="SCOPE")])
    monkeypatch.setattr(r_stage, "run_calls", lambda step, units, per=4: {})
    monkeypatch.setattr(r_stage, "decide", lambda u, res: [])
    check.v2lib.use_repo(repo)
    shown = {}
    check.r_round(repo, "t", sts, dict(raw={"1": {}, "2": {}}), {"s1": "1", "s2": "2"}, {}, shown=shown)
    want = {PROG, "app/cpy/s1.cpy", "app/cpy/s2.cpy", "app/cpy/PAYREC.cpy"}
    assert shown == {"s1": want, "s2": want}


def test_a_typed_path_settles_a_program_id_in_two_files(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    os.makedirs(os.path.join(repo.root, "old"))
    with open(os.path.join(repo.root, PROG), "rb") as a, open(os.path.join(repo.root, "old", "PAYCALC1.CBL"), "wb") as b:
        b.write(a.read())
    S = scope.build_scope(graph.Repo(repo.root, repo.db), f"rules of {PROG}")
    assert S["targets"] and S["ambiguous_phrases"] == [] and PROG in S["target_files"]


def test_the_prose_is_written_again_when_the_scope_description_changes_never_the_folder_name(monkeypatch):
    from tests.domain.test_v3_prose import STATEMENTS
    rows = prose.rows_of(STATEMENTS)
    text_of = {r["id"]: store.sha(r["text"].encode()) for r in rows}
    seen = []
    monkeypatch.setattr(prose, "prose_all", lambda sts, desc, start=0: seen.append(desc) or dict(rows=[], groups=[], uncited=[], counts={}))
    g = dict(g=1, rule=dict(id="g1.r", cites=sorted(text_of)), details=[], withheld=[])
    prior = {store.GROUP: {"x": dict(group=g, desc="", inputs=dict(text_of), uncited={})}}
    # no description: the writer is told the folder's name, which is not part of the reuse key
    assert run.prose_for(STATEMENTS, "checkout-a", "", prior)[2] is True
    assert run.prose_for(STATEMENTS, "checkout-b", "", prior)[2] is True and seen == []
    assert run.prose_for(STATEMENTS, "billing", "billing", prior)[2] is False and seen == ["billing"]


def test_two_runs_in_one_second_get_two_evidence_directories(tmp_path, monkeypatch):
    sc = tmp_path / "scope.json"
    sc.write_text(json.dumps(dict(intent="PAYCALC1")))
    outs = []
    monkeypatch.setattr(run, "run", lambda root, db, s, out, log=None, write=None: outs.append(out))
    monkeypatch.setattr(time, "strftime", lambda fmt, t=None: "20260101T000000Z")
    for _ in range(2):
        run.main(["--db", "x.db", "--repo-root", str(tmp_path), "--scope", str(sc)])
    assert len(set(outs)) == 2


def test_two_scoped_programs_with_one_file_name_get_two_batches(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    os.makedirs(tmp_path / "b")
    S = dict(target_files=["a/X.cbl", "b/X.cbl"], targets=[], reached_from=[])
    plan, _ = batches.cobol_plan(repo, S, [], str(tmp_path / "b"))
    assert plan == []  # no targets, but the batch texts are two files
    names = sorted(os.listdir(tmp_path / "b"))
    assert len(names) == 2 and all(n.startswith("X.cbl-") and n.endswith(".txt") for n in names), names
    # paths that flatten alike still get two names
    os.makedirs(tmp_path / "c")
    batches.cobol_plan(repo, dict(target_files=["a/b/X.cbl", "a_b/X.cbl"], targets=[], reached_from=[]), [], str(tmp_path / "c"))
    assert len(os.listdir(tmp_path / "c")) == 2


@pytest.mark.parametrize("claim", [dict(i=[0], type="condition", text="x", lines=[f"{PROG}:24"]),
                                   dict(i=0, type="condition", text="x", lines=f"{PROG}:24"),
                                   dict(i=0, type="effect", text=7, when=[[0]], lines=[f"{PROG}:24"]),
                                   dict(i=0, type="condition", text=7, lines=[f"{PROG}:24"]),
                                   dict(i=0, type="effect", text="x", when=0, lines=[f"{PROG}:24"]),
                                   dict(i=0, type="effect", text="x", when=[True], lines=[f"{PROG}:24"])])
def test_a_malformed_claim_is_refused_not_raised(tmp_path, claim):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    t = _target(repo, S, "READ-PARA")
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    errs = extract.check_statement(repo, dict(anchor=dict(file=PROG, lines=t["lines"]), claims=[claim]), t, call)
    assert errs and all(e.startswith(("M1", "M2", "M4")) for e in errs), errs


# ---------------- review round 3 ----------------
def test_a_model_answer_s_nulls_and_stray_elements_are_shaped_before_any_reader():
    j = model_calls.parse_json('{"targets": null, "results": [1, {"n": 1, "claims": null}], "x": [1]}')
    assert j == {"targets": [], "results": [{"n": 1, "claims": []}], "x": [1]}
    assert model_calls.parse_json("[1, 2]") is None


@pytest.mark.parametrize("anchor", [None, "app/cbl/PAYCALC1.cbl", [20, 29]])
def test_a_statement_with_a_malformed_anchor_or_context_is_refused(tmp_path, anchor):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    t = _target(repo, S, "READ-PARA")
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    st = dict(anchor=anchor, context=5, claims=[dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"])])
    keep, _, fails, _ = extract.check_target(repo, dict(statements=[st], not_rules=[]), t, call)
    assert any(e.startswith("M2 anchor") for e in fails[0]) and any(e.startswith("M1 context") for e in fails[0])


def test_a_full_typed_path_is_matched_exactly(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    os.makedirs(os.path.join(repo.root, "archive", "app", "cbl"))
    with open(os.path.join(repo.root, PROG), "rb") as a, open(os.path.join(repo.root, "archive", PROG), "wb") as b:
        b.write(a.read())
    S = scope.build_scope(graph.Repo(repo.root, repo.db), f"rules of archive/{PROG}")
    assert f"archive/{PROG}" in S["target_files"] and PROG not in S["target_files"]


def test_an_oversized_citation_makes_its_whole_file_one_piece(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(repo, S, "READ-PARA")
    st = dict(claims=[dict(lines=[f"{PROG}:1-{10 ** 12}"])])
    n = len(graph.flines(repo, PROG))
    ps = store.pieces(repo, t, [st], store._unit_spans(repo), S["targets"])
    assert any(p[:3] == [PROG, 1, n] for p in ps), ps


def test_an_r_prompt_s_copybooks_are_in_its_statements_batch(tmp_path, monkeypatch):
    from domain import r_stage
    repo = make_repo(tmp_path, "mini-cobol")
    sts = [dict(id="s1", anchor=dict(file=PROG, lines=[20, 29]), claims=[])]
    monkeypatch.setattr(check.v2lib, "want", lambda repo, s, extra=None: {PROG: {1}})
    monkeypatch.setattr(check.v2lib, "render_code", lambda repo, w: "")
    monkeypatch.setattr(check, "facts", lambda f: "")
    monkeypatch.setattr(r_stage, "flagged_claims", lambda r: [dict(i=0, case="SCOPE")])
    monkeypatch.setattr(r_stage, "run_calls", lambda step, units, per=4: {})
    monkeypatch.setattr(r_stage, "decide", lambda u, res: [])
    check.v2lib.use_repo(repo)
    shown = {}
    check.r_round(repo, "t", sts, dict(raw={"1": {}}), {"s1": "1"}, {}, shown=shown)
    assert "app/cpy/PAYREC.cpy" in shown["s1"]


# ---------------- coord round 2 ----------------
def _supported(prompt):
    res = []
    for ln in prompt.splitlines():
        if ln.startswith('{"n":'):
            it = json.loads(ln)
            res.append(dict(n=it["n"], claims=[dict(i=c["i"], verdict="SUPPORTED") for c in it["claims"]]))
    return json.dumps(dict(results=res))


def test_a_statement_is_checked_only_when_both_passes_answered_it(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    st = lambda k: dict(id=f"s{k:02d}", anchor=dict(file=PROG, lines=[23, 28]), claims=[
        dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"])])
    sts = [st(k) for k in range(11)]  # two chunks of the C6 round: s00..s09, then s10

    def codex(step, cid, prompt, timeout=1500, role=None):
        if step == "t-a" and cid == "c1":
            return "", 1  # pass a's second chunk fails; pass b answers it
        return _supported(prompt), 0
    monkeypatch.setattr(model_calls, "codex", codex)
    model_calls.configure(str(tmp_path / "calls"))
    _, _, _, status, _, _ = check.check3(repo, str(tmp_path), "t", sts, fetch=False)
    assert status["s10"] == "noresult"
    assert all(status[f"s{k:02d}"] == "Checked" for k in range(10)), status


def test_a_ruling_keys_on_what_a_statement_says_never_its_position_or_lines():
    a = dict(id="t#0", anchor=dict(file=PROG, lines=[23, 28]), claims=[dict(i=0, type="condition", text="`X > 40`", lines=["p:24"])])
    moved = dict(a, id="t#3", anchor=dict(file=PROG, lines=[40, 45]), claims=[dict(a["claims"][0], lines=["p:41"])])
    other = dict(a, claims=[dict(a["claims"][0], text="`X > 45`")])
    assert store.content_hash(a) == store.content_hash(moved) != store.content_hash(other)


def test_every_stored_rule_row_carries_its_content_hash(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    _, R, _, _ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r"), write=fake_write)
    rules = stored(repo.db)[store.RULE]
    by = {s["id"]: s for s in R["statements"]}
    assert rules and all(v["content_hash"] == store.content_hash(by[k]) for k, v in rules.items())


def test_only_the_groups_whose_statements_changed_are_written_again(monkeypatch):
    from tests.domain.test_v3_prose import STATEMENTS
    text_of = {r["id"]: store.sha(r["text"].encode()) for r in prose.rows_of(STATEMENTS)}
    g1 = dict(g=1, title="A", kind="business", rule=dict(id="g1.r", text="a", cites=["a#0"]), details=[], withheld=[])
    g2 = dict(g=2, title="B", kind="business", rule=dict(id="g2.r", text="b", cites=["b#0"]), details=[], withheld=[])
    prior = {store.GROUP: {"x": dict(group=g1, desc="", inputs={"a#0": text_of["a#0"]}, uncited={}),
                           "y": dict(group=g2, desc="", inputs={"b#0": "stale"}, uncited={})}}
    asked = []

    def prose_all(sts, desc, start=0):
        asked.append(([s["id"] for s in sts], start))
        rows = prose.rows_of(sts)
        return dict(rows=rows, groups=[dict(g=start + 1, title="B2", kind="business", rule=dict(id="x", text="b2", cites=["S1"]),
                                            details=[], withheld=[])], uncited=[], counts={})
    monkeypatch.setattr(prose, "prose_all", prose_all)
    groups, meta, whole, _, uncited = run.prose_for(STATEMENTS, "repo", "", prior)
    assert asked == [(["b#0"], 1)] and whole is False and uncited == []
    assert [g["g"] for g in groups] == [1, 2] and groups[0] is g1 and groups[1]["rule"]["cites"] == ["b#0"]
    assert meta == dict(text_of=text_of, desc="")


def _prose_seats(monkeypatch, answers):
    sent = []

    def claude(step, cid, prompt, timeout=1500, role=None, **kw):
        sent.append((step, prompt))
        return json.dumps(answers[step]), 0

    def codex(step, cid, prompt, timeout=1500, role=None):
        sent.append((step, prompt))
        return json.dumps(dict(verdicts=[dict(id=i, verdict="SUPPORTED") for i in __import__("re").findall(r"^\[(g\d+\.\w+)\]", prompt, 8)])), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    monkeypatch.setattr(model_calls, "codex", codex)
    return sent


def test_a_malformed_group_is_withheld_with_its_reason_and_its_statements_are_written_again(monkeypatch):
    from tests.domain.test_v3_prose import STATEMENTS
    bad = dict(g=1, title="Overtime", kind="rules", rule=dict(text="Hours over 40 are overtime.", cites=["S1"]), details=[])
    good = dict(g=1, title="Overtime", kind="business", rule=dict(text="Hours over 40 are overtime.", cites=["S1", "S2"]), details=[])
    sent = _prose_seats(monkeypatch, {"prose": dict(groups=[bad]), "prose-left": dict(groups=[good])})
    res = prose.prose_all(STATEMENTS, "COBOL/JCL Demo")
    assert [s for s, _ in sent] == ["prose", "prose-left", "prose-check"]
    (w, ok) = res["groups"]
    assert w["g"] == 1 and w["rule"] is None and w["withheld"] == [
        dict(id="g1", layer="group", text="", reason="M1 shape: kind 'rules' is not business or housekeeping", cites=["S1"])]
    assert ok["g"] == 2 and ok["rule"]["cites"] == ["S1", "S2"] and ok["rule"]["verdict"] == "SUPPORTED"
    assert res["uncited"] == []


def test_a_statement_the_writer_left_out_goes_to_the_writer_once_more(monkeypatch):
    from tests.domain.test_v3_prose import STATEMENTS
    one = dict(g=1, title="Overtime", kind="business", rule=dict(text="Hours over 40 are overtime.", cites=["S1"]), details=[])
    two = dict(g=1, title="Council", kind="business", rule=dict(text="A council size is checked.", cites=["S2"]), details=[])
    sent = _prose_seats(monkeypatch, {"prose": dict(groups=[one]), "prose-left": dict(groups=[two])})
    res = prose.prose_all(STATEMENTS, "COBOL/JCL Demo")
    left = next(p for s, p in sent if s == "prose-left")
    assert "[S2]" in left and "[S1]" not in left
    assert [g["g"] for g in res["groups"]] == [1, 2] and res["uncited"] == []
