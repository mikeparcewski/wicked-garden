"""Refresh map re-asks the mapped behaviours whose code changed since the map was built
(wicked-garden#1425) — hermetic: a real git repository, a store in estate's table shapes, and the
host steps with injected estate/core clients.

The lane reqgraph-validate R5 journey: `sum` was mapped with a "code doesn't meet it" finding (it
skipped the first element), the person fixed it, and Refresh map mapped only the new `max`; `sum`
kept its old finding while the page read as current. Falsifier: frame only coverage's unmapped and
placeholders (or accept only those in apply) and `sum` is never asked, so its finding stays.
"""

import json
import sqlite3
import subprocess
from pathlib import Path

from domain import apply_rules, extract_loop, generation, prepare_worklist, refresh, rules_file
from tests.domain.test_extraction_files import _wt

BUGGY = ("export function sum(xs) { let t = 0; for (let i = 1; i < xs.length; i++) t += xs[i]; "
         "return t; }\n"
         "export function mean(xs) { return sum(xs) / xs.length; }\n")
FIXED = ("export function sum(xs) { let t = 0; for (let i = 0; i < xs.length; i++) t += xs[i]; "
         "return t; }\n"
         "export function mean(xs) { return sum(xs) / xs.length; }\n")
OTHER = "export function clamp(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }\n"
TEST = "test('sum', () => { assert.equal(sum([1, 2]), 3); });\n"
SUM, MEAN, CLAMP, TSUM = ("js . src/math/sum().", "js . src/math/mean().",
                          "js . src/other/clamp().", "js . test/math.test/sum-test().")


def _git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                          *args], check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _repo(tmp_path):
    """Commit 1: sum skips the first element. Commit 2: sum is fixed (and its test changes);
    src/other.js is untouched."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "test").mkdir()
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "config", "core.fsmonitor", "false")
    (repo / "src" / "math.js").write_text(BUGGY)
    (repo / "src" / "other.js").write_text(OTHER)
    (repo / "test" / "math.test.js").write_text(TEST)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "one")
    built = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "math.js").write_text(FIXED)
    (repo / "test" / "math.test.js").write_text(TEST + "// more\n")
    _git(repo, "commit", "-q", "-am", "fix sum")
    return repo, built, _git(repo, "rev-parse", "HEAD")


def _store(tmp_path, built, base, *, code_commit=True):
    """A store indexed at `base` whose map was built from `built`: sum, mean and clamp mapped
    (sum with a mismatch), a test unit mapped too."""
    (tmp_path / "graphs").mkdir()
    db = tmp_path / "graphs" / "estate.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE symbols (sid INTEGER PRIMARY KEY, sym TEXT);
        CREATE TABLE nodes (symbol INTEGER, name TEXT, file TEXT, data TEXT, requirement TEXT,
                            requirement_validated INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE edges (source INTEGER, target INTEGER, kind TEXT);
        CREATE TABLE files (path TEXT, git_sha TEXT);
        CREATE TABLE content (git_sha TEXT, blob BLOB);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE annotations (id INTEGER PRIMARY KEY AUTOINCREMENT, node_sym INTEGER,
            key TEXT, value TEXT, confidence REAL DEFAULT 1.0, provenance TEXT DEFAULT '',
            author TEXT DEFAULT '', ts INTEGER DEFAULT 0, type TEXT DEFAULT 'note');
    """)
    texts = {"src/math.js": FIXED, "src/other.js": OTHER, "test/math.test.js": TEST}
    for i, (path, text) in enumerate(texts.items()):
        sha = f"{i:040d}"
        c.execute("INSERT INTO files VALUES (?, ?)", (path, sha))
        c.execute("INSERT INTO content VALUES (?, ?)", (sha, text.encode()))
    spans = {SUM: ("src/math.js", 0, FIXED.index("\n")),
             MEAN: ("src/math.js", FIXED.index("\n") + 1, len(FIXED) - 1),
             CLAMP: ("src/other.js", 0, len(OTHER) - 1),
             TSUM: ("test/math.test.js", 0, len(TEST) - 1)}
    statements = {SUM: "The sum of numbers must include every element.",
                  MEAN: "The mean is the sum divided by the count.",
                  CLAMP: "A value is held within [lo, hi].",
                  TSUM: "sum adds two numbers."}
    for sid, (sym, (file, a, b)) in enumerate(spans.items(), start=1):
        c.execute("INSERT INTO symbols VALUES (?, ?)", (sid, sym))
        data = {"kind": "function", "location": {"file": file,
                                                 "span": {"start_byte": a, "end_byte": b}}}
        c.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, 1)",
                  (sid, sym.split("/")[-1].rstrip("()."), file, json.dumps(data),
                   statements[sym]))
        c.execute("INSERT INTO annotations (node_sym, key, value, author, ts, type) VALUES "
                  "(?, ?, ?, 'extract-loop', 10, 'business_rule')",
                  (sid, f"RULE-{sid}", statements[sym]))
    c.execute("INSERT INTO annotations (node_sym, key, value, author, ts, type) VALUES "
              "(1, 'RULE-1:mismatch', 'the loop starts at index 1', 'extract-loop', 9, "
              "'code_mismatch')")
    meta = {"generation": 1}
    if code_commit:
        meta["code_commit"] = built
    c.execute("INSERT INTO symbols VALUES (99, ?)", (refresh.BUILD_SYMBOL,))
    c.execute("INSERT INTO nodes VALUES (99, 'requirements graph', 'requirements-graph/build', ?,"
              " NULL, 0)", (json.dumps({"metadata": meta}),))
    c.execute("INSERT INTO meta VALUES ('repo_commit', ?)", (base,))
    c.commit()
    c.close()
    return str(db)


