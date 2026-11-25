"""J6 v3 scope, reach and batches (DES-j6-build G1) over real estate graphs.

The two fixture trees under ``fixtures/v3`` were indexed by ``wicked-estate index`` 0.35.10; ``<tree>.sql`` is that
store's ``nodes`` and ``edges`` tables as sqlite3 dumped them, loaded into a scratch store per test. The port's
equivalence with the J6 v3 proof on CardDemo and crew (90 targets, reach 3/3; 13 files, 19 registrations, 14/15
sites; every batch text byte-identical) is a lane check, since those trees are not in this repository.
"""
import os
import sqlite3

import pytest

from domain import batches, defs, graph, lookup, scope

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "v3")


@pytest.fixture
def repo_of(tmp_path):
    made = []

    def make(name):
        made.append(name)
        db = tmp_path / f"{name}-{len(made)}.db"
        con = sqlite3.connect(db)
        with open(os.path.join(FIX, f"{name}.sql")) as fh:
            con.executescript(fh.read())
        con.commit()
        con.close()
        return graph.Repo(os.path.join(FIX, name), str(db))
    return make


def test_a_cobol_program_named_in_the_intent_scopes_its_program_jcl_and_copybooks(repo_of):
    repo = repo_of("mini-cobol")
    sc = scope.build_scope(repo, "Extract the payroll calculation rules (PAYCALC1) and PAYCALC9.")
    assert sc["phrases"] == {"PAYCALC1": ["app/cbl/PAYCALC1.cbl"]}
    assert sc["unmatched_phrases"] == ["PAYCALC9"]
    assert sc["questions"] == ["'PAYCALC9' matches no code: type a file, function or screen name, or drop it"]
    assert sc["reached_from"] == ["STEP1 -> PAYCALC1 (app/jcl/PAYJOB.jcl:2)"]
    assert sc["config_read"] == {"PAYCALC1": ["INFILE=PAY.HOURS.IN"]}
    assert sc["target_files"] == ["app/cbl/PAYCALC1.cbl", "app/jcl/PAYJOB.jcl"]
    assert sc["context_files"] == ["app/cpy/PAYREC.cpy"]
    names = {t.get("name") for t in sc["targets"] if t["kind"] == "node"}
    assert {"MAIN-PARA", "READ-PARA"} <= names
    assert sc["model_calls"] == 0


def test_a_typescript_phrase_matches_its_definition_and_the_route_that_reaches_it(repo_of):
    repo = repo_of("mini-ts")
    sc = scope.build_scope(repo, "Extract the launch posture rules.", ["launch posture", "billing cycle"])
    assert sc["phrases"]["launch posture"]["defs"] == ["launchPosture"]
    # the test file defines a matching name and is not scoped
    assert sc["target_files"] == ["src/core/launch-posture.ts"]
    assert sc["unmatched_phrases"] == ["billing cycle"]
    # POST /runs reaches launchPosture in 2 hops; GET /runs reaches nothing scoped
    assert sc["reached_from"] == ["POST /runs (src/api/routes.ts:5) via launch.ts:3 > launch-posture.ts:3"]
    assert sc["registrations_scanned"] == 2
    assert sc["reached_shown"] == sc["reached_from"] and sc["reached_more"] == 0
    assert sc["config_read"] == {"WICKED_POWER": 1}
    assert [t["name"] for t in sc["targets"]] == ["launchPosture"]


def test_reach_stops_at_its_hop_limit(repo_of):
    from domain import reach
    repo = repo_of("mini-ts")
    scanned, hit = reach.reached_from(repo, {"src/core/launch-posture.ts": ["launchPosture"]}, max_hops=1)
    assert scanned == 2 and hit == []


def test_the_scope_hash_is_stable_and_moves_with_the_code(repo_of, tmp_path):
    repo = repo_of("mini-ts")
    a = scope.build_scope(repo, "x", ["launch posture"])["scope_hash"]
    assert scope.build_scope(repo_of("mini-ts"), "x", ["launch posture"])["scope_hash"] == a
    tree = tmp_path / "tree"
    import shutil
    shutil.copytree(os.path.join(FIX, "mini-ts"), tree)
    (tree / "src/core/launch-posture.ts").write_text((tree / "src/core/launch-posture.ts").read_text() + "\n// edited\n")
    moved = graph.Repo(str(tree), repo.db)
    assert scope.build_scope(moved, "x", ["launch posture"])["scope_hash"] != a


