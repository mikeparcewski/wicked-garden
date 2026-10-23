"""discover.py: CI config first, then manifests; candidates with file:line; no runner table."""

from __future__ import annotations

from bg_helpers import FIXTURES, run_script


def _discover(name: str) -> dict:
    code, report = run_script("discover", "--repo", str(FIXTURES / name))
    assert code == 0, report
    return report


def test_cargo_repo_names_the_ci_test_step_and_skips_the_build_step():
    report = _discover("cargo-repo")
    assert report["verdict"] == "candidates"
    assert report["files"] == [".github/workflows/ci.yml", "Cargo.toml"]
    commands = [c["command"] for c in report["commands"]]
    assert commands == ["cargo test --workspace --no-fail-fast"]
    assert report["commands"][0]["source"] == ".github/workflows/ci.yml:9"


def test_pytest_repo_reads_a_run_block():
    report = _discover("pytest-repo")
    sources = {c["source"]: c["command"] for c in report["commands"]}
    assert sources == {".github/workflows/ci.yml:13": "pip install pytest",
                       ".github/workflows/ci.yml:14": "python3 -m pytest -q -p no:cacheprovider -rfE"}
    assert "pyproject.toml" in report["files"]


def test_vitest_repo_follows_npm_test_into_the_package_script():
    report = _discover("vitest-repo")
    npm_test = next(c for c in report["commands"] if c["command"] == "npm test")
    assert npm_test["resolves"] == [{"source": "package.json#scripts.test", "command": "vitest run"}]
    assert {"source": "package.json#scripts.test", "command": "vitest run"} in report["commands"]


def test_a_make_target_is_followed_into_its_recipe():
    report = _discover("tinyrun-repo")
    make_test = next(c for c in report["commands"] if c["command"] == "make test")
    assert make_test["resolves"] == [{"source": "Makefile:2", "command": "python3 tinyrun.py"}]
    assert report["files"] == [".github/workflows/ci.yml", "Makefile"]


def test_a_repo_with_no_tests_says_so_even_with_the_npm_placeholder():
    report = _discover("no-tests-repo")
    assert report["verdict"] == "no-test-command"
    assert [c.get("placeholder") for c in report["commands"]] == [True]


def test_a_missing_repo_is_a_usage_error(tmp_path):
    code, report = run_script("discover", "--repo", str(tmp_path / "nope"))
    assert code == 2 and "is not a directory" in report["error"]
