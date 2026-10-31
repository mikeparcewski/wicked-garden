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
    wt = _wt(tmp_path)
    (wt / ".wicked").mkdir(parents=True)
    (wt / ".wicked" / "domain").symlink_to(outside, target_is_directory=True)
    for rel in (rules_file.RULES_REL, "../x.json", str(outside / "x.json")):
        with pytest.raises(rules_file.RulesFileRefused):
            rules_file.write_json_file(wt, rel, {})
    assert list(outside.iterdir()) == []


# --- fixture: a store, a repository, and the host's binaries faked ------------------------------

def _wt(tmp_path):
    """The run's worktree (it exists before any step runs)."""
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    return wt


def _git_repo(tmp_path, tracked=("f.py",)):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.fsmonitor", "false"], check=True)
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
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
    estate = _Estate()
    core = _Core(estate, {s: "f.py" for s in _STAR})
    _write_rules(wt, "codex", [_rule("s::core"), {"symbol_id": "s::a", "statement": "",
                                                  "confidence": 0.0}])
    report = _apply(wt, db, repo, estate, core)
    assert report["applied"] == {"resolved": 1, "risk": 1, "kept": 0}
    # The host authors what it applies: the seat a file names is the seat's own claim.
    assert estate.writes["s::core"]["req"] == ("amount must be positive", True, "extract-loop")
    assert estate.writes["s::core"]["ann"]["author"] == "extract-loop"
    req, validated, _ = estate.writes["s::a"]["req"]
    assert req.startswith("[RISK]") and validated is False
    assert json.loads((wt / "coverage-report.json").read_text())["resolved"] == 2
    report_file = json.loads((wt / apply_rules.REPORT_REL).read_text())
    assert (report_file["refused_count"], report_file["declared_seat"]) == (0, "codex")


def test_apply_refuses_a_bad_file_and_writes_nothing(tmp_path):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
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
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
    estate = _Estate()
    monkeypatch.setattr(_clients, "host_estate_client", lambda db: estate)
    monkeypatch.setattr(_clients, "host_core_client", lambda: _Core(estate, {}))
    monkeypatch.chdir(wt)
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1  # no rules file
    (wt / ".wicked" / "domain").mkdir(parents=True)
    (wt / rules_file.RULES_REL).write_text("not json")
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1
    assert estate.writes == {}


def test_apply_refuses_rules_about_files_not_in_the_repo_or_not_unmapped(tmp_path):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
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
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
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

    def model(batch, argv, **kw):
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
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
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
    assert {w["req"][2] for w in estate.writes.values()} == {"extract-loop"}
    assert report["declared_seat"] == "copilot"


# --- opt-in: the same chain on the real binaries -------------------------------------------------

def _bin(env, package):
    if env in os.environ:
        return os.environ[env].strip() or None
    return shutil.which(package)


_ESTATE = _bin("WICKED_ESTATE_BIN", "wicked-estate")
# The precedence `_clients.host_core_client` uses: WICKED_CORE_BIN (empty = off), then the
# engine's WICKED_CORE_EXE, then PATH.
_CORE = (_bin("WICKED_CORE_BIN", "wicked-core") if "WICKED_CORE_BIN" in os.environ
         else (os.environ.get("WICKED_CORE_EXE") or "").strip() or shutil.which("wicked-core"))


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
    wt = _wt(tmp_path)
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


# --- review round 1 (codex + agy on #1363): every finding, a regression ---------------------------

def _plant(path, mode=0o755):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\ntouch \"$0.ran\"\n")
    path.chmod(mode)


def test_host_steps_never_run_a_binary_from_the_worktree(tmp_path, monkeypatch):
    for var in ("WICKED_ESTATE_BIN", "WICKED_CORE_BIN", "WICKED_CORE_EXE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(_clients, "_config_preference", lambda key: None)
    _plant(tmp_path / "node_modules" / ".bin" / "wicked-estate")
    _plant(tmp_path / "bin" / "wicked-core")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "bin")  # a relative PATH entry resolves inside the worktree
    with pytest.raises(RuntimeError, match="not resolvable"):
        _clients.host_estate_client("x.db")  # node_modules/.bin is never consulted
    with pytest.raises(RuntimeError, match="inside the working directory"):
        _clients.host_core_client()
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))  # absolute, but still the worktree
    with pytest.raises(RuntimeError, match="inside the working directory"):
        _clients.host_core_client()
    assert not list(tmp_path.rglob("*.ran"))


