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
        assert len(mine) == 2 * len(set(mine)), f"every call of {step} was sent twice, no more"
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
