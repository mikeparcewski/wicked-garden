"""garden#1604: a statement's rendered text names each copybook field it uses with the line that declares it, as the host
resolved it (``extract.cite_copybooks``, ``by: "host"``); a model's own context entry is never shown as fact. Fixtures:
the mini-cobol estate of ``test_v3_store.py`` (``app/cpy/PAYREC.cpy``: PAY-HOURS on line 3, PAY-RATE 4, PAY-AMOUNT 5)
through the real ``run.run`` with its scripted seats."""
import os

from domain import extract, graph, lookup, model_calls, render, run, scope, store
from tests.domain.test_v3_store import PROG, FakeSeats, fake_write, make_repo, stored

CPY = "app/cpy/PAYREC.cpy"


def test_the_stored_statement_and_the_writers_input_name_each_copybook_field_with_its_line(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats, prompts = FakeSeats(S), []
    monkeypatch.setattr(model_calls, "claude", lambda step, cid, prompt, *a, **k: prompts.append((step, prompt)) or seats.claude(step, cid, prompt, *a, **k))
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1", description="payroll"), str(tmp_path / "r1"), write=fake_write)
    rule = next(v for v in stored(repo.db)[store.RULE].values() if v["contract"]["anchor"]["file"] == PROG)
    # the scripted claims name PAY-HOURS, PAY-AMOUNT and PAY-RATE, in that order
    row = f"- Uses: `PAY-HOURS` ({CPY}:3), `PAY-AMOUNT` ({CPY}:5), `PAY-RATE` ({CPY}:4)"
    assert rule["statement"].splitlines()[1] == row, rule["statement"]
    assert any(step == "prose" and row in p for step, p in prompts)  # the prose writer reads it too


def _resolved(tmp_path, context, claims_text, cpy=None):
    repo = make_repo(tmp_path, "mini-cobol")
    if cpy:
        with open(os.path.join(repo.root, CPY), "a") as fh:
            fh.write(cpy)
        repo = graph.Repo(repo.root, repo.db)
    lookup.use_repo(repo)
    st = dict(anchor=dict(file=PROG, lines=[20, 29]), context=context,
              claims=[dict(i=0, type="effect", text=claims_text, lines=[f"{PROG}:25"])])
    return extract.cite_copybooks(st)


def test_a_line_the_model_gave_for_a_copybook_field_is_replaced_by_the_declaring_line(tmp_path):
    st = _resolved(tmp_path, [dict(symbol="PAY-HOURS", at=f"{CPY}:5"), dict(symbol="WS-OTHER", at="app/cpy/X.cpy:1")],
                   "`PAY-HOURS` is added")
    assert st["context"] == [dict(symbol="PAY-HOURS", at=f"{CPY}:3", by="host"), dict(symbol="WS-OTHER", at="app/cpy/X.cpy:1")]
    assert render.render(st, "P").splitlines()[1] == f"- Uses: `PAY-HOURS` ({CPY}:3)"  # the model's own entry is not shown


def test_an_88_level_name_is_cited_at_its_own_line_not_its_parents(tmp_path):
    st = _resolved(tmp_path, [], "`PAY-OK` is true", cpy="           05  PAY-FLAG            PIC X.\n               88  PAY-OK          VALUE 'Y'.\n")
    assert st["context"] == [dict(symbol="PAY-OK", at=f"{CPY}:7", by="host")]


def test_a_statement_with_no_host_resolved_context_renders_as_before():
    st = dict(anchor=dict(file="a.ts", lines=[1, 4]), claims=[dict(i=0, type="effect", text="`x` is set", lines=["a.ts:2"])])
    before = render.render(st, "f")
    for ctx in (None, [], "bad", ["x"], [dict(symbol="x", at="a.ts:1")], [dict(symbol="x", by="host")],
                [dict(symbol="x", at="  ", by="host")], [dict(symbol="  ", at="a.ts:1", by="host")], [dict(at="a.ts:1", by="host")]):
        assert render.render(dict(st, context=ctx), "f") == before, ctx
    assert "Uses" not in before


def test_a_repeated_entry_is_named_once_in_stored_order():
    st = dict(anchor=dict(file="P.cbl", lines=[1, 4]), claims=[],
              context=[dict(symbol="B", at="c/X.cpy:2", by="host"), dict(symbol="A", at="c/X.cpy:1", by="host"),
                       dict(symbol="B", at="c/X.cpy:2", by="host")])
    assert render.render(st, "P").splitlines()[1] == "- Uses: `B` (c/X.cpy:2), `A` (c/X.cpy:1)"
