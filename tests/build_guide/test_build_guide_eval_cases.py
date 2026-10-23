"""The build-guide eval cases are well formed, and their expectations agree with the reference outputs.

This grades the REFERENCE outputs (the seeds and test guides, plus a reference final message) with
eval_grade.py. That proves the grader and the cases agree. Grading an agent's run is user-triggered
(see eval_cases/README.md).
"""

from __future__ import annotations

import importlib.util
import json
import shutil

import pytest

from bg_helpers import FIXTURES, GUIDES, HERE, SEEDS

CASES = sorted((HERE / "eval_cases").glob("*.json"))
UNAVAILABLE = "probe unavailable: the guide is unverified, so the floor will not use it for exclusion"
NO_GUIDE = "no build/test guide: the floor will run this repo's checks exit-code only"
REQUIRED = {"case_id", "skill", "fixture", "prompt", "host", "expect", "rationale"}
EXPECT_KEYS = {"guide", "check_draft_ok", "results_kind", "parser_uses", "derivedFrom_includes", "no_verified",
               "rehearsal", "message_includes", "message_includes_any"}

_spec = importlib.util.spec_from_file_location("build_guide_eval_grade", HERE / "eval_grade.py")
grader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grader)

REFERENCE = {
    "cargo-text-parser": (SEEDS / "cargo-libtest.json", UNAVAILABLE),
    "pytest-junit": (SEEDS / "pytest-short-summary.json",
                     f"JUnit ids (classname + name) do not round-trip to pytest node ids; using the short test "
                     f"summary. {UNAVAILABLE}"),
    "vitest-junit": (SEEDS / "vitest-junit.json",
                     f"deselect-many failed: vitest rejects a repeated name pattern; alone failed: vitest's JUnit "
                     f"lists filtered-out tests as skipped testcases. {UNAVAILABLE}"),
    "fake-runner-no-structured-output": (GUIDES / "tinyrun-text.json", UNAVAILABLE),
    "no-tests": (None, NO_GUIDE),
}


def test_there_is_one_case_per_required_scenario():
    assert {p.stem for p in CASES} == set(REFERENCE)


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_case_shape(path):
    case = json.loads(path.read_text(encoding="utf-8"))
    assert REQUIRED <= set(case), REQUIRED - set(case)
    assert case["case_id"] == path.stem
    assert case["skill"] == "wicked-garden-build-guide"
    assert (FIXTURES / case["fixture"]).is_dir()
    assert set(case["expect"]) <= EXPECT_KEYS, set(case["expect"]) - EXPECT_KEYS
    assert case["expect"]["guide"] in ("present", "absent")


def _grade(case_id: str, tmp_path):
    case = json.loads((HERE / "eval_cases" / f"{case_id}.json").read_text(encoding="utf-8"))
    guide, message = REFERENCE[case_id]
    return grader.grade(case, FIXTURES / case["fixture"], message, guide)


@pytest.mark.parametrize("case_id", ["fake-runner-no-structured-output", "pytest-junit", "no-tests"])
def test_reference_outputs_pass_their_case(case_id, tmp_path, python3_on_path, monkeypatch):
    monkeypatch.setenv("PATH", python3_on_path["PATH"])
    result = _grade(case_id, tmp_path)
    assert result["ok"], result["assertions"]


@pytest.mark.skipif(shutil.which("cargo") is None, reason="needs cargo on PATH")
def test_cargo_reference_output_passes_its_case(tmp_path):
    result = _grade("cargo-text-parser", tmp_path)
    assert result["ok"], result["assertions"]


def test_a_junit_guide_fails_the_pytest_case(tmp_path, python3_on_path, monkeypatch):
    monkeypatch.setenv("PATH", python3_on_path["PATH"])
    case = json.loads((HERE / "eval_cases" / "pytest-junit.json").read_text(encoding="utf-8"))
    result = grader.grade(case, FIXTURES / "pytest-repo", UNAVAILABLE, GUIDES / "pytest-junit.json")
    assert not result["ok"]
    assert result["assertions"]["results kind"] == "fail: kind is junit"
    assert result["assertions"]["rehearsal"].startswith("fail:")


def test_a_hand_written_verified_fails_a_case(tmp_path, python3_on_path, monkeypatch):
    monkeypatch.setenv("PATH", python3_on_path["PATH"])
    guide = json.loads((GUIDES / "tinyrun-text.json").read_text(encoding="utf-8"))
    guide["checks"][0]["verified"] = {"baseSha": "x", "runnerVersion": "x", "at": "x", "results": {"mutation": "pass"}}
    path = tmp_path / "build-guide.json"
    path.write_text(json.dumps(guide), encoding="utf-8")
    case = json.loads((HERE / "eval_cases" / "fake-runner-no-structured-output.json").read_text(encoding="utf-8"))
    result = grader.grade(case, FIXTURES / "tinyrun-repo", UNAVAILABLE, path)
    assert result["assertions"]["no hand-written verified"].startswith("fail")
    assert result["assertions"]["check --draft"].startswith("fail")


def test_inventing_a_guide_for_the_no_tests_repo_fails(tmp_path):
    case = json.loads((HERE / "eval_cases" / "no-tests.json").read_text(encoding="utf-8"))
    result = grader.grade(case, FIXTURES / "no-tests-repo", "here is your guide", GUIDES / "tinyrun-text.json")
    assert not result["ok"]
    assert result["assertions"]["guide"] == "fail: guide is present"
