"""J6 G7 (DES-C2-v2 §8): a later run applies what a person ruled, 0 real model calls.

A ruling is the row ``wicked-core domain-ruling`` writes (crates/wicked-governance/src/domain_extract.rs,
``write_ruling``): ``rule_ruling:<statement|target>:<id>`` on the subject's node, value ``{subject, id, action, by, at,
note?, statement_key?, target_hash}``. It applies on unchanged code only, and a statement ruling only to the statement
whose ``statement_key`` it names. The keys core built for the mini-cobol run are in ``fixtures/v3/statement-keys.json``.
"""
import json
import os
import sqlite3

from domain import batches, extract, model_calls, run, scope, store
from domain.followups import refusal_rows

from .test_v3_store import PROG, FakeSeats, edit, fake_write, make_repo

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "v3")
EOF_TEXT = "the read reaches the end of `PAY-FILE`"


def test_the_statement_key_is_cores_byte_for_byte():
    with open(os.path.join(FIX, "statement-keys.json"), encoding="utf-8") as fh:
        cases = json.load(fh)["statements"]
    assert len(cases) == 4
    for c in cases:
        assert store.statement_key(c["contract"]) == c["statement_key"], c["id"]
    st = cases[0]["contract"]
    swapped = json.loads(json.dumps(st))
    swapped["claims"][0]["i"], swapped["claims"][1]["i"] = 1, 0  # which claim a guard points at changed
    assert store.statement_key(swapped) != store.statement_key(st)
    moved = json.loads(json.dumps(st))
    moved["anchor"]["lines"] = [30, 39]
    moved["claims"][0]["lines"] = [f"{PROG}:34"]
    assert store.statement_key(moved) == store.statement_key(st), "moving lines keeps the key"


class RulingSeats(FakeSeats):
    """FakeSeats, plus: READ-PARA also gets a statement the checker cannot confirm (open, UNVERIFIABLE) and one that
    fails the M checks (a `when` naming an effect); MAIN-PARA gets no answer at all (an unaccounted target)."""

    def __init__(self, S):
        super().__init__(S)
        self.prompts, self.checked = [], []

    def claude(self, step, cid, prompt, timeout=1500, role=None, **kw):
        self.prompts.append((step, prompt))
        out, rc = super().claude(step, cid, prompt, timeout, role, **kw)
        if step != "extract":
            return out, rc
        j = json.loads(out)
        keep = []
        for t in j["targets"]:
            name = next(x.get("name") for x in self.S["targets"] if x["id"] == t["target"])
            if name == "MAIN-PARA":
                continue
            if name == "READ-PARA":
                t["statements"] += [
                    dict(anchor=dict(file=PROG, lines=[20, 29]), claims=[
                        dict(i=0, type="condition", text=EOF_TEXT, lines=[f"{PROG}:21-22"]),
                        dict(i=1, type="effect", text="`WS-EOF` is set to `'Y'`", when=[0], lines=[f"{PROG}:22"])]),
                    dict(anchor=dict(file=PROG, lines=[20, 29]), claims=[
                        dict(i=0, type="effect", text="`PAY-AMOUNT` is set to zero", lines=[f"{PROG}:25-26"]),
                        dict(i=1, type="effect", text="`PAY-AMOUNT` is `PAY-RATE * PAY-HOURS`", when=[0], lines=[f"{PROG}:27-28"])]),
                ]
            keep.append(t)
        return json.dumps(dict(targets=keep)), 0

    def codex(self, step, cid, prompt, timeout=1500, role=None):
        out, rc = super().codex(step, cid, prompt, timeout, role)
        if not (step.startswith("check") or step.startswith("recheck")):
            return out, rc
        self.checked.append(prompt)
        items = {json.loads(ln)["n"]: json.loads(ln) for ln in prompt.splitlines() if ln.startswith('{"n":')}
        j = json.loads(out)
        for r in j["results"]:
            if any(c.get("text") == EOF_TEXT for c in items[r["n"]]["claims"]):
                r["claims"] = [dict(i=c["i"], verdict="UNVERIFIABLE", reason="the excerpt does not show what AT END covers")
                               for c in items[r["n"]]["claims"]]
        return json.dumps(j), 0


