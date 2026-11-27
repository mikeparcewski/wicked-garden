"""garden#1545 (DES-1545-t18 B-min): the prose writer is told that every business sentence cites only business
statements, that a routine which only reads a record and handles its status is housekeeping, and that a DETAIL
mixing a business step with its mechanics is two DETAILs (garden#1607). A repair may not add to a business sentence a
statement only housekeeping sentences cite. Core makes a requirement of every statement a shown business sentence
cites (wicked-core domain_extract.rs:824-849), so these cites decide the Requirements tab.
0 real model calls (scripted writer, checker and repair)."""
import json

from domain import model_calls, prose


def st(sid, lines, claims):
    f = "app/cbl/R.cbl"
    return dict(id=sid, status="Checked", kind="rule", name="P", anchor=dict(file=f, lines=lines),
                claims=[dict(c, i=k, lines=[f"{f}:{lines[0] + k}"]) for k, c in enumerate(claims)])


# The train-17 REQ-006 shape (CBACT04C): S1 decides the fallback and performs the re-read (1200-GET-INTEREST-RATE);
# S2 is the re-read routine, a read that accepts only '00' and otherwise abends (1200-A-GET-DEFAULT-INT-RATE);
# S3 computes the interest (1300-COMPUTE-INTEREST).
STATEMENTS = [
    st("r#0", [10, 14], [dict(type="condition", text="`DISCGRP-STATUS = '23'`"),
                         dict(type="effect", text="moves `'DEFAULT'` to `FD-DIS-ACCT-GROUP-ID` and performs "
                              "`1200-A-GET-DEFAULT-INT-RATE`", when=[0])]),
    st("r#1", [20, 30], [dict(type="effect", text="reads `DISCGRP-FILE` into `DIS-GROUP-RECORD`"),
                         dict(type="condition", text="`DISCGRP-STATUS = '00'`"),
                         dict(type="else", text="performs `9999-ABEND-PROGRAM`", unless=[1])]),
    st("r#2", [40, 42], [dict(type="effect", text="computes `WS-MONTHLY-INT` as `TRAN-CAT-BAL * DIS-INT-RATE / 1200`")]),
]
FALLBACK = "When `DISCGRP-STATUS = '23'`, `'DEFAULT'` is moved to `FD-DIS-ACCT-GROUP-ID` and `1200-A-GET-DEFAULT-INT-RATE` is performed."
REREAD = "`DISCGRP-FILE` is read into `DIS-GROUP-RECORD`; unless `DISCGRP-STATUS = '00'`, `9999-ABEND-PROGRAM` is performed."
INTEREST = "`WS-MONTHLY-INT` is `TRAN-CAT-BAL * DIS-INT-RATE / 1200`."


def scripted(monkeypatch, groups, seen, flag=(), repairs=()):
    """The writer answers ``groups``; the first check flags the sentence ids in ``flag`` and supports the rest; the
    repair answers ``repairs``; the recheck supports every repaired sentence."""
    def claude(step, cid, prompt, timeout=1500, role=None):
        seen.append((step, prompt))
        if step == "prose":
            return json.dumps({"groups": groups}), 0
        return json.dumps({"repairs": list(repairs)}), 0

    def codex(step, cid, prompt, timeout=1500, role=None):
        ids = [ln[1:ln.index("]")] for ln in prompt.split("\n") if ln.startswith("[g")]
        bad = flag if step == "prose-check" else ()
        return json.dumps({"verdicts": [{"id": i, "verdict": "OVERREACH" if i in bad else "SUPPORTED", "case": "SCOPE",
                                         "reason": "x"} for i in ids]}), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    monkeypatch.setattr(model_calls, "codex", codex)


def group(n, kind, rule, details=()):
    return dict(g=n, title=f"T{n}", area="R", kind=kind, rule=dict(text=rule[0], cites=rule[1]),
                details=[dict(text=t, cites=c, kind=k) for t, c, k in details])


def business_cites(res):
    return {c for g in res["groups"] if g["kind"] == "business"
            for s in ([g["rule"]] if g.get("rule") else []) + g["details"] for c in s["cites"]}


