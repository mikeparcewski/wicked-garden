"""`qe accept` keeps the reviewer isolated AND keeps the caller's turn going (garden#1290).

On a claude QE seat the governed unit's turn ended on the writer's test plan: the seat loaded the
writer skill inline and the brief's "Return the complete test plan" became its final reply. The
inline fix (#1291, reverted in 12.53.3) ran writer, executor and reviewer inline in one context,
which removed reviewer isolation (the reviewer already held the executor's reasoning).

The contract pinned here, on the skill text every seat reads:
- each worker runs as a SEPARATE WORKER (a fresh context whose only input is its brief, whose
  reply comes back to the caller); on Claude Code the Hand-off names the Agent tool with the
  `general-purpose` type, since plugin worker skills are not agent types there;
- the reviewer is never opened inline; with no separate worker the verdict is FAIL `inconclusive`;
- no hand-off brief says "Return ..." (the turn-ending instruction), and each phase continues;
- no qe text still claims a `context: fork` boundary that the skills no longer declare;
- the reviewer skill self-checks for an inline (non-isolated) opening.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCEPT = ROOT / "skills" / "qe" / "refs" / "accept.md"
REVIEWER = ROOT / "skills" / "qe-acceptance-test-reviewer" / "SKILL.md"
NO_ISOLATED = "inconclusive — no isolated reviewer"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _phase(text: str, number: int) -> str:
    m = re.search(rf"^### {number}\. [^\n]*\n(.*?)(?=^### |\Z)", text, re.S | re.M)
    assert m, f"accept.md has no '### {number}.' phase"
    return m.group(1)


def _handoff(section: str) -> str:
    m = re.search(r"^\*\*Hand-off\*\*[^\n]*", section, re.M)
    assert m, "phase has no Hand-off paragraph"
    return m.group(0)


def _briefs(text: str) -> list[str]:
    return re.findall(r"```markdown\n(.*?)```", text, re.S)


def test_separate_worker_handoff_names_the_claude_mechanism_and_returns_to_the_caller():
    m = re.search(r"^## Separate workers\n(.*?)(?=^## )", _read(ACCEPT), re.S | re.M)
    assert m, "accept.md needs a '## Separate workers' section"
    body = m.group(1)
    hand = _handoff(body)
    assert "Agent tool" in hand and "general-purpose" in hand
    assert "never the end of your turn" in hand


def test_writer_and_executor_run_as_separate_workers_and_continue():
    text = _read(ACCEPT)
    for number, nxt in ((2, 3), (3, 4)):
        section = _phase(text, number)
        hand = _handoff(section)
        assert "as a separate worker" in hand
        assert f"continue to step {nxt} in this same turn" in hand
        flag = "--phase write" if number == 2 else "--phase execute"
        assert f"unless `{flag}`" in hand, "the hand-off must not override the phase stop"
        assert f"Otherwise continue to step {nxt} in this same turn" in section


def test_reviewer_is_never_inline_and_has_no_isolated_fallback_verdict():
    text = _read(ACCEPT)
    hand = _handoff(_phase(text, 5))
    assert "as a separate worker" in hand
    assert "Never open it inline" in hand
    assert re.search(rf"record `FAIL` with `reason: {NO_ISOLATED}", hand)
    assert "continue to step 6 in this same turn" in hand
    step6 = _phase(text, 6)
    assert re.search(rf"`reviewerVerdict` is `'FAIL'`, `reviewerSummary` is\s+`'{NO_ISOLATED}", step6)
    assert "`reviewerResponse` is `{}`" in step6


def test_no_brief_ends_the_turn_with_return():
    for brief in _briefs(_read(ACCEPT)):
        assert not re.search(r"^Return\b", brief, re.M), brief[:120]


def test_reviewer_brief_carries_paths_only():
    review = _briefs(_phase(_read(ACCEPT), 5))
    assert len(review) == 1
    brief = review[0]
    placeholders = set(re.findall(r"\{[^{}\n]*\}", brief))
    # only paths (and the equivalence-facet field list) may be interpolated into the reviewer brief
    assert placeholders <= {
        "{scenario file path only — reviewer reads it independently}",
        "{EVIDENCE_DIR}",
        "{ baseline_ref, baseline_sha, method, diff_count, tolerance, matched }",
    }, placeholders
    assert "{EVIDENCE_DIR}/test-plan.md" in brief
    assert not re.search(r"(?i)executor (output|report|stdout|reasoning)\s*\n?\s*\{", brief)


def test_no_qe_text_claims_a_fork_boundary():
    paths = [ACCEPT, REVIEWER, ROOT / "skills" / "qe" / "SKILL.md",
             ROOT / "skills" / "qe" / "refs" / "review.md",
             ROOT / "skills" / "qe" / "refs" / "campaign-grading.md"]
    for p in paths:
        text = _read(p)
        assert "context: fork" not in text, p
        assert not re.search(r"\bforked\b", text), p


def test_reviewer_skill_self_checks_for_an_inline_opening():
    text = _read(REVIEWER)
    assert "Isolation self-check" in text
    m = re.search(r"\*\*Isolation self-check[^\n]*\n(.*?)\n\n", text, re.S)
    assert m, "reviewer skill needs an Isolation self-check paragraph"
    assert "inconclusive — reviewer not isolated" in m.group(1)
    assert "`VERDICT: FAIL`" in m.group(1)


# --- engine-run reviewer (DES-QE-EVERY-SEAT): QE on every seat, isolation held by the engine ---

def _engine_section() -> str:
    m = re.search(r"^## Engine-run reviewer[^\n]*\n(.*?)(?=^## )", _read(ACCEPT), re.S | re.M)
    assert m, "accept.md needs an '## Engine-run reviewer' section"
    return m.group(1)


def test_evidence_phase_writes_no_verdict_and_names_the_dir_before_the_verdict_line():
    body = _engine_section()
    assert "--phase evidence [--resume <dir>]" in body
    assert "write no verdict" in body
    assert "`{EVIDENCE_DIR}/scenario.md`" in body
    assert "`QE-EVIDENCE: {EVIDENCE_DIR}`" in body
    assert "before your `VERDICT:` line" in body
    assert "never the QE verdict" in body


def test_engine_review_session_reviews_inline_only_under_the_engine_variable():
    body = _engine_section()
    assert "--phase review --evidence <dir>" in body
    assert "when `WICKED_QE_REVIEW_SESSION` is set" in body
    assert "IS the separate worker" in body
    assert "store.get('runs', id)" in body
    # Without the variable the step-5 rule still holds: never inline.
    assert re.search(r"\*\*Without the\s+variable\*\*, `--phase review` keeps step 5's rule", body)


def test_the_verdict_row_carries_the_review_session_stamp():
    step6 = _phase(_read(ACCEPT), 6)
    assert "review_session: process.env.WICKED_QE_REVIEW_SESSION" in step6
    # …only when the engine started the session.
    assert "process.env.WICKED_QE_REVIEW_SESSION ?" in step6


def test_usage_lists_the_engine_phases():
    text = _read(ACCEPT)
    assert "--phase evidence [--resume <evidence-dir>]" in text
    assert "--phase review --evidence <evidence-dir>" in text


def test_reviewer_skill_names_the_engine_session_as_isolated():
    text = _read(REVIEWER)
    m = re.search(r"\*\*Isolation self-check[^\n]*\n(.*?)\n\n", text, re.S)
    assert m
    assert "WICKED_QE_REVIEW_SESSION" in m.group(1) and "it is isolated" in m.group(1)


def test_resume_empties_the_evidence_dir_so_the_reviewer_sees_only_this_attempt():
    text = _read(ACCEPT)
    assert "EMPTY\n// <dir> (every file in it, the previous manifest.json included" in text
    assert "empties `<dir>` first" in _engine_section()
