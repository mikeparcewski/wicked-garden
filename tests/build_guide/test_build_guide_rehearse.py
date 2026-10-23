"""rehearse.py against REAL runners in scratch copies of the fixture repos.

* tinyrun (a runner with no structured output) and pytest run everywhere (pytest is in CI).
* cargo runs where cargo is on PATH (GitHub's ubuntu runners have it).
* vitest needs `npm install`, so it is opt-in: WICKED_GARDEN_E2E_NPM=1 (the env the MCP template
  E2E uses).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from bg_helpers import FIXTURES, GUIDES, SEEDS, run_script

ALL_PASS = {"list": "pass", "run": "pass", "mutation": "pass", "ids": "pass", "alone": "pass",
            "deselect": "pass", "multi": "pass"}


def _rehearse(repo: Path, guide: Path, env: dict | None = None, timeout: int = 300) -> tuple[int, dict]:
    return run_script("rehearse", "--repo", str(repo), "--guide", str(guide), env=env, timeout=timeout)


def _results(report: dict) -> dict:
    return report["checks"][0]["results"]


def _variant(tmp_path: Path, source: Path, edit) -> Path:
    guide = json.loads(source.read_text(encoding="utf-8"))
    edit(guide["checks"][0])
    path = tmp_path / f"variant-{source.name}"
    path.write_text(json.dumps(guide), encoding="utf-8")
    return path


def test_tinyrun_text_parser_passes_every_probe(python3_on_path):
    code, report = _rehearse(FIXTURES / "tinyrun-repo", GUIDES / "tinyrun-text.json", python3_on_path)
    assert code == 0, report
    assert _results(report) == ALL_PASS
    assert report["rehearsal"] is True and "verified is not written" in report["note"]


def test_tinyrun_per_line_rule_is_forged_by_test_output(tmp_path, python3_on_path):
    def per_line(check):
        check["parser"] = {"failed": ["^\\[[a-z]+\\] (?P<id>\\S+) \\.\\.\\. FAIL$"]}

    code, report = _rehearse(FIXTURES / "tinyrun-repo", _variant(tmp_path, GUIDES / "tinyrun-text.json", per_line),
                             python3_on_path)
    assert code == 1
    assert _results(report)["run"] == "fail: exit 0 with 1 parsed failure(s)"


def test_rehearsal_never_writes_the_guide(tmp_path, python3_on_path):
    guide = tmp_path / "guide.json"
    shutil.copyfile(GUIDES / "tinyrun-text.json", guide)
    before = guide.read_bytes()
    _rehearse(FIXTURES / "tinyrun-repo", guide, python3_on_path)
    assert guide.read_bytes() == before


def test_a_red_base_still_rehearses_and_the_mutation_is_the_one_new_failure(fixture_copy, python3_on_path):
    repo = fixture_copy("tinyrun-repo")
    (repo / "checks" / "broken.tc").write_text("off 1 == 0\n", encoding="utf-8")
    code, report = _rehearse(repo, GUIDES / "tinyrun-text.json", python3_on_path)
    assert code == 0, report
    assert _results(report) == ALL_PASS


def test_a_red_exit_with_no_parsed_failure_fails_the_run_probe(fixture_copy, python3_on_path):
    repo = fixture_copy("tinyrun-repo")
    (repo / "checks" / "unreadable.tc").write_text("bad 1 == x\n", encoding="utf-8")
    code, report = _rehearse(repo, GUIDES / "tinyrun-text.json", python3_on_path)
    assert code == 1
    assert _results(report)["run"].startswith("fail: exit 1 with 0 parsed failure(s)")


def test_a_guide_that_does_not_lint_is_refused_before_anything_runs(tmp_path):
    bad = _variant(tmp_path, GUIDES / "tinyrun-text.json", lambda c: c["deselect"].update(append=["--skip"]))
    code, report = _rehearse(FIXTURES / "tinyrun-repo", bad)
    assert code == 2 and report["ok"] is False
    assert any("deselect.append" in e for e in report["errors"])


def test_pytest_short_summary_seed_passes_every_probe(python3_on_path):
    code, report = _rehearse(FIXTURES / "pytest-repo", SEEDS / "pytest-short-summary.json", python3_on_path)
    assert code == 0, report
    assert _results(report) == ALL_PASS


def test_pytest_seed_passes_in_ci_mode_too(python3_on_path):
    """With CI set, pytest's short summary prints multi-line messages unless --force-short-summary."""
    code, report = _rehearse(FIXTURES / "pytest-repo", SEEDS / "pytest-short-summary.json",
                             {**python3_on_path, "CI": "true"})
    assert code == 0, report
    assert _results(report) == ALL_PASS