def test_the_writer_is_told_business_sentences_cite_only_business_statements(monkeypatch):
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]))], seen)
    prose.prose_all(STATEMENTS[:1], "demo")
    sent = [p for step, p in seen if step == "prose"]
    assert len(sent) == 1
    # The rules, as the writer reads them (prompts/prose.txt, rule 1).
    assert 'Every business sentence (a business group\'s RULE, and each DETAIL of kind "business") cites only business statements.' in sent[0]
    assert ("Any other statement whose claims only read a record (a lookup or a re-read), or only write or rewrite a record "
            "whose values other statements set, and then handle its status (accept it, set a found, not-found or end-of-file "
            "flag, display an error or abend) is housekeeping") in sent[0]
    assert ("The business sentence then cites the statement that performs that routine, and says only what that statement "
            "states (for example that it performs the routine).") in sent[0]
    assert 'is two DETAILs: a "business" one with the business step, and a "housekeeping" one with the mechanics.' in sent[0]
    # The precedence: the job's business input and a statement that sets a business record's values stay business,
    # status handling and all (prose.txt:10; coord ruling c1 on the CBTRN03C date-range read).
    assert ("set the values of a business record it writes or rewrites, or read the job's business input (for example its "
            "date range parameters, together with that read's status handling)") in sent[0]


def test_a_split_mixed_detail_leaves_only_the_business_statement_cited_by_business(monkeypatch):
    # The writer's answer as the rules ask for it (this pins the host side the rules rely on; it passes on the
    # #1608 mover alone): the business half cites the performing statement, the re-read's statement is cited only
    # by the housekeeping half, and the host files that half with the area's housekeeping group (prose.py:199).
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]),
                                 [(FALLBACK, ["S1"], "business"), (REREAD, ["S2"], "housekeeping")])], seen)
    res = prose.prose_all(STATEMENTS[:2], "demo")
    by = {g["g"]: g for g in res["groups"]}
    assert [d["id"] for d in by[1]["details"]] == ["g1.d1"]
    hk = [g for g in res["groups"] if g["kind"] == "housekeeping"]
    assert len(hk) == 1 and [(d["id"], d["cites"]) for d in hk[0]["details"]] == [("g1.d2", ["S2"])]
    assert business_cites(res) == {"S1"}
    assert res["uncited"] == [] and res["counts"]["moved_housekeeping"] == 1 and res["counts"].get("withheld", 0) == 0


def test_a_repair_that_adds_a_housekeeping_only_statement_to_a_business_sentence_is_withheld(monkeypatch):
    # The repair sees neither kinds nor rule 1, so it may "fix" the fallback by citing the re-read too. S2 is cited
    # only by the housekeeping group, so the repaired business sentence is withheld rather than making S2 a
    # requirement; S2 stays cited by its housekeeping group.
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]), [(FALLBACK, ["S1"], "business")]),
                           group(2, "housekeeping", ("The rate file is read and checked.", ["S2"]), [(REREAD, ["S2"], "housekeeping")])],
             seen, flag=("g1.d1",), repairs=[{"id": "g1.d1", "text": FALLBACK, "cites": ["S1", "S2"]}])
    res = prose.prose_all(STATEMENTS[:2], "demo")
    by = {g["g"]: g for g in res["groups"]}
    assert by[1]["details"] == []
    assert [(w["id"], w["reason"], w["cites"]) for w in by[1]["withheld"]] == [
        ("g1.d1", "the repair cited S2, which only housekeeping sentences cite", ["S1", "S2"])]
    assert business_cites(res) == {"S1"}
    assert res["uncited"] == []


def every_cite(res):
    return {c for g in res["groups"] for s in ([g["rule"]] if g.get("rule") else []) + g["details"] + g["withheld"]
            for c in s["cites"]}


def test_a_guard_withheld_sentence_keeps_a_statement_whose_housekeeping_sentence_was_repaired_away(monkeypatch):
    # codex-check on cc2f9bb (W20): the business repair adds S2 while the only housekeeping sentence citing S2 is
    # repaired to cite S1. The withheld business sentence keeps the repair's cites, so S2 is still in a group
    # (garden#1549) and still no business sentence cites it (no requirement).
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]), [(FALLBACK, ["S1"], "business")]),
                           group(2, "housekeeping", ("The rate file is read and checked.", ["S2"]))],
             seen, flag=("g1.d1", "g2.r"), repairs=[{"id": "g1.d1", "text": FALLBACK, "cites": ["S1", "S2"]},
                                                     {"id": "g2.r", "text": "A missing group falls back to DEFAULT.", "cites": ["S1"]}])
    res = prose.prose_all(STATEMENTS[:2], "demo")
    by = {g["g"]: g for g in res["groups"]}
    assert by[2]["rule"]["cites"] == ["S1"]
    assert "S2" in every_cite(res)
    assert business_cites(res) == {"S1"}


