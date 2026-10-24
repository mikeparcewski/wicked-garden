"""check.py: a guide against contract v1 (wicked-core's schema, vendored) plus the lint the schema does not express."""

from __future__ import annotations

import copy
import shutil
import hashlib
import json
from pathlib import Path

import pytest

from bg_helpers import FIXTURES, GUIDES, REPO, SEEDS, run_script

SCHEMA = REPO / "schemas" / "build-guide.v1.json"
# git blob sha of schemas/build-guide.v1.json on wicked-core feat/floor-v2-exit-codes@b923fed (#1066).
CORE_BLOB = "ea27dc4455945fb6bbcf5a42c0168b86d0216cc2"
SEED_REPOS = {
    "cargo-libtest.json": "cargo-repo",
    "pytest-short-summary.json": "pytest-repo",
    "vitest-junit.json": "vitest-repo",
}


def _write(tmp_path: Path, guide: dict) -> Path:
    path = tmp_path / "guide.json"
    path.write_text(json.dumps(guide), encoding="utf-8")
    return path


def _t(guide: dict) -> dict:
    """The guide's test check (the one with a `list`)."""
    return next(c for c in guide["checks"] if "list" in c)


def _seed(name: str = "cargo-libtest.json") -> dict:
    return json.loads((SEEDS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("seed,repo", sorted(SEED_REPOS.items()))
def test_every_seed_is_a_clean_draft_for_its_fixture_repo(seed, repo):
    code, report = run_script("check", "--guide", str(SEEDS / seed), "--repo", str(FIXTURES / repo), "--draft")
    assert code == 0, report["errors"]
    assert report["schema"].startswith("wicked-core feat/floor-v2-exit-codes@b923fed")


@pytest.mark.parametrize("guide,repo", [("tinyrun-text.json", "tinyrun-repo"), ("pytest-junit.json", "pytest-repo")])
def test_test_guides_are_clean_drafts(guide, repo):
    code, report = run_script("check", "--guide", str(GUIDES / guide), "--repo", str(FIXTURES / repo), "--draft")
    assert code == 0, report["errors"]


def test_a_draft_carrying_verified_is_refused(tmp_path):
    guide = _seed()
    _t(guide)["verified"] = {"baseSha": "abc", "runnerVersion": "x", "at": "now", "results": {"mutation": "pass"}}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any("only `wicked-core floor probe` writes it" in e for e in report["errors"])


def test_a_probed_guide_may_carry_verified(tmp_path):
    guide = _seed()
    _t(guide)["verified"] = {"baseSha": "abc", "runnerVersion": "cargo 1.99.0", "at": "2026-10-23T00:00:00Z",
                                      "results": {"mutation": "pass", "deselect": "fail: exit 101"}}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)))
    assert code == 0, report["errors"]


@pytest.mark.parametrize("mutate,needle", [
    (lambda g: g.update(extra=1), "additional property 'extra'"),
    (lambda g: _t(g).update(results={"kind": "xml", "how": {}}), "is not one of"),
    (lambda g: _t(g).pop("parser"), "results.kind=text needs a parser"),
    (lambda g: _t(g)["probes"]["mutation"].pop("expectId"), "missing required property 'expectId'"),
    (lambda g: _t(g).update(stage="creator"), "is not of type 'array'"),
    (lambda g: _t(g).update(failedExit=["101"]), "is not of type 'integer'"),
    (lambda g: _t(g).pop("alone"), "alone: missing or empty; the floor will not use this check"),
    (lambda g: _t(g).pop("deselect"), "deselect: missing or empty; the floor will not use this check"),
    (lambda g: _t(g).update(failedExit=[]), "the floor would not load this guide: the check has a `list` and no "
                                            "`failedExit`"),
    (lambda g: _t(g).update(stage=["ci"]), "the floor would not load this guide: the check has a `stage` other than"),
    (lambda g: _t(g).update(run=[]), "the floor would not load this guide: the check has an empty `run`"),
    (lambda g: _t(g)["probes"].pop("mutation"), "probes.mutation: missing; the `mutation` probe"),
    (lambda g: _t(g)["probes"].pop("mutation2"), "probes.mutation2: missing; the `multi` probe"),
    (lambda g: _t(g)["probes"].update(mutation2=dict(_t(g)["probes"]["mutation"])),
     "must be a second, distinct failing test"),
    (lambda g: g.pop("derivedFrom"), "derivedFrom: missing or empty"),
    (lambda g: _t(g)["results"].update(id=["name"]), "id/idJoin are only for results.kind=junit"),
    (lambda g: (_t(g).pop("parser"), _t(g).update(results={"kind": "tap", "how": {}})),
     "tap is reserved in v1"),
    (lambda g: g.update(version=2), "!= const 1"),
])
def test_schema_violations_are_named(tmp_path, mutate, needle):
    guide = _seed()
    mutate(guide)
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any(needle in e for e in report["errors"]), report["errors"]


