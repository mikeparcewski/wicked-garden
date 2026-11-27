"""garden#1545 (DES-1545-t18 B-min): the prose writer is told that every business sentence cites only business
statements, that a routine which only reads or writes and then handles its status is housekeeping, and that a DETAIL
mixing a business step with its mechanics is two DETAILs (garden#1607). Core makes a requirement of every statement a
shown business sentence cites (wicked-core domain_extract.rs:824-849), so these cites decide the Requirements tab.
0 real model calls (scripted writer and checker)."""
import json

from domain import model_calls, prose


def st(sid, file, lines, cond, effect, typ):
    return dict(id=sid, status="Checked", kind="rule", name="P", anchor=dict(file=file, lines=lines),
                claims=[dict(i=0, type="condition", text=cond, lines=[f"{file}:{lines[0]}"]),
                        dict(i=1, type=typ, text=effect, **({"when": [0]} if typ == "effect" else {"unless": [0]}),
                             lines=[f"{file}:{lines[1]}"])])


# S1 decides (the fallback group, as CBACT04C 1200-GET-INTEREST-RATE); S2 is the routine it performs, a re-read that
# accepts only '00' and otherwise abends (as 1200-A-GET-DEFAULT-INT-RATE, the train-17 REQ-006).
STATEMENTS = [st("r#0", "app/cbl/R.cbl", [10, 14], "`DISCGRP-STATUS = '23'`", "moves `'DEFAULT'` to `FD-DIS-ACCT-GROUP-ID`", "effect"),
              st("r#1", "app/cbl/R.cbl", [20, 30], "`DISCGRP-STATUS = '00'`", "performs `9999-ABEND-PROGRAM`", "else")]


def scripted(monkeypatch, groups, seen):
    def claude(step, cid, prompt, timeout=1500, role=None):
        seen.append((step, prompt))
        return (json.dumps({"groups": groups}), 0) if step == "prose" else (json.dumps({"repairs": []}), 0)

    def codex(step, cid, prompt, timeout=1500, role=None):
        ids = [ln[1:ln.index("]")] for ln in prompt.split("\n") if ln.startswith("[g")]
        return json.dumps({"verdicts": [{"id": i, "verdict": "SUPPORTED", "case": "SCOPE", "reason": "x"} for i in ids]}), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    monkeypatch.setattr(model_calls, "codex", codex)


def business_cites(res):
    return {c for g in res["groups"] if g["kind"] == "business"
            for s in ([g["rule"]] if g.get("rule") else []) + g["details"] for c in s["cites"]}


def test_the_writer_is_told_business_sentences_cite_only_business_statements(monkeypatch):
    seen = []
    scripted(monkeypatch, [dict(g=1, title="Rate", area="R", kind="business",
                                rule=dict(text="A missing group falls back to DEFAULT.", cites=["S1"]), details=[])], seen)
    prose.prose_all(STATEMENTS[:1], "demo")
    sent = [p for step, p in seen if step == "prose"]
    assert len(sent) == 1
    # The three rules, as the writer reads them (prompts/prose.txt, rule 1).
    assert 'Every business sentence (a business group\'s RULE, and each DETAIL of kind "business") cites only business statements.' in sent[0]
    assert "A statement whose claims only read, write or rewrite a file or record and then accept the status, display an error or abend is housekeeping" in sent[0]
    assert "Cite the statement that performs that routine instead, and leave the routine's own statement to the housekeeping group." in sent[0]
    assert "is two DETAILs: a \"business\" one with the business step, and a \"housekeeping\" one with the mechanics." in sent[0]
    # The writer's own business input stays business (prose.txt:10; coord ruling c1 on the date-range read).
    assert "or read the job's business input (for example its date range parameters)" in sent[0]


def test_a_split_mixed_detail_leaves_only_the_business_statement_cited_by_business(monkeypatch):
    # A writer following the rules: the RULE cites the deciding statement, the mixed DETAIL is split, and the routine's
    # statement is cited only by the housekeeping half. The host files that half with the area's housekeeping group
    # (prose.py:199), so no business sentence cites S2 and core makes no requirement of it.
    seen = []
    scripted(monkeypatch, [dict(g=1, title="Rate", area="R", kind="business",
                                rule=dict(text="A missing group falls back to DEFAULT.", cites=["S1"]),
                                details=[dict(text="When `DISCGRP-STATUS = '23'`, `'DEFAULT'` is moved to `FD-DIS-ACCT-GROUP-ID`.",
                                              cites=["S1"], kind="business"),
                                         dict(text="Unless `DISCGRP-STATUS = '00'`, `9999-ABEND-PROGRAM` is performed.",
                                              cites=["S2"], kind="housekeeping")])], seen)
    res = prose.prose_all(STATEMENTS, "demo")
    by = {g["g"]: g for g in res["groups"]}
    assert [d["id"] for d in by[1]["details"]] == ["g1.d1"]
    hk = [g for g in res["groups"] if g["kind"] == "housekeeping"]
    assert len(hk) == 1 and [(d["id"], d["cites"]) for d in hk[0]["details"]] == [("g1.d2", ["S2"])]
    assert business_cites(res) == {"S1"}
    assert res["uncited"] == [] and res["counts"]["moved_housekeeping"] == 1 and res["counts"].get("withheld", 0) == 0