def test_the_engines_cli_and_the_operators_env_are_trusted(monkeypatch):
    monkeypatch.delenv("WICKED_CORE_BIN", raising=False)
    monkeypatch.setenv("WICKED_CORE_EXE", "/engine/wicked-core")
    assert _clients.host_core_client()._bin == ["/engine/wicked-core"]
    monkeypatch.setenv("WICKED_ESTATE_BIN", "/opt/wicked-estate")
    assert _clients.host_estate_client("x.db")._bin == ["/opt/wicked-estate"]


def _apply_env(tmp_path):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
    estate = _Estate()
    return db, repo, wt, estate, _Core(estate, {s: "f.py" for s in _STAR})


def test_a_symlinked_rules_file_is_refused_and_nothing_is_read_through_it(tmp_path):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps(rules_file.rules_doc("", [_rule("s::core")])))
    (wt / ".wicked" / "domain").mkdir(parents=True)
    (wt / rules_file.RULES_REL).symlink_to(secret)
    with pytest.raises(rules_file.RulesFileRefused, match="plain file"):
        _apply(wt, db, repo, estate, core)
    assert estate.writes == {}


@pytest.mark.parametrize("plant", ["symlink", "hardlink"])
def test_the_coverage_report_replaces_a_planted_link_instead_of_writing_through_it(tmp_path, plant):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    target = tmp_path / "outside.txt"
    target.write_text("keep me")
    _write_rules(wt, "", [_rule("s::core")])
    leaf = wt / "coverage-report.json"
    if plant == "symlink":
        leaf.symlink_to(target)
        with pytest.raises(rules_file.RulesFileRefused):
            _apply(wt, db, repo, estate, core)
        assert estate.writes == {}  # refused before the store changed
    else:
        os.link(target, leaf)
        _apply(wt, db, repo, estate, core)
        assert json.loads(leaf.read_text())["behavior_bearing"] == len(_STAR)
    assert target.read_text() == "keep me"


def test_an_unusable_report_destination_is_refused_before_any_store_write(tmp_path):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _write_rules(wt, "", [_rule("s::core")])
    (wt / apply_rules.REPORT_REL).mkdir(parents=True)
    with pytest.raises(rules_file.RulesFileRefused, match="not a regular file"):
        _apply(wt, db, repo, estate, core)
    assert estate.writes == {}


def test_a_seat_cannot_name_its_author(tmp_path):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _write_rules(wt, "not-the-actual-seat", [_rule("s::core")])
    report = _apply(wt, db, repo, estate, core)
    assert estate.writes["s::core"]["ann"]["author"] == "extract-loop"
    assert (report["author"], report["declared_seat"]) == ("extract-loop", "not-the-actual-seat")


@pytest.mark.parametrize("entry,why", [
    ({**_rule("s::a"), "statement": "bad \ud800 text"}, "not valid Unicode"),
    ({**_rule("s::a"), "confidence": 10 ** 400}, "confidence"),
])
def test_an_unencodable_or_huge_value_is_a_refused_entry_and_its_siblings_apply(tmp_path, entry, why):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    rules_file.write_json_file(wt, rules_file.RULES_REL,
                               rules_file.rules_doc("", [_rule("s::core"), entry]))
    report = _apply(wt, db, repo, estate, core)
    assert report["applied"]["resolved"] == 1 and set(estate.writes) == {"s::core"}
    assert why in report["refused"][0]["why"]
    json.loads((wt / apply_rules.REPORT_REL).read_text())  # the report still serializes


def test_a_seat_name_with_a_trailing_newline_is_refused():
    with pytest.raises(rules_file.RulesFileRefused, match="seat"):
        rules_file.check_rules_doc(rules_file.rules_doc("codex\n", []))
    assert rules_file.seat_name("codex\n") == "codex"  # stripped from the env, then checked
    assert rules_file.seat_name("a b") == ""


def test_a_long_symbol_keeps_its_provenance_ref():
    sid = "s::" + "x" * 700
    _, accepted, refused = rules_file.check_rules_doc(rules_file.rules_doc("", [_rule(sid)]))
    assert refused == [] and accepted[0]["provenance"]["ref"] == sid


