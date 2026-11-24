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
    repo, seats, second, R = _run_twice(tmp_path, monkeypatch, codex_first=lambda *a, **k: ("", 1))
    assert second["reuse"]["revalidate"] == 1 and second["checked"] == 1, second
    assert seats.n > 0


def test_a_statement_that_failed_the_m_checks_is_extracted_again(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(repo, S, "READ-PARA")
    by = {"id": {t["id"]: dict(target=t["id"], file=PROG, text_sha="x", batch_files=[PROG], batch_hash="y",
                               pieces=[], not_rules=[], _statements=[dict(status="open", m_fail=["M2 x"])])}, "text": {}}
    monkeypatch.setattr(store, "prior_targets", lambda prior: by)
    monkeypatch.setattr(store, "match_prior", lambda by, t, h, used: by["id"].get(t["id"]))
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
    rows, _ = store.rows_for(repo, dict(statements=[]), [rec], [g], "h", [], store.load(repo.db), str, uncited=["a#0"])
    (row,) = [r for r in rows if r["type"] == store.GROUP]
    assert json.loads(row["value"]) == dict(group=g, rows_hash="h", uncited=["a#0"])


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
    time.sleep(1.1)
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
