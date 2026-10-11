"""`qe accept` inside a governed unit runs writer -> executor -> reviewer in ONE turn (garden#1290).

On a claude QE seat the unit's turn ended right after the writer's test plan: the seat tried an
`Agent` dispatch (no such agent in a headless unit), loaded the writer skill inline via the Skill
tool, and the writer's "Return the complete test plan" became the seat's final reply. No executor,
no reviewer, no `VERDICT:` line, so the engine escalated `verdict_not_pass`.

The contract pinned here, on the skill text every seat reads:
- accept.md has a governed-unit section keyed on WICKED_RUN_ID that runs the three phases inline in
  one turn, with no sub-agent dispatch, and ends only after the verdict is recorded and printed;
- no hand-off brief in accept.md tells the worker to "return" its output (a turn-ending instruction
  once the worker is carried out inline); each brief marks its output as intermediate and continues;
- the writer and executor skills say their output is an intermediate artifact of accept, never the
  end of the turn, and the reviewer hands its verdict back to accept for the write.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCEPT = ROOT / "skills" / "qe" / "refs" / "accept.md"
WORKERS = {
    name: ROOT / "skills" / f"qe-acceptance-test-{name}" / "SKILL.md"
    for name in ("writer", "executor", "reviewer")
}


def _accept() -> str:
    return ACCEPT.read_text(encoding="utf-8")


def _governed_section(text: str) -> str:
    m = re.search(r"^## Governed unit[^\n]*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "accept.md needs a '## Governed unit' section (garden#1290)"
    return m.group(1)


def test_governed_section_keys_on_wicked_run_id_and_runs_inline_in_one_turn():
    sec = _governed_section(_accept())
    assert "WICKED_RUN_ID" in sec
    low = sec.lower()
    assert "one turn" in low
    assert "inline" in low
    # never dispatch sub-agents: a headless unit has none, and a fork returns to nobody
    for word in ("Agent", "Task"):
        assert re.search(rf"\b{word}\b", sec), f"governed section must forbid the {word} tool"
    assert "never end" in low and "VERDICT:" in sec


def test_governed_section_precedes_the_instructions():
    text = _accept()
    assert text.index("## Governed unit") < text.index("## Instructions")


def test_no_hand_off_brief_ends_the_turn():
    text = _accept()
    briefs = re.findall(r"\*\*Hand-off\*\*.*?```markdown\n(.*?)```", text, re.S)
    assert len(briefs) >= 3, "expected writer, executor and reviewer hand-off briefs"
    for brief in briefs:
        assert not re.search(r"^\s*Return the complete", brief, re.M), (
            "a hand-off brief says 'Return the complete ...': carried out inline, that reply ends the turn"
        )
    for line in re.findall(r"^\*\*Hand-off\*\*.*$", text, re.M):
        assert "continue" in line.lower(), f"hand-off must say to continue: {line[:80]}"


def test_worker_skills_mark_their_output_intermediate():
    for name in ("writer", "executor"):
        body = WORKERS[name].read_text(encoding="utf-8")
        assert "garden#1290" in body, f"{name}: missing the intermediate-artifact clause"
        low = body.lower()
        assert "intermediate" in low and "never end" in low and "turn" in low
    reviewer = WORKERS["reviewer"].read_text(encoding="utf-8")
    assert "garden#1290" in reviewer and "continue" in reviewer.lower()
