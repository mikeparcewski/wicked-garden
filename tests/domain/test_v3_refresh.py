"""garden#1613 (DES-1613, coord option 1): after a run stores its model, the targets an earlier pipeline version stated,
on unchanged code and with no ruling, are stated and checked again; the store takes them all, in a second write, or
none, and then their records say so and the next runs make no refresh call until the version moves. Fixtures: the
mini-cobol estate of ``test_v3_store.py``, run through the real ``run.run`` and the real ``model_calls.call`` (its cache
and its calls ledger); only the ``wicked-core model-call`` process is replaced (``test_v3_carry_calls.seat_process``)."""
import json
import os

from domain import run, scope, store
from tests.domain.test_v3_carry_calls import seat_process
from tests.domain.test_v3_rulings import RulingSeats, by_text, rule, target_row
from tests.domain.test_v3_store import PROG, FakeSeats, edit, fake_write, make_repo, stored

OLD = "0" * 16
NOW = store.STATING
BIG = "\x1b[31m" + "Z" * 10000


class Seats(FakeSeats):
    """FakeSeats; ``mode`` changes what the seats answer: ``unsupported`` (the checker refutes every claim),
    ``silent`` (the writer's extract does not answer), ``mfail`` (the writer's statement fails the M checks, with a
    10 kB claim text), ``reworded`` (the writer says the overtime claim in other words)."""
    mode = None

    def claude(self, step, cid, prompt, timeout=1500, role=None, **kw):
        if step == "extract" and self.mode == "silent":
            self.n += 1
            return "", 1
        out, rc = super().claude(step, cid, prompt, timeout, role, **kw)
        if step == "extract" and self.mode in ("mfail", "reworded"):
            j = json.loads(out)
            for t in j["targets"]:
                for st in t["statements"]:
                    if self.mode == "mfail":
                        st["claims"][1]["when"] = [1]  # a `when` naming itself: fails the M checks
                        st["claims"][1]["text"] = BIG
                    else:
                        st["claims"][1]["text"] = "`PAY-AMOUNT` is paid at the overtime rate"
            out = json.dumps(j)
        return out, rc

    def codex(self, step, cid, prompt, timeout=1500, role=None):
        out, rc = super().codex(step, cid, prompt, timeout, role)
        if self.mode == "unsupported" and (step.startswith("check") or step.startswith("recheck")):
            j = json.loads(out)
            for r in j["results"]:
                r["claims"] = [dict(c, verdict="UNSUPPORTED", reason="not what the code says") for c in r["claims"]]
            out = json.dumps(j)
        return out, rc


def setup(tmp_path, monkeypatch, seats_cls=Seats):
    """A store the OLD pipeline version stated (run1); returns what the next runs need."""
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = seats_cls(S)
    seats.sent = seat_process(monkeypatch, seats)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    monkeypatch.setattr(store, "STATING", OLD)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), log=lambda s: None, write=fake_write)
    monkeypatch.setattr(store, "STATING", NOW)
    seats.n = 0
    return repo, S, seats, scope_in


def again(repo, scope_in, tmp_path, seats, name, write=fake_write):
    seats.n, lines = 0, []
    seats.sent.clear()
    summary, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / name), log=lines.append, write=write)
    return summary, lines, seats.n


def versions(db):
    return {r.get("pipeline") for r in store.load(db)[store.TARGET].values()}


def test_a_full_refresh_is_adopted_and_the_next_run_reports_nothing_earlier_and_makes_no_call(tmp_path, monkeypatch):
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    n = len(S["targets"])
    before = stored(repo.db)
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    assert calls > 0 and summary["refresh"] == dict(eligible=n, adopted=n, refused=0, reasons=[]), summary["refresh"]
    assert summary["earlier_pipeline"] == dict(targets=0, groups=0) and summary["model_calls"] == calls
    assert any("refresh · adopted" in ln for ln in lines), lines
    assert versions(repo.db) == {NOW}
    after = stored(repo.db)
    assert {k: v["statement"] for k, v in after[store.RULE].items()} == {k: v["statement"] for k, v in before[store.RULE].items()}
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run3")
    assert calls == 0 and summary["refresh"]["eligible"] == 0 and summary["earlier_pipeline"]["targets"] == 0
    assert not any("earlier pipeline version" in ln for ln in lines), lines