def test_model_provenance_is_cleaned_not_dropped():
    entry = extract_loop.to_entry("s::a", {
        "statement": "x", "confidence": 0.9,
        "provenance": {"source": "m\x01", "ref": "s::a", "line": 4,
                       "source_kinds": ["code-body", "vibes"]}})
    assert entry["provenance"] == {"source": "m ", "ref": "s::a", "source_kinds": ["code-body"]}
    assert _rule_extractor.validate_rule(entry, {"s::a"})[0]


def _worklist(wt, n=6):
    units = [{"symbol_id": f"s::{i}", "name": str(i), "file": "f.py", "source": "def f(): ..."}
             for i in range(n)]
    rules_file.write_json_file(wt, rules_file.WORKLIST_REL,
                               {"schema": rules_file.WORKLIST_SCHEMA, "units": units})
    return units


def test_an_outage_on_a_fresh_pass_leaves_no_rules_file_for_apply_to_accept(tmp_path, monkeypatch):
    _worklist(tmp_path)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["m"])
    monkeypatch.setattr(extract_loop, "_ask_model", lambda *a, **k: 75)
    rc = extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                time_budget=30, limit=0, batch=4, dry_run=False)
    assert rc == 75 and not (tmp_path / rules_file.RULES_REL).exists()


def test_the_budget_bounds_the_model_call_and_skips_a_retry_it_cannot_afford(monkeypatch):
    seen = []

    def slow(batch, argv, timeout=None):
        seen.append(timeout)
        raise RuntimeError("rule model exceeded 5s")
    monkeypatch.setattr(_rule_extractor, "extract_rules", slow)
    monkeypatch.setattr(extract_loop.time, "sleep", lambda s: pytest.fail("slept past the budget"))
    take = [{"symbol_id": "s::a"}]
    deadline = extract_loop.time.monotonic() + 5
    assert extract_loop._ask_model(take, take, {"s::a"}, ["m"], False, deadline=deadline) \
        == extract_loop._OUT_OF_TIME
    assert seen and seen[0] <= 5
    assert extract_loop._ask_model(take, take, {"s::a"}, ["m"], False,
                                   deadline=extract_loop.time.monotonic() - 1) \
        == extract_loop._OUT_OF_TIME


def test_file_mode_never_writes_more_entries_than_apply_accepts(tmp_path, monkeypatch):
    _worklist(tmp_path, n=10)
    monkeypatch.setattr(rules_file, "MAX_RULES", 5)
    rc = extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                time_budget=30, limit=0, batch=4, dry_run=True)
    assert rc == 0
    _, accepted, refused = rules_file.check_rules_doc(
        rules_file.read_json_file(tmp_path, rules_file.RULES_REL))
    assert 0 < len(accepted) <= 5 and refused == []


def test_resume_drops_entries_the_worklist_no_longer_holds(tmp_path):
    _worklist(tmp_path, n=2)
    _write_rules(tmp_path, "", [_rule("s::old")])
    assert extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=4, dry_run=True) == 0
    _, accepted, _ = rules_file.check_rules_doc(
        rules_file.read_json_file(tmp_path, rules_file.RULES_REL))
    assert [e["symbol_id"] for e in accepted] == ["s::0", "s::1"]


def test_check_rules_names_entries_outside_the_worklist_and_a_missing_worklist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_rules(tmp_path, "", [_rule("s::0")])
    assert extract_loop.main(["--check-rules", rules_file.RULES_REL,
                              "--worklist", rules_file.WORKLIST_REL]) == 1  # no worklist
    _worklist(tmp_path, n=1)
    assert extract_loop.main(["--check-rules", rules_file.RULES_REL,
                              "--worklist", rules_file.WORKLIST_REL]) == 0
    _write_rules(tmp_path, "", [_rule("s::typo")])
    assert extract_loop.main(["--check-rules", rules_file.RULES_REL,
                              "--worklist", rules_file.WORKLIST_REL]) == 1


# --- review round 2 (codex on #1363) -------------------------------------------------------------