class _Estate:
    """Estate's write surface with replace-by-(symbol, type, key) semantics."""
    def __init__(self):
        self.anns, self.reqs = {}, {}
    def read_clusters(self):
        return []
    def list_nodes(self):
        return []
    def rank(self, limit=200):
        return [SUM]
    def annotate(self, symbol_id, type, key, value, **kw):
        self.anns.setdefault(symbol_id, {})[(type, key)] = value
    def set_requirement(self, symbol_id, requirement, validated, validated_by="extract-loop"):
        self.reqs[symbol_id] = (requirement, validated)
    def read_annotations(self, symbol_id):
        return [{"key": k, "value": v} for (_t, k), v in self.anns.get(symbol_id, {}).items()]


class _Core:
    """Every behaviour is a real requirement already: nothing unmapped, no placeholder."""
    def coverage(self, db, out):
        doc = {"coverage": 1.0, "behavior_bearing": 3, "resolved": 3, "risk_flagged": 0,
               "unaccounted": 0, "unaccounted_nodes": [], "placeholder_nodes": [],
               "not_product": 1}
        Path(out).write_text(json.dumps(doc))
        return doc
    def coverage_against_minimum(self, db, out):
        return self.coverage(db, out), True, "coverage: 100% real, minimum 80%"


def _prepare(db, repo, wt):
    return prepare_worklist.prepare(db, str(repo), wt, rules_file.WORKLIST_REL, 0,
                                    estate=_Estate(), core=_Core())