def test_a_refresh_that_states_less_is_refused_stamped_and_not_tried_again_until_the_version_moves(tmp_path, monkeypatch):
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    before = stored(repo.db)
    seats.mode = "unsupported"
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    fr = summary["refresh"]
    assert calls > 0 and fr["adopted"] == 0 and fr["refused"] == fr["eligible"] > 0
    # a refuted claim goes to repair and re-check: what is left is unchecked (noresult) or fewer Checked statements
    codes = {r["code"] for r in fr["reasons"]}
    assert codes and codes <= {"noresult", "fewer_checked"}, fr
    assert any("refresh · not adopted" in ln and all(c in ln for c in codes) for ln in lines), lines
    after = stored(repo.db)
    assert after[store.RULE] == before[store.RULE] and after[store.GROUP] == before[store.GROUP]
    assert versions(repo.db) == {OLD}
    assert {r.get("refresh_refused") for r in after[store.TARGET].values()} == {NOW}
    # the same version: 0 refresh calls, and the run says why
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run3")
    assert calls == 0 and summary["refresh"]["eligible"] == 0
    assert any("were refused at this version and stay as stored" in ln for ln in lines), lines
    assert {r.get("refresh_refused") for r in store.load(repo.db)[store.TARGET].values()} == {NOW}, "the stamp is kept"
    # a pipeline bump tries again
    seats.mode = None
    monkeypatch.setattr(store, "STATING", "1" * 16)
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run4")
    assert calls > 0 and summary["refresh"]["adopted"] == summary["refresh"]["eligible"] > 0
    assert versions(repo.db) == {"1" * 16}
    assert {r.get("refresh_refused") for r in store.load(repo.db)[store.TARGET].values()} == {None}


def test_a_writer_that_does_not_answer_in_the_refresh_leaves_the_store_unstamped_and_the_run_succeeds(tmp_path, monkeypatch):
    # partial failure: the first write stands, no stamp, so the next run tries again
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    before = stored(repo.db)
    seats.mode = "silent"
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    assert summary["refresh"]["reasons"] == [dict(target=None, code="call_failed")] and summary["refresh"]["adopted"] == 0
    after = stored(repo.db)
    assert after[store.RULE] == before[store.RULE] and versions(repo.db) == {OLD}
    assert {r.get("refresh_refused") for r in after[store.TARGET].values()} == {None}
    seats.mode = None
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run3")
    assert calls > 0 and summary["refresh"]["adopted"] > 0 and versions(repo.db) == {NOW}


def test_a_failing_second_write_leaves_the_first_write_and_no_stamp(tmp_path, monkeypatch):
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    before = stored(repo.db)
    writes = []

    def second_fails(db, rows):
        writes.append(rows)
        if len(writes) == 2:
            raise RuntimeError("wicked-estate write-batch failed (1): \x1b[31m" + "Y" * 5000)
        return fake_write(db, rows)
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2", write=second_fails)
    assert len(writes) == 2 and summary["refresh"]["reasons"] == [dict(target=None, code="write_failed")]
    after = stored(repo.db)
    assert after[store.RULE] == before[store.RULE] and versions(repo.db) == {OLD}
    assert {r.get("refresh_refused") for r in after[store.TARGET].values()} == {None}
    with open(tmp_path / "run2" / "summary.json") as fh:
        assert "YYYY" not in fh.read() and not any("YYYY" in ln for ln in lines)


def test_a_statement_that_fails_the_m_checks_in_the_refresh_blocks_it_and_its_text_stays_out_of_the_summary(
        tmp_path, monkeypatch):
    # untrusted text out: the reasons are fixed codes; the writer's 10 kB claim text reaches no summary or log line
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    seats.mode = "mfail"
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    fr = summary["refresh"]
    assert fr["refused"] > 0 and "m_fail" in {r["code"] for r in fr["reasons"]}, fr
    assert {r["code"] for r in fr["reasons"]} <= set(run.REFRESH_CODES)
    with open(tmp_path / "run2" / "summary.json") as fh:
        text = fh.read()
    assert "ZZZZ" not in text and "\\u001b" not in text
    assert not any("ZZZZ" in ln or "\x1b" in ln for ln in lines)
    assert versions(repo.db) == {OLD}