def test_a_worktree_link_on_path_is_refused_even_when_it_points_outside(tmp_path, monkeypatch):
    for var in ("WICKED_ESTATE_BIN", "WICKED_CORE_BIN", "WICKED_CORE_EXE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(_clients, "_config_preference", lambda key: None)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "wicked-core").symlink_to(shutil.which("true") or "/usr/bin/true")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    with pytest.raises(RuntimeError, match="inside the working directory"):
        _clients.host_core_client()
    monkeypatch.setenv("WICKED_CORE_BIN", "wicked-core")  # a bare-name override is looked up too
    with pytest.raises(RuntimeError, match="inside the working directory"):
        _clients.host_core_client()


def test_a_trusted_binary_is_pinned_to_the_file_that_runs(tmp_path, monkeypatch):
    real = tmp_path / "opt" / "wicked-estate-0.30"
    _plant(real)
    link = tmp_path / "bin" / "wicked-estate"
    link.parent.mkdir()
    link.symlink_to(real)
    wt = _wt(tmp_path)
    monkeypatch.chdir(wt)
    monkeypatch.delenv("WICKED_ESTATE_BIN", raising=False)
    monkeypatch.setattr(_clients, "_config_preference", lambda key: None)
    monkeypatch.setenv("PATH", str(link.parent))
    assert _clients.host_estate_client("x.db")._bin == [os.path.realpath(real)]


def test_a_planted_git_in_the_worktree_never_runs(tmp_path, monkeypatch):
    _plant(tmp_path / "bin" / "git")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "bin") + os.pathsep + os.environ.get("PATH", ""))
    with pytest.raises(RuntimeError, match="inside the working directory"):
        rules_file.tracked_files(tmp_path)
    assert not list(tmp_path.rglob("*.ran"))


def _star_with_annotations(db):
    import sqlite3
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS annotations (node_sym INTEGER, type TEXT, key TEXT, "
                "author TEXT)")
    con.commit()
    con.close()


def test_a_rule_mapped_by_another_writer_meanwhile_is_not_overwritten(tmp_path):
    import sqlite3
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _star_with_annotations(db)
    _write_rules(wt, "", [_rule("s::core"), _rule("s::a")])

    def another_writer_maps_core():
        con = sqlite3.connect(db)
        con.execute("UPDATE nodes SET requirement = 'theirs' WHERE symbol = "
                    "(SELECT sid FROM symbols WHERE sym = 's::core')")
        con.commit()
        con.close()
        return []
    estate.read_clusters = another_writer_maps_core  # runs after the coverage snapshot
    report = _apply(wt, db, repo, estate, core)
    assert set(estate.writes) == {"s::a"}
    assert any(r["symbol_id"] == "s::core" and "another writer" in r["why"]
               for r in report["refused"])


def test_a_failure_after_the_store_changed_is_never_called_nothing_written(tmp_path, monkeypatch,
                                                                           capsys):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _write_rules(wt, "", [_rule("s::core")])
    real_write = rules_file.write_json_file

    def report_fails(base, rel, doc):
        if rel == apply_rules.REPORT_REL:
            raise rules_file.RulesFileRefused("swapped after the check")
        return real_write(base, rel, doc)
    monkeypatch.setattr(rules_file, "write_json_file", report_fails)
    monkeypatch.setattr(_clients, "host_estate_client", lambda db: estate)
    monkeypatch.setattr(_clients, "host_core_client", lambda: core)
    monkeypatch.chdir(wt)
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1
    err = capsys.readouterr().err
    assert "FAILED after writing" in err and "1 rule(s) were written" in err
    assert "nothing written" not in err


def test_a_destination_that_cannot_take_a_file_is_refused_before_any_store_write(tmp_path):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _write_rules(wt, "", [_rule("s::core")])
    report_dir = wt / ".wicked" / "domain"
    report_dir.chmod(0o555)
    try:
        if os.access(report_dir, os.W_OK):
            pytest.skip("running as a user that writes read-only directories (root)")
        with pytest.raises(rules_file.RulesFileRefused, match="cannot take a new file"):
            _apply(wt, db, repo, estate, core)
    finally:
        report_dir.chmod(0o755)
    assert estate.writes == {}


def test_a_resume_never_rewrites_a_file_past_the_byte_limit(tmp_path, monkeypatch):
    units = _worklist(tmp_path, n=3)
    compact = rules_file.rules_doc("", [_rule(u["symbol_id"], "y" * 200) for u in units])
    raw = json.dumps(compact, separators=(",", ":")).encode()
    (tmp_path / rules_file.RULES_REL).write_bytes(raw)
    monkeypatch.setattr(rules_file, "MAX_RULES_BYTES", len(raw) + 10)  # fits compact, not indented
    assert len(rules_file.encoded(compact)) > rules_file.MAX_RULES_BYTES
    assert extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=4, dry_run=True) == 0
    assert (tmp_path / rules_file.RULES_REL).read_bytes() == raw  # the checkpoint is kept


# --- review round 3 (codex + agy on #1363) -------------------------------------------------------

