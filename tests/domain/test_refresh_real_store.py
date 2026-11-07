"""Refresh map against a store REAL estate built (e2e-1105 F40).

The first refresh tests (`test_refresh_changed.py`) ran on a hand-built store whose `meta` table
had the wrong columns. The real store's is `meta(k, v)`, so `refresh.py` read nothing, called it
"the store records no indexed commit", re-asked nothing, and the map that the run then rebuilt
read as current while `sum` kept its stale "code doesn't meet it".

These tests read `fixtures/refresh/`, which `fixtures/refresh/build.py` made with wicked-estate
0.32.1 (cf27389) and wicked-core (2dcfa8c): a mapped store whose build record names the commit the
map was built from, re-indexed after `sum` was fixed, plus a labelled store and the repository as a
git bundle. Falsifier: query `meta(key, value)` again and every test here fails.
"""

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from domain import apply_rules, generation, prepare_worklist, refresh, rules_file
from tests.domain.test_extraction_files import _wt
from tests.domain.test_refresh_changed import _Core, _Estate

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "refresh"
MANIFEST = json.loads((FIXTURE / "manifest.json").read_text())
SUM, MEAN, CLAMP = (MANIFEST["symbols"][k] for k in ("sum", "mean", "clamp"))


def _repo(tmp_path) -> Path:
    repo = tmp_path / "tm"
    subprocess.run(["git", "clone", "-q", str(FIXTURE / "repo.bundle"), str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.fsmonitor", "false"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", MANIFEST["base"]], check=True)
    return repo


def _db(tmp_path, name="estate.db") -> str:
    (tmp_path / "graphs").mkdir(exist_ok=True)
    db = tmp_path / "graphs" / name
    shutil.copyfile(FIXTURE / name, db)
    return str(db)


def test_the_real_store_names_the_build_commit_and_the_indexed_commit(tmp_path):
    built, base, _why = refresh.build_and_base(_db(tmp_path))
    assert (built, base) == (MANIFEST["built"], MANIFEST["base"])


def test_a_labelled_store_is_read_through_its_one_label(tmp_path):
    con = sqlite3.connect(_db(tmp_path, "labelled.db"))
    try:
        assert refresh.indexed_commit(con) == (MANIFEST["base"], "repo:tm:commit")
    finally:
        con.close()


def test_the_fixed_function_and_its_caller_are_re_asked_from_the_real_store(tmp_path, monkeypatch):
    repo, db, wt = _repo(tmp_path), _db(tmp_path), _wt(tmp_path)
    units, line = refresh.changed_units(db, str(repo), rules_file.tracked_files(repo), set())
    assert {u["symbol_id"] for u in units} == {SUM, MEAN}, line
    assert "2 mapped behaviour(s) in 1 file(s) changed" in line

    monkeypatch.setenv("WICKED_RUN_ID", "run-f40")
    doc = prepare_worklist.prepare(db, str(repo), wt, rules_file.WORKLIST_REL, 0,
                                   estate=_Estate(), core=_Core())
    framed = {u["symbol_id"]: u for u in doc["units"]}
    assert set(framed) == {SUM, MEAN}
    assert framed[SUM]["prior_statement"] == "The sum of numbers must include every element."
    assert "the loop starts at index 1" not in json.dumps(framed[SUM])
    assert generation.changed(generation.load(db, "run-f40")) == {SUM, MEAN}

    # The seat restates sum (the code meets it now); apply, reading the real store, writes it
    # and "code meets it" over the stale finding.
    rules = [{"symbol_id": SUM, "statement": "The sum of numbers must include every element.",
              "confidence": 0.9, "provenance": {"source": "math", "ref": SUM,
                                                "source_kinds": ["code-body"]}}]
    rules_file.write_json_file(wt, rules_file.RULES_REL, rules_file.rules_doc("claude", rules))
    estate = _Estate()
    report = apply_rules.apply(db, str(repo), wt, rules_file.RULES_REL, "coverage-report.json",
                               estate=estate, core=_Core())
    assert report["changed_since_build"] == {"listed": 2, "restated": 1}
    mismatches = {k: v for (t, k), v in estate.anns[SUM].items() if t == "code_mismatch"}
    assert list(mismatches.values()) == ["code meets it"], mismatches


def test_a_store_the_refresh_cannot_read_fails_the_step_and_says_why(tmp_path, monkeypatch):
    repo, db, wt = _repo(tmp_path), _db(tmp_path), _wt(tmp_path)
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE meta RENAME COLUMN v TO value")
    con.commit()
    con.close()
    with pytest.raises(refresh.RefreshUnreadable, match="no such column"):
        refresh.build_and_base(db)
    monkeypatch.setenv("WICKED_RUN_ID", "run-f40b")
    with pytest.raises(RuntimeError, match="Refresh map cannot tell what changed"):
        prepare_worklist.prepare(db, str(repo), wt, rules_file.WORKLIST_REL, 0,
                                 estate=_Estate(), core=_Core())


@pytest.mark.parametrize("data, why", [
    ('{"metadata": {"code_commit": 123}}', "not text"),
    ('{"metadata": ["bad"]}', "no metadata object"),
    ("not json", "not JSON"),
])
def test_a_build_record_that_does_not_parse_is_unreadable_not_absent(tmp_path, data, why):
    """codex r1: a malformed build record must not read as "no build commit recorded"."""
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    con.execute("UPDATE nodes SET data = ? WHERE symbol = (SELECT sid FROM symbols WHERE sym = ?)",
                (data, refresh.BUILD_SYMBOL))
    con.commit()
    con.close()
    with pytest.raises(refresh.RefreshUnreadable, match=why):
        refresh.build_and_base(db)


def test_a_meta_value_that_is_not_text_is_unreadable_not_absent(tmp_path):
    """codex r1: a BLOB `repo_commit` must not read as "no indexed commit"."""
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    con.execute("UPDATE meta SET v = ? WHERE k = 'repo_commit'", (sqlite3.Binary(b"x"),))
    con.commit()
    con.close()
    with pytest.raises(refresh.RefreshUnreadable, match="repo_commit"):
        refresh.build_and_base(db)


def test_the_fixture_carries_no_identity_of_the_machine_that_built_it(tmp_path):
    """codex r1: the bundled commits are unsigned, by a synthetic author, and no file of the
    fixture holds a home path."""
    repo = _repo(tmp_path)
    log = subprocess.run(["git", "-C", str(repo), "log", "--all",
                          "--format=%an <%ae> %cn <%ce> %G?"], check=True, capture_output=True,
                         text=True).stdout.split("\n")
    assert {line for line in log if line} == {
        "fixture <fixture@example.invalid> fixture <fixture@example.invalid> N"}
    for f in FIXTURE.iterdir():
        if f.suffix == ".py":  # the builder names what it turns off
            continue
        raw = f.read_bytes()
        for marker in (b"/Users/", b"/home/", b"/private/", b"gpgsig", b"SSH SIGNATURE"):
            assert marker not in raw, (f.name, marker)