@pytest.mark.parametrize("rule,needle", [
    ("^(?=x)failures:$", "lookaround"),
    ("^(a)\\1$", "backreference"),
    ("^failures:(", "does not compile"),
])
def test_parser_regexes_must_be_anchored_re2(tmp_path, rule, needle):
    guide = _seed()
    _t(guide)["parser"]["blocks"][0]["start"] = rule
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any(needle in e for e in report["errors"]), report["errors"]


def test_an_unanchored_rule_is_a_warning_not_an_error(tmp_path):
    guide = _seed()
    _t(guide)["parser"]["blocks"][0]["end"] = "^test result: FAILED"
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 0, report["errors"]
    assert any("not anchored ^...$" in w for w in report["warnings"])


def test_item_rules_need_an_id_group_and_templates_their_placeholders(tmp_path):
    guide = _seed()
    check = _t(guide)
    check["parser"]["blocks"][0]["item"] = "^    (\\S+)$"
    check["alone"]["run"] = ["cargo", "test"]
    check["deselect"]["append"] = ["--skip"]
    check["affected"] = {"run": ["cargo", "test"]}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    text = "\n".join(report["errors"])
    assert code == 1
    for needle in ("needs a (?P<id>...) group", "alone.run: needs an {id}", "deselect.append: needs an {id}",
                   "affected.run: needs a {files}"):
        assert needle in text


def test_a_parser_on_a_structured_kind_is_refused(tmp_path):
    guide = _seed()
    _t(guide)["results"] = {"kind": "junit", "how": {"path": "out.xml"}}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any("only for results.kind=text" in e for e in report["errors"])


def test_paths_must_be_repo_relative_and_derived_from_files_must_exist(tmp_path):
    guide = _seed()
    guide["derivedFrom"] = ["../outside.yml", "missing.toml"]
    _t(guide)["probes"]["mutation"]["file"] = "/abs/probe.rs"
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(FIXTURES / "cargo-repo"),
                              "--draft")
    text = "\n".join(report["errors"])
    assert code == 1
    assert "must be repo-relative" in text and "'missing.toml' matches nothing in the repo" in text


def test_a_mutation_over_an_existing_file_warns(tmp_path):
    guide = _seed()
    _t(guide)["probes"]["mutation"]["file"] = "src/lib.rs"
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(FIXTURES / "cargo-repo"),
                              "--draft")
    assert code == 0
    assert any("would overwrite a real file" in w for w in report["warnings"])


def test_the_vendored_schema_is_byte_for_byte_wicked_cores():
    data = SCHEMA.read_bytes()
    assert hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == CORE_BLOB


def test_a_schema_with_keywords_the_validator_cannot_check_is_refused(tmp_path):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    strict = copy.deepcopy(schema)
    strict["properties"]["checks"]["uniqueItems"] = True
    schema_path = tmp_path / "core-schema.json"
    schema_path.write_text(json.dumps(strict), encoding="utf-8")
    code, report = run_script("check", "--guide", str(SEEDS / "cargo-libtest.json"), "--schema", str(schema_path))
    assert code == 1
    assert "does not implement" in report["errors"][0] and "uniqueItems" in report["errors"][0]
    assert report["schema"] == str(schema_path)


def test_core_s_own_guide_checks_clean_and_its_stale_verified_is_flagged():
    """core's guide at 3fb9c86 declares gates without results and a version piece; its committed
    `verified` predates the version probe, so the floor would not rely on it yet."""
    code, report = run_script("check", "--guide", str(GUIDES / "wicked-core.json"))
    assert code == 0, report["errors"]
    assert any("the floor will not rely on this check (version: never ran)" in w for w in report["warnings"])


def test_a_probed_guide_whose_required_probe_failed_is_flagged(tmp_path):
    guide = _seed()
    _t(guide)["verified"] = {"baseSha": "abc", "runnerVersion": "cargo 1.99.0", "at": "2026-10-23T00:00:00Z",
                                      "results": {p: "pass" for p in ("list", "run", "ids", "alone", "deselect",
                                                                      "mutation")}}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)))
    assert code == 0
    assert any("the floor will not rely on this check (multi: never ran; version: never ran)" in w for w in report["warnings"])


def test_a_shell_in_argv_is_flagged(tmp_path):
    guide = _seed()
    _t(guide)["run"] = ["sh", "-c", "cargo test"]
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert any("runs through a shell" in w for w in report["warnings"])


def test_a_gate_check_needs_no_list_or_probes(tmp_path):
    guide = _seed()
    gate = next(c for c in guide["checks"] if "list" not in c)
    assert gate["name"] == "build"
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(FIXTURES / "cargo-repo"),
                              "--draft")
    assert code == 0, report["errors"]
    assert not [w for w in report["warnings"] if "checks[0]" in w]


def test_a_ci_step_the_guide_does_not_declare_is_flagged(tmp_path):
    guide = _seed()
    guide["checks"] = [c for c in guide["checks"] if "list" in c]
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(FIXTURES / "cargo-repo"),
                              "--draft")
    assert code == 0
    flagged = [w for w in report["warnings"] if w.startswith("CI runs")]
    assert len(flagged) == 1
    assert flagged[0].startswith("CI runs `cargo build --locked --workspace` (.github/workflows/ci.yml:8) but no check "
                                 "declares it there")


