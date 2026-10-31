"""domain-extraction across the seat boundary (wicked-garden#1362) — hermetic.

A seat container has no `wicked-core`, no `wicked-estate` and no writable store, so the work is
split: the HOST prepares the worklist file (`prepare_worklist.py`), the SEAT states the rules into
a rules file (`extract_loop.py --worklist … --rules-out …`), and the HOST checks and writes them
(`apply_rules.py`). These tests prove the file round trip, that the apply step refuses what is
outside the schema or about files the repository does not track (and writes nothing for a refused
file), and the whole prepare → seat → apply chain on a fixture. The real-binary run of the same
chain is in the opt-in lane at the bottom.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from domain import _clients, _rule_extractor, apply_rules, extract_loop, prepare_worklist, rules_file


def _rule(sid, statement="amount must be positive", confidence=0.9):
    return {"symbol_id": sid, "statement": statement, "confidence": confidence,
            "provenance": {"source": "m", "ref": sid, "source_kinds": ["code-body"]}}


# --- the schema ---------------------------------------------------------------------------------

def test_a_rules_file_round_trips(tmp_path):
    rules = [_rule("s::a"), {"symbol_id": "s::b", "statement": "", "confidence": 0.0}]
    rules_file.write_json_file(tmp_path, rules_file.RULES_REL, rules_file.rules_doc("codex", rules))
    seat, accepted, refused = rules_file.check_rules_doc(
        rules_file.read_json_file(tmp_path, rules_file.RULES_REL))
    assert (seat, accepted, refused) == ("codex", rules, [])


@pytest.mark.parametrize("doc,why", [
    ([], "expected a JSON object"),
    ({"schema": "other@1", "seat": "", "rules": []}, "schema"),
    ({"schema": rules_file.RULES_SCHEMA, "seat": "", "rules": [], "extra": 1}, "unknown top-level"),
    ({"schema": rules_file.RULES_SCHEMA, "seat": "a b; rm", "rules": []}, "seat"),
    ({"schema": rules_file.RULES_SCHEMA, "seat": "", "rules": {}}, "no `rules` list"),
])
def test_a_document_outside_the_schema_is_refused_whole(doc, why):
    with pytest.raises(rules_file.RulesFileRefused, match=why):
        rules_file.check_rules_doc(doc)


@pytest.mark.parametrize("entry,why", [
    ("s::a", "expected an object"),
    ({**_rule("s::a"), "requirement": "x"}, "unknown key"),
    ({"symbol_id": "s::a", "statement": "x"}, "missing 'confidence'"),
    ({**_rule("s::a"), "symbol_id": ""}, "symbol_id is empty"),
    ({**_rule("s::a"), "statement": "bad\x00rule"}, "control characters"),
    ({**_rule("s::a"), "statement": "x" * 2001}, "limit"),
    ({**_rule("s::a"), "confidence": True}, "confidence"),
    ({**_rule("s::a"), "confidence": 1.5}, "confidence"),
    ({**_rule("s::a"), "confidence": float("nan")}, "confidence"),
    ({**_rule("s::a"), "provenance": {"source": "m", "author": "x"}}, "provenance has unknown"),
    ({**_rule("s::a"), "provenance": {"source_kinds": ["vibes"]}}, "source_kinds"),
])
def test_an_entry_outside_the_schema_is_refused(entry, why):
    doc = rules_file.rules_doc("", [entry])
    _, accepted, refused = rules_file.check_rules_doc(doc)
    assert accepted == [] and len(refused) == 1 and why in refused[0]["why"]


def test_a_repeated_symbol_keeps_only_its_first_entry():
    _, accepted, refused = rules_file.check_rules_doc(
        rules_file.rules_doc("", [_rule("s::a"), _rule("s::a", "other")]))
    assert [e["statement"] for e in accepted] == ["amount must be positive"]
    assert refused[0]["index"] == 1 and "repeats" in refused[0]["why"]


def test_paths_never_leave_the_worktree(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    wt = tmp_path / "wt"
    (wt / ".wicked").mkdir(parents=True)
    (wt / ".wicked" / "domain").symlink_to(outside, target_is_directory=True)
    for rel in (rules_file.RULES_REL, "../x.json", str(outside / "x.json")):
        with pytest.raises(rules_file.RulesFileRefused):
            rules_file.write_json_file(wt, rel, {})
    assert list(outside.iterdir()) == []


# --- fixture: a store, a repository, and the host's binaries faked ------------------------------

def _git_repo(tmp_path, tracked=("f.py",)):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for name in tracked:
        (repo / name).write_text("x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    (repo / "untracked.py").write_text("y = 2\n")
    return str(repo)


class _Estate:
    """The store's write surface, with estate's replace-by-key semantics."""
    def __init__(self):
        self.writes = {}
    def read_clusters(self):
        return []
    def list_nodes(self):
        return []
    def rank(self, limit=200):
        return ["s::core"]
    def source(self, sid):
        return f"def {sid}(): ..."
    def annotate(self, symbol_id, **kw):
        self.writes.setdefault(symbol_id, {})["ann"] = kw
    def set_requirement(self, symbol_id, requirement, validated, validated_by="extract-loop"):
        self.writes.setdefault(symbol_id, {})["req"] = (requirement, validated, validated_by)
    def read_annotations(self, symbol_id):
        ann = self.writes.get(symbol_id, {}).get("ann")
        return [{"key": ann["key"]}] if ann else []


class _Core:
    """Coverage over `nodes` ({sid: file}): unmapped = no requirement written yet."""
    def __init__(self, estate, nodes):
        self.estate, self.nodes = estate, nodes
    def _doc(self):
        left = [{"symbol_id": s, "name": s.split("::")[-1], "file": f, "kind": "Function"}
                for s, f in self.nodes.items() if "req" not in self.estate.writes.get(s, {})]
        n = len(self.nodes)
        return {"coverage": (n - len(left)) / n, "behavior_bearing": n, "resolved": n - len(left),
                "unaccounted": len(left), "unaccounted_nodes": left}
    def coverage(self, db, out):
        doc = self._doc()
        Path(out).write_text(json.dumps(doc))
        return doc
    def coverage_against_minimum(self, db, out):
        doc = self.coverage(db, out)
        pct = round(doc["coverage"] * 100)
        return doc, pct >= 80, f"coverage: {pct}% mapped, minimum 80%"


def _star(tmp_path):
    from tests.domain.test_extract_loop import _star_db
    return _star_db(tmp_path)


_STAR = ["s::core", "s::a", "s::b", "s::c", "s::a1", "s::i1", "s::i2", "s::route"]


def _apply(wt, db, repo, estate, core, rules_rel=rules_file.RULES_REL):
    return apply_rules.apply(db, repo, wt, rules_rel, "coverage-report.json",
                             estate=estate, core=core)


def _write_rules(wt, seat, rules):
    rules_file.write_json_file(wt, rules_file.RULES_REL, rules_file.rules_doc(seat, rules))


# --- apply: the host's trust line ---------------------------------------------------------------

def test_apply_writes_conforming_rules_as_the_seat_and_reports_coverage(tmp_path):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), tmp_path / "wt"
    estate = _Estate()
    core = _Core(estate, {s: "f.py" for s in _STAR})
    _write_rules(wt, "codex", [_rule("s::core"), {"symbol_id": "s::a", "statement": "",
                                                  "confidence": 0.0}])
    report = _apply(wt, db, repo, estate, core)
    assert report["applied"] == {"resolved": 1, "risk": 1, "kept": 0}
    assert estate.writes["s::core"]["req"] == ("amount must be positive", True, "extract-loop:codex")
    assert estate.writes["s::core"]["ann"]["author"] == "extract-loop:codex"
    req, validated, _ = estate.writes["s::a"]["req"]
    assert req.startswith("[RISK]") and validated is False
    assert json.loads((wt / "coverage-report.json").read_text())["resolved"] == 2
    assert json.loads((wt / apply_rules.REPORT_REL).read_text())["refused_count"] == 0


def test_apply_refuses_a_bad_file_and_writes_nothing(tmp_path):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), tmp_path / "wt"
    estate = _Estate()
    core = _Core(estate, {s: "f.py" for s in _STAR})
    rules_file.write_json_file(wt, rules_file.RULES_REL,
                               {"schema": rules_file.RULES_SCHEMA, "seat": "claude",
                                "rules": [_rule("s::core")], "write_to": "/etc"})
    with pytest.raises(rules_file.RulesFileRefused, match="unknown top-level"):
        _apply(wt, db, repo, estate, core)
    assert estate.writes == {}
    assert not (wt / "coverage-report.json").exists()


def test_apply_main_exits_1_on_a_refused_or_missing_file(tmp_path, monkeypatch):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), tmp_path / "wt"
    wt.mkdir()
    estate = _Estate()
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "CliEstateClient", _Estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: _Core(estate, {}))
    monkeypatch.chdir(wt)
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1  # no rules file
    (wt / ".wicked" / "domain").mkdir(parents=True)
    (wt / rules_file.RULES_REL).write_text("not json")
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1
    assert estate.writes == {}


def test_apply_refuses_rules_about_files_not_in_the_repo_or_not_unmapped(tmp_path):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), tmp_path / "wt"
    estate = _Estate()
    estate.writes["s::b"] = {"req": ("earlier", True, "extract-loop"), "ann": {"key": "k"}}
    nodes = {s: "f.py" for s in _STAR}
    nodes["s::c"] = "untracked.py"     # on disk, not tracked
    nodes["s::route"] = "../../etc/x"  # not a repository path at all
    core = _Core(estate, nodes)
    _write_rules(wt, "pi", [_rule("s::core"), _rule("s::c"), _rule("s::route"), _rule("s::b"),
                            _rule("s::nope"), {**_rule("s::a"), "extra": 1}])
    report = _apply(wt, db, repo, estate, core)
    why = {r["symbol_id"]: r["why"] for r in report["refused"]}
    assert "not tracked" in why["s::c"] and "not tracked" in why["s::route"]
    assert "not an unmapped behaviour" in why["s::b"] and "not an unmapped" in why["s::nope"]
    assert "unknown key" in why["s::a"]
    assert report["applied"]["resolved"] == 1
    assert set(estate.writes) == {"s::core", "s::b"}
    assert estate.writes["s::b"]["req"][0] == "earlier"  # an already-mapped node is untouched


def test_apply_re_derives_the_judgment_the_seat_cannot_vouch_for(tmp_path):
    """A conforming entry is still judged by the host: ungrounded provenance or a low confidence
    is RISK-flagged, never resolved, whatever the seat wanted."""
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), tmp_path / "wt"
    estate = _Estate()
    core = _Core(estate, {s: "f.py" for s in _STAR})
    _write_rules(wt, "", [{"symbol_id": "s::core", "statement": "x is y", "confidence": 1.0},
                          _rule("s::a", confidence=0.5)])
    report = _apply(wt, db, repo, estate, core)
    assert report["applied"] == {"resolved": 0, "risk": 2, "kept": 0}
    assert estate.writes["s::core"]["req"][2] == "extract-loop"  # no seat named → the default


# --- the seat: file mode ------------------------------------------------------------------------

def test_file_mode_states_every_unit_into_a_conforming_file_and_resumes(tmp_path, monkeypatch):
    wt = tmp_path
    units = [{"symbol_id": f"s::{i}", "name": str(i), "file": "f.py", "source": "def f(): ..."}
             for i in range(6)]
    rules_file.write_json_file(wt, rules_file.WORKLIST_REL,
                               {"schema": rules_file.WORKLIST_SCHEMA, "units": units})
    monkeypatch.setenv("WICKED_RUN_AGENT", "claude")
    calls = []

    def model(batch, argv):
        calls.append([c["symbol_id"] for c in batch])
        return [{**_rule(c["symbol_id"]), "junk": 1, "confidence": "high" if c["name"] == "1"
                 else 0.9} for c in batch]
    monkeypatch.setattr(_rule_extractor, "extract_rules", model)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["m"])
    rc = extract_loop.run_files(wt, rules_file.WORKLIST_REL, rules_file.RULES_REL, time_budget=30,
                                limit=4, batch=4, dry_run=False)
    assert rc == 0
    seat, accepted, refused = rules_file.check_rules_doc(
        rules_file.read_json_file(wt, rules_file.RULES_REL))
    assert seat == "claude" and refused == [] and len(accepted) == 4
    assert accepted[1]["confidence"] == 0.0  # a non-number confidence is carried as 0, not dropped
    # a second pass resumes after the four already stated
    rc = extract_loop.run_files(wt, rules_file.WORKLIST_REL, rules_file.RULES_REL, time_budget=30,
                                limit=0, batch=4, dry_run=False)
    assert rc == 0 and calls[-1] == ["s::4", "s::5"]
    assert extract_loop.main(["--check-rules", str(wt / rules_file.RULES_REL)]) == 1  # absolute
    monkeypatch.chdir(wt)
    assert extract_loop.main(["--check-rules", rules_file.RULES_REL,
                              "--worklist", rules_file.WORKLIST_REL]) == 0


def test_file_mode_without_a_model_says_so_and_writes_nothing(tmp_path, monkeypatch):
    rules_file.write_json_file(tmp_path, rules_file.WORKLIST_REL,
                               {"schema": rules_file.WORKLIST_SCHEMA, "units": []})
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: None)
    assert extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=4, dry_run=False) == 2
    assert not (tmp_path / rules_file.RULES_REL).exists()


def test_file_mode_needs_no_store_or_binaries(tmp_path, monkeypatch):
    """The seat container has neither binary: file mode never asks for them."""
    def boom(*a, **k):
        raise AssertionError("file mode reached for a host binary")
    monkeypatch.setattr(_clients, "estate_client", boom)
    monkeypatch.setattr(_clients, "core_client", boom)
    rules_file.write_json_file(tmp_path, rules_file.WORKLIST_REL,
                               {"schema": rules_file.WORKLIST_SCHEMA,
                                "units": [{"symbol_id": "s::a", "name": "a", "source": ""}]})
    monkeypatch.chdir(tmp_path)
    assert extract_loop.main(["--worklist", rules_file.WORKLIST_REL, "--rules-out",
                              rules_file.RULES_REL, "--dry-run"]) == 0


# --- the chain on a fixture: prepare (host) → extract (seat) → apply (host) ---------------------

def test_prepare_seat_apply_maps_the_fixture_hub_first(tmp_path, monkeypatch):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), tmp_path / "wt"
    estate = _Estate()
    nodes = {s: "f.py" for s in _STAR}
    nodes["s::i2"] = "untracked.py"
    core = _Core(estate, nodes)
    doc = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 0, estate=estate,
                                   core=core)
    assert doc["not_in_repo"] == 1
    order = [u["symbol_id"] for u in doc["units"]]
    assert order[0] == "s::core" and "s::i2" not in order
    assert {u["hop"] for u in doc["units"][1:4]} == {1}

    monkeypatch.setenv("WICKED_RUN_AGENT", "copilot")
    assert extract_loop.run_files(wt, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=4, dry_run=True) == 0
    report = _apply(wt, db, repo, estate, core)
    assert report["applied"]["resolved"] == 7 and report["refused_count"] == 0
    assert report["coverage"]["unaccounted"] == 1  # the untracked file's node stays unmapped
    assert {w["req"][2] for w in estate.writes.values()} == {"extract-loop:copilot"}


# --- opt-in: the same chain on the real binaries -------------------------------------------------

def _bin(env, package):
    if env in os.environ:
        return os.environ[env].strip() or None
    return shutil.which(package)


_ESTATE = _bin("WICKED_ESTATE_BIN", "wicked-estate")
_CORE = _bin("WICKED_CORE_BIN", "wicked-core") or os.environ.get("WICKED_CORE_EXE")


@pytest.mark.skipif(_ESTATE is None or _CORE is None,
                    reason="wicked-estate and/or wicked-core not installed — real-binary lane")
def test_real_binaries_prepare_seat_apply_domain_graph(tmp_path, monkeypatch):
    repo = Path(_git_repo(tmp_path, tracked=()))
    (repo / "math.js").write_text(
        "export function sum(xs) { let t = 0; for (const x of xs) t += x; return t; }\n"
        "export function mean(xs) { return sum(xs) / xs.length; }\n")
    (repo / "untracked.py").unlink()
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    db = str(tmp_path / "estate.db")
    subprocess.run([_ESTATE, "index", str(repo), "--db", db], check=True, capture_output=True)
    monkeypatch.setenv("WICKED_CORE_BIN", _CORE)
    monkeypatch.setenv("WICKED_ESTATE_BIN", _ESTATE)
    wt = tmp_path / "wt"
    wt.mkdir()
    monkeypatch.chdir(wt)
    assert prepare_worklist.main(["--db", db, "--repo-root", str(repo)]) == 0
    monkeypatch.setenv("WICKED_RUN_AGENT", "claude")
    assert extract_loop.main(["--worklist", rules_file.WORKLIST_REL, "--rules-out",
                              rules_file.RULES_REL, "--dry-run"]) == 0
    assert apply_rules.main(["--db", db, "--repo-root", str(repo)]) == 0
    cov = json.loads((wt / "coverage-report.json").read_text())
    assert cov["unaccounted"] == 0 and cov["resolved"] >= 2
    out = tmp_path / "rg.json"
    subprocess.run([_CORE, "domain-graph", "--db", db, "--out", str(out)], check=True,
                   capture_output=True)
    assert json.loads(out.read_text())["metadata"]["coverage"]["mapped_pct"] == 100


def test_the_host_uses_the_engines_core_cli(monkeypatch):
    """Tool steps inherit crew's WICKED_CORE_EXE (the CLI matching the engine); it is not on PATH."""
    monkeypatch.delenv("WICKED_CORE_BIN", raising=False)
    monkeypatch.setenv("WICKED_CORE_EXE", "/engine/wicked-core")
    assert _clients.core_client()._bin == ["/engine/wicked-core"]
    monkeypatch.setenv("WICKED_CORE_BIN", "")  # the kill-switch still wins
    assert _clients.core_client() is None
