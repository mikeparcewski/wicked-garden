"""garden#1604: a statement's rendered text names the definitions its ``context`` holds (a copybook field's line, put
there by ``extract.cite_copybooks``), so the text a person reads shows the copybook it uses. Fixtures: the mini-cobol
estate of ``test_v3_store.py`` through the real ``run.run`` with its scripted seats."""
import re

from domain import model_calls, render, run, scope, store
from tests.domain.test_v3_store import PROG, FakeSeats, fake_write, make_repo, stored


def test_the_stored_statement_and_the_writers_input_name_each_copybook_field_with_its_line(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats, prompts = FakeSeats(S), []
    monkeypatch.setattr(model_calls, "claude", lambda step, cid, prompt, *a, **k: prompts.append((step, prompt)) or seats.claude(step, cid, prompt, *a, **k))
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    run.run(repo.root, repo.db, dict(intent="PAYCALC1", description="payroll"), str(tmp_path / "r1"), write=fake_write)
    rule = next(v for v in stored(repo.db)[store.RULE].values() if v["contract"]["anchor"]["file"] == PROG)
    ctx = rule["contract"]["context"]
    assert ctx and all(x["at"].startswith("app/cpy/PAYREC.cpy:") for x in ctx), ctx  # cite_copybooks' own entries
    uses = [ln for ln in rule["statement"].splitlines() if ln.startswith("- Uses: ")]
    assert uses == ["- Uses: " + ", ".join(f"`{x['symbol']}` ({x['at']})" for x in ctx)]
    assert rule["statement"].splitlines()[1] == uses[0]  # right under "Runs:"
    assert any(step == "prose" and uses[0] in p for step, p in prompts)  # the prose writer reads it too


def test_a_statement_with_no_usable_context_renders_as_before():
    st = dict(anchor=dict(file="a.ts", lines=[1, 4]), claims=[dict(i=0, type="effect", text="`x` is set", lines=["a.ts:2"])])
    before = render.render(st, "f")
    for ctx in (None, [], "bad", [dict(symbol="x")], [dict(symbol="x", at="  ")], [{"at": "a.ts:1"}], ["x"]):
        assert render.render(dict(st, context=ctx), "f") == before
    assert not re.search(r"Uses", before)


def test_a_repeated_entry_is_named_once_in_stored_order():
    st = dict(anchor=dict(file="P.cbl", lines=[1, 4]), claims=[],
              context=[dict(symbol="B", at="c/X.cpy:2"), dict(symbol="A", at="c/X.cpy:1"), dict(symbol="B", at="c/X.cpy:2")])
    assert render.render(st, "P").splitlines()[1] == "- Uses: `B` (c/X.cpy:2), `A` (c/X.cpy:1)"