@pytest.mark.parametrize("seed,repo", sorted(SEED_REPOS.items()))
def test_every_seed_declares_every_ci_step_of_its_fixture(seed, repo):
    code, report = run_script("check", "--guide", str(SEEDS / seed), "--repo", str(FIXTURES / repo), "--draft")
    assert not [w for w in report["warnings"] if w.startswith("CI runs")], report["warnings"]


def test_make_and_npm_indirection_count_as_declared():
    code, report = run_script("check", "--guide", str(GUIDES / "tinyrun-text.json"), "--repo",
                              str(FIXTURES / "tinyrun-repo"), "--draft")
    assert not [w for w in report["warnings"] if w.startswith("CI runs")]


def test_a_retried_pass_counts_as_passed(tmp_path):
    guide = _seed()
    _t(guide)["verified"] = {"baseSha": "abc", "runnerVersion": "cargo 1.99.0", "at": "2026-10-23T00:00:00Z",
                             "results": {p: "pass" for p in ("list", "run", "ids", "alone", "deselect", "mutation",
                                                             "version")} | {"multi": "pass (retried)"}}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)))
    assert code == 0 and not [w for w in report["warnings"] if "will not rely" in w]


def test_ids_re_all_among_the_per_id_tokens_is_refused(tmp_path):
    guide = _seed("vitest-junit.json")
    _t(guide)["deselect"]["append"] = ["--not={id}", "--all={ids:re|}", "--raw={id}"]
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any("`{ids:re|}` among the per-id tokens of `deselect.append` (it is once-only)" in e
               for e in report["errors"])


def test_a_version_piece_on_a_gate_is_refused_by_the_schema(tmp_path):
    guide = _seed()
    next(c for c in guide["checks"] if "list" not in c)["version"] = {"run": ["cargo", "--version"]}
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any("property 'version' requires property 'list'" in e for e in report["errors"])


def test_a_list_needs_results(tmp_path):
    guide = _seed()
    _t(guide).pop("results")
    _t(guide).pop("parser")
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert any("property 'list' requires property 'results'" in e for e in report["errors"])


def test_derived_from_takes_git_pathspec_globs(tmp_path):
    guide = _seed()
    guide["derivedFrom"] = ["Cargo.toml", ".github/workflows/*.yml", "crates/*/Cargo.toml"]
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(FIXTURES / "cargo-repo"),
                              "--draft")
    assert code == 1
    assert [e for e in report["errors"] if "derivedFrom" in e] == [
        "derivedFrom[2]: 'crates/*/Cargo.toml' matches nothing in the repo"]


def test_a_ci_step_in_a_sub_package_must_be_declared_with_that_cwd(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES / "cargo-repo", repo)
    (repo / "web").mkdir()
    ci = repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(ci.read_text(encoding="utf-8") + "      - name: web lint\n        working-directory: web\n"
                  "        run: npm run lint\n", encoding="utf-8")
    guide = _seed()
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(repo), "--draft")
    flagged = [w for w in report["warnings"] if w.startswith("CI runs")]
    assert len(flagged) == 1 and flagged[0].startswith("CI runs `npm run lint` in `web`")
    guide["checks"].insert(0, {"name": "web-lint", "cwd": "web", "stage": ["verify"], "run": ["npm", "run", "lint"]})
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--repo", str(repo), "--draft")
    assert not [w for w in report["warnings"] if w.startswith("CI runs")]


@pytest.mark.parametrize("edit,needle", [
    (lambda c: c.update(failedExit=[0, 101]), "`0` in `failedExit` (a failure exits nonzero)"),
    (lambda c: c.update(cwd="../x"), "a `cwd` that is absolute, climbs (`..`) or has an empty segment"),
    (lambda c: c.update(cwd="/abs"), "a `cwd` that is absolute, climbs (`..`) or has an empty segment"),
    (lambda c: c.update(cwd="a//b"), "a `cwd` that is absolute, climbs (`..`) or has an empty segment"),
    (lambda c: c["deselect"].update(append=["--suite={q}", "--p=^(?!(?:{ids:re|})$)"]),
     "`{ids:re|}` and `{q}` in one `deselect.append` (the pattern cannot bind ids to qualifiers)"),
])
def test_core_load_time_refusals_are_reported_in_its_words(tmp_path, edit, needle):
    guide = _seed()
    edit(_t(guide))
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert code == 1
    assert any("the floor would not load this guide" in e and needle in e for e in report["errors"]), report["errors"]


def test_a_nested_cwd_is_fine(tmp_path):
    guide = _seed()
    guide["checks"].insert(0, {"name": "sub", "cwd": "crates/x", "run": ["cargo", "fmt", "--check"]})
    code, report = run_script("check", "--guide", str(_write(tmp_path, guide)), "--draft")
    assert not [e for e in report["errors"] if "cwd" in e]