@pytest.mark.parametrize("kind", ["business_rule", "risk", "assumption", "question"])
def test_an_annotation_written_meanwhile_also_counts_as_mapped(tmp_path, kind):
    import sqlite3
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _star_with_annotations(db)
    _write_rules(wt, "", [_rule("s::core")])

    def another_writer_annotates_core():
        con = sqlite3.connect(db)
        con.execute("INSERT INTO annotations VALUES ((SELECT sid FROM symbols WHERE sym = "
                    "'s::core'), ?, 'K-x', 'someone')", (kind,))
        con.commit()
        con.close()
        return []
    estate.read_clusters = another_writer_annotates_core
    report = _apply(wt, db, repo, estate, core)
    assert estate.writes == {} and "another writer" in report["refused"][0]["why"]


@pytest.mark.parametrize("rel", [rules_file.RULES_REL, rules_file.WORKLIST_REL])
def test_a_directory_where_a_file_belongs_is_refused_not_a_crash(tmp_path, rel):
    (tmp_path / rel).mkdir(parents=True)
    with pytest.raises(rules_file.RulesFileRefused, match="not a regular file"):
        rules_file.read_json_file(tmp_path, rel)


def test_a_directory_that_cannot_be_created_is_refused_not_a_crash(tmp_path):
    (tmp_path / ".wicked").mkdir()
    (tmp_path / ".wicked").chmod(0o555)
    try:
        if os.access(tmp_path / ".wicked", os.W_OK):
            pytest.skip("running as a user that writes read-only directories (root)")
        with pytest.raises(rules_file.RulesFileRefused, match="not a usable directory"):
            rules_file.write_json_file(tmp_path, rules_file.RULES_REL, {})
    finally:
        (tmp_path / ".wicked").chmod(0o755)


def test_a_pass_that_states_nothing_leaves_no_file_and_says_so(tmp_path, monkeypatch):
    _worklist(tmp_path)
    monkeypatch.setattr(extract_loop, "_ask_model", lambda *a, **k: extract_loop._OUT_OF_TIME)
    assert extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=4, dry_run=True) == 75
    assert not (tmp_path / rules_file.RULES_REL).exists()


def test_a_failure_before_any_write_says_nothing_was_written(tmp_path, monkeypatch, capsys):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    estate.writes["s::core"] = {"req": ("earlier", True, "x"), "ann": {"key": "k"}}  # not unmapped
    _write_rules(wt, "", [_rule("s::core")])
    monkeypatch.setattr(core, "coverage_against_minimum",
                        lambda db, out: (_ for _ in ()).throw(RuntimeError("core crashed")))
    monkeypatch.setattr(_clients, "host_estate_client", lambda db: estate)
    monkeypatch.setattr(_clients, "host_core_client", lambda: core)
    monkeypatch.chdir(wt)
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1
    err = capsys.readouterr().err
    assert "FAILED: core crashed" in err and "after writing" not in err


def test_prepare_never_publishes_a_worklist_the_seat_would_refuse(tmp_path, monkeypatch):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
    estate = _Estate()
    monkeypatch.setattr(extract_loop._DirectStore, "source_slice", lambda self, sid, cap=4000: "x" * 3000)
    core = _Core(estate, {s: "f.py" for s in _STAR})
    monkeypatch.setattr(rules_file, "MAX_WORKLIST_BYTES", 64 * 1024 + 9000)
    doc = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 0, estate=estate,
                                   core=core)
    assert 0 < len(doc["units"]) < len(_STAR)
    assert extract_loop.read_worklist(wt, rules_file.WORKLIST_REL)["units"] == doc["units"]


# --- the live rig run (c612ae61 on :7721) ----------------------------------------------------------

def test_a_model_that_is_not_signed_in_in_the_seat_hands_over_at_once(tmp_path, monkeypatch):
    """In a seat container the nested `claude -p` answered "Not logged in": that is no model, not
    a judgment — the harness used to RISK-floor every unit into empty placeholders."""
    _worklist(tmp_path)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["claude", "-p"])

    def not_signed_in(batch, argv, timeout=None):
        raise RuntimeError("rule model exited 1: Not logged in · Please run /login")
    monkeypatch.setattr(_rule_extractor, "extract_rules", not_signed_in)
    monkeypatch.setattr(extract_loop.time, "sleep", lambda s: pytest.fail("retried a login failure"))
    assert extract_loop.run_files(tmp_path, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=30, limit=0, batch=4, dry_run=False) == 2
    assert not (tmp_path / rules_file.RULES_REL).exists()