def test_a_cobol_unit_batches_the_program_its_copybook_and_its_jcl(repo_of, tmp_path):
    repo = repo_of("mini-cobol")
    sc = scope.build_scope(repo, "PAYCALC1")
    plan = batches.plan_batches(repo, sc, str(tmp_path / "b"))
    assert [c["files"] for c in plan["calls"]] == [["app/cbl/PAYCALC1.cbl", "app/cpy/PAYREC.cpy", "app/jcl/PAYJOB.jcl"]]
    assert sorted(plan["calls"][0]["targets"]) == sorted(t["id"] for t in sc["targets"])
    text = open(plan["calls"][0]["text_file"]).read()
    assert "app/cpy/PAYREC.cpy:0003|            05  PAY-HOURS" in text


def test_a_typescript_batch_carries_the_spans_its_target_uses(repo_of, tmp_path):
    repo = repo_of("mini-ts")
    sc = scope.build_scope(repo, "x", ["start run"])
    assert [t["name"] for t in sc["targets"]] == ["startRun"]
    plan = batches.plan_batches(repo, sc, str(tmp_path / "b"))
    (call,) = plan["calls"]
    # launchPosture, imported from another file, is shown with the target that calls it
    assert call["shown"] == {"src/core/launch-posture.ts": [3, 4, 5, 6, 7, 8], "src/core/launch.ts": [3, 4, 5, 6]}


def test_copy_resolves_beside_the_program_else_to_the_one_copybook_of_that_name(tmp_path):
    (tmp_path / "src/cbl").mkdir(parents=True)
    (tmp_path / "src/cpy").mkdir()
    (tmp_path / "lib/shared").mkdir(parents=True)
    (tmp_path / "src/cpy/NEAR.cpy").write_text("       01  NEAR-REC PIC X.\n")
    (tmp_path / "lib/shared/FAR.CPY").write_text("       01  FAR-REC PIC X.\n")
    (tmp_path / "src/cbl/P.cbl").write_text("       COPY NEAR.\n       COPY FAR.\n       COPY NONE.\n")
    defs.set_root(str(tmp_path))
    assert defs.copybooks("src/cbl/P.cbl") == ["src/cpy/NEAR.cpy", "lib/shared/FAR.CPY"]


def test_a_bms_symbolic_map_is_not_resolved_as_a_copybook(tmp_path):
    (tmp_path / "app/cbl").mkdir(parents=True)
    (tmp_path / "app/cpy").mkdir()
    (tmp_path / "app/cpy-bms").mkdir()
    (tmp_path / "app/bms").mkdir()
    (tmp_path / "app/cpy/REC.cpy").write_text("       01  REC PIC X.\n")
    (tmp_path / "app/cpy-bms/SCRN01.CPY").write_text("       01  SCRN01I.\n           02  FLDI PIC X.\n")
    (tmp_path / "app/bms/SCRN01.bms").write_text("SCRN01 DFHMSD TYPE=MAP\n")
    (tmp_path / "app/cbl/P.cbl").write_text("       COPY REC.\n       COPY SCRN01.\n")
    defs.set_root(str(tmp_path))
    # the map's fields are screen I/O: the J6 v3 checker was calibrated without them
    assert defs.copybooks("app/cbl/P.cbl") == ["app/cpy/REC.cpy"]


def test_the_language_split_replaces_the_proofs_repository_split():
    assert lookup.lang_of("app/cbl/X.cbl") == "cobol"
    assert lookup.lang_of("app/jcl/X.jcl") == "cobol"
    assert lookup.lang_of("src/a.ts") == "ts"
    assert lookup.lang_of("src/a.py") == "other"
    assert lookup.card_facts(None, "app/cbl/X.cbl").startswith("CARD FACTS")
    assert lookup.card_facts(None, "app/cbl/X.cbl") != lookup.card_facts(None, "src/a.ts")


def test_a_phrase_of_only_stopwords_matches_nothing_and_asks(repo_of):
    # `all([])` is true: a phrase with no word left would match every definition in the repository
    repo = repo_of("mini-ts")
    sc = scope.build_scope(repo, "x", ["the of", "launch posture"])
    assert sc["phrases"]["the of"]["n"] == 0
    assert sc["target_files"] == ["src/core/launch-posture.ts"]
    assert sc["unmatched_phrases"] == ["the of"]
    assert "'the of' has no word to match: type a file, function or screen name, or drop it" in sc["questions"]
