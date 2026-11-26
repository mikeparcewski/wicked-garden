"""garden#1548 (DES-1548): record updates are statements, a statement's concerns are checked and raised as follow-ups,
and a statement names the copybook its fields come from.

Fixtures: mini-cobol (``fixtures/v3``, the estate graph ``wicked-estate index`` wrote), its targets from
``scope.build_scope`` and its batches from ``batches.plan_batches``, as a run makes them. A case that needs a record
update rewrites one line of the tree copy in place, so every line number and target the graph holds still applies.
"""
import json
import os
import time

from domain import batches, check, extract, followups, graph, lookup, model_calls, run, scope, store
from tests.domain.test_v3_store import PROG, FakeSeats, edit, fake_write, make_repo, stored

WRITE_18 = b"           WRITE PAY-LINE"  # MAIN-PARA's CLOSE (line 18) becomes a record update
WRITE_28 = b"           WRITE PAY-LINE FROM PAY-RECORD"  # READ-PARA's ELSE (line 28) becomes one


def _at(n, text):
    def fn(L):
        L[n - 1] = text
        return L
    return fn


def _target(S, name):
    return next(t for t in S["targets"] if t.get("name") == name)


def _call(repo, S, t, tmp_path):
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    return next(c for c in C["calls"] if t["id"] in c["targets"])