def test_source_slices_come_from_the_repository_when_the_store_blob_is_unreadable(tmp_path,
                                                                                monkeypatch):
    import json as J, sqlite3
    db = tmp_path / "e.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE symbols (sid INTEGER PRIMARY KEY, sym TEXT);
        CREATE TABLE nodes (symbol INTEGER, name TEXT, file TEXT, data TEXT, requirement TEXT);
        CREATE TABLE edges (source INTEGER, target INTEGER, kind TEXT);
        CREATE TABLE files (path TEXT, git_sha TEXT);
        CREATE TABLE content (git_sha TEXT, blob BLOB);
    """)
    span = {"location": {"span": {"start_byte": 4, "end_byte": 9}}}
    for i, (sym, file) in enumerate([("s::ok", "m.js"), ("s::out", "../secret.js")], start=1):
        c.execute("INSERT INTO symbols VALUES (?, ?)", (i, sym))
        c.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, NULL)", (i, sym, file, J.dumps(span)))
        c.execute("INSERT INTO files VALUES (?, ?)", (file, f"sha{i}"))
        c.execute("INSERT INTO content VALUES (?, ?)", (f"sha{i}", b"\x28\xb5\x2f\xfd" + b"zstd"))
    c.commit(); c.close()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "m.js").write_text("let total = 0;")
    (tmp_path / "secret.js").write_text("SECRET-VALUE")
    # The rig's seat-snapshot Python (3.13, no zstandard) cannot read zstd blobs.
    monkeypatch.setattr(extract_loop, "_maybe_decompress", lambda blob: b"")
    store = extract_loop._DirectStore(str(db))
    assert store.source_slice("s::ok") == ""  # no decompressor and no repository: nothing
    store = extract_loop._DirectStore(str(db))
    store.repo_root = str(repo)
    assert store.source_slice("s::ok") == "total"
    assert store.source_slice("s::out") == ""  # never outside the repository


# --- review round 4 (codex on #1363) -------------------------------------------------------------

def test_a_write_that_fails_halfway_through_a_rule_says_so(tmp_path, monkeypatch, capsys):
    db, repo, wt, estate, core = _apply_env(tmp_path)
    _write_rules(wt, "", [_rule("s::core")])

    def semantics_times_out(*a, **k):
        raise RuntimeError("wicked-estate exceeded 120s")
    estate.set_requirement = semantics_times_out  # the annotation lands, the requirement does not
    monkeypatch.setattr(_clients, "host_estate_client", lambda db: estate)
    monkeypatch.setattr(_clients, "host_core_client", lambda: core)
    monkeypatch.chdir(wt)
    assert apply_rules.main(["--db", db, "--repo-root", repo]) == 1
    err = capsys.readouterr().err
    assert "FAILED after writing" in err and "s::core may be partly written" in err


def test_prepare_reads_a_store_whose_path_has_uri_characters(tmp_path):
    import shutil as sh
    odd = tmp_path / "Issue#1362?x%"
    odd.mkdir()
    db = str(odd / "estate.db")
    sh.copy(_star(tmp_path), db)
    repo, wt = _git_repo(tmp_path), _wt(tmp_path)
    estate = _Estate()
    doc = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 0, estate=estate,
                                   core=_Core(estate, {s: "f.py" for s in _STAR}))
    assert doc["units"][0]["symbol_id"] == "s::core"


def test_the_published_worklist_fits_even_when_the_estimate_does_not(tmp_path, monkeypatch):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
    estate = _Estate()
    monkeypatch.setattr(extract_loop._DirectStore, "source_slice",
                        lambda self, sid, cap=4000: "line\n" * 300)
    monkeypatch.setattr(prepare_worklist, "_ENVELOPE", 0)  # the estimate alone would let all in
    unit_bytes = 8 * len(rules_file.encoded({"symbol_id": "s::core", "source": "line\n" * 300}))
    monkeypatch.setattr(rules_file, "MAX_WORKLIST_BYTES", unit_bytes + 2000)
    doc = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 0, estate=estate,
                                   core=_Core(estate, {s: "f.py" for s in _STAR}))
    assert len(rules_file.encoded(doc)) <= rules_file.MAX_WORKLIST_BYTES
    assert extract_loop.read_worklist(wt, rules_file.WORKLIST_REL)["units"] == doc["units"]
