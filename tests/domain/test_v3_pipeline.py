"""J6 v3 model calls and extract (DES-j6-build G2) on the tiny CardDemo-shaped tree, 0 real model calls.

``model_calls`` goes through ``wicked-core model-call``; here ``WICKED_CORE_BIN`` names a stand-in that answers
with its prompt, so the call log, the cache and the no-overwrite rule are exercised as the run uses them. The
scope and batches come from the real route (``scope.build_scope``, ``batches.plan_batches``) over the fixture
store. The port's equivalence with the proof's recorded runs (every extract, M-repair, C6, fetch, R, repair and
re-check prompt and result) is a lane check, since those runs are not in this repository.
"""
import json
import os
import sqlite3
import stat
import sys

import pytest

from domain import batches, extract, graph, model_calls, scope

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "v3")


@pytest.fixture
def core_bin(tmp_path, monkeypatch):
    """A stand-in `wicked-core`: `model-call --family F --in P --out O` writes `F: <prompt>`; exit 2 on `FAIL`."""
    log = tmp_path / "invocations.txt"
    script = tmp_path / "wicked-core"
    script.write_text(f"""#!{sys.executable}
import sys
a = sys.argv[1:]
open({str(log)!r}, "a").write(" ".join(a[:3]) + "\\n")
v = lambda k: a[a.index(k) + 1]
p = open(v("--in")).read()
if "FAIL" in p:
    sys.stderr.write("model-call: the seat failed\\n")
    sys.exit(2)
open(v("--out"), "w").write(v("--family") + ": " + p)
""")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv(model_calls.CORE_ENV, str(script))
    model_calls.configure(str(tmp_path / "calls"))
    return log


def test_a_call_is_logged_reused_when_identical_and_never_overwritten(core_bin, tmp_path):
    text, rc = model_calls.claude("extract", "c0", "write it")
    assert (text, rc) == ("claude: write it", 0)
    assert model_calls.claude("extract", "c0", "write it") == ("claude: write it", 0)
    assert core_bin.read_text().count("model-call") == 1, "the identical re-run reused the call"
    with pytest.raises(RuntimeError, match="different prompt"):
        model_calls.claude("extract", "c0", "write something else")
    rows = [json.loads(x) for x in (tmp_path / "calls" / "ledger.jsonl").read_text().splitlines()]
    assert [r["note"] for r in rows] == ["", "cache hit: reused the completed call"]
    assert rows[0]["role"] == "extractor" and rows[0]["provider"] == "claude"


def test_a_failed_call_returns_its_exit_code_and_keeps_its_stderr(core_bin, tmp_path):
    text, rc = model_calls.codex("check-a", "c0", "FAIL now")
    assert (text, rc) == ("", 2)
    assert "seat failed" in (tmp_path / "calls" / "check-a" / "c0.stderr.txt").read_text()
    assert not (tmp_path / "calls" / "check-a" / "c0.out.txt").exists()


@pytest.fixture
def cobol_run(tmp_path):
    db = tmp_path / "mini-cobol.db"
    con = sqlite3.connect(db)
    with open(os.path.join(FIX, "mini-cobol.sql")) as fh:
        con.executescript(fh.read())
    con.commit()
    con.close()
    repo = graph.Repo(os.path.join(FIX, "mini-cobol"), str(db))
    S = scope.build_scope(repo, "PAYCALC1")
    C = batches.plan_batches(repo, S, str(tmp_path / "batches"))
    return repo, S, C


def test_an_extract_answer_missing_a_target_gets_one_m_repair_with_the_failures(cobol_run, monkeypatch):
    repo, S, C = cobol_run
    sent = []

    def fake(step, cid, prompt, timeout=1500, role="extractor", **kw):
        sent.append((step, cid, prompt))
        return "{}", 0
    monkeypatch.setattr(model_calls, "claude", fake)
    res = extract.extract_all(repo, S, C)
    assert [s for s, _, _ in sent] == ["extract", "mrepair"]
    assert "target missing from output" in sent[1][2]
    assert res["m_repair_calls"] == 1 and res["statements"] == []
    assert all(t["unaccounted"] for t in res["targets"].values())


def test_the_machine_checks_refuse_a_citation_outside_the_batch_and_an_unshown_literal(cobol_run):
    repo, S, C = cobol_run
    call = C["calls"][0]
    t = next(x for x in S["targets"] if x["file"] == "app/cbl/PAYCALC1.cbl" and x.get("name") == "READ-PARA")
    f, (a, b) = t["file"], t["lines"]
    st = {"anchor": {"file": f, "lines": [a, b]},
          "claims": [{"i": 0, "type": "condition", "text": "`PAY-HOURS` is over `40`", "lines": [f"{f}:{a + 4}"]},
                     {"i": 1, "type": "value", "text": "the rate is `'DOUBLE'`", "lines": [f"{f}:{a + 4}"]},
                     {"i": 2, "type": "effect", "text": "it stops", "lines": ["app/cbl/OTHER.cbl:1"]}]}
    errs = extract.check_statement(repo, st, t, call)
    assert any("claim 2 line ref app/cbl/OTHER.cbl:1 is not inside the batch" in e for e in errs), errs
    assert any("claim 1 quotes the literal `DOUBLE`" in e for e in errs), errs
    assert not any("claim 0" in e for e in errs), errs


def test_the_proof_output_cap_reaches_the_writer_invocation_for_extract_and_m_repair(cobol_run, tmp_path, monkeypatch):
    """The proof ran its writer with a 64000-token answer cap (CLAUDE_CODE_MAX_OUTPUT_TOKENS); two of its extract
    answers were over 35K tokens. The port carries it on the model-call command line, for every writer call that
    answers a whole batch: extract and its M-repair."""
    repo, S, C = cobol_run
    model_calls.configure(str(tmp_path / "calls"))
    monkeypatch.setenv(model_calls.CORE_ENV, "wicked-core")
    argvs = []

    class Done:
        returncode, stderr = 0, ""

    def run(cmd, **kw):
        argvs.append(cmd)
        with open(cmd[cmd.index("--out") + 1], "w") as fh:
            fh.write("{}")
        return Done()
    monkeypatch.setattr(model_calls.subprocess, "run", run)
    extract.extract_all(repo, S, C)
    assert [c[c.index("--family") + 1] for c in argvs] == [model_calls.WRITER, model_calls.WRITER]
    assert all(c[c.index("--max-output-tokens") + 1] == "64000" for c in argvs), argvs
    # the checker's answers are short; it gets no cap
    argvs.clear()
    model_calls.codex("check", "c0", "p")
    assert "--max-output-tokens" not in argvs[0]
