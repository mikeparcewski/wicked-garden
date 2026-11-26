"""J6 v3 persistence and reuse (DES-j6-build G4; v1 §3.8), 0 real model calls.

The trees are copies of ``fixtures/v3`` (so a case can edit them), with the store loaded from ``<tree>.sql``
(``wicked-estate index`` 0.35.10) plus that version's ``annotations`` table, whose DDL below is copied from a store the
same binary made. Writes go through :func:`fake_write`, which applies a ``write-batch`` row as 0.35.10 does (one row
per node and key; ``replace`` overwrites it, measured: ``{"rows":1,"annotations":1,"replaced":1}``). When
``wicked-estate`` is on PATH, :func:`test_the_real_writer_round_trips_a_run` writes through the real binary instead.
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess

import pytest

from domain import batches, graph, model_calls, run, scope, store

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "v3")
PROG = "app/cbl/PAYCALC1.cbl"

# `wicked-estate index` 0.35.10's annotations table, as `sqlite_master.sql` shows it.
ANNOTATIONS_DDL = """CREATE TABLE annotations (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  node_sym          INTEGER NOT NULL,
  key               TEXT NOT NULL,
  value             TEXT NOT NULL,
  confidence        REAL    NOT NULL DEFAULT 1.0,
  provenance        TEXT    NOT NULL DEFAULT '',
  author            TEXT    NOT NULL DEFAULT '',
  ts                INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
  type              TEXT    NOT NULL DEFAULT 'note',
  source_type       TEXT    NOT NULL DEFAULT 'unspecified',
  extraction_method TEXT    NOT NULL DEFAULT 'manual',
  last_verified     INTEGER NOT NULL DEFAULT 0
)"""


def make_repo(tmp_path, name, tag="a"):
    tree = tmp_path / f"{name}-{tag}"
    if not tree.exists():
        shutil.copytree(os.path.join(FIX, name), tree)
    db = tmp_path / f"{name}.db"
    if not db.exists():
        con = sqlite3.connect(db)
        with open(os.path.join(FIX, f"{name}.sql")) as fh:
            con.executescript(fh.read())
        con.executescript(ANNOTATIONS_DDL)
        con.commit()
        con.close()
    return graph.Repo(str(tree), str(db))


def fake_write(db, rows):
    con = sqlite3.connect(db)
    sym = {json.loads(d)["symbol"]: s for s, d in con.execute("select symbol, data from nodes")}
    replaced = 0
    for r in rows:
        node = sym[r["symbol"]]  # write-batch refuses a symbol that is not a node
        if r.get("replace"):
            replaced += con.execute("delete from annotations where node_sym = ? and key = ?", (node, r["key"])).rowcount
        con.execute("insert into annotations (node_sym, key, value, type, author) values (?, ?, ?, ?, ?)",
                    (node, r["key"], r["value"], r.get("type", "note"), r.get("author", "")))
    con.commit()
    con.close()
    return dict(rows=len(rows), annotations=len(rows), replaced=replaced)


def edit(repo, f, fn):
    p = os.path.join(repo.root, f)
    with open(p, "rb") as fh:
        L = fh.read().split(b"\n")
    with open(p, "wb") as fh:
        fh.write(b"\n".join(fn(L)))


# ---------------- the six invalidation cases (v1 §10 step 10) ----------------
def cobol_statement():
    return dict(id="t#0", anchor=dict(file=PROG, lines=[20, 29]),
                claims=[dict(i=0, type="trigger", text="performed until `WS-EOF = 'Y'`", lines=[f"{PROG}:17"]),
                        dict(i=1, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"]),
                        dict(i=2, type="effect", text="`PAY-AMOUNT` gets the overtime rate", when=[1], lines=[f"{PROG}:25-26"])])


def record_for(repo, S, C, t, st):
    call = next(c for c in C["calls"] if t["id"] in c["targets"])
    return store.target_record(repo, t, call, [st], [], {}, store._unit_spans(repo), S["targets"])


@pytest.mark.parametrize("case, change, decision", [
    ("unchanged", None, "carry"),
    ("1 an edit to a cited line", lambda L: L[:23] + [L[23].replace(b"> 40", b"> 45")] + L[24:], "extract"),
    ("2 an IF added around an effect, inside the target, on no cited line",
     lambda L: L[:24] + [b"           IF WS-EOF = 'N'"] + L[24:26] + [b"           END-IF"] + L[26:], "extract"),
    ("3 a change in column 1 of a target line", lambda L: L[:20] + [b"9" + L[20][1:]] + L[21:], "extract"),
    ("5 the cited caller's trigger inverted, in another paragraph",
     lambda L: L[:16] + [L[16].replace(b"'Y'", b"'N'")] + L[17:], "extract"),
    ("6 a change in the same file outside every cited unit",
     lambda L: L[:13] + [b"       01  WS-COUNT                PIC 9 VALUE 0."] + L[13:], "revalidate"),
])
def test_an_invalidation_case_is_never_reused(tmp_path, case, change, decision):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    t = next(x for x in S["targets"] if x.get("name") == "READ-PARA")
    st = cobol_statement()
    rec = record_for(repo, S, C, t, st)
    if change:
        edit(repo, PROG, change)
    again = graph.Repo(repo.root, repo.db)
    d, moves = store.decide(again, rec)
    assert d == decision, case
    if d == "revalidate":
        moved = store.relocate(st, moves)
        assert moved["anchor"]["lines"] == [21, 30]
        assert [c["lines"] for c in moved["claims"]] == [[f"{PROG}:18"], [f"{PROG}:25"], [f"{PROG}:26-27"]]


def test_whitespace_inside_a_literal_of_a_cited_definition_is_never_reused(tmp_path):
    """Case 4 (the proof's was a trailing space in a JS template literal): exact bytes, no normalization."""
    repo = make_repo(tmp_path, "mini-ts")
    S = scope.build_scope(repo, "x", ["launch posture"])
    C = batches.plan_batches(repo, S, str(tmp_path / "b"))
    f = "src/core/launch-posture.ts"
    t = next(x for x in S["targets"] if x.get("name") == "launchPosture")
    st = dict(id="t#0", anchor=dict(file=f, lines=t["lines"]),
              claims=[dict(i=0, type="condition", text="`spec.power` and `WICKED_POWER` is `'1'`", lines=[f"{f}:4"]),
                      dict(i=1, type="value", text="otherwise `PHASED`", lines=[f"{f}:7"])],
              context=[dict(name="PHASED", at=f"{f}:1")])
    rec = record_for(repo, S, C, t, st)
    assert store.decide(graph.Repo(repo.root, repo.db), rec)[0] == "carry"
    edit(repo, f, lambda L: [L[0].replace(b"'phased'", b"'phased '")] + L[1:])
    assert store.decide(graph.Repo(repo.root, repo.db), rec)[0] == "extract"


# ---------------- a whole run, twice ----------------
class FakeSeats:
    """Answers each step as a writer and a checker would, in their output shapes, and counts the calls."""

    def __init__(self, S):
        self.S, self.n = S, 0

    def claude(self, step, cid, prompt, timeout=1500, role=None, **kw):
        self.n += 1
        if step == "extract":
            out = []
            for t in self.S["targets"]:
                if f'"target": "{t["id"]}"' not in prompt:
                    continue
                if t.get("name") == "READ-PARA":
                    out.append(dict(target=t["id"], not_rules=[], statements=[dict(anchor=dict(file=PROG, lines=t["lines"]), claims=[
                        dict(i=0, type="condition", text="`PAY-HOURS > 40`", lines=[f"{PROG}:24"]),
                        dict(i=1, type="effect", text="`PAY-AMOUNT` gets the overtime rate", when=[0], lines=[f"{PROG}:25-26"]),
                        dict(i=2, type="else", text="`PAY-AMOUNT` is `PAY-RATE * PAY-HOURS`", lines=[f"{PROG}:27-28"])])]))
                else:
                    a, b = t["lines"]
                    out.append(dict(target=t["id"], statements=[], not_rules=[dict(lines=f"{t['file']}:{a}-{b}", reason="control-only")]))
            return json.dumps(dict(targets=out)), 0
        if step == "prose":
            sids = sorted(set(re.findall(r"^\[(S\d+)\]$", prompt, re.M)), key=lambda s: int(s[1:]))
            return json.dumps(dict(groups=[dict(g=1, title="Overtime pay", area="PAYCALC1", kind="business",
                                                rule=dict(text="Hours over forty are paid at the overtime rate.", cites=sids),
                                                details=[])])), 0
        return "{}", 0

    def codex(self, step, cid, prompt, timeout=1500, role=None):
        self.n += 1
        if step.startswith("check") or step.startswith("recheck"):
            res = []
            for ln in prompt.splitlines():
                if ln.startswith('{"n":'):
                    it = json.loads(ln)
                    res.append(dict(n=it["n"], claims=[dict(i=c["i"], verdict="SUPPORTED") for c in it["claims"]]))
            return json.dumps(dict(results=res)), 0
        if step.startswith("prose"):
            ids = re.findall(r"^\[(g\d+\.\w+)\]", prompt, re.M)
            return json.dumps(dict(verdicts=[dict(id=i, verdict="SUPPORTED") for i in ids])), 0
        return "{}", 0


def stored(db):
    got = store.load(db)
    return {t: dict(sorted(v.items())) for t, v in got.items()}


def test_an_unchanged_rerun_makes_no_model_call_and_writes_the_same_model(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", scope_hash=S["scope_hash"], description="payroll")
    lines = []
    first, R1, groups1, _ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run1"), log=lines.append, write=fake_write)
    assert seats.n > 0 and first["checked"] >= 1, first
    assert first["reuse"]["carry"] == 0
    model1 = stored(repo.db)
    assert model1[store.RULE] and model1[store.TARGET] and model1[store.GROUP]
    seats.n = 0
    second, R2, groups2, _ = run.run(repo.root, repo.db, scope_in, str(tmp_path / "run2"), log=lines.append, write=fake_write)
    assert seats.n == 0 and second["model_calls"] == 0, second
    assert second["reuse"] == dict(carry=len(S["targets"]), revalidate=0, extract=0)
    assert second["prose_reused"] and groups2 == groups1
    assert stored(repo.db) == model1, "the re-run changed the stored model"
    assert any(x.startswith("reuse · ") for x in lines) and lines[-1].endswith("0 model calls")


def test_a_stale_scope_is_refused_before_any_call(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "mini-cobol")
    seats = FakeSeats(scope.build_scope(repo, "PAYCALC1"))
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    with pytest.raises(run.Refused, match="code changed since the preview"):
        run.run(repo.root, repo.db, dict(intent="PAYCALC1", scope_hash="0" * 64), str(tmp_path / "r"), write=fake_write)
    assert seats.n == 0


def test_a_record_the_next_run_no_longer_has_is_retired(tmp_path):
    repo = make_repo(tmp_path, "mini-cobol")
    S = scope.build_scope(repo, "PAYCALC1")
    sym = next(t["anchor_symbol"] for t in S["targets"] if t.get("name") == "READ-PARA")
    fake_write(repo.db, [dict(op="annotate", symbol=sym, key="business_rule:old#0", value=json.dumps(dict(status="Checked")),
                              type=store.RULE, replace=True)])
    prior = store.load_symbols(repo.db, store.load(repo.db))
    assert "old#0" in prior[store.RULE]
    rows, _ = store.rows_for(repo, dict(statements=[]), [], [], "h", [], prior, str)
    assert rows == [dict(op="annotate", symbol=sym, key="business_rule:old#0", value=json.dumps(dict(status="retired")),
                         type=store.RULE, author=store.AUTHOR, replace=True)]
    fake_write(repo.db, rows)
    assert "old#0" not in store.load(repo.db)[store.RULE]


@pytest.mark.skipif(shutil.which("wicked-estate") is None, reason="wicked-estate is not installed")
def test_the_real_writer_round_trips_a_run(tmp_path, monkeypatch):
    """The real route: a store `wicked-estate index` made, a run written by `wicked-estate write-batch`, read back."""
    tree = tmp_path / "mini-cobol"
    shutil.copytree(os.path.join(FIX, "mini-cobol"), tree)
    db = str(tmp_path / "real.db")
    env = dict(os.environ, HOME=str(tmp_path / "home"), WICKED_HOME=str(tmp_path / "wh"))
    subprocess.run(["wicked-estate", "index", str(tree), "--db", db], check=True, capture_output=True, env=env)
    for k in ("HOME", "WICKED_HOME"):
        monkeypatch.setenv(k, env[k])
    repo = graph.Repo(str(tree), db)
    S = scope.build_scope(repo, "PAYCALC1")
    seats = FakeSeats(S)
    monkeypatch.setattr(model_calls, "claude", seats.claude)
    monkeypatch.setattr(model_calls, "codex", seats.codex)
    scope_in = dict(intent="PAYCALC1", description="payroll")
    first, _, _, _ = run.run(str(tree), db, scope_in, str(tmp_path / "run1"), log=lambda s: None)
    assert first["store"]["rows"] > 0 and first["unplaced"] == [], first
    model1 = stored(db)
    seats.n = 0
    second, _, _, _ = run.run(str(tree), db, scope_in, str(tmp_path / "run2"), log=lambda s: None)
    # every row is replaced but the run's own record, which is new per run (domain_run:<run id>)
    assert seats.n == 0 and second["store"]["replaced"] == second["store"]["rows"] - 1
    assert stored(db) == model1
