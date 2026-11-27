"""garden#1601 (DES-1601, coord option (b)): each stored target and rule group carries the version of the pipeline that
made it; a run over a store made by an earlier version carries it and says how many targets and groups an earlier
version made. garden#1613 (DES-1613): after the store, those targets are stated again and adopted when none is worse
(``test_v3_refresh.py``). Fixtures: the mini-cobol estate of ``test_v3_store.py``, run
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
def test_a_store_an_earlier_stating_pipeline_made_is_carried_said_and_refreshed_once(tmp_path, monkeypatch, old):
    S, out = _runs(tmp_path, monkeypatch, dict(STATING=old), more=2)
    n = len(S["targets"])
    (calls, lines, summary, model), (calls2, lines2, summary2, model2) = out
    assert summary["reuse"] == dict(carry=n, revalidate=0, extract=0), summary
    assert any(f"{n} targets were stated by an earlier pipeline version · {n} are stated again after the store" in ln
               for ln in lines), lines
    # garden#1613: the refresh states them again and the store takes them (the scripted seats answer as before)
    assert calls > 0 and summary["refresh"]["adopted"] == n and summary["earlier_pipeline"] == dict(targets=0, groups=0)
    assert {r.get("pipeline") for r in model[store.TARGET].values()} == {store.STATING}
    assert calls2 == 0 and summary2["refresh"]["eligible"] == 0 and summary2["earlier_pipeline"] == dict(targets=0, groups=0)
    assert not any("earlier pipeline version" in ln for ln in lines2), lines2


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


# a manifest whose versions main computed before HOST existed (garden#1601's algorithm): HOST 0 must keep them
LEGACY_SUMS = "a" * 64 + "  prompts/extract.txt\n" + "b" * 64 + "  cards/cobol.md\n" + "c" * 64 + "  prompts/prose.txt\n"
LEGACY = ("dc58274e6a2d4d1e", "030e0e3b449a5cae")


def test_a_host_bump_moves_only_the_stating_version_and_host_zero_keeps_the_versions_stores_already_carry(tmp_path):
    # garden#1610: identity. HOST 0 is the version every store made before HOST existed carries; each bump is a new one.
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(LEGACY_SUMS)
    assert store.pipeline_versions(str(sums), host=0, prose_host=0) == LEGACY
    ids = [store.pipeline_versions(str(sums), host=h, prose_host=0) for h in (0, 1, 2)]
    assert len({v[0] for v in ids}) == 3 and {v[1] for v in ids} == {LEGACY[1]}, "a host bump never moves the prose version"
    assert store.pipeline_versions(SUMS) == store.pipeline_versions(SUMS, host=store.HOST) == NOW
    for bad in (-1, "1", True, 1.0):
        with pytest.raises(ValueError):
            store.pipeline_versions(str(sums), host=bad)


def test_a_store_the_previous_host_code_stated_is_reported_after_a_host_bump(tmp_path, monkeypatch):
    # garden#1610: a stale read. The store was stated under the current HOST; a host-only upgrade bumps it, and the run
    # says its targets were stated by an earlier pipeline version (main kept the old extraction as current); garden#1613
    # then states them again. Groups carry the prose version (run.py prose_for), which a host bump does not move.
    before = store.pipeline_versions(SUMS, host=store.HOST)
    bumped = store.pipeline_versions(SUMS, host=store.HOST + 1)
    monkeypatch.setattr(store, "HOST", store.HOST + 1)
    assert store.pipeline_versions(SUMS) == bumped, "the version follows store.HOST (store.STATING is it at import)"
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    monkeypatch.setattr(store, "STATING", before[0])
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    monkeypatch.setattr(store, "STATING", bumped[0])
    seats.n, lines = 0, []
    summary, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    n = len(S["targets"])
    assert any(f"{n} targets were stated by an earlier pipeline version" in ln for ln in lines), lines
    assert summary["refresh"]["eligible"] == n and summary["refresh"]["adopted"] == n and seats.n > 0
    assert summary["earlier_pipeline"] == dict(targets=0, groups=0)


def test_a_prose_host_bump_moves_only_the_prose_version_and_zero_keeps_the_versions_stores_already_carry(tmp_path):
    # garden#1625: the prose half of garden#1610
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(LEGACY_SUMS)
    assert store.pipeline_versions(str(sums), host=0, prose_host=0) == LEGACY
    got = [store.pipeline_versions(str(sums), host=0, prose_host=k) for k in (0, 1, 2)]
    assert len({p for _, p in got}) == 3 and {s for s, _ in got} == {LEGACY[0]}
    # round 1 on garden#1628: these oracles hold whatever the shipped counters are (a real bump sets them above 0)
    assert store.pipeline_versions(str(sums), host=1, prose_host=1)[0] == store.pipeline_versions(str(sums), host=1)[0]
    assert store.pipeline_versions(SUMS) == store.pipeline_versions(SUMS, prose_host=store.PROSE_HOST) == NOW
    for bad in (-1, "1", True, 1.0):
        with pytest.raises(ValueError, match="PROSE_HOST"):
            store.pipeline_versions(str(sums), prose_host=bad)


def test_groups_the_previous_prose_host_code_wrote_are_reported_after_a_prose_host_bump(tmp_path, monkeypatch):
    # garden#1625: a stale read. Main kept a group the old prose.py wrote as current; after a bump the run says an
    # earlier prose version wrote it (reused as before, DES-1601), and the targets are not reported
    before = store.pipeline_versions(SUMS, prose_host=store.PROSE_HOST)
    bumped = store.pipeline_versions(SUMS, prose_host=store.PROSE_HOST + 1)
    assert bumped[0] == before[0] and bumped[1] != before[1]
    monkeypatch.setattr(store, "PROSE_HOST", store.PROSE_HOST + 1)
    assert store.pipeline_versions(SUMS) == bumped
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    monkeypatch.setattr(store, "PROSE", before[1])
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    monkeypatch.setattr(store, "PROSE", bumped[1])
    seats.n = 0
    summary, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lambda s: None, write=fake_write)
    groups = stored(repo.db)[store.GROUP]
    assert groups and summary["earlier_pipeline"] == dict(targets=0, groups=len(groups)) and seats.n == 0
    assert {g["pipeline"] for g in groups.values()} == {before[1]}


def test_the_version_oracles_hold_with_both_counters_shipped_above_zero(tmp_path, monkeypatch):
    # round 1 on garden#1628: a real bump ships HOST or PROSE_HOST above 0; the oracles name both counters explicitly
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(LEGACY_SUMS)
    monkeypatch.setattr(store, "HOST", 3)
    monkeypatch.setattr(store, "PROSE_HOST", 3)
    assert store.pipeline_versions(str(sums), host=0, prose_host=0) == LEGACY
    shipped = store.pipeline_versions(str(sums))
    assert shipped[0] != LEGACY[0] and shipped[1] != LEGACY[1]
    assert shipped == store.pipeline_versions(str(sums), host=3, prose_host=3)