def first_run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = RulingSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), log=lambda s: None, write=fake_write)
    seats.n, seats.prompts, seats.checked = 0, [], []
    return repo, S, seats, scope_in


def by_text(db, text):
    rules = store.load(db)[store.RULE]
    return next((k, v) for k, v in rules.items() if any(c.get("text") == text for c in v["contract"]["claims"]))


def target_row(db, name):
    return next(v for v in store.load(db)[store.TARGET].values() if v["target"].endswith(f"#{name}()."))


def rule(db, subject, ident, action, symbol, note=None, **hashes):
    """A ruling row exactly as core's ``write_ruling`` writes it."""
    v = dict(hashes, subject=subject, id=ident, action=action, by="ana", at=1795593124)
    if note:
        v["note"] = note
    fake_write(db, [dict(op="annotate", symbol=symbol, key=f"{store.RULING}:{subject}:{ident}", value=json.dumps(v),
                         type=store.RULING, author="wicked-core/domain-ruling", replace=True)])


def rerun(repo, scope_in, tmp_path, name="run2"):
    return run.run(repo.root, repo.db, scope_in, str(tmp_path / name), log=lambda s: None, write=fake_write)


def test_the_scenario_has_an_open_statement_an_m_failed_one_and_an_unaccounted_target(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    _, eof = by_text(repo.db, EOF_TEXT)
    assert (eof["status"], eof["contract"].get("status1")) == ("open", "unverifiable")
    _, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    assert bad["status"] == "open" and bad["contract"]["m_fail"]
    assert target_row(repo.db, "MAIN-PARA")["state"]["unaccounted"]
    # without a ruling the M-failed statement and the unanswered target are asked again
    second, _, _, _ = rerun(repo, scope_in, tmp_path)
    assert second["reuse"]["extract"] == 2 and seats.n > 0


def sent_to_writer(seats, target):
    return [p for st, p in seats.prompts if st == "extract" and f'"target": "{target}"' in p]


def section(prompt, banner):
    tail = prompt.split(banner, 1)[1]
    return json.JSONDecoder().raw_decode(tail[tail.index("\n["):].lstrip())[0]


def test_a_confirmed_statement_is_carried_and_never_checked_again(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    sid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    read = target_row(repo.db, "READ-PARA")
    rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    second, _, _, _ = rerun(repo, scope_in, tmp_path)
    assert second["reuse"]["extract"] == 1, second["reuse"]  # MAIN-PARA only
    assert not sent_to_writer(seats, read["target"])
    assert not any("is set to zero" in p for p in seats.checked), "a confirmed statement is never checked again"
    sid2, after = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    assert sid2 == sid and after["contract"] == bad["contract"] and after["status"] == "open"
    assert after["target_hash"] == read["target_hash"], "core keeps applying the confirm"
    assert second["confirmed"] == 1 and second["open"] == 1, second  # the EOF statement is still open


def test_a_rejected_statement_goes_back_to_the_writer_and_a_confirmed_sibling_stands(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    read = target_row(repo.db, "READ-PARA")
    bid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    rule(repo.db, "statement", bid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    # with only the confirm, READ-PARA would be carried: the reject alone sends it back
    S0 = scope.build_scope(repo, "PAYCALC1")
    C0 = batches.plan_batches(repo, S0, str(tmp_path / "b0"))
    plan = run.plan_reuse(repo, S0, C0, store.load_symbols(repo.db, store.load(repo.db)))
    assert plan[0][read["target"]] == "carry"
    eid, eof = by_text(repo.db, EOF_TEXT)
    rule(repo.db, "statement", eid, "reject", read["anchor_symbol"], note="AT END covers the FD, not the record",
         statement_key=store.statement_key(eof["contract"]), target_hash=read["target_hash"])
    lines = []
    second, _, _, _ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    sent = sent_to_writer(seats, read["target"])
    assert len(sent) == 1
    assert section(sent[0], "=== REJECTED BY A PERSON ===") == [
        dict(target=read["target"], statement=eof["statement"], note="AT END covers the FD, not the record")]
    assert section(sent[0], "=== CONFIRMED BY A PERSON ===") == [
        dict(target=read["target"], statement=bad["statement"], lines=bad["contract"]["anchor"]["lines"])]
    # the confirmed one stands under its id; the writer's new statements take other ids
    rules = store.load(repo.db)[store.RULE]
    assert rules[bid]["contract"]["claims"] == bad["contract"]["claims"]
    assert store.statement_key(rules[bid]["contract"]) == store.statement_key(bad["contract"])
    assert len([k for k in rules if k.startswith(read["target"])]) == 4, sorted(rules)  # 3 restated + the confirmed
    # the fake writer states the rejected statement again, word for word: the run says so
    assert second["rejected_again"] == [read["target"]]
    assert any(x.startswith("the writer stated a rejected statement again") for x in lines)
    assert any(x.startswith("rulings · 1 statements and 0 targets confirmed · 1 rejected") for x in lines)


def test_a_batch_no_person_ruled_on_sends_the_frozen_prompt_as_it_was(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    call = next(c for c in C["calls"] if any(t.endswith("#READ-PARA().") for t in c["targets"]))
    tby = {t["id"]: t for t in S["targets"]}
    sent = []
    monkeypatch.setattr(model_calls, "claude", lambda step, cid, p, **kw: (sent.append(p), ("{}", 0))[1])
    extract.extract_call(repo, tby, call)
    ts = [tby[x] for x in call["targets"]]
    with open(call["text_file"]) as fh:
        frozen = extract.XP.replace("{{CARD}}", extract.card_for(call, ts)).replace("{{BATCH}}", fh.read()).replace(
            "{{TARGETS}}", json.dumps([extract.tgt_json(t) for t in ts], indent=0))
    assert sent[0] == frozen
    t = next(t for t in ts if t["id"].endswith("#READ-PARA()."))
    t["rejected"] = [dict(statement="S", note="N", key="k")]
    sent.clear()
    extract.extract_call(repo, tby, call)
    assert sent[0] == frozen + extract.REJECTED + json.dumps([dict(target=t["id"], statement="S", note="N")], indent=0)


def test_a_confirmed_unaccounted_target_is_not_asked_again(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    main = target_row(repo.db, "MAIN-PARA")
    rule(repo.db, "target", main["target"], "confirm", main["anchor_symbol"], target_hash=main["target_hash"])
    second, _, _, _ = rerun(repo, scope_in, tmp_path)
    assert all(f'"target": "{main["target"]}"' not in p for st, p in seats.prompts if st == "extract")
    assert target_row(repo.db, "MAIN-PARA")["target_hash"] == main["target_hash"]


def test_a_ruling_that_no_longer_matches_is_ignored(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    sid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    read = target_row(repo.db, "READ-PARA")
    main = target_row(repo.db, "MAIN-PARA")
    rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"], statement_key="v1:" + "0" * 64,
         target_hash=read["target_hash"])
    rule(repo.db, "target", main["target"], "confirm", main["anchor_symbol"], target_hash="0" * 64)
    second, _, _, _ = rerun(repo, scope_in, tmp_path)
    assert second["reuse"]["extract"] == 2, "a ruling on another statement or other code changes nothing"
    assert second["rulings_stale"] == 0, "it never applied, so it did not stop applying"


def test_a_ruling_on_code_that_changed_stops_applying_and_the_run_says_so(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    sid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    read = target_row(repo.db, "READ-PARA")
    rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    edit(repo, PROG, lambda L: L[:23] + [L[23].replace(b"> 40", b"> 45")] + L[24:])
    lines = []
    unpinned = {k: v for k, v in scope_in.items() if k != "scope_hash"}  # the edit moved the scope's hash
    second, _, _, _ = run.run(repo.root, repo.db, unpinned, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    assert second["rulings_stale"] == 1 and second["confirmed"] == 0
    assert any("1 no longer apply" in x for x in lines)


def test_the_counts_follow_what_a_person_confirmed(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    read, main = target_row(repo.db, "READ-PARA"), target_row(repo.db, "MAIN-PARA")
    for text in (EOF_TEXT, "`PAY-AMOUNT` is set to zero"):
        sid, v = by_text(repo.db, text)
        rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"],
             statement_key=store.statement_key(v["contract"]), target_hash=read["target_hash"])
    rule(repo.db, "target", main["target"], "confirm", main["anchor_symbol"], target_hash=main["target_hash"])
    lines = []
    second, _, _, _ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    assert seats.n == 0 and second["reuse"]["extract"] == 0
    assert (second["open"], second["confirmed"], second["accounted"]) == (0, 2, second["targets"]), second
    progress = [x for x in lines if " · checked " in x]
    assert progress and all(" · 0 open · " in x for x in progress), progress
    assert sum(int(x.split(" · ")[-1].split("/")[0]) for x in progress) == second["targets"], progress


def test_a_kept_confirm_whose_target_now_cites_other_code_is_said_to_stop(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    read = target_row(repo.db, "READ-PARA")
    bid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    eid, eof = by_text(repo.db, EOF_TEXT)
    rule(repo.db, "statement", bid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    rule(repo.db, "statement", eid, "reject", read["anchor_symbol"], note="wrong",
         statement_key=store.statement_key(eof["contract"]), target_hash=read["target_hash"])
    plain = seats.claude

    def cites_the_caller(step, cid, prompt, **kw):
        out, rc = plain(step, cid, prompt, **kw)
        if step == "extract":
            j = json.loads(out)
            for t in j["targets"]:
                for st in t["statements"][:1]:
                    st["context"] = [dict(symbol="MAIN-PARA", at=f"{PROG}:17")]
            out = json.dumps(j)
        return out, rc

    monkeypatch.setattr(model_calls, "claude", cites_the_caller)
    lines = []
    second, _, _, _ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    assert target_row(repo.db, "READ-PARA")["target_hash"] != read["target_hash"]
    assert second["confirmed"] == 0 and second["rulings_stale"] >= 1, second
    assert any("confirmed no longer apply" in x for x in lines)


def test_a_new_statement_never_takes_the_id_family_of_a_kept_repaired_one(monkeypatch):
    t = dict(id="t", anchor_name="P", confirmed=[dict(id="t#0~r0", anchor=None, statement="s")])
    S = dict(targets=[t])
    C = dict(calls=[dict(id="c", targets=["t"])])
    got = dict(statements=[dict(claims=[]), dict(claims=[])], not_rules=[], fails={}, tfails=[])
    monkeypatch.setattr(extract, "extract_call", lambda repo, tby, call: (call, {"t": got}, False, []))
    monkeypatch.setattr(extract.v2lib, "use_repo", lambda repo: None)
    monkeypatch.setattr(extract.calls, "check_distinct", lambda: None)
    res = extract.extract_all(None, S, C, workers=1)
    assert [s["id"] for s in res["statements"]] == ["t#1", "t#2"]


def test_each_run_records_its_scope(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    monkeypatch.setenv("WICKED_RUN_ID", "run-42")
    rerun(repo, scope_in, tmp_path)
    monkeypatch.delenv("WICKED_RUN_ID")
    rerun(repo, scope_in, tmp_path, name="run3")
    con = sqlite3.connect(repo.db)
    rows = dict(con.execute("select key, value from annotations where type = ?", (store.RUN,)).fetchall())
    con.close()
    assert set(rows) == {f"{store.RUN}:run1", f"{store.RUN}:run-42", f"{store.RUN}:run3"}, "one record per run"
    v = json.loads(rows[f"{store.RUN}:run-42"])
    assert v["scope"] == dict(intent="PAYCALC1", description="payroll") and v["scope_hash"] == S["scope_hash"]
    assert v["run_id"] == "run-42" and isinstance(v["at"], int)
    assert store.run_row(repo, [dict(file="no/such.file")], {}, "h", "r", 0) is None


def test_the_refused_row_says_what_a_confirm_means():
    S = dict(targets=[dict(id="t", file=PROG, lines=[15, 19])])
    row = refusal_rows({"t": dict(unaccounted=True, tfails=["M7 x"])}, [], S)[0]
    assert "confirm these lines make no business decision" in row["check"] and "plumbing" not in row["check"]
