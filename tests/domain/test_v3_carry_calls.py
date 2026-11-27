"""garden#1614: a failed attempt's writer answers are carried to the retry of the same scope, 0 real model calls.

Each attempt of a run has its own out dir (run.main), so model_calls' byte-identical-prompt cache never spans a retry.
The calls go through the real ``model_calls.call``; only the ``wicked-core model-call`` process is replaced, by one
that answers in the writer's and the checker's own output shapes (``FakeSeats``).
"""
import os
import types

import pytest

from domain import model_calls, run, scope
from tests.domain.test_v3_store import PROG, FakeSeats, edit, fake_write, make_repo, stored

CHECK_FAILS = lambda family, step: family == "codex" and step.startswith("check")  # noqa: E731


def seat_process(monkeypatch, seats, fail=lambda family, step: False):
    """``wicked-core model-call --family F --in <calls>/<step>/<id>.prompt.txt --out O`` answered by ``seats``."""
    sent = []
    monkeypatch.setattr(model_calls, "RETRY_WAIT_S", 0, raising=False)  # garden#1617's resend of a silent pass

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
    first = seat_process(monkeypatch, seats, fail=CHECK_FAILS)
    with pytest.raises(model_calls.CallFailed, match="checker answered none"):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=fake_write)
    assert ("claude", "extract") in first
    assert not any(stored(repo.db).values()), "a failed attempt stores nothing"
    assert len(os.listdir(runs / ".carry")) == 1

    sent, said = seat_process(monkeypatch, seats), []
    summary, *_ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), log=said.append, write=fake_write)
    assert ("claude", "extract") not in sent, "the writer's extract answer came from the failed attempt"
    assert any(f == "codex" and s.startswith("check") for f, s in sent), "the checker is asked again"
    assert summary["checked"] > 0 and summary["model_calls"] == len(sent)
    outs = [f for f in os.listdir(runs / "a2" / "calls" / "extract") if f.endswith(".out.txt")]
    assert outs and all((runs / "a2" / "calls" / "extract" / f).stat().st_size > 0 for f in outs), \
        "a carried answer is kept in the attempt's own calls as evidence"
    notes = (runs / "a2" / "calls" / "ledger.jsonl").read_text()
    n = notes.count("cache hit: carried from an earlier attempt")
    assert n == sum(1 for f, _ in first if f == "claude") and f"reuse · {n} writer answers from the failed attempt" in said, said
    assert not (runs / ".carry").exists(), "a stored run leaves no carry behind"


def test_a_retry_after_a_failed_store_reuses_every_writer_answer_and_asks_the_checker_again(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    runs = tmp_path / "runs"
    first = seat_process(monkeypatch, seats)

    def broken(db, rows):
        raise RuntimeError("wicked-estate write-batch failed (1): disk full")
    with pytest.raises(RuntimeError, match="write-batch"):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=broken)
    writer = [s for f, s in first if f == "claude"]
    assert "prose" in writer, "the late failure had the prose writer's answer too"
    sent, said = seat_process(monkeypatch, seats), []
    run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), log=said.append, write=fake_write)
    assert [x for x in sent if x[0] == "claude"] == []
    assert sorted(s for f, s in sent) == sorted(s for f, s in first if f == "codex"), "every checker call is sent again"
    assert f"reuse · {len(writer)} writer answers from the failed attempt" in said, said


def test_a_running_attempt_writes_no_carry_and_a_carry_that_cannot_be_written_never_fails_a_run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / ".carry").write_text("not a directory")
    seen = []

    def watch(db, rows):  # the store write is the last step: by then every model call was made
        seen.append(os.path.isfile(runs / ".carry"))
        return fake_write(db, rows)
    seat_process(monkeypatch, seats, fail=CHECK_FAILS)
    with pytest.raises(model_calls.CallFailed):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=fake_write)
    seat_process(monkeypatch, seats)
    summary, *_ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), write=watch)
    assert summary["checked"] == 1 and seen == [True], "nothing was written into the carry while the run ran"


def test_the_carry_misses_on_another_prompt_step_family_or_output_cap_and_on_an_unreadable_file(tmp_path, monkeypatch):
    model_calls.configure(str(tmp_path / "a1" / "calls"))
    carry = tmp_path / ".carry" / "h"
    model_calls.carry_from(str(carry))
    seats = types.SimpleNamespace(claude=lambda step, cid, p: (f"answer to {p}", 0), codex=lambda step, cid, p: ("{}", 0))
    sent = seat_process(monkeypatch, seats)
    model_calls.claude("extract", "c0", "P", max_output_tokens=64000)
    model_calls.codex("check-a", "c0", "P")
    assert model_calls.publish_carry() == 0, "nothing of a stage the attempt did not finish is carried"
    model_calls.accept_answers()
    assert model_calls.publish_carry() == 1, "only the writer's answer is carried"
    model_calls.configure(str(tmp_path / "a2" / "calls"))
    model_calls.carry_from(str(carry))
    sent.clear()
    assert model_calls.claude("extract", "c0", "P", max_output_tokens=64000) == ("answer to P", 0)
    assert sent == []
    model_calls.claude("extract", "c1", "P2", max_output_tokens=64000)
    model_calls.claude("repair", "c0", "P", max_output_tokens=64000)
    model_calls.claude("extract", "c2", "P")
    model_calls.codex("check-a", "c0", "P")
    assert sent == [("claude", "extract"), ("claude", "repair"), ("claude", "extract"), ("codex", "check-a")]
    (f,) = os.listdir(carry)
    (carry / f).write_bytes(b"\xff\xfe broken")
    model_calls.configure(str(tmp_path / "a3" / "calls"))
    model_calls.carry_from(str(carry))
    sent.clear()
    assert model_calls.claude("extract", "c0", "P", max_output_tokens=64000) == ("answer to P", 0)
    assert sent == [("claude", "extract")], "an unreadable carry is asked again, never a crash"


def test_a_carried_answer_is_never_used_for_changed_code(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    runs = tmp_path / "runs"
    seat_process(monkeypatch, seats, fail=CHECK_FAILS)
    with pytest.raises(model_calls.CallFailed):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=fake_write)
    edit(repo, PROG, lambda L: L[:24] + [L[24].replace(b"PAY-RATE * 40", b"PAY-RATE * 41")] + L[25:])
    seats.S = scope.build_scope(repo, "PAYCALC1")
    sent = seat_process(monkeypatch, seats)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), write=fake_write)
    assert ("claude", "extract") in sent, "the changed code is asked about again"
    assert not (runs / ".carry").exists(), "the stored run drops the earlier scope's carry too"


def test_a_writer_answer_the_failed_stage_could_not_use_is_asked_again(tmp_path, monkeypatch):
    # codex-check round 2 on garden#1620 (W12): a malformed extract answer failed the attempt inside the extract stage;
    # carried, it would fail every retry with 0 calls. Only the answers of a stage the attempt finished are carried.
    repo = make_repo(tmp_path, "mini-cobol")
    good = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    bad = types.SimpleNamespace(claude=lambda step, cid, p, **k: ('{"targets": 1}', 0), codex=good.codex)
    runs = tmp_path / "runs"
    seat_process(monkeypatch, bad)
    with pytest.raises(Exception):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a1"), write=fake_write)
    sent = seat_process(monkeypatch, good)
    summary, *_ = run.run(repo.root, repo.db, dict(intent="PAYCALC1"), str(runs / "a2"), write=fake_write)
    assert ("claude", "extract") in sent and summary["checked"] == 1
