"""garden#1601 (DES-1601, coord option (b)): each stored target and rule group carries the version of the pipeline that
made it; a run over a store made by an earlier version carries it as today and says how many targets and groups an
earlier version made (a fresh store makes them again). Fixtures: the mini-cobol estate of ``test_v3_store.py``, run
through the real ``run.run`` with its scripted seats."""
import os

import pytest

from domain import model_calls, run, scope, store
from tests.domain.test_v3_store import FakeSeats, fake_write, make_repo, stored

SUMS = os.path.join(os.path.dirname(store.__file__), "SHA256SUMS")
NOW = (store.STATING, store.PROSE)


def _runs(tmp_path, monkeypatch, first, more=1):
    """Run once with ``first`` (attribute -> value) set on ``store``, then ``more`` times with the real versions."""
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    for k, v in first.items():
        monkeypatch.setattr(store, k, v)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    monkeypatch.setattr(store, "STATING", NOW[0])
    monkeypatch.setattr(store, "PROSE", NOW[1])
    out = []
    for k in range(more):
        seats.n, lines = 0, []
        summary, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / f"run{k + 2}"), log=lines.append, write=fake_write)
        out.append((seats.n, lines, summary, stored(repo.db)))
    return S, out


@pytest.mark.parametrize("old", [None, "0" * 16])  # a store from before versions were kept; one from another version
def test_a_store_an_earlier_stating_pipeline_made_is_carried_and_the_run_says_so_every_time(tmp_path, monkeypatch, old):
    S, out = _runs(tmp_path, monkeypatch, dict(STATING=old), more=2)
    n = len(S["targets"])
    for calls, lines, summary, model in out:
        assert calls == 0 and summary["reuse"] == dict(carry=n, revalidate=0, extract=0), summary
        assert summary["earlier_pipeline"] == dict(targets=n, groups=0)
        assert any(f"{n} targets were stated by an earlier pipeline version; a fresh store states them with this one" in ln
                   for ln in lines), lines
        assert {r.get("pipeline") for r in model[store.TARGET].values()} == {old}  # kept: the next run says it again


def test_groups_an_earlier_prose_pipeline_wrote_are_reused_and_counted(tmp_path, monkeypatch):
    S, out = _runs(tmp_path, monkeypatch, dict(PROSE="0" * 16), more=2)
    for calls, lines, summary, model in out:
        groups = model[store.GROUP]
        assert calls == 0 and summary["prose_reused"] and groups
        assert summary["earlier_pipeline"] == dict(targets=0, groups=len(groups))
        assert {g["pipeline"] for g in groups.values()} == {"0" * 16}


def test_a_store_this_pipeline_made_reports_nothing_and_makes_no_call(tmp_path, monkeypatch):
    S, out = _runs(tmp_path, monkeypatch, {})
    calls, lines, summary, model = out[0]
    assert calls == 0 and summary["earlier_pipeline"] == dict(targets=0, groups=0)
    assert not any("earlier pipeline version" in ln for ln in lines)
    assert {r["pipeline"] for r in model[store.TARGET].values()} == {store.STATING}
    assert {g["pipeline"] for g in model[store.GROUP].values()} == {store.PROSE}


def test_a_prose_file_moves_only_the_prose_version_and_any_other_only_the_stating_one(tmp_path):
    with open(SUMS) as fh:
        lines = fh.read().splitlines()
    assert store.pipeline_versions(SUMS) == NOW

    def bumped(name):
        p = tmp_path / name.replace("/", "_")
        p.write_text("\n".join(("f" * 64 + "  " + ln.split()[1]) if ln.split()[1] == name else ln for ln in lines) + "\n")
        return store.pipeline_versions(str(p))
    stating, prose = bumped("prompts/prose_check.txt")
    assert stating == NOW[0] and prose != NOW[1]
    stating, prose = bumped("cards/cobol.md")
    assert stating != NOW[0] and prose == NOW[1]
