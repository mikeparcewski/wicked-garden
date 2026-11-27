"""garden#1614: a failed attempt's answers are carried to the retry of the same scope, 0 real model calls.

Each attempt of a run has its own out dir (run.main), so model_calls' byte-identical-prompt cache never spans a retry.
The calls go through the real ``model_calls.call``; only the ``wicked-core model-call`` process is replaced, by one
that answers in the writer's and the checker's own output shapes (``FakeSeats``).
"""
import os
import types

import pytest

from domain import model_calls, run, scope
from tests.domain.test_v3_store import PROG, FakeSeats, edit, fake_write, make_repo, stored


def seat_process(monkeypatch, seats, fail=lambda family, step: False):
    """``wicked-core model-call --family F --in <calls>/<step>/<id>.prompt.txt --out O`` answered by ``seats``."""
    sent = []

    def fake_run(cmd, **kw):
        v = lambda k: cmd[cmd.index(k) + 1]  # noqa: E731
        family, inp = v("--family"), v("--in")
        step, cid = os.path.basename(os.path.dirname(inp)), os.path.basename(inp)[:-len(".prompt.txt")]
        sent.append((family, step))
        if fail(family, step):
            return types.SimpleNamespace(returncode=4, stderr="model-call: the seat is signed out\n")
        with open(inp) as fh:
            text, rc = getattr(seats, family)(step, cid, fh.read())
        with open(v("--out"), "w") as fh:
            fh.write(text)
        return types.SimpleNamespace(returncode=rc, stderr="")

    monkeypatch.setattr(model_calls, "core_bin", lambda: "wicked-core")
    monkeypatch.setattr(model_calls, "subprocess", types.SimpleNamespace(run=fake_run, TimeoutExpired=TimeoutError))
    return sent


def test_a_retry_after_a_failed_check_reuses_the_writers_answers_and_a_stored_run_keeps_no_carry(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    runs = tmp_path / "runs"
    sent = seat_process(monkeypatch, seats, fail=lambda family, step: family == "codex" and step.startswith("check"))
    with pytest.raises(model_calls.CallFailed, match="checker answered none"):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=fake_write)
    assert ("claude", "extract") in sent
    answered = sum(1 for f, s in sent if f == "claude")  # every writer call answered; the checker's did not
    assert not any(stored(repo.db).values()), "a failed attempt stores nothing"
    assert len(os.listdir(runs / ".carry")) == 1

    sent, said = seat_process(monkeypatch, seats), []
    summary, *_ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), log=said.append, write=fake_write)
    assert ("claude", "extract") not in sent, "the writer's extract answer came from the failed attempt"
    assert any(s.startswith("check") for f, s in sent if f == "codex")
    assert summary["checked"] > 0 and summary["model_calls"] == len(sent)
    notes = (runs / "a2" / "calls" / "ledger.jsonl").read_text()
    assert "cache hit: carried from an earlier attempt" in notes
    assert f"reuse · {answered} model answers from the failed attempt" in said, said
    assert not os.listdir(runs / ".carry"), "a stored run leaves no carry behind"


def test_a_carried_answer_is_never_used_for_changed_code(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    runs = tmp_path / "runs"
    seat_process(monkeypatch, seats, fail=lambda family, step: family == "codex" and step.startswith("check"))
    with pytest.raises(model_calls.CallFailed):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=fake_write)
    edit(repo, PROG, lambda L: L[:24] + [L[24].replace(b"PAY-RATE * 40", b"PAY-RATE * 41")] + L[25:])
    seats.S = scope.build_scope(repo, "PAYCALC1")
    sent = seat_process(monkeypatch, seats)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), write=fake_write)
    assert ("claude", "extract") in sent, "the changed code is asked about again"
