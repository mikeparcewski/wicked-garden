"""J6 v3 business prose and follow-ups (DES-j6-build §5, §7), 0 real model calls.

The statements are in the checker's own shape (``check.check_all``'s ``statements``), rendered by the frozen
renderer. The port reproduces the prose calibration's writer and prose-check prompts byte for byte and its M4 and
check counts (CardDemo 72 statements: 11 M4 DETAILs, 15 flagged; crew 68: 1 and 21); that replay is a lane check,
since the recorded runs are not in this repository.
"""
import json

from domain import model_calls, prose


def st(sid, file, lines, text, status="Checked"):
    return dict(id=sid, status=status, kind="rule", name="P", anchor=dict(file=file, lines=lines),
                claims=[dict(i=0, type="condition", text=text, lines=[f"{file}:{lines[0]}"]),
                        dict(i=1, type="effect", text="move `'Y'` to `WS-DONE`", when=[0], lines=[f"{file}:{lines[1]}"])])


STATEMENTS = [st("a#0", "app/cbl/A.cbl", [10, 12], "`PAY-HOURS > 40`"),
              st("b#0", "app/cbl/B.cbl", [5, 6], "`isCouncilSize(v)` holds"),
              st("c#0", "app/cbl/B.cbl", [8, 9], "never shown", status="open")]


def test_only_checked_rule_statements_are_prosed_in_file_order():
    rows = prose.rows_of(STATEMENTS)
    assert [(r["sid"], r["id"]) for r in rows] == [("S1", "a#0"), ("S2", "b#0")]
    assert rows[0]["text"].startswith("Runs: P (app/cbl/A.cbl:10-12)")


def test_the_m4_token_rule_and_the_m5_rule():
    rows = prose.rows_of(STATEMENTS)
    by = {r["sid"]: r for r in rows}
    ok = dict(text="`isCouncilSize(v)` and `WS-DONE`", cites=["S2"])
    assert prose.sentence_fails(ok, "detail", by) == []
    cobol = dict(text="`9999-ABEND` runs", cites=["S1"])
    assert prose.sentence_fails(cobol, "detail", by) == ["M4 `9999-ABEND` is in no cited statement"]
    assert prose.sentence_fails(dict(text="`PAY-HOURS` over 40", cites=["S1"]), "rule", by)[0].startswith("M5")
    assert prose.sentence_fails(dict(text="x", cites=["S9"]), "detail", by)[0].startswith("M2")


def test_the_writer_packs_whole_files_up_to_its_cap(monkeypatch):
    monkeypatch.setattr(prose, "PER_WRITE", 1)
    rows = prose.rows_of(STATEMENTS)
    assert [[r["sid"] for r in p] for p in prose.packs(rows)] == [["S1"], ["S2"]]


def test_a_sentence_that_fails_after_its_one_repair_is_withheld_with_its_reason(monkeypatch):
    writes = {"groups": [{"g": 1, "title": "Overtime", "area": "A", "kind": "business",
                          "rule": {"text": "Hours over 40 are overtime.", "cites": ["S1"]},
                          "details": [{"text": "`isCouncilSize(v)` holds", "cites": ["S2"]},
                                      {"text": "`9999-ABEND` runs", "cites": ["S1"]}]}]}
    sent = []

    def claude(step, cid, prompt, timeout=1500, role=None):
        sent.append((step, cid, prompt))
        if step == "prose":
            return json.dumps(writes), 0
        return json.dumps({"repairs": [{"id": "g1.r", "text": "WITHHOLD", "cites": ["S1"]},
                                       {"id": "g1.d2", "text": "`WS-DONE` is set", "cites": ["S1"]}]}), 0

    def codex(step, cid, prompt, timeout=1500, role=None):
        sent.append((step, cid, prompt))
        if step == "prose-check":
            return json.dumps({"verdicts": [{"id": "g1.r", "verdict": "OVERREACH", "case": "SCOPE", "reason": "drops a test"},
                                            {"id": "g1.d1", "verdict": "SUPPORTED"}, {"id": "g1.d2", "verdict": "SUPPORTED"}]}), 0
        return json.dumps({"verdicts": [{"id": "g1.d2", "verdict": "SUPPORTED"}]}), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    monkeypatch.setattr(model_calls, "codex", codex)
    res = prose.prose_all(STATEMENTS, "COBOL/JCL Demo")
    assert [(s, c) for s, c, _ in sent] == [("prose", "w0"), ("prose-check", "c0"), ("prose-repair", "r0"), ("prose-recheck", "c0")]
    # the repair is told both objections: the checker's and the mechanical one
    assert "OVERREACH SCOPE: drops a test" in sent[2][2] and "M4 `9999-ABEND`" in sent[2][2]
    (g,) = res["groups"]
    assert g["rule"] is None
    assert g["withheld"] == [dict(id="g1.r", layer="rule", text="Hours over 40 are overtime.", reason="OVERREACH SCOPE: drops a test",
                                 cites=["S1"])]
    assert [(d["id"], d["fate"], d["text"]) for d in g["details"]] == [("g1.d1", "as written", "`isCouncilSize(v)` holds"),
                                                                        ("g1.d2", "repaired", "`WS-DONE` is set")]
    assert res["counts"]["m_failed"] == 1 and res["counts"]["check_flagged"] == 1


def test_a_follow_up_names_where_what_is_unknown_and_the_sites_to_check():
    import os
    from domain import defs, followups
    defs.set_root(os.path.join(os.path.dirname(__file__), "fixtures", "v3", "mini-cobol"))
    f = "app/cbl/PAYCALC1.cbl"
    open_st = dict(id="r#0", target="t1", status="open", status1="unverifiable", anchor=dict(file=f, lines=[20, 29]),
                   claims=[dict(i=0, type="trigger", text="performed until end of file", lines=[f"{f}:17"])],
                   check=dict(claims=[dict(i=0, verdict="UNVERIFIABLE", need="the loop's end", reason="the excerpt stops early")]))
    rows = followups.statement_rows([open_st, dict(open_st, id="ok", status="Checked")])
    (r,) = rows
    assert r["kind"] == "open" and r["where"] == dict(file=f, lines=[20, 29])
    assert "the checker needs: the loop's end" in r["unknown"]
    assert r["sites"] == [17] and r["check"].endswith("Reached from 1 site: PAYCALC1.cbl:17.")
