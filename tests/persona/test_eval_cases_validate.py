"""Deterministic validation of the model-graded persona LIFT eval cases.

The cases in `eval_cases/*.json` require paid Claude API calls to EXECUTE
(user-gated). This suite does the free part: it proves every case file parses and
conforms to the schema, so a broken case can never silently no-op when the
user does run the paid eval.

Provenance: garden persona-surface review (2026-06). T1 determinism: pure file
parsing, no network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent / "eval_cases"

# Every methodology persona under test must have at least one case.
EXPECTED_PERSONAS = {"platform", "qe", "agentic"}

REQUIRED_TOP_LEVEL = {
    "case_id", "persona", "task", "arms", "lift_assertions",
    "scoring", "pass_threshold",
}


def _case_files():
    return sorted(EVAL_DIR.glob("*.json"))


def test_eval_cases_exist():
    """At least one case per methodology persona must exist."""
    files = _case_files()
    assert files, f"no eval case files found in {EVAL_DIR}"
    personas = set()
    for f in files:
        personas.add(json.loads(f.read_text(encoding="utf-8"))["persona"])
    missing = EXPECTED_PERSONAS - personas
    assert not missing, f"methodology personas with no LIFT eval case: {sorted(missing)}"


@pytest.mark.parametrize(
    "case_file", _case_files(), ids=lambda p: p.stem
)
def test_eval_case_conforms_to_schema(case_file: Path):
    """Each case parses and carries the fields the (user-gated) runner needs."""
    case = json.loads(case_file.read_text(encoding="utf-8"))

    missing = REQUIRED_TOP_LEVEL - set(case)
    assert not missing, f"{case_file.name}: missing fields {sorted(missing)}"

    # case_id must match the filename so results are traceable.
    assert case["case_id"] == case_file.stem, (
        f"{case_file.name}: case_id '{case['case_id']}' should equal the filename stem"
    )

    # Two arms: a baseline (no persona) and a persona arm — this is what makes it
    # a LIFT measurement rather than a single-arm sanity check.
    arms = case["arms"]
    assert set(arms) == {"baseline", "persona"}, (
        f"{case_file.name}: arms must be exactly {{baseline, persona}} for a lift delta"
    )

    # Lift assertions must be concrete: each one names the failure mode it expects
    # the persona to raise, via a non-empty must_mention_any list + a rationale.
    lift = case["lift_assertions"]
    assert lift, f"{case_file.name}: must declare at least one lift_assertion"
    for a in lift:
        assert a.get("id"), f"{case_file.name}: a lift_assertion is missing 'id'"
        mentions = a.get("must_mention_any")
        assert mentions and isinstance(mentions, list), (
            f"{case_file.name}: lift_assertion '{a.get('id')}' needs a non-empty "
            "must_mention_any list"
        )
        assert a.get("rationale"), (
            f"{case_file.name}: lift_assertion '{a.get('id')}' needs a rationale "
            "(WHY this failure mode is the lift)"
        )

    assert isinstance(case["pass_threshold"], int) and case["pass_threshold"] >= 1, (
        f"{case_file.name}: pass_threshold must be an int >= 1 (persona must beat baseline)"
    )
