"""The inventory-report codebook an enumerating step reads (wicked-crew#721).

A step that lists things a later step acts on ends its reply with a fenced `wicked-inventory` JSON
block that says whether the list is complete (wicked-crew#648: two runs, one inventory silently
six items short, nothing on the wire to tell them apart). crew parses the block.

Pinned: strict frontmatter, the 2 KB budget, the field vocabulary crew parses, and the rule that
`full` needs nothing unread and the count to match.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ci"))
from validate import frontmatter_yaml_error  # noqa: E402

CODEBOOK = _REPO_ROOT / "skills" / "core" / "refs" / "inventory-report.md"
FIELDS = ["source", "answered", "listed", "expected", "unread"]
ANSWERED = ["full", "partial", "none"]


def _text() -> str:
    return CODEBOOK.read_text(encoding="utf-8")


def test_the_codebook_exists_within_two_kilobytes():
    assert CODEBOOK.is_file(), CODEBOOK
    assert len(CODEBOOK.read_bytes()) <= 2048, len(CODEBOOK.read_bytes())


def test_its_frontmatter_parses_strictly():
    text = _text()
    assert text.startswith("---\n")
    assert frontmatter_yaml_error(text) is None
    import yaml

    fm = yaml.safe_load(text.split("---\n", 2)[1])
    assert fm == {"codebook": "inventory-report", "version": 1, "block": "wicked-inventory"}


def test_the_example_is_valid_json_with_every_field_and_a_consistent_answer():
    m = re.search(r"```wicked-inventory\n(.*?)\n```", _text(), re.DOTALL)
    assert m, "the codebook shows the block"
    block = json.loads(m.group(1))
    assert list(block) == FIELDS
    assert block["answered"] in ANSWERED
    # The example is the #648 shape: short of the total, with the missing item named, so not `full`.
    assert block["listed"] < block["expected"] and block["unread"]
    assert block["answered"] == "partial"


def test_it_names_the_vocabulary_and_the_full_rule():
    text = _text()
    for word in FIELDS + ANSWERED:
        assert f"`{word}`" in text, word
    flat = " ".join(text.split()).lower()
    assert "`full` only when the source returned everything, `unread` is empty, and `listed` equals `expected`" in flat
    assert "a fallback" in flat and "is a different source" in flat
    assert "crew reads the block" in flat


def test_the_gh_cli_skill_points_enumerating_steps_at_it():
    skill = (_REPO_ROOT / "skills" / "platform" / "gh-cli" / "SKILL.md").read_text(encoding="utf-8")
    assert "skills/core/refs/inventory-report.md" in skill or "core/refs/inventory-report.md" in skill
