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


def test_new_rules_have_provenance_rows():
    body = FLOOR.read_text(encoding="utf-8")
    for rule_id in ("C6", "C7", "E3"):
        assert re.search(rf"^\| {rule_id} \|", body, re.M), rule_id