def test_a_refreshed_group_is_written_again_when_its_statements_read_otherwise(tmp_path, monkeypatch):
    # identity reuse: the refreshed statements keep their ids, so a group keyed on their old text is not reused
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    seats.mode = "reworded"
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    assert summary["refresh"]["adopted"] > 0 and ("claude", "prose") in seats.sent, summary["refresh"]
    model = stored(repo.db)
    text_of = {k: store.sha(v["statement"].encode()) for k, v in model[store.RULE].items()}
    assert any("overtime rate" in v["statement"] and "paid at" in v["statement"] for v in model[store.RULE].values())
    for g in model[store.GROUP].values():
        assert all(text_of.get(i) == h for i, h in g["inputs"].items()), "a stored group rests on the text it was written on"


def test_a_target_whose_code_changed_is_stated_by_the_run_itself_and_never_refreshed(tmp_path, monkeypatch):
    # stale reads: only unchanged code (carry) is refreshed; a target extracted again is stated at this version anyway
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    edit(repo, PROG, lambda L: L[:23] + [L[23].replace(b"> 40", b"> 45")] + L[24:])  # test_v3_store case 1
    scope_in = {k: v for k, v in scope_in.items() if k != "scope_hash"}  # no preview to hold the run to
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    # the edited target is extracted at this version; its batch moved, so the others are re-validated, not carried,
    # and none is refreshed in this run
    assert summary["reuse"] == dict(carry=0, revalidate=3, extract=1) and summary["refresh"]["eligible"] == 0
    assert versions(repo.db) == {OLD, NOW}
    # the next run carries the three on unchanged code and refreshes them
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run3")
    assert summary["refresh"]["eligible"] == 3 and summary["refresh"]["adopted"] == 3, summary["refresh"]
    assert versions(repo.db) == {NOW}


def test_a_target_a_person_ruled_on_is_never_refreshed_and_keeps_its_statements_and_ids(tmp_path, monkeypatch):
    # identity reuse: rulings are keyed by statement id, so a ruled target is held as stored
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch, RulingSeats)
    sid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    read = target_row(repo.db, "READ-PARA")
    rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    before = {k: v["statement"] for k, v in store.load(repo.db)[store.RULE].items() if k.startswith(read["target"])}
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    assert read["target"] not in {r["target"] for r in summary["refresh"]["reasons"]}
    after_read = target_row(repo.db, "READ-PARA")
    assert after_read["pipeline"] == OLD and after_read.get("refresh_refused") is None
    assert {k: v["statement"] for k, v in store.load(repo.db)[store.RULE].items() if k.startswith(read["target"])} == before
    assert summary["confirmed"] == 1


def test_the_refresh_keeps_its_own_call_cache_apart_from_the_runs(tmp_path, monkeypatch):
    # shared/cached reads: a run dir that already holds an extract call under the same id with another prompt (a
    # re-run in the same out dir) must neither refuse the refresh (no-overwrite) nor hand it that answer
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    d = tmp_path / "run2" / "calls" / "extract"
    d.mkdir(parents=True)
    for c in os.listdir(tmp_path / "run1" / "calls" / "extract"):
        if c.endswith(".prompt.txt"):
            (d / c).write_text("another prompt")
            (d / c.replace(".prompt.txt", ".out.txt")).write_text('{"targets": []}')
    summary, lines, calls = again(repo, scope_in, tmp_path, seats, "run2")
    assert summary["refresh"]["adopted"] == summary["refresh"]["eligible"] > 0, summary["refresh"]
    assert os.path.isdir(tmp_path / "run2" / "refresh" / "calls" / "extract")


def test_stored_after_is_the_store_the_first_write_left(tmp_path, monkeypatch):
    # shared/cached reads: the refresh plans its write over the first write's rows, in memory (never a read-back);
    # they must be exactly the store that write left, as store.load reads it
    repo, S, seats, scope_in = setup(tmp_path, monkeypatch)
    got = []

    def keep(db, rows):
        if not got:
            before = store.load_symbols(db, store.load(db))
            report = fake_write(db, rows)
            got.append((before, rows, store.load(db)))
            return report
        return fake_write(db, rows)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lambda s: None, write=keep)
    before, rows, read_back = got[0]
    after = run.stored_after(before, rows)
    for t in store.TYPES:
        assert after[t] == read_back[t], t
