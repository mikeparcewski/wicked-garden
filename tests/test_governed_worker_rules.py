"""The governed-worker floor carries the rules runs were lost without (garden#1229, #1223).

Text-presence pins: the floor is the one brief every seat reads before every turn, so a rule
that silently drops out of it is a regression even when no code changes.
"""

from __future__ import annotations

import re
from pathlib import Path

FLOOR = Path(__file__).resolve().parents[1] / "skills" / "governed-worker" / "SKILL.md"


def _rule(rule_id: str) -> str:
    body = FLOOR.read_text(encoding="utf-8")
    m = re.search(rf"^- \*\*{rule_id} — (.*?)(?=^- \*\*|^\S|\Z)", body, re.M | re.S)
    assert m, f"{rule_id} is missing from the governed-worker floor"
    return " ".join(m.group(1).split())


def test_c7_keeps_tool_debris_under_the_notes_root():  # garden#1229
    rule = _rule("C7")
    assert "notes root" in rule and "$WICKED_NOTES_ROOT" in rule
    for kind in ("Reporter output", "coverage", "screenshots", "logs", "scratch files"):
        assert kind in rule, kind
    assert "never in the repository" in rule
    assert "--outputFile" in rule and "delete the file before the turn ends" in rule


def test_c6_no_turn_ends_with_tasks_pending():  # garden#1223
    rule = _rule("C6")
    assert "foreground" in rule and "exit code" in rule
    assert '"Running in the background" is never a closing line' in rule


def test_c2_pre_existing_cites_the_base_run_or_is_a_failure():  # garden#1223
    rule = _rule("C2")
    assert "base tree" in rule and "exit code" in rule and "or it is a failure" in rule


def test_e3_verdict_items_stay_in_scope_unless_a_human_strikes_them():  # garden#1223
    rule = _rule("E3")
    assert "human ruling strikes it by name" in rule


def test_e4_parity_items_are_judged_on_values_from_both_sides():  # garden#1253
    rule = _rule("E4")
    assert "derive the value X actually produces" in rule
    assert "quote it with `file:line`" in rule and "compare the two" in rule
    assert "a test the creator wrote pinning a value is never the evidence" in rule
    assert "Values that differ are a Critical" in rule
    # The corpus case rides the rule: a creator-pinned `before:1` against the form's `before:2` FAILs.
    assert "Example (FAIL)" in rule and "`before:1`" in rule and "`before:2`" in rule and "the item FAILs" in rule


def test_review_archetype_points_parity_items_at_e4():  # garden#1253
    review = (FLOOR.parents[1] / "archetype" / "refs" / "review.md").read_text(encoding="utf-8")
    assert "Parity items compare values (garden#1253)" in review and "rule E4" in review


def test_c8_checks_the_chosen_stack_before_writing_code():  # operator ruling 2026-10-12, POL-2101
    rule = _rule("C8")
    assert "The user and the steering policies choose the framework or library" in rule
    assert "POL-2101" in rule and "never swap in another" in rule
    assert "at the version the repo pins" in rule
    assert "Record the check in your output" in rule
    assert "say why the built-in does not fit" in rule
    assert "fastmcp" in rule


def test_e5_evaluators_flag_every_duplicate_of_a_built_in():  # operator ruling 2026-10-12, POL-2101
    rule = _rule("E5")
    assert "even when the creator gave a reason" in rule and "`file:line`" in rule
    assert "judge the creator's reason" in rule
    assert "An unjustified duplicate is at least a Concern" in rule
    assert "records no built-in check (C8)" in rule


def test_engineering_review_and_plan_carry_the_built_in_check():  # POL-2101
    eng = FLOOR.parents[1] / "engineering"
    review = (eng / "refs" / "review.md").read_text(encoding="utf-8")
    assert "## Duplicates of a built-in — always flag" in review
    assert "### Duplicates of a Built-in" in review and "POL-2101" in review
    plan = (eng / "refs" / "plan.md").read_text(encoding="utf-8")
    assert "### Built-ins Checked" in plan and "POL-2101" in plan


def test_new_rules_have_provenance_rows():
    body = FLOOR.read_text(encoding="utf-8")
    for rule_id in ("C6", "C7", "C8", "E3", "E4", "E5"):
        assert re.search(rf"^\| {rule_id} \|", body, re.M), rule_id
