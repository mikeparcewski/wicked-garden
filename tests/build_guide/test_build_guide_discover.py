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
    assert commands == ["cargo test --locked --workspace --no-fail-fast"]
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


def test_ci_steps_list_every_gating_command_not_only_tests():
    report = _discover("cargo-repo")
    assert [(s["source"], s["command"]) for s in report["ciSteps"]] == [
        (".github/workflows/ci.yml:8", "cargo build --locked --workspace"),
        (".github/workflows/ci.yml:9", "cargo test --locked --workspace --no-fail-fast")]
    vitest = _discover("vitest-repo")
    assert [s["command"] for s in vitest["ciSteps"]] == ["npm install --no-audit --no-fund", "npm test"]


def _repo(tmp_path, workflow: str, files: dict | None = None):
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text(workflow, encoding="utf-8")
    for rel, body in (files or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body, encoding="utf-8")
    return repo


def test_a_dash_run_block_ends_at_the_steps_other_keys(tmp_path):
    """`- run: |` with sibling keys after the block (agy on #1332): only the block is commands."""
    repo = _repo(tmp_path, "jobs:\n  t:\n    steps:\n      - run: |\n          cargo test\n"
                           "        working-directory: crates/foo\n        env:\n          X: 1\n")
    code, report = run_script("discover", "--repo", str(repo))
    assert code == 0
    assert [(s["command"], s["cwd"]) for s in report["ciSteps"]] == [("cargo test", "crates/foo")]


def test_a_step_in_a_subdirectory_resolves_that_directorys_scripts(tmp_path):
    """`npm test` with `working-directory: web` reads web/package.json, not the root's (agy on #1332)."""
    repo = _repo(tmp_path, "jobs:\n  t:\n    steps:\n      - run: npm test\n        working-directory: web\n",
                 {"package.json": '{"scripts": {"test": "echo root"}}',
                  "web/package.json": '{"scripts": {"test": "vitest run"}}'})
    code, report = run_script("discover", "--repo", str(repo))
    step = next(s for s in report["ciSteps"] if s["command"] == "npm test")
    assert step["resolves"] == [{"source": "web/package.json#scripts.test", "command": "vitest run"}]


def test_a_wrapper_whose_recipe_runs_the_tests_is_a_candidate(tmp_path):
    """`make check` running pytest is not "no test command" (codex on #1332)."""
    repo = _repo(tmp_path, "jobs:\n  t:\n    steps:\n      - run: make check\n",
                 {"Makefile": "check:\n\tpython3 -m pytest -q\n"})
    code, report = run_script("discover", "--repo", str(repo))
    assert report["verdict"] == "candidates"
    assert any(c["command"] == "make check" for c in report["commands"])
