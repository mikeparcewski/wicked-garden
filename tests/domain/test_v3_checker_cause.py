"""garden#1617: a checker pass in which no call answered is sent once more, and a run it stops names the cause.
0 real model calls: the calls go through the real ``model_calls.call``; only the ``wicked-core model-call`` process
is replaced, by one that answers in the writer's and the checker's own shapes (``FakeSeats``) or fails like a client.
"""
import os
import types

import pytest

from domain import model_calls, prose, run, scope
from tests.domain.test_v3_store import FakeSeats, fake_write, make_repo, stored


def seat_process(monkeypatch, seats, fail=lambda family, step, cid, n: None):
    """``wicked-core model-call --family F --in <calls>/<step>/<id>.prompt.txt --out O``, answered by ``seats`` unless
    ``fail(family, step, id, nth send of this call)`` returns ``(exit code, stderr)``."""
    sent = []
    monkeypatch.setattr(model_calls, "RETRY_WAIT_S", 0)

    def fake_run(cmd, **kw):
        v = lambda k: cmd[cmd.index(k) + 1]  # noqa: E731
        family, inp = v("--family"), v("--in")
        step, cid = os.path.basename(os.path.dirname(inp)), os.path.basename(inp)[:-len(".prompt.txt")]
        sent.append((family, step, cid))
        f = fail(family, step, cid, sent.count((family, step, cid)))
        if f:
            return types.SimpleNamespace(returncode=f[0], stderr=f[1])
        with open(inp) as fh:
            text, rc = getattr(seats, family)(step, cid, fh.read())
        with open(v("--out"), "w") as fh:
            fh.write(text)
        return types.SimpleNamespace(returncode=rc, stderr="")

    monkeypatch.setattr(model_calls, "core_bin", lambda: "wicked-core")
    monkeypatch.setattr(model_calls, "subprocess", types.SimpleNamespace(run=fake_run, TimeoutExpired=TimeoutError))
    return sent


RATE = (1, "codex: starting\nERROR: 429 Too Many Requests: retry after 60s\n")


def test_a_check_pass_that_never_answers_is_tried_twice_and_the_stop_names_the_exit_codes_and_last_error(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    sent = seat_process(monkeypatch, seats, fail=lambda f, step, cid, n: RATE if f == "codex" and step.startswith("check") else None)
    with pytest.raises(model_calls.CallFailed) as e:
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r1"), write=fake_write)
    checks = [x for x in sent if x[0] == "codex"]
    for step in {s for _, s, _ in checks}:  # the two checkers' passes run side by side (check.check_all)
        mine = [c for _, s, c in checks if s == step]
        assert all(mine.count(c) == 2 for c in mine), f"every call of {step} was sent twice, no more"
    step = next(s for _, s, _ in checks if s in str(e.value))
    n = len({c for _, s, c in checks if s == step})
    assert str(e.value) == (f"the checker answered none of the {n} {step} calls (codex, tried twice: {n} x exit 1; "
                            "last error: 'ERROR: 429 Too Many Requests: retry after 60s'); nothing was stored")
    assert not any(stored(repo.db).values())


def test_a_check_pass_that_fails_once_and_then_answers_stores_the_run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    seat_process(monkeypatch, seats, fail=lambda f, step, cid, n: RATE if f == "codex" and step.startswith("check") and n == 1 else None)
    summary, *_ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(tmp_path / "r1"), write=fake_write)
    assert summary["checked"] == 1 and summary["open"] == 0


def test_a_prose_check_that_never_answers_names_the_cause_too(tmp_path, monkeypatch):
    model_calls.configure(str(tmp_path / "calls"))
    seat_process(monkeypatch, FakeSeats(dict(targets=[])), fail=lambda f, step, cid, n: (0, "") if f == "codex" else None)
    sents = [dict(id="g1.r", text="Hours over forty are paid at the overtime rate.", cites=["S1"])]
    with pytest.raises(model_calls.CallFailed) as e:
        prose.check(sents, {"S1": dict(text="`PAY-HOURS > 40`")}, "prose-check")
    assert str(e.value) == ("the checker answered none of the 1 prose-check calls (codex, tried twice: 1 x exit 0 with "
                            "an empty answer; the client wrote no error); nothing was stored")


def _pass(tmp_path, monkeypatch, answers):
    """A checker pass of ``len(answers)`` calls through the real ``model_calls.call``; ``answers[k]`` is the list of
    (exit code, text, stderr) the client gives call ``c<k>`` on each send."""
    model_calls.configure(str(tmp_path / "calls"))
    monkeypatch.setattr(model_calls, "RETRY_WAIT_S", 0)
    sent = []

    def fake_run(cmd, **kw):
        v = lambda k: cmd[cmd.index(k) + 1]  # noqa: E731
        cid = os.path.basename(v("--in"))[:-len(".prompt.txt")]
        sent.append(cid)
        rc, text, err = answers[int(cid[1:])][min(sent.count(cid), len(answers[int(cid[1:])])) - 1]
        if text is not None:
            with open(v("--out"), "w") as fh:
                fh.write(text)
        return types.SimpleNamespace(returncode=rc, stderr=err)
    monkeypatch.setattr(model_calls, "core_bin", lambda: "wicked-core")
    monkeypatch.setattr(model_calls, "subprocess", types.SimpleNamespace(run=fake_run, TimeoutExpired=TimeoutError))
    one = lambda k: (k,) + model_calls.codex("check-a", f"c{k}", f"prompt {k}")  # noqa: E731
    return sent, lambda: model_calls.checker_pass("check-a", len(answers), one, 2)


def test_a_pass_where_one_call_answered_resends_nothing(tmp_path, monkeypatch):
    # round 1 on garden#1621: only a fully silent pass is sent again; a failed call among answered ones stays open
    sent, run_pass = _pass(tmp_path, monkeypatch, [[(0, "{}", "")], [(1, None, "boom\n"), (0, "{}", "")]])
    assert run_pass() == [(0, True), (1, False)]
    assert sorted(sent) == ["c0", "c1"]


def test_a_blank_answer_is_asked_again_never_replayed_from_the_cache(tmp_path, monkeypatch):
    # round 1 on garden#1621: a whitespace answer was kept as the call's output, so the resend replayed it
    sent, run_pass = _pass(tmp_path, monkeypatch, [[(0, " \n", ""), (0, '{"results": []}', "")]])
    assert run_pass() == [(0, True)]
    assert sent == ["c0", "c0"]


def test_the_stop_says_only_what_the_ledger_holds_of_the_latest_attempt(tmp_path, monkeypatch):
    # round 1 on garden#1621: an exit-0 call's stderr is not in the ledger, nor the head of a long line, nor an
    # earlier attempt's error
    long_line = "SECRET-HEAD " + "x" * 400 + " tail-of-the-line"
    sent, run_pass = _pass(tmp_path, monkeypatch, [[(1, None, "first attempt error\n"), (0, None, "exit-0 diagnostic\n")],
                                                   [(1, None, long_line + "\n"), (1, None, long_line + "\n")]])
    with pytest.raises(model_calls.CallFailed) as e:
        run_pass()
    msg = str(e.value)
    assert "SECRET-HEAD" not in msg and "exit-0 diagnostic" not in msg and "first attempt error" not in msg
    assert msg.endswith("x tail-of-the-line'); nothing was stored") and "1 x exit 0 with an empty answer, 1 x exit 1" in msg