def test_a_fixed_function_is_re_asked_restated_and_its_mismatch_cleared(tmp_path, monkeypatch):
    repo, built, base = _repo(tmp_path)
    db, wt = _store(tmp_path, built, base), _wt(tmp_path)
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")

    doc = _prepare(db, repo, wt)
    units = {u["symbol_id"]: u for u in doc["units"]}
    # The changed file's mapped behaviours, never the untouched file's or the test's.
    assert set(units) == {SUM, MEAN}, sorted(units)
    assert units[SUM]["changed_since_build"] is True
    assert units[SUM]["prior_statement"] == "The sum of numbers must include every element."
    assert doc["changed_since_build"] == 2
    assert generation.changed(generation.load(db, "run-1")) == {SUM, MEAN}

    rules = [{"symbol_id": SUM, "statement": "The sum of numbers must include every element.",
              "confidence": 0.9, "provenance": {"source": "math", "ref": SUM,
                                                "source_kinds": ["code-body"]}},
             # unsure now: a real requirement is never degraded to a placeholder by a page
             {"symbol_id": MEAN, "statement": "maybe the mean", "confidence": 0.3,
              "provenance": {"source": "math", "ref": MEAN, "source_kinds": ["code-body"]}},
             # not changed since the build: still refused
             {"symbol_id": CLAMP, "statement": "A value is held within [lo, hi].",
              "confidence": 0.9, "provenance": {"source": "other", "ref": CLAMP,
                                                "source_kinds": ["code-body"]}}]
    rules_file.write_json_file(wt, rules_file.RULES_REL, rules_file.rules_doc("claude", rules))
    estate = _Estate()
    report = apply_rules.apply(db, str(repo), wt, rules_file.RULES_REL, "coverage-report.json",
                               estate=estate, core=_Core())
    assert report["applied"] == {"resolved": 1, "risk": 0, "kept": 1}
    assert report["changed_since_build"] == {"listed": 2, "restated": 1}
    assert [r["symbol_id"] for r in report["refused"]] == [CLAMP]
    # sum: restated, "code meets it" written as its NEWEST code_mismatch (wicked-core reads the
    # newest per node, whatever its key: `code_mismatch_of`), and the earlier rule row
    # (under another key: `RULE-1` here) superseded too, so the graph keeps no obsolete statement
    rid = extract_loop.rule_key(SUM, "extract-loop")
    assert rid != "RULE-1"
    assert estate.anns[SUM][("code_mismatch", f"{rid}:mismatch")] == extract_loop.CODE_MEETS
    assert estate.anns[SUM][("business_rule", rid)] == rules[0]["statement"]
    assert estate.anns[SUM][("business_rule", "RULE-1")] == rules[0]["statement"]
    assert estate.reqs[SUM] == ("The sum of numbers must include every element.", True)
    assert MEAN not in estate.anns and MEAN not in estate.reqs


def test_a_map_built_without_a_code_commit_re_asks_nothing_and_says_so(tmp_path, monkeypatch,
                                                                        capsys):
    repo, built, base = _repo(tmp_path)
    db, wt = _store(tmp_path, built, base, code_commit=False), _wt(tmp_path)
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    assert _prepare(db, repo, wt)["units"] == []
    assert "no build commit recorded" in capsys.readouterr().err


def test_a_commit_the_checkout_does_not_hold_re_asks_nothing(tmp_path):
    repo, built, base = _repo(tmp_path)
    db = _store(tmp_path, "f" * 40, base)
    units, line = refresh.changed_units(db, str(repo), rules_file.tracked_files(repo), set())
    assert units == [] and "could not be read" in line


def test_outside_a_run_nothing_is_re_asked(tmp_path, monkeypatch):
    repo, built, base = _repo(tmp_path)
    db, wt = _store(tmp_path, built, base), _wt(tmp_path)
    monkeypatch.delenv("WICKED_RUN_ID", raising=False)
    assert _prepare(db, repo, wt)["units"] == []


def _gen_doc(pct, page=1, grant_page=0, changed=(), visited=()):
    return {"schema": generation.SCHEMA, "run_id": "r", "repo": "tm",
            "points": [{"page": 0, "pct": 100, "real": 3, "behaviours": 3, "at": 0},
                       {"page": page, "pct": pct, "real": 3, "behaviours": 3, "at": 60000}],
            "grant": {"page": grant_page, "at": 0},
            "changed": list(changed), "visited": list(visited)}


