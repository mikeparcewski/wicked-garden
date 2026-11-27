"""garden#1601: a stored target or rule group made by another version of the pipeline is made again, so an upgrade that
changes what is stated reaches a store kept across it; unchanged code under the same pipeline still makes 0 calls.
Fixtures: the mini-cobol estate of ``test_v3_store.py``, run through the real ``run.run`` with its scripted seats."""
import json
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


def test_a_refresh_the_writer_leaves_unaccounted_keeps_the_stored_record_and_is_tried_again(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    monkeypatch.setattr(store, "STATING", "0" * 16)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    before = stored(repo.db)
    monkeypatch.setattr(store, "STATING", pipeline_now)
    # the upgraded writer answers nothing usable (and its M repair neither)
    monkeypatch.setattr(model_calls, "claude", lambda step, *a, **k: ("{}", 0) if step != "prose" else seats.claude(step, *a, **k))
    lines = []
    second, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    after = stored(repo.db)
    n = len(S["targets"])
    ok = {r["target"] for r in before[store.TARGET].values() if not (r.get("state") or {}).get("unaccounted")}
    # the scripted writer leaves MAIN-PARA unaccounted from the start, with a refused not-rule: kept too, as it said
    # nothing new at all
    assert 0 < len(ok) < n
    assert any(f"{n} targets the new pipeline left unaccounted kept as stored" in ln for ln in lines), lines
    assert {k: (v["status"], v["contract"]["claims"]) for k, v in after[store.RULE].items()} == \
        {k: (v["status"], v["contract"]["claims"]) for k, v in before[store.RULE].items()}
    assert {r["pipeline"] for r in after[store.TARGET].values()} == {"0" * 16}
    assert {r["target"] for r in after[store.TARGET].values() if not (r.get("state") or {}).get("unaccounted")} == ok
    # the next run, with a writer that answers, states them under the current version
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    third, *_ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run3"), write=fake_write)
    assert third["reuse"]["extract"] == n and {r["pipeline"] for r in stored(repo.db)[store.TARGET].values()} == {store.STATING}


def test_a_target_a_person_confirmed_stays_as_stored_and_says_so_every_run(tmp_path, monkeypatch):
    from tests.domain.test_v3_rulings import RulingSeats, by_text, rule, target_row
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = RulingSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    monkeypatch.setattr(store, "STATING", "0" * 16)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    monkeypatch.setattr(store, "STATING", pipeline_now)
    sid, bad = by_text(repo.db, "`PAY-AMOUNT` is set to zero")
    read = target_row(repo.db, "READ-PARA")
    rule(repo.db, "statement", sid, "confirm", read["anchor_symbol"],
         statement_key=store.statement_key(bad["contract"]), target_hash=read["target_hash"])
    for k in (2, 3):
        seats.prompts, lines = [], []
        run.run(repo.root, repo.db, scope_in, str(tmp_path / f"run{k}"), log=lines.append, write=fake_write)
        assert not [p for st, p in seats.prompts if st == "extract" and f'"target": "{read["target"]}"' in p]
        assert any("1 targets stored by an earlier version of the pipeline kept as they are: a person's confirm holds them"
                   in ln for ln in lines), lines
        now = target_row(repo.db, "READ-PARA")
        assert now["pipeline"] == "0" * 16 and now["target_hash"] == read["target_hash"]
        assert by_text(repo.db, "`PAY-AMOUNT` is set to zero")[1]["status"] == "open"


class PartSeats(FakeSeats):
    """FakeSeats, but READ-PARA's statement is anchored on lines 24-28 only: Checked, with 20-23 and 29 unaccounted."""

    def claude(self, step, cid, prompt, timeout=1500, role=None, **kw):
        out, rc = super().claude(step, cid, prompt, timeout, role, **kw)
        if step != "extract":
            return out, rc
        j = json.loads(out)
        for t in j["targets"]:
            for st in t["statements"]:
                st["anchor"]["lines"] = [24, 28]
        return json.dumps(j), 0


def test_a_failed_refresh_never_empties_a_partly_accounted_target_of_its_checked_statement(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = PartSeats(S)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    monkeypatch.setattr(store, "STATING", "0" * 16)
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), write=fake_write)
    read = next(r for r in stored(repo.db)[store.TARGET].values() if r["target"].endswith("#READ-PARA()."))
    rules = stored(repo.db)[store.RULE]
    assert read["state"]["unaccounted"] and [rules[i]["status"] for i in read["statements"]] == ["Checked"]
    monkeypatch.setattr(store, "STATING", pipeline_now)
    monkeypatch.setattr(model_calls, "claude", lambda step, *a, **k: ("{}", 0) if step != "prose" else seats.claude(step, *a, **k))
    run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), write=fake_write)
    now = next(r for r in stored(repo.db)[store.TARGET].values() if r["target"].endswith("#READ-PARA()."))
    assert now["pipeline"] == "0" * 16 and now["statements"] == read["statements"]
    assert [stored(repo.db)[store.RULE][i]["status"] for i in now["statements"]] == ["Checked"]


pipeline_now = store.STATING
