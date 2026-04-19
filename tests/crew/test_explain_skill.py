#!/usr/bin/env python3
"""
Structural tests for the wicked-garden:crew:explain skill (issue #480).

The skill itself is prose — there is no code to unit-test — but we can
assert on the shape and contract of SKILL.md and commands/crew/explain.md
so future edits don't silently break the marketplace registration or the
three-style contract (``terse``, ``paired``, ``plain-only``).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL = _REPO_ROOT / "skills" / "crew" / "explain" / "SKILL.md"
_COMMAND = _REPO_ROOT / "commands" / "crew" / "explain.md"


class SkillFilePresenceTests(unittest.TestCase):
    def test_skill_md_exists(self) -> None:
        self.assertTrue(
            _SKILL.exists(),
            "skills/crew/explain/SKILL.md must exist for #480.",
        )

    def test_command_md_exists(self) -> None:
        self.assertTrue(
            _COMMAND.exists(),
            "commands/crew/explain.md must exist for #480.",
        )


class SkillContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = _SKILL.read_text(encoding="utf-8")

    def test_has_yaml_frontmatter_with_name(self) -> None:
        m = re.match(r"^---\n(.*?)\n---\n", self.content, re.DOTALL)
        self.assertIsNotNone(m, "SKILL.md must open with YAML frontmatter")
        frontmatter = m.group(1)
        self.assertIn("name: explain", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_names_three_output_styles(self) -> None:
        for style in ("terse", "paired", "plain-only"):
            self.assertIn(
                style, self.content,
                f"SKILL.md must document the '{style}' output style",
            )

    def test_enforces_grade_8_and_short_output(self) -> None:
        lower = self.content.lower()
        self.assertIn("grade", lower)
        # The rule is "2-4 sentences" — accept either dash form.
        self.assertTrue(
            re.search(r"2[\s–-]4\s+sentences", lower),
            "SKILL.md must cap output at 2-4 sentences",
        )

    def test_forbids_specialist_vocab(self) -> None:
        # The "No specialist vocab" rulebook must appear.
        self.assertIn("No specialist vocab", self.content)

    def test_stays_under_200_lines(self) -> None:
        line_count = len(self.content.splitlines())
        self.assertLessEqual(
            line_count, 200,
            f"SKILL.md must stay <= 200 lines (progressive disclosure); "
            f"current: {line_count}",
        )


class CommandContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = _COMMAND.read_text(encoding="utf-8")

    def test_has_frontmatter_with_description(self) -> None:
        m = re.match(r"^---\n(.*?)\n---\n", self.content, re.DOTALL)
        self.assertIsNotNone(m, "explain.md must open with YAML frontmatter")
        self.assertIn("description:", m.group(1))

    def test_references_the_skill(self) -> None:
        self.assertIn(
            "wicked-garden:crew:explain", self.content,
            "explain.md must reference the wicked-garden:crew:explain skill",
        )

    def test_has_h1_command_header(self) -> None:
        self.assertTrue(
            re.search(
                r"^# /wicked-garden:crew:explain\s*$",
                self.content,
                re.MULTILINE,
            ),
            "explain.md h1 header must match the command name",
        )

    def test_documents_style_flag(self) -> None:
        # --style flag with the three modes is part of the public contract.
        self.assertIn("--style", self.content)
        for style in ("paired", "plain-only"):
            self.assertIn(style, self.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