def test_pytest_seed_without_force_short_summary_loses_failures_in_ci_mode(tmp_path, python3_on_path):
    guide = _variant(tmp_path, SEEDS / "pytest-short-summary.json", lambda c: c["results"]["how"].update(argvAppend=[]))
    code, report = _rehearse(FIXTURES / "pytest-repo", guide, {**python3_on_path, "CI": "true"})
    assert code == 1
    assert _results(report)["multi"].startswith("fail: with both mutations the new failures are [('', "
                                                "'tests/test_wicked_mutation.py::test_wicked_mutation_probe')]")


def test_pytest_junit_ids_fail_the_ids_probe_for_class_methods(python3_on_path):
    """xunit1 JUnit with id [file, name] equals the node id only for module-level tests; a class
    method's node id carries its class. Only the `ids` probe sees it."""
    code, report = _rehearse(FIXTURES / "pytest-repo", GUIDES / "pytest-junit.json", python3_on_path)
    results = _results(report)
    assert code == 1
    assert {k: v for k, v in results.items() if k != "ids"} == {k: v for k, v in ALL_PASS.items() if k != "ids"}
    assert results["ids"] == ("fail: the results name `tests/test_calc.py::test_param[1]` (q ``), "
                              "which the list does not")


needs_cargo = pytest.mark.skipif(shutil.which("cargo") is None, reason="needs cargo on PATH")


@needs_cargo
def test_cargo_libtest_seed_passes_every_probe():
    code, report = _rehearse(FIXTURES / "cargo-repo", SEEDS / "cargo-libtest.json", timeout=600)
    assert code == 0, report
    assert _results(report) == ALL_PASS


@needs_cargo
def test_cargo_flag_and_value_in_two_tokens_breaks_two_ids(tmp_path):
    """Only the tokens from the first {id} on repeat per id, so `--skip`, `{id}` becomes
    `--skip a b`: libtest takes `b` as a filter and runs the second mutation (exit 101)."""

    def split_flag(check):
        check["deselect"]["append"] = ["--", "--skip", "{id}", "--exact"]

    guide = _variant(tmp_path, SEEDS / "cargo-libtest.json", split_flag)
    code, report = _rehearse(FIXTURES / "cargo-repo", guide, timeout=600)
    results = _results(report)
    assert code == 1
    assert {k: v for k, v in results.items() if k != "multi"} == {k: v for k, v in ALL_PASS.items() if k != "multi"}
    assert results["multi"] == "fail: deselecting both did not leave the clean run's failures (exit 101)"


@pytest.mark.skipif(os.environ.get("WICKED_GARDEN_E2E_NPM") != "1" or shutil.which("npm") is None,
                    reason="needs the npm registry: set WICKED_GARDEN_E2E_NPM=1")
def test_vitest_junit_seed_fails_only_multi(fixture_copy):
    """vitest's JUnit reports the tests a name filter left out as <skipped/> testcases, which
    neither pass nor fail, so `alone` passes; vitest rejects a repeated name pattern, so the two-id
    deselect in `multi` fails."""
    repo = fixture_copy("vitest-repo")
    subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=repo, check=True, capture_output=True,
                   timeout=300)
    code, report = _rehearse(repo, SEEDS / "vitest-junit.json", timeout=600)
    results = _results(report)
    assert code == 1
    assert results["multi"] == "fail: deselecting both did not leave the clean run's failures (exit 1)"
    assert {k: v for k, v in results.items() if k != "multi"} == {k: v for k, v in ALL_PASS.items() if k != "multi"}

