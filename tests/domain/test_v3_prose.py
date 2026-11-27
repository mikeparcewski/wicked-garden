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


# garden#1631: two lines of COACTUPC 1100-RECEIVE-MAP (app/cbl/COACTUPC.cbl:1039-1425) as render.py wrote them in the
# train-18 J6 cert's Run B (the exported statement text, cut to the names this test needs)
RECEIVE_MAP = ("Runs: 1100-RECEIVE-MAP (app/cbl/COACTUPC.cbl:1039-1425)\n"
               "- When for each of the five amount fields moved, `FUNCTION TEST-NUMVAL-C` of the `-X` field = 0, unless "
               "`ACUP-DETAILS-NOT-FETCHED`: computes the matching `-N` field (`ACUP-NEW-CREDIT-LIMIT-N`, "
               "`ACUP-NEW-CASH-CREDIT-LIMIT-N`) as `FUNCTION NUMVAL-C` of the value [1079-1080, 1093-1094]")


def test_m4_passes_a_hyphen_marked_part_that_a_cited_name_carries_as_that_part():
    # the B2-B4 withholds: the writer's family shorthand is a real part of cited names
    by = {"S1": dict(text=RECEIVE_MAP)}
    fails = lambda t: prose.sentence_fails(dict(text=t, cites=["S1"]), "detail", by)  # noqa: E731
    assert fails("the `-N` value is computed when `FUNCTION TEST-NUMVAL-C` of the `-X` field is 0") == []
    assert fails("the amounts come from the `ACUP-NEW-` fields") == []
    assert fails("the `-CREDIT-LIMIT-` fields") == []
    assert fails("`ACUP-NEW-CREDIT-LIMIT-N` and `ACUP-NEW-CASH-CREDIT-LIMIT-N`") == []


def test_m4_still_fails_a_part_no_cited_name_carries_on_its_marked_side():
    by = {"S1": dict(text=RECEIVE_MAP)}
    fails = lambda t: prose.sentence_fails(dict(text=t, cites=["S1"]), "detail", by)  # noqa: E731
    # coord (i): the marked side is a hyphen and the other side the name's end
    assert fails("the `-LIMIT` field") == ["M4 `LIMIT` is in no cited statement"]  # only -LIMIT-N ends a name
    assert fails("the `ACUP-NE-` fields") == ["M4 `ACUP-NE` is in no cited statement"]  # never ACUP-NEW-
    assert fails("the `-CREDIT-LIM-` fields") == ["M4 `CREDIT-LIM` is in no cited statement"]
    assert fails("the `NEW-CREDIT-` fields") == ["M4 `NEW-CREDIT` is in no cited statement"]  # a prefix starts a name
    by2 = {"S1": dict(text="moves `WS-ACCT-XY` and `ACUP-NEWER-ID`")}
    fails2 = lambda t: prose.sentence_fails(dict(text=t, cites=["S1"]), "detail", by2)  # noqa: E731
    assert fails2("the `-X` field") == ["M4 `X` is in no cited statement"]  # a name ending in -XY is not -X
    assert fails2("the `ACUP-NEW-` fields") == ["M4 `ACUP-NEW` is in no cited statement"]  # ACUP-NEWER is not ACUP-NEW-
    # an unmarked part is a name, and still needs the whole name
    assert fails("`ACUP-NEW` and `X`") == ["M4 `ACUP-NEW` is in no cited statement", "M4 `X` is in no cited statement"]
    assert fails("the `-Z` field") == ["M4 `Z` is in no cited statement"]
    # a quoted literal is matched as written, never as a part
    assert fails("`'-N'`") == ["M4 `'-N'` is in no cited statement"]


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


def test_what_to_check_says_one_thing_per_sentence():
    """core#1955: each part of a follow-up's "What to check" is its own sentence. A checker's reason or the repair's
    errors carry no full stop of their own, and the "Reached from" sites used to run on from them."""
    import os
    from domain import defs, followups
    defs.set_root(os.path.join(os.path.dirname(__file__), "fixtures", "v3", "mini-cobol"))
    f = "app/cbl/PAYCALC1.cbl"
    claims = [dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{f}:24"]),
              dict(i=1, type="effect", text="`PAY-AMOUNT` is set to zero", when=[0], lines=[f"{f}:25-26"])]
    base = dict(target="t1", status="open", anchor=dict(file=f, lines=[20, 29]), claims=claims)
    flagged = dict(base, id="r#3", status1="flagged", repair=dict(errors=["repair returned no statement"]),
                   check=dict(claims=[dict(i=1, verdict="OVERREACH", case="VALUE", both=True, witness="never zero")]))
    unsure = dict(base, id="r#1", status1="unverifiable",
                  check=dict(claims=[dict(i=0, verdict="UNVERIFIABLE", need="the FD of PAY-FILE",
                                          reason="the excerpt does not show what AT END covers")]))
    blank = dict(base, id="r#2", status1="unverifiable",
                 check=dict(claims=[dict(i=0, verdict="UNVERIFIABLE", need="x", reason="")]))
    checks = [r["check"] for r in followups.statement_rows([flagged, unsure, blank])]
    assert checks == [
        "Whether claim 1 holds: \"`PAY-AMOUNT` is set to zero\". The automatic repair failed its checks: repair "
        "returned no statement. Reached from 1 site: PAYCALC1.cbl:17.",
        "the excerpt does not show what AT END covers. Reached from 1 site: PAYCALC1.cbl:17.",
        "Reached from 1 site: PAYCALC1.cbl:17.",
    ]
    # With no sites (not COBOL), the reason still ends as a sentence.
    (r,) = followups.statement_rows([dict(unsure, anchor=dict(file="src/a.ts", lines=[1, 2]))])
    assert r["check"] == "the excerpt does not show what AT END covers."