def test_a_repair_may_add_a_statement_a_business_sentence_already_cites(monkeypatch):
    # S3 is business (a business RULE cites it), so a repair that adds it to the flagged DETAIL is rechecked and kept.
    seen = []
    scripted(monkeypatch, [group(1, "business", ("Interest is the balance times the rate over 1200.", ["S3"]), [(FALLBACK, ["S1"], "business")]),
                           group(2, "housekeeping", ("The rate file is read and checked.", ["S2"]), [])],
             seen, flag=("g1.d1",), repairs=[{"id": "g1.d1", "text": FALLBACK, "cites": ["S1", "S3"]}])
    res = prose.prose_all(STATEMENTS, "demo")
    by = {g["g"]: g for g in res["groups"]}
    assert [(d["id"], d["cites"], d["fate"]) for d in by[1]["details"]] == [("g1.d1", ["S1", "S3"], "repaired")]
    assert business_cites(res) == {"S1", "S3"}


def test_a_detail_the_writer_marked_housekeeping_may_be_repaired_with_any_statement(monkeypatch):
    # The guard reads the writer's kinds: a housekeeping DETAIL in a business group (filed later with housekeeping)
    # may cite the re-read in its repair; it moves, so no business sentence cites S2.
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]),
                                 [("`9999-ABEND-PROGRAM` is performed unless `DISCGRP-STATUS = '00'`.", ["S1"], "housekeeping")]),
                           group(2, "housekeeping", ("The rate file is read and checked.", ["S2"]), [])],
             seen, flag=("g1.d1",), repairs=[{"id": "g1.d1", "text": REREAD, "cites": ["S2"]}])
    res = prose.prose_all(STATEMENTS[:2], "demo")
    hk = [g for g in res["groups"] if g["kind"] == "housekeeping"]
    assert [(d["id"], d["cites"], d["fate"]) for d in hk[0]["details"]] == [("g1.d1", ["S2"], "repaired")]
    assert business_cites(res) == {"S1"}


def test_the_writer_is_told_a_clock_reply_message_assembly_and_call_order_are_housekeeping(monkeypatch):
    # garden#1616 and the Run B residual (coord option 1, 2026-11-27): the CODATE01 date reply (CODATE01.cbl:339-364),
    # COACTUPC's message assembly and first-message flag (COACTUPC.cbl:1838-1844), and COPAUS0C's call order
    # (COPAUS0C.cbl:785) were judged plumbing; the writer reads them as housekeeping examples (prompts/prose.txt, rule 1).
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]))], seen)
    prose.prose_all(STATEMENTS[:1], "demo")
    (sent,) = [p for step, p in seen if step == "prose"]
    assert ("a reply whose only content is the system date or time (a clock service: a program that only obtains the "
            "system date or time and returns it, with no other decision, input or record, has no business group)") in sent
    assert ("how a message is assembled (STRING, trimming, the field name put in front of the text) and a flag used only "
            "so that the first failure sets the message (a flag or condition that decides whether the input is accepted, "
            "or chooses between business paths, stays business, as does the message that tells the user an entered value "
            "is invalid)") in sent
    assert "control flow that only performs other paragraphs, including the order in which a routine performs others" in sent
    # the user-visible validation message stays business (prose.txt:10)
    assert "the result of validating an entered value (including the message that tells the user the value is invalid)" in sent


def test_the_writer_is_told_key_moves_report_lines_response_messages_and_commarea_copies_are_housekeeping(monkeypatch):
    # garden#1623, the train-18 J6 residual (DES-1623 option 1): the judge marked plumbing a lookup key moved before a
    # read (CBTRN02C.cbl:382-394), a report line written and counted (CBTRN03C.cbl:372), a message chosen from a CICS
    # response code (COACCT01.cbl:428-435, COTRN02C.cbl:723-748) and fields copied into the COMMAREA
    # (COACTUPC.cbl:2625-2632, :3803-3811). The writer reads them as housekeeping examples (prompts/prose.txt, rule 1).
    seen = []
    scripted(monkeypatch, [group(1, "business", ("A missing group falls back to DEFAULT.", ["S1"]))], seen)
    prose.prose_all(STATEMENTS[:1], "demo")
    (sent,) = [p for step, p in seen if step == "prose"]
    assert ("the key moved into a file's key field before a read or write, and writing a report or output line that "
            "other statements built, with its line and page counters") in sent
    assert ("including copying fetched fields into the COMMAREA to keep them as old values, and the screen-state flags "
            "that choose which view shows next") in sent
    assert ("the reply or message chosen from a CICS or file response code (normal, duplicate key, not found, any other) "
            "with the colour and field clearing that follow it") in sent
    # the old "as does the text the user reads" kept every user message business; only a validation message stays
    assert "as does the text the user reads" not in sent
    assert "the result of validating an entered value (including the message that tells the user the value is invalid)" in sent