# ---------------- 1. record updates ----------------
def test_a_record_update_is_a_write_on_the_line_or_a_perform_of_a_paragraph_that_writes(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    edit(repo, PROG, _at(28, WRITE_28))
    edit(repo, PROG, _at(16, b"           DISPLAY 'WRITE PAY-LINE'"))  # a literal is not an update
    # 17 PERFORMs READ-PARA, which writes at 28; 16's WRITE is inside a literal; 18's CLOSE is not an update
    assert graph.updates_records(repo, PROG, range(15, 30)) == [17, 28]
    assert graph.updates_records(repo, "app/cpy/PAYREC.cpy", range(1, 6)) == []


def test_unchanged_code_has_no_record_update(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    assert graph.updates_records(repo, PROG, range(1, 30)) == []


def test_a_not_rule_over_a_record_update_is_refused(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    edit(repo, PROG, _at(18, WRITE_18))
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(S, "MAIN-PARA")
    out = dict(statements=[], not_rules=[dict(lines=f"{PROG}:18-18", reason="io-wrapper", note="writes the line")])
    _, nrs, _, tf = extract.check_target(repo, out, t, _call(repo, S, t, tmp_path))
    assert nrs[0]["refused"]
    assert any(e.startswith(f"M7 not_rule {PROG}:18-18 updates a record on line(s) [18]") for e in tf), tf


def test_a_not_rule_over_a_close_is_not_refused_as_an_update(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(S, "MAIN-PARA")
    out = dict(statements=[], not_rules=[dict(lines=f"{PROG}:18-18", reason="io-wrapper", note="closes the file")])
    _, nrs, _, tf = extract.check_target(repo, out, t, _call(repo, S, t, tmp_path))
    assert not nrs[0].get("refused") and not any("updates a record" in e for e in tf), tf


def test_an_effect_only_statement_of_a_write_stays_a_statement(tmp_path):
    """Without the record-update branch of ``is_rule`` this statement is derived into a control-only not-rule, which
    the M7 record-update check then refuses: the target could never be accounted."""
    repo = make_repo(tmp_path, "mini-cobol")
    edit(repo, PROG, _at(18, WRITE_18))
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(S, "MAIN-PARA")
    st = dict(anchor=dict(file=PROG, lines=[18, 18]), claims=[dict(i=0, type="effect", text="writes `PAY-LINE`", lines=[f"{PROG}:18"])])
    keep, nrs, fails, tf = extract.check_target(repo, dict(statements=[st], not_rules=[]), t, _call(repo, S, t, tmp_path))
    assert len(keep) == 1 and not fails, fails
    assert not any(n.get("derived") for n in nrs)
    assert not any("updates a record" in e for e in tf), tf


def test_an_effect_only_statement_with_no_update_is_still_derived_a_not_rule(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(S, "MAIN-PARA")
    st = dict(anchor=dict(file=PROG, lines=[18, 18]), claims=[dict(i=0, type="effect", text="closes `PAY-FILE`", lines=[f"{PROG}:18"])])
    keep, nrs, _, _ = extract.check_target(repo, dict(statements=[st], not_rules=[]), t, _call(repo, S, t, tmp_path))
    assert keep == [] and [n["reason"] for n in nrs if n.get("derived")] == ["control-only"]


# ---------------- 2. concerns ----------------
def test_a_concern_must_have_a_text_and_cite_batch_lines(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(S, "READ-PARA")
    call = _call(repo, S, t, tmp_path)
    base = dict(anchor=dict(file=PROG, lines=t["lines"]), claims=[dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"])])
    about = lambda errs: [e for e in errs if " concern" in e]  # noqa: E731
    assert about(extract.check_statement(repo, base, t, call)) == []
    assert about(extract.check_statement(repo, dict(base, concerns=[dict(text="the ELSE also runs at end of file", lines=[f"{PROG}:22"])]), t, call)) == []
    errs = about(extract.check_statement(repo, dict(base, concerns=[dict(text="", lines=[f"{PROG}:22"]), dict(text="x", lines=[f"{PROG}:9999"])]), t, call))
    assert [e.split(" ", 3)[:3] for e in errs] == [["M1", "concern", "0"], ["M2", "concern", "1"]], errs
    assert about(extract.check_statement(repo, dict(base, concerns="none"), t, call)) == ["M1 concerns is not a list of {text, lines}"]


CONCERN = "the ELSE also runs on the end-of-file pass, with the last record's fields"


class ConcernSeats(FakeSeats):
    """READ-PARA's statement carries a concern; the checker answers each concern with ``verdict`` (both passes)."""

    def __init__(self, S, verdict):
        super().__init__(S)
        self.verdict, self.asked = verdict, []

    def claude(self, step, cid, prompt, timeout=1500, role=None, **kw):
        out, rc = super().claude(step, cid, prompt, timeout, role, **kw)
        if step != "extract":
            return out, rc
        j = json.loads(out)
        for t in j["targets"]:
            for st in t["statements"]:
                st["concerns"] = [dict(text=CONCERN, lines=[f"{PROG}:22", f"{PROG}:27-28"])]
        return json.dumps(j), rc

    def codex(self, step, cid, prompt, timeout=1500, role=None):
        if not (step.startswith("check") or step.startswith("recheck")):
            return super().codex(step, cid, prompt, timeout, role)
        self.n += 1
        res = []
        for ln in prompt.splitlines():
            if ln.startswith('{"n":'):
                it = json.loads(ln)
                self.asked += [c for c in it["claims"] if c.get("type") == "concern"]
                res.append(dict(n=it["n"], claims=[dict(i=c["i"], verdict=self.verdict if c.get("type") == "concern" else "SUPPORTED",
                                                        reason="the loop runs the paragraph once more after AT END")
                                                   for c in it["claims"]]))
        return json.dumps(dict(results=res)), 0


def _run(tmp_path, monkeypatch, verdict):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = ConcernSeats(S, verdict)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    first, _, _, _ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), log=lambda _: None, write=fake_write)
    return repo, seats, first, stored(repo.db)


def _read_para_rule(got):
    return next(v for v in got[store.RULE].values() if v.get("status") != store.RETIRED
                and any("PAY-HOURS > 40" in (c.get("text") or "") for c in v["contract"]["claims"]))


def test_a_supported_concern_is_a_flagged_follow_up_and_the_statement_stays_checked(tmp_path, monkeypatch):
    repo, seats, first, got = _run(tmp_path, monkeypatch, "SUPPORTED")
    # one question per concern, in each of the two passes, on the concern's own lines
    assert [(c["i"], c["text"], c["lines"]) for c in seats.asked] == [(1000, CONCERN, [f"{PROG}:22", f"{PROG}:27-28"])] * 2
    rule = _read_para_rule(got)
    assert rule["status"] == "Checked"
    assert rule["contract"]["concerns"][0]["checked"] == "SUPPORTED"
    rows = [v for v in got[store.FOLLOWUP].values() if v.get("concern_of") == rule["contract"]["id"]]
    assert len(rows) == 1, got[store.FOLLOWUP]
    r = rows[0]
    assert (r["kind"], r["statement"], r["where"]) == ("flagged", None, dict(file=PROG, lines=[22, 22]))
    assert CONCERN in r["unknown"] and "could not confirm" not in r["unknown"]
    # the concern's lines are part of what the statement cites, so a change there checks it again
    assert (PROG, 22) in store.cited(rule["contract"])


def test_a_concern_both_passes_refute_raises_no_follow_up(tmp_path, monkeypatch):
    repo, seats, first, got = _run(tmp_path, monkeypatch, "WRONG")
    rule = _read_para_rule(got)
    assert rule["status"] == "Checked"  # a refuted concern never opens the statement it rides on
    assert rule["contract"]["concerns"][0]["checked"] == "WRONG"
    assert not [v for v in got[store.FOLLOWUP].values() if v.get("concern_of")]


def test_a_concern_the_checker_cannot_settle_is_raised_as_not_confirmed(tmp_path, monkeypatch):
    repo, seats, first, got = _run(tmp_path, monkeypatch, "UNVERIFIABLE")
    rule = _read_para_rule(got)
    assert rule["status"] == "Checked"
    rows = [v for v in got[store.FOLLOWUP].values() if v.get("concern_of")]
    assert len(rows) == 1 and "could not confirm" in rows[0]["unknown"]


def test_a_concern_moves_with_its_code_when_its_target_is_revalidated(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    t = _target(S, "READ-PARA")
    st = dict(id="t#0", anchor=dict(file=PROG, lines=[20, 29]),
              claims=[dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"])],
              concerns=[dict(text=CONCERN, lines=[f"{PROG}:22"])])
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    rec = store.target_record(repo, t, call, [st], [], {}, store._unit_spans(repo), S["targets"])
    edit(repo, PROG, lambda L: L[:13] + [b"       01  WS-COUNT                PIC 9 VALUE 0."] + L[13:])
    d, moves = store.decide(graph.Repo(repo.root, repo.db), rec)
    assert d == "revalidate"
    assert store.relocate(st, moves)["concerns"][0]["lines"] == [f"{PROG}:23"]


# ---------------- 3. stubs ----------------
def test_a_stub_stated_as_doing_nothing_with_its_comment_is_a_statement(tmp_path):
    """Rule 12's shape: an effect that it does nothing, a value quoting the comment, and a concern naming the stub."""
    repo = make_repo(tmp_path, "mini-cobol")
    edit(repo, PROG, _at(16, b"      * To be implemented"))
    edit(repo, PROG, _at(17, b"           EXIT."))
    S = scope.build_scope(repo, "PAYCALC1")
    t = _target(S, "MAIN-PARA")
    st = dict(anchor=dict(file=PROG, lines=[15, 17]),
              claims=[dict(i=0, type="effect", text="does nothing", lines=[f"{PROG}:17"]),
                      dict(i=1, type="value", text='`"To be implemented"`', of=0, lines=[f"{PROG}:16"])],
              concerns=[dict(text="the paragraph is a stub: it holds only `EXIT`", lines=[f"{PROG}:16-17"])])
    keep, nrs, fails, _ = extract.check_target(repo, dict(statements=[st], not_rules=[]), t, _call(repo, S, t, tmp_path))
    assert len(keep) == 1 and not fails, fails
    assert not any(n.get("derived") for n in nrs)


# ---------------- 4. copybook fields ----------------
def test_a_statement_names_the_copybook_line_of_each_field_it_quotes(tmp_path, monkeypatch):
    repo, seats, first, got = _run(tmp_path, monkeypatch, "SUPPORTED")
    ctx = {x["symbol"]: x["at"] for x in _read_para_rule(got)["contract"]["context"]}
    # PAYREC.cpy: 05 PAY-HOURS at 3, PAY-RATE at 4, PAY-AMOUNT at 5 (the claims quote all three)
    assert ctx == {"PAY-HOURS": "app/cpy/PAYREC.cpy:3", "PAY-RATE": "app/cpy/PAYREC.cpy:4", "PAY-AMOUNT": "app/cpy/PAYREC.cpy:5"}


def test_a_field_the_program_defines_gets_no_copybook_context(tmp_path):
    lookup.use_repo(make_repo(tmp_path, "mini-cobol"))
    st = dict(anchor=dict(file=PROG, lines=[20, 29]), claims=[dict(i=0, type="effect", text="moves `'Y'` to `WS-EOF`", lines=[f"{PROG}:22"])])
    assert extract.cite_copybooks(st)["context"] == []


# ---------------- round-1 review folds ----------------
FORMS = "app/cbl/FORMS1.cbl"
_FORMS = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. FORMS1.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM CICS-PARA
           PERFORM QUEUE-PARA
           PERFORM POST-SEC
           PERFORM low-para
           CLOSE PAY-FILE *> WRITE PAY-LINE
           GOBACK.
       CICS-PARA.
           EXEC CICS WRITE
                FILE('ACCTDAT')
           END-EXEC.
       QUEUE-PARA.
           EXEC CICS WRITEQ TS QUEUE('Q1') FROM(WS-X) END-EXEC
           EXEC CICS WRITE OPERATOR TEXT(WS-MSG) END-EXEC
           EXEC CICS DELETE CONTAINER('C1') CHANNEL('CH') END-EXEC
           MOVE 'Y' TO WS-WRITE-FLAG.
       POST-SEC SECTION.
       POST-A.
           MOVE 1 TO WS-N.
       POST-B.
           REWRITE 01-ACCT-REC.
       low-para.
           DELETE ACCT-FILE RECORD.
"""


def _forms(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    with open(os.path.join(repo.root, FORMS), "w") as fh:
        fh.write(_FORMS)
    return repo


def test_a_cics_or_line_end_verb_is_an_update_a_queue_or_operator_message_is_not(tmp_path):
    repo = _forms(tmp_path)
    L = graph.flines(repo, FORMS)
    got = graph.updates_records(repo, FORMS, range(1, len(L) + 1))
    # 5 CICS-PARA, 7 POST-SEC (its POST-B rewrites), 8 low-para (a lower-case header); 12 the line-end CICS WRITE;
    # 24 a digit-led record name; 26 DELETE ... RECORD. Not: 6 (a queue, an operator message, a container, a data
    # name), 9 (the WRITE is in an inline comment), 16-19.
    assert got == [5, 7, 8, 12, 24, 26], got


def test_a_model_range_is_cut_to_the_file_before_it_is_walked(tmp_path):
    repo = _forms(tmp_path)
    t0 = time.time()
    assert graph.updates_records(repo, FORMS, range(1, 10 ** 12)) == [5, 7, 8, 12, 24, 26]
    st = dict(anchor=dict(file=FORMS, lines=[11, 14]), claims=[dict(i=0, type="effect", text="writes", lines=[f"{FORMS}:1-{10 ** 12}"])])
    assert extract.is_rule(st, repo) and time.time() - t0 < 5


def test_a_claim_numbered_like_a_concern_keeps_its_verdict():
    st = dict(id="s", claims=[dict(i=0, type="condition"), dict(i=1000, type="effect")], concerns=[dict(text="x", lines=["a:1"])])
    assert check.concern_ids(st) == [1001]
    assert [c["i"] for c in check.table(st)] == [0, 1000, 1001]
    res = {"s": dict(claims=[dict(i=0, verdict="SUPPORTED"), dict(i=1000, verdict="WRONG"), dict(i=1001, verdict="SUPPORTED")])}
    got = check.split_concerns(res, [st])
    assert [c["i"] for c in res["s"]["claims"]] == [0, 1000] and list(got["s"]) == [0]
    plain = dict(id="p", claims=[dict(i=1000, type="effect")])
    res = {"p": dict(claims=[dict(i=1000, verdict="SUPPORTED")])}
    check.split_concerns(res, [plain])
    assert res["p"]["claims"] == [dict(i=1000, verdict="SUPPORTED")]  # no concerns: nothing is taken


def test_each_repair_child_gets_its_own_unjudged_copy_of_the_concerns():
    s = dict(concerns=[dict(text="x", lines=["a:1"], checked="SUPPORTED", reason="r")])
    a, b = check.inherited_concerns({}, s), check.inherited_concerns({}, s)
    assert a == b == [dict(text="x", lines=["a:1"])]
    check.judge_concerns(dict(concerns=a), {0: dict(verdict="WRONG")}, {0: dict(verdict="WRONG")})
    assert a[0]["checked"] == "WRONG" and "checked" not in b[0] and s["concerns"][0]["checked"] == "SUPPORTED"
    # a repair's own concern is added to the parent's, never in place of it; one with the parent's text is not repeated
    got = check.inherited_concerns(dict(concerns=[dict(text="own", lines=["a:2"]), dict(text="x", lines=["a:1"])]), s)
    assert got == [dict(text="x", lines=["a:1"]), dict(text="own", lines=["a:2"])]


def test_the_reason_comes_from_the_pass_that_gave_the_verdict():
    st = dict(concerns=[dict(text="x", lines=["a:1"])])
    check.judge_concerns(st, {0: dict(verdict="UNVERIFIABLE", reason="not shown")}, {0: dict(verdict="SUPPORTED", reason="it holds")})
    assert (st["concerns"][0]["checked"], st["concerns"][0]["reason"]) == ("SUPPORTED", "it holds")


def test_two_concerns_with_one_text_and_place_are_two_stored_rows(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    lookup.use_repo(repo)
    S = scope.build_scope(repo, "PAYCALC1")
    st = dict(id="t#0", status="Checked", target=_target(S, "READ-PARA")["id"], name="READ-PARA", anchor=dict(file=PROG, lines=[20, 29]),
              concerns=[dict(text=CONCERN, lines=[f"{PROG}:22"], checked="SUPPORTED")] * 2)
    other = dict(st, id="t#1")
    rows = followups.concern_rows([st, other])
    assert len(rows) == 4 and len({(r["concern_of"], r["concern"]) for r in rows}) == 4
    out, _ = store.rows_for(repo, dict(statements=[]), [], [], None, rows, {}, str)
    fk = [r["key"] for r in out if r["key"].startswith(store.FOLLOWUP + ":")]
    assert len(fk) == 4 and len(set(fk)) == 4, fk  # the store writer's own keys: no row overwrites another


def test_a_malformed_or_unchecked_concern_raises_no_row_and_crashes_nothing(tmp_path):
    lookup.use_repo(make_repo(tmp_path, "mini-cobol"))
    base = dict(id="t#0", status="open", target="t", anchor=dict(file=PROG, lines=[20, 29]),
                claims=[dict(i=0, type="effect", text=42, lines=[f"{PROG}:22"])])
    for bad in (123, "x", [123, dict(text=7, lines=[f"{PROG}:22"], checked="SUPPORTED")], [dict(text="never asked", lines=[f"{PROG}:22"])],
                [dict(text="t", lines=5, checked="SUPPORTED")]):
        st = dict(base, concerns=bad)
        rows = followups.concern_rows([st])
        if isinstance(bad, list) and isinstance(bad[0], dict) and bad[0].get("lines") == 5:
            assert [r["where"] for r in rows] == [dict(file=PROG, lines=[20, 29])]  # unusable lines: the row sits on the anchor
        else:
            assert rows == [], bad
        store.cited(st)
        store.relocate(st, {})
        extract.cite_copybooks(st)
        check.table(dict(st, claims=[dict(i=0, type="effect", text="x")]))


def test_a_quoted_literal_or_a_field_two_copybooks_define_gets_no_copybook_context(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    with open(os.path.join(repo.root, "app/cpy/PAYDUP.cpy"), "w") as fh:
        fh.write("       01  PAY-DUP.\n           05  PAY-RATE            PIC 9(3)V99.\n")
    edit(repo, PROG, _at(13, b"       COPY PAYDUP."))  # WS-EOF's line becomes a second COPY: PAY-RATE is now in two
    lookup.use_repo(graph.Repo(repo.root, repo.db))
    st = dict(anchor=dict(file=PROG, lines=[20, 29]),
              claims=[dict(i=0, type="effect", text="moves `'PAY-HOURS'` to the message; `PAY-RATE` times `PAY-AMOUNT`", lines=[f"{PROG}:25"])])
    assert {x["symbol"]: x["at"] for x in extract.cite_copybooks(st)["context"]} == {"PAY-AMOUNT": "app/cpy/PAYREC.cpy:5"}


WRAP = "app/cbl/WRAP1.cbl"
_WRAP = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. WRAP1.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM
               SAVE-PARA
           PERFORM A-PARA
              THRU A-EXIT
           PERFORM B-PARA THRU B-EXIT
           MOVE 'START OF A LONG MESSAGE THAT SAYS WRITE THE RECO
      -    'RD' TO WS-MSG
           GOBACK.
       A-PARA.
           MOVE 1 TO WS-N.
       A-EXIT.
           EXIT.
       A-WRITE.
           WRITE A-REC.
       SAVE-PARA. *> keeps the record
           EXEC CICS WRITE
                OPERATOR TEXT(WS-MSG)
           END-EXEC
           REWRITE S-REC.
       SEC-1 SECTION.
       B-PARA.
           MOVE 2 TO WS-N.
       SEC-2 SECTION.
       B-EXIT.
           EXIT.
       C-PARA.
           DELETE C-FILE RECORD.
"""


def test_a_wrapped_call_a_split_cics_command_and_a_continued_literal_read_as_the_code_runs(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    with open(os.path.join(repo.root, WRAP), "w") as fh:
        fh.write(_WRAP)
    L = graph.flines(repo, WRAP)
    got = graph.updates_records(repo, WRAP, range(1, len(L) + 1))
    # 5: PERFORM with its name on the next line (SAVE-PARA, a header with an inline comment, rewrites at 23).
    # Not: 7 (A-PARA THRU A-EXIT on the next line: A-WRITE is after the range), 9 (B-PARA THRU B-EXIT crosses into
    # SEC-2 but stops before C-PARA's DELETE), 10-11 (WRITE inside a continued literal), 20 (a CICS WRITE OPERATOR
    # split over two lines). 18, 23 and 31 are the updates themselves.
    assert got == [5, 18, 23, 31], got


def test_a_field_one_copybook_defines_twice_gets_no_copybook_context(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    with open(os.path.join(repo.root, "app/cpy/PAYREC.cpy"), "a") as fh:
        fh.write("       01  PAY-OLD.\n           05  PAY-AMOUNT          PIC 9(5)V99.\n")
    lookup.use_repo(graph.Repo(repo.root, repo.db))
    st = dict(anchor=dict(file=PROG, lines=[20, 29]),
              claims=[dict(i=0, type="effect", text="adds `PAY-AMOUNT`", lines=[f"{PROG}:25"])])
    assert extract.cite_copybooks(st)["context"] == []


QUAL = "app/cbl/QUAL1.cbl"
_QUAL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. QUAL1.
       PROCEDURE DIVISION.
       MAIN-SEC SECTION.
       MAIN-PARA.
           PERFORM SAVE-REC OF CLEANUP-SEC
           PERFORM SAVE-REC IN OUTPUT-SEC
           PERFORM SAVE-REC
           GOBACK.
       OUTPUT-SEC SECTION.
       OUT-A.
           PERFORM SAVE-REC.
       SAVE-REC.
           WRITE OUT-REC.
       CLEANUP-SEC SECTION.
       CLEAN-A.
           PERFORM SAVE-REC.
       SAVE-REC.
           CLOSE OUT-FILE.
"""


def test_a_paragraph_name_two_sections_share_resolves_to_the_one_the_call_means(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    with open(os.path.join(repo.root, QUAL), "w") as fh:
        fh.write(_QUAL)
    got = graph.updates_records(repo, QUAL, range(1, 20))
    # 6 names CLEANUP-SEC's SAVE-REC (a CLOSE); 7 OUTPUT-SEC's (a WRITE); 8 is ambiguous from MAIN-SEC, so not counted;
    # 12 and 17 mean their own section's SAVE-REC; 14 is the WRITE itself
    assert got == [7, 12, 14], got


def test_a_field_the_model_named_with_no_reference_gets_its_copybook_line(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    lookup.use_repo(graph.Repo(repo.root, repo.db))
    st = dict(anchor=dict(file=PROG, lines=[20, 29]), context=[dict(symbol="PAY-AMOUNT")],
              claims=[dict(i=0, type="effect", text="adds `PAY-AMOUNT`", lines=[f"{PROG}:25"])])
    assert extract.cite_copybooks(st)["context"] == [dict(symbol="PAY-AMOUNT", at="app/cpy/PAYREC.cpy:5")]