def test_paging_goes_on_at_the_minimum_while_changed_behaviours_are_left():
    doc = _gen_doc(100, changed=[SUM, MEAN], visited=[SUM])
    left = generation.changed_left(doc)
    assert left == 1
    d = generation.decide(doc, repo="tm", target=80, now=60000, max_pages=20, max_minutes=240,
                          left_to_map=0, changed_left=left)
    assert d["next"] == "continue" and "1 mapped behaviour changed" in d["line"]
    spent = generation.decide(doc, repo="tm", target=80, now=60000, max_pages=1, max_minutes=240,
                              left_to_map=0, changed_left=left)
    assert spent["next"] == "ask" and [c["id"] for c in spent["choices"]] == ["continue", "finish"]
    done = generation.decide(_gen_doc(100, changed=[SUM], visited=[SUM]), repo="tm", target=80,
                             now=60000, max_pages=20, max_minutes=240, left_to_map=0,
                             changed_left=0)
    assert done["next"] == "done"


def test_below_the_minimum_changed_behaviours_are_asked_before_the_lower_ask():
    doc = _gen_doc(66, changed=[SUM])
    d = generation.decide(doc, repo="tm", target=80, now=60000, max_pages=20, max_minutes=240,
                          left_to_map=0, changed_left=1)
    assert d["next"] == "continue"


def test_the_rule_prompt_carries_the_earlier_statement_of_a_changed_unit_as_data():
    from domain import _rule_extractor
    unit = {"symbol_id": SUM, "name": "sum", "file": "src/math.js", "source": "x",
            "changed_since_build": True, "prior_statement": "old ```rule```"}
    text = _rule_extractor._build_prompt([unit])
    assert "mapped before and its code has changed since" in text
    assert "old '''rule'''" in text  # no fence of its own inside the data fence
    assert "earlier statement" not in _rule_extractor._build_prompt([{**unit,
                                                                     "changed_since_build": False}])


def test_changed_units_past_the_first_page_keep_the_run_paging(tmp_path, monkeypatch):
    """codex r1: with one unit per page, the record must hold every changed unit found, not only
    the page's, or the next-page decision sees none left after the first."""
    repo, built, base = _repo(tmp_path)
    db, wt = _store(tmp_path, built, base), _wt(tmp_path)
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    doc = prepare_worklist.prepare(db, str(repo), wt, rules_file.WORKLIST_REL, 1,
                                   estate=_Estate(), core=_Core())
    assert len(doc["units"]) == 1
    rec = generation.load(db, "run-1")
    assert generation.changed(rec) == {SUM, MEAN}
    generation.record_answered(db, "run-1", [doc["units"][0]["symbol_id"]])
    rec = generation.load(db, "run-1")
    generation.close_page(rec, _Core().coverage(db, str(tmp_path / "c.json")))
    assert generation.changed_left(rec) == 1


def test_a_low_yield_page_still_offers_to_go_on_while_changed_units_are_left():
    """codex r1: below the minimum, nothing unmapped left, a page that resolved none of its 20
    framed units must still offer to continue when changed units remain."""
    doc = _gen_doc(66, changed=[f"s::{i}" for i in range(40)])
    doc["points"][-1].update(framed=20, page_real=0)
    d = generation.decide(doc, repo="tm", target=80, now=60000, max_pages=20, max_minutes=240,
                          left_to_map=0, changed_left=20)
    assert d["next"] == "ask" and "continue" in [c["id"] for c in d["choices"]]


