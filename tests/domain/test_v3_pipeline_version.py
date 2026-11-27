"""garden#1601: a stored target or rule group made by another version of the pipeline is made again, so an upgrade that
changes what is stated reaches a store kept across it; unchanged code under the same pipeline still makes 0 calls.
Fixtures: the mini-cobol estate of ``test_v3_store.py``, run through the real ``run.run`` with its scripted seats."""
import os

import pytest

from domain import model_calls, run, scope, store
from tests.domain.test_v3_store import FakeSeats, fake_write, make_repo, stored

SUMS = os.path.join(os.path.dirname(store.__file__), "SHA256SUMS")


def _two_runs(tmp_path, monkeypatch, first):
    """Run once with ``first`` (attribute -> value) set on ``store``, then once with the real versions."""
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats, steps = FakeSeats(S), []
    monkeypatch.setattr(model_calls, "claude", lambda step, *a, **k: steps.append(step) or seats.claude(step, *a, **k))
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    real = {k: getattr(store, k) for k in first}
    for k, v in first.items():
        monkeypatch.setattr(store, k, v)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    for k, v in real.items():
        monkeypatch.setattr(store, k, v)
    seats.n, steps[:], lines = 0, [], []
    second, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    return S, seats, steps, lines, second, stored(repo.db)


@pytest.mark.parametrize("old", [None, "0" * 16])  # a store from before versions were kept; one from another version
def test_a_target_stored_by_another_stating_pipeline_is_extracted_again(tmp_path, monkeypatch, old):
    S, seats, steps, lines, second, model = _two_runs(tmp_path, monkeypatch, dict(STATING=old))
    n = len(S["targets"])
    assert second["reuse"] == dict(carry=0, revalidate=0, extract=n), second
    assert "extract" in steps and seats.n > 0
    assert any(f"{n} to extract ({n} stored by an earlier version of the pipeline)" in ln for ln in lines), lines
    assert {r["pipeline"] for r in model[store.TARGET].values()} == {store.STATING}


def test_a_prose_only_change_rewrites_the_groups_and_extracts_nothing(tmp_path, monkeypatch):
    S, seats, steps, lines, second, model = _two_runs(tmp_path, monkeypatch, dict(PROSE="0" * 16))
    assert second["reuse"] == dict(carry=len(S["targets"]), revalidate=0, extract=0), second
    assert not second["prose_reused"] and "prose" in steps and "extract" not in steps
    assert {g["pipeline"] for g in model[store.GROUP].values()} == {store.PROSE}


def test_the_same_pipeline_on_unchanged_code_makes_no_call(tmp_path, monkeypatch):
    S, seats, steps, lines, second, model = _two_runs(tmp_path, monkeypatch, {})
    assert seats.n == 0 and second["prose_reused"] and second["reuse"]["carry"] == len(S["targets"])


def test_a_prose_file_moves_only_the_prose_version_and_any_other_only_the_stating_one(tmp_path):
    with open(SUMS) as fh:
        lines = fh.read().splitlines()
    assert store.pipeline_versions(SUMS) == (store.STATING, store.PROSE)

    def bumped(name):
        p = tmp_path / name.replace("/", "_")
        p.write_text("\n".join(("f" * 64 + "  " + ln.split()[1]) if ln.split()[1] == name else ln for ln in lines) + "\n")
        return store.pipeline_versions(str(p))
    stating, prose = bumped("prompts/prose_check.txt")
    assert stating == store.STATING and prose != store.PROSE
    stating, prose = bumped("cards/cobol.md")
    assert stating != store.STATING and prose == store.PROSE
