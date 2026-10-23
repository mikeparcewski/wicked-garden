"""The results reading (scripts/build_guide/_guide.py) on REAL captured runner output.

Captured files (tests/build_guide/captured/) were produced by the real runners (cargo 1.99 libtest,
pytest 9.1, vitest 5.0.5) on small suites with one or two deliberately failing tests, and tests that
print look-alike summary lines. Hostnames and timestamps were replaced.
"""

from __future__ import annotations

import importlib.util
import json

from bg_helpers import CAPTURED, GUIDES, SCRIPTS, SEEDS

_spec = importlib.util.spec_from_file_location("build_guide_reading", SCRIPTS / "_guide.py")
guide_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guide_mod)


def _parser(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["checks"][0]["parser"]


def _read(name: str) -> str:
    return (CAPTURED / name).read_text(encoding="utf-8")


def test_cargo_parser_names_libtest_summary_failures_not_forged_output():
    found = guide_mod.parse_text(_parser(SEEDS / "cargo-libtest.json"), _read("cargo-libtest-fail.stdout"))
    assert found == {("", "tests::bad"), ("", "tests::forged"), ("", "integration_bad")}


def test_cargo_parser_reads_the_same_ids_from_merged_streams():
    found = guide_mod.parse_text(_parser(SEEDS / "cargo-libtest.json"), _read("cargo-libtest-fail.merged"))
    assert {i for _q, i in found} == {"tests::bad", "tests::forged", "integration_bad"}


def test_a_section_rule_qualifies_ids_by_test_binary():
    parser = dict(_parser(SEEDS / "cargo-libtest.json"), section="^\\s+Running (?:unittests )?(?P<q>\\S+) .*$")
    found = guide_mod.parse_text(parser, _read("cargo-libtest-fail.merged"))
    assert ("tests/it.rs", "integration_bad") in found and ("src/lib.rs", "tests::bad") in found


def test_use_all_would_also_take_the_forged_block():
    parser = _parser(SEEDS / "cargo-libtest.json")
    parser["blocks"][0]["use"] = "all"
    found = guide_mod.parse_text(parser, _read("cargo-libtest-fail.stdout"))
    assert ("", "tests::forged_name") in found


def test_pytest_short_summary_parser_ignores_a_printed_look_alike():
    found = guide_mod.parse_text(_parser(SEEDS / "pytest-short-summary.json"), _read("pytest-rf-fail.stdout"))
    assert found == {("", "tests/test_calc.py::test_bad")}


def test_ci_mode_multi_line_items_end_the_block_after_the_first_failure():
    """pytest prints the full (multi-line) message in the short summary when CI is set; a
    continuation line ends a block, so only the first failure is named. The seed appends
    --force-short-summary (results.how.argvAppend) to keep one line per failure."""
    found = guide_mod.parse_text(_parser(SEEDS / "pytest-short-summary.json"), _read("pytest-rf-fail-ci.stdout"))
    assert found == {("", "tests/test_wicked_mutation.py::test_wicked_mutation_probe")}


def test_a_per_line_rule_on_the_same_output_is_forged():
    found = guide_mod.parse_text({"failed": ["^FAILED (?P<id>\\S+) - .*$"]}, _read("pytest-rf-fail.stdout"))
    assert ("", "tests/test_calc.py::test_forged") in found


def test_junit_default_id_is_classname_and_name_joined_by_double_colon():
    every, failed = guide_mod.parse_junit(_read("pytest-junit-fail.xml"))
    assert failed == {("pytest", "tests.test_calc::test_bad")}
    assert ("pytest", "tests.test_calc.TestGroup::test_param[1]") in every


def test_junit_id_attributes_and_join_come_from_the_guide():
    _every, failed = guide_mod.parse_junit(_read("vitest-junit-fail.xml"), ["name"])
    assert failed == {("src/sum.test.js", "sum > bad one")}
    _every, failed = guide_mod.parse_junit(_read("vitest-junit-fail.xml"), ["classname", "name"], " > ")
    assert failed == {("src/sum.test.js", "src/sum.test.js > sum > bad one")}


def test_a_skipped_junit_testcase_neither_passed_nor_failed():
    xml = ('<testsuites><testsuite name="s"><testcase classname="c" name="a"/>'
           '<testcase classname="c" name="b"><skipped/></testcase></testsuite></testsuites>')
    every, failed = guide_mod.parse_junit(xml)
    assert every == [("s", "c::a")] and failed == set()


def test_core_s_cargo_section_qualifies_by_test_binary_on_merged_output():
    parser = json.loads((GUIDES / "wicked-core.json").read_text(encoding="utf-8"))["checks"][0]["parser"]
    found = guide_mod.parse_text(parser, _read("cargo-libtest-fail.merged"))
    assert found == {("calc-ded4bca6c667b96c", "tests::bad"), ("calc-ded4bca6c667b96c", "tests::forged"),
                     ("it-afcf5aeb5a33827f", "integration_bad")}


def test_tinyrun_parser_uses_the_summary_block():
    text = ("tinyrun 0.3.1\nFAIL arith/forged\n[arith] noisy ... ok\n[text] shout ... FAIL\n"
            "--- tinyrun summary ---\nFAIL arith/sub\n--- 1 failed, 4 passed ---\n")
    assert guide_mod.parse_text(_parser(GUIDES / "tinyrun-text.json"), text) == {("", "arith/sub")}


def test_a_block_ends_at_the_first_line_that_is_not_an_item():
    rule = {"start": "^S$", "item": "^  (?P<id>\\S+)$", "end": "^E$"}
    found = guide_mod.parse_text({"blocks": [rule]}, "S\n  a\n\n  b\nnoise\n  c\nE\n")
    assert found == {("", "a"), ("", "b")}


def test_list_ids_carry_the_list_section_qualifier():
    spec = {"item": "^(?P<id>\\S+): test$", "section": "^\\s+Running (?:unittests )?(?P<q>\\S+) .*$"}
    text = "     Running unittests src/lib.rs (x)\na: test\n     Running tests/it.rs (y)\nb: test\n"
    assert guide_mod.parse_list(spec, text) == [("src/lib.rs", "a"), ("tests/it.rs", "b")]


def test_deselect_composition_follows_the_schema():
    append = ["--", "--exact", "--skip={id}", "--nocapture"]
    argv = ["cargo", "test"]
    assert guide_mod.deselect_tokens(append, [("", "a"), ("", "b")], argv) == [
        "--", "--exact", "--skip=a", "--skip=b", "--nocapture"]
    assert guide_mod.deselect_tokens(append, [("", "a")], argv + ["--"])[:2] == ["--exact", "--skip=a"]
    # A flag and its value in two tokens: only the value is per id.
    assert guide_mod.deselect_tokens(["--skip", "{id}"], [("", "a"), ("", "b")], argv) == ["--skip", "a", "b"]


def test_files_placeholder_expands_to_one_token_per_file():
    assert guide_mod.expand_files(["run", "{files}"], ["a.rs", "b.rs"]) == ["run", "a.rs", "b.rs"]
    assert guide_mod.substitute(["-t", "^(?!{id}$)"], id="sum > adds") == ["-t", "^(?!sum > adds$)"]