def test_the_seat_harness_keeps_the_refresh_framing_through_to_the_prompt(tmp_path, monkeypatch):
    """codex r2: `run_files` re-frames each worklist unit; the changed mark and the earlier
    statement must survive to the prompt the model sees."""
    from domain import _rule_extractor
    repo, built, base = _repo(tmp_path)
    db, wt = _store(tmp_path, built, base), _wt(tmp_path)
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    _prepare(db, repo, wt)
    prompts = []

    def model(take, framed, ids, model_argv, dry_run, deadline=None):
        prompts.append(_rule_extractor._build_prompt(framed))
        return {}
    monkeypatch.setattr(extract_loop, "_ask_model", model)
    extract_loop.run_files(wt, rules_file.WORKLIST_REL, rules_file.RULES_REL, time_budget=30,
                           limit=0, batch=8, dry_run=True)
    assert prompts and "mapped before and its code has changed since" in prompts[0]
    assert "The sum of numbers must include every element." in prompts[0]


def test_a_changed_unit_closes_only_on_the_host_answer_record(tmp_path):
    """codex r2: without an answer record, a page closes what is real now; a changed mapped unit
    was real before the page, so it must stay open until the host records it answered."""
    db = str(tmp_path / "estate.db")
    cov = {"behavior_bearing": 3, "resolved": 3, "risk_flagged": 0, "unaccounted": 0,
           "unaccounted_nodes": [], "placeholder_nodes": [], "not_product": 0}
    generation.open_record(db, "run-1", cov, "tm")
    generation.frame_page(db, "run-1", [SUM, "s::new"], changed_ids=[SUM])
    rec = generation.load(db, "run-1")  # extract-apply never recorded its answers
    generation.close_page(rec, cov)
    assert rec["visited"] == ["s::new"] and generation.changed_left(rec) == 1


def test_lower_still_ends_the_mapping_with_changed_units_left(tmp_path):
    """codex r2: "Lower the minimum ... and build the graph" keeps its word."""
    from domain import next_page

    class Core(_Core):
        def __init__(self):
            self.target = 80
        def coverage(self, db, out):
            doc = {"coverage": 1.0, "behavior_bearing": 3, "resolved": 2, "risk_flagged": 0,
                   "unaccounted": 1, "unaccounted_nodes": [], "placeholder_nodes": [],
                   "not_product": 0}
            Path(out).write_text(json.dumps(doc))
            return doc
        def requirements_target(self, db, set_pct=None):
            if set_pct is not None:
                self.target = set_pct
            return self.target, "repository" if set_pct is not None or self.target != 80 else "daemon"
    db = str(tmp_path / "estate.db")
    core = Core()
    generation.open_record(db, "run-1", core.coverage(db, str(tmp_path / "c.json")), "tm")
    generation.frame_page(db, "run-1", [SUM], changed_ids=[SUM, MEAN])
    env = {"WICKED_RUN_ID": "run-1", "WICKED_REPEAT_CHOICE": "lower", "WICKED_REPEAT_PASS": "1"}
    repo, _built, _base = _repo(tmp_path)
    d = next_page.run(db, str(repo), core=core, env=env, now=60000)
    assert d["next"] == "done"


def test_an_ask_under_one_percent_with_changed_units_left_offers_a_way_to_finish():
    """codex r2: with no share to lower to, the budget ask must still let the operator finish."""
    doc = _gen_doc(0, changed=[SUM])
    doc["points"][-1].update(real=1, behaviours=1000)
    d = generation.decide(doc, repo="tm", target=80, now=60000, max_pages=1, max_minutes=240,
                          left_to_map=0, changed_left=1)
    assert d["next"] == "ask" and [c["id"] for c in d["choices"]] == ["continue", "finish"]


def test_at_the_minimum_a_page_that_answered_none_of_its_units_is_asked_not_paged_on():
    """pi r2: a seat that never reaches the changed units must not burn the whole budget."""
    doc = _gen_doc(100, changed=[f"s::{i}" for i in range(30)])
    doc["points"][-1].update(framed=30, page_real=0)
    d = generation.decide(doc, repo="tm", target=80, now=60000, max_pages=20, max_minutes=240,
                          left_to_map=0, changed_left=30)
    assert d["next"] == "ask" and [c["id"] for c in d["choices"]] == ["continue", "finish"]
