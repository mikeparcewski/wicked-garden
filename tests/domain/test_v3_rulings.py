"""J6 G7 (DES-C2-v2 §8): a later run applies what a person ruled, 0 real model calls.

A ruling is the row ``wicked-core domain-ruling`` writes (crates/wicked-governance/src/domain_extract.rs,
``write_ruling``): ``rule_ruling:<statement|target>:<id>`` on the subject's node, value ``{subject, id, action, by, at,
note?, statement_key?, target_hash}``. It applies on unchanged code only, and a statement ruling only to the statement
whose ``statement_key`` it names. The keys core built for the mini-cobol run are in ``fixtures/v3/statement-keys.json``.
"""
import json
import os

from domain import extract, model_calls, run, scope, store
from domain.followups import refusal_rows

from .test_v3_store import PROG, FakeSeats, fake_write, make_repo

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
        self.prompts = []

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
    seats.n, seats.prompts = 0, []
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


def test_a_confirmed_statement_is_carried_and_never_checked_again(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    sid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    read = target_row(repo.db, "READ-PARA")
    rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    second, _, _, _ = rerun(repo, scope_in, tmp_path)
    assert second["reuse"]["extract"] == 1, second["reuse"]  # MAIN-PARA only
    assert all(f'"target": "{read["target"]}"' not in p for st, p in seats.prompts if st == "extract")
    sid2, after = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    assert sid2 == sid and store.statement_key(after["contract"]) == store.statement_key(bad["contract"])
    assert after["target_hash"] == read["target_hash"], "core keeps applying the confirm"


def test_a_rejected_statement_sends_its_target_back_to_the_writer_with_the_note(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    sid, eof = by_text(repo.db, EOF_TEXT)
    read = target_row(repo.db, "READ-PARA")
    rule(repo.db, "statement", sid, "reject", read["anchor_symbol"], note="AT END covers the FD, not the record",
         statement_key=store.statement_key(eof["contract"]), target_hash=read["target_hash"])
    rerun(repo, scope_in, tmp_path)
    sent = [p for st, p in seats.prompts if st == "extract" and f'"target": "{read["target"]}"' in p]
    assert len(sent) == 1
    tail = sent[0].split("=== REJECTED BY A PERSON ===", 1)[1]
    assert json.loads(tail[tail.index("["):]) == [dict(target=read["target"], statement=eof["statement"],
                                                       note="AT END covers the FD, not the record")]


def test_a_batch_with_no_reject_sends_the_frozen_prompt_unchanged(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    rerun(repo, scope_in, tmp_path)
    assert seats.prompts and not any(extract.REJECTED.strip() in p for _, p in seats.prompts)


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


def test_each_run_records_its_scope(tmp_path, monkeypatch):
    repo, S, seats, scope_in = first_run(tmp_path, monkeypatch)
    monkeypatch.setenv("WICKED_RUN_ID", "run-42")
    rerun(repo, scope_in, tmp_path)
    import sqlite3
    con = sqlite3.connect(repo.db)
    rows = con.execute("select key, value from annotations where type = ?", (store.RUN,)).fetchall()
    con.close()
    assert [k for k, _ in rows] == [f"{store.RUN}:{S['scope_hash']}"], "one row per scope, replaced by each run"
    v = json.loads(rows[0][1])
    assert v["scope"] == dict(intent="PAYCALC1", description="payroll") and v["scope_hash"] == S["scope_hash"]
    assert v["run_id"] == "run-42" and isinstance(v["at"], int)


def test_the_refused_row_says_what_a_confirm_means():
    S = dict(targets=[dict(id="t", file=PROG, lines=[15, 19])])
    row = refusal_rows({"t": dict(unaccounted=True, tfails=["M7 x"])}, [], S)[0]
    assert "confirm these lines make no business decision" in row["check"] and "plumbing" not in row["check"]
