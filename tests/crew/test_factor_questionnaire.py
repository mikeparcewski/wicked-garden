"""tests/crew/test_factor_questionnaire.py — Unit tests for factor_questionnaire.py (#625).

Provenance: AC-1 (all 9 factors defined), AC-2 (deterministic scorer math),
AC-3 (skill wrapper returns correct shape), AC-4 (backward compat — env var),
AC-5 (tested against cluster-A description).

T1: deterministic — no randomness, no sleep, no external I/O
T2: no sleep-based sync
T3: isolated — each test uses only in-process data
T4: single focus per test function
T5: descriptive names
T6: each docstring cites its AC
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from crew.factor_questionnaire import (  # noqa: E402
    QUESTIONNAIRE,
    Question,
    FactorRubric,
    score_factor,
    score_all,
    render_questionnaire,
    parse_answers,
)

# ---------------------------------------------------------------------------
# AC-1: all 9 canonical factors defined
# ---------------------------------------------------------------------------

CANONICAL_FACTORS = {
    "reversibility",
    "blast_radius",
    "compliance_scope",
    "user_facing_impact",
    "novelty",
    "scope_effort",
    "state_complexity",
    "operational_risk",
    "coordination_cost",
}


def test_all_nine_factors_present():
    """AC-1: QUESTIONNAIRE contains exactly the 9 canonical factors."""
    assert set(QUESTIONNAIRE.keys()) == CANONICAL_FACTORS


def test_each_factor_has_at_least_three_questions():
    """AC-1: each factor has enough questions to produce spread across readings."""
    for name, rubric in QUESTIONNAIRE.items():
        assert len(rubric.questions) >= 3, (
            f"factor '{name}' has only {len(rubric.questions)} questions; need >= 3"
        )


def test_all_question_weights_positive():
    """AC-1: yes_weight must be a positive integer (no zero-weight dead questions)."""
    for name, rubric in QUESTIONNAIRE.items():
        for q in rubric.questions:
            assert q.yes_weight > 0, (
                f"{name}.{q.id} has yes_weight={q.yes_weight}; must be > 0"
            )


def test_low_threshold_strictly_greater_than_medium():
    """AC-1: low_threshold > medium_threshold for all factors (avoids degenerate scoring)."""
    for name, rubric in QUESTIONNAIRE.items():
        assert rubric.low_threshold > rubric.medium_threshold, (
            f"{name}: low_threshold ({rubric.low_threshold}) must exceed "
            f"medium_threshold ({rubric.medium_threshold})"
        )


# ---------------------------------------------------------------------------
# AC-2: threshold math
# ---------------------------------------------------------------------------

def _rubric_for(name: str) -> FactorRubric:
    return QUESTIONNAIRE[name]


def test_zero_points_gives_high():
    """AC-2: all-no answers → HIGH reading (0 points below medium_threshold)."""
    rubric = _rubric_for("reversibility")
    reading, why = score_factor(rubric, {})
    assert reading == "HIGH"
    assert "no risk-flagging" in why


def test_all_yes_gives_low():
    """AC-2: all-yes answers → LOW reading (max points >= low_threshold)."""
    for name, rubric in QUESTIONNAIRE.items():
        all_yes = {q.id: True for q in rubric.questions}
        reading, _ = score_factor(rubric, all_yes)
        assert reading == "LOW", (
            f"factor '{name}': expected LOW with all-yes, got {reading}"
        )


def test_medium_threshold_produces_medium():
    """AC-2: answers summing to exactly medium_threshold → MEDIUM."""
    rubric = _rubric_for("reversibility")
    # r4 has weight 1, medium_threshold=1 → should yield MEDIUM
    answers = {"r4": True}
    reading, why = score_factor(rubric, answers)
    assert reading == "MEDIUM"
    assert "r4" in why


def test_low_threshold_produces_low():
    """AC-2: answers summing to exactly low_threshold → LOW."""
    rubric = _rubric_for("reversibility")
    # r1 has weight 3, low_threshold=3 → should yield LOW
    answers = {"r1": True}
    reading, why = score_factor(rubric, answers)
    assert reading == "LOW"
    assert "r1" in why


# ---------------------------------------------------------------------------
# Calibration regression guards (added 2026-04-25 per council on PR #629)
# Pin the new u1=2 weight so a future bump back to 3 fails loudly.
# Without these, the cluster-A integration test (which uses u1=False)
# would not catch a silent regression of the calibration fix.
# ---------------------------------------------------------------------------

def test_user_facing_impact_u1_alone_is_medium():
    """AC-2 calibration: single u1=YES must read MEDIUM (was LOW with weight=3)."""
    rubric = _rubric_for("user_facing_impact")
    # u1 weight=2, medium_threshold=1 → 2 pts → MEDIUM (not LOW: low_threshold=3)
    reading, _ = score_factor(rubric, {"u1": True})
    assert reading == "MEDIUM"


def test_user_facing_impact_u1_plus_u2_is_low():
    """AC-2 calibration: two visible-surface YES answers must still reach LOW."""
    rubric = _rubric_for("user_facing_impact")
    # u1 (2) + u2 (2) = 4 pts ≥ low_threshold=3 → LOW (confirms LOW remains reachable)
    reading, _ = score_factor(rubric, {"u1": True, "u2": True})
    assert reading == "LOW"


def test_why_string_includes_yes_question_ids():
    """AC-2: why field lists the IDs of questions answered yes."""
    rubric = _rubric_for("reversibility")
    answers = {"r1": True, "r2": True, "r3": False}
    _, why = score_factor(rubric, answers)
    assert "r1" in why
    assert "r2" in why
    assert "r3" not in why


def test_score_all_returns_all_nine_factors():
    """AC-2: score_all returns exactly 9 factor keys matching canonical list."""
    result = score_all({})
    assert set(result.keys()) == CANONICAL_FACTORS


def test_score_all_each_entry_has_reading_and_why():
    """AC-2: every entry in score_all output has reading, risk_level, and why."""
    result = score_all({})
    for name, entry in result.items():
        assert "reading" in entry, f"{name} missing 'reading'"
        assert "why" in entry, f"{name} missing 'why'"
        assert "risk_level" in entry, f"{name} missing 'risk_level'"
        assert entry["reading"] in ("HIGH", "MEDIUM", "LOW"), (
            f"{name} reading must be HIGH|MEDIUM|LOW, got {entry['reading']}"
        )


# ---------------------------------------------------------------------------
# parse_answers — YAML input
# ---------------------------------------------------------------------------

_YAML_SAMPLE = """
```yaml
answers:
  reversibility:
    r1: true
    r2: false
    r3: false
    r4: false
  blast_radius:
    b1: false
    b2: false
    b3: true
    b4: false
    b5: false
```
"""

def test_parse_answers_yaml_parses_booleans():
    """parse_answers: YAML true/false values parse to Python bools."""
    result = parse_answers(_YAML_SAMPLE)
    assert result["reversibility"]["r1"] is True
    assert result["reversibility"]["r2"] is False
    assert result["blast_radius"]["b3"] is True


def test_parse_answers_yaml_handles_yes_no_variants():
    """parse_answers: YAML 'yes'/'no' values also parse correctly."""
    yaml_text = """
answers:
  reversibility:
    r1: yes
    r2: no
"""
    result = parse_answers(yaml_text)
    assert result["reversibility"]["r1"] is True
    assert result["reversibility"]["r2"] is False


# ---------------------------------------------------------------------------
# parse_answers — JSON input
# ---------------------------------------------------------------------------

_JSON_SAMPLE = """{
  "answers": {
    "reversibility": {"r1": false, "r2": false, "r3": false, "r4": false},
    "compliance_scope": {"c1": true, "c2": false, "c3": false, "c4": false}
  }
}"""

def test_parse_answers_json_with_wrapper():
    """parse_answers: JSON with top-level 'answers' wrapper parses correctly."""
    result = parse_answers(_JSON_SAMPLE)
    assert result["reversibility"]["r1"] is False
    assert result["compliance_scope"]["c1"] is True


def test_parse_answers_json_bare_dict():
    """parse_answers: bare JSON factor dict (no 'answers' wrapper) also accepted."""
    import json
    bare = json.dumps({
        "reversibility": {"r1": True, "r2": False},
        "novelty": {"n1": True},
    })
    result = parse_answers(bare)
    assert result["reversibility"]["r1"] is True
    assert result["novelty"]["n1"] is True


# ---------------------------------------------------------------------------
# parse_answers — error cases
# ---------------------------------------------------------------------------

def test_parse_answers_raises_on_empty_string():
    """parse_answers: empty string raises ValueError (R4: no swallowed errors)."""
    with pytest.raises(ValueError):
        parse_answers("")


def test_parse_answers_raises_on_unknown_factor_yaml():
    """parse_answers: unknown factor in YAML raises ValueError."""
    bad_yaml = """
answers:
  made_up_factor:
    x1: true
"""
    with pytest.raises(ValueError, match="unknown factor"):
        parse_answers(bad_yaml)


def test_parse_answers_raises_on_unknown_factor_json():
    """parse_answers: unknown factor in JSON raises ValueError."""
    import json
    bad = json.dumps({"answers": {"made_up_factor": {"x1": True}}})
    with pytest.raises(ValueError, match="unknown factor"):
        parse_answers(bad)


def test_parse_answers_raises_on_invalid_json():
    """parse_answers: malformed JSON raises ValueError (not a bare exception)."""
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_answers("{not valid json}")


def test_parse_answers_raises_on_non_bool_json_value():
    """parse_answers: JSON integer value where bool expected raises ValueError."""
    import json
    bad = json.dumps({"answers": {"reversibility": {"r1": 1}}})
    with pytest.raises(ValueError, match="must be a boolean"):
        parse_answers(bad)


# ---------------------------------------------------------------------------
# render_questionnaire
# ---------------------------------------------------------------------------

def test_render_questionnaire_contains_all_factor_names():
    """render_questionnaire: output markdown contains all 9 factor headings."""
    rendered = render_questionnaire()
    for name in CANONICAL_FACTORS:
        assert name in rendered, f"factor '{name}' missing from rendered questionnaire"


def test_render_questionnaire_contains_all_question_ids():
    """render_questionnaire: every question ID appears in the rendered output."""
    rendered = render_questionnaire()
    for name, rubric in QUESTIONNAIRE.items():
        for q in rubric.questions:
            assert q.id in rendered, (
                f"question id '{q.id}' missing from rendered questionnaire"
            )


def test_render_questionnaire_is_string():
    """render_questionnaire: returns a non-empty string."""
    result = render_questionnaire()
    assert isinstance(result, str)
    assert len(result) > 100


# ---------------------------------------------------------------------------
# AC-5: cluster-A validation
#
# Canned answers based on the cluster-A description (wicked-garden v8 workflow-
# surface review: crew commands, smaht rename, mem migration before v9).
#
# This is a skill/plugin change touching 13+ skill files across 5 domains,
# introducing new patterns (crew:guide, smaht:state), requiring design+build
# handoffs, no direct PII handling, no schema migration.
#
# My manual readings from the session:
#   reversibility=HIGH, blast_radius=MEDIUM, compliance_scope=LOW,
#   user_facing_impact=MEDIUM, novelty=LOW, scope_effort=MEDIUM,
#   state_complexity=LOW, operational_risk=LOW, coordination_cost=LOW
# ---------------------------------------------------------------------------

_CLUSTER_A_ANSWERS = {
    "reversibility": {
        "r1": False,  # skill files, git-revertable
        "r2": False,  # no data migration
        "r3": False,  # no external API consumers removed
        "r4": False,  # no production state change
    },
    "blast_radius": {
        "b1": False,   # plugin-only, not shared infra
        "b2": False,   # no auth/billing/storage
        "b3": False,   # unlikely to page on-call
        "b4": True,    # touches multiple crew commands simultaneously — weight 2
        "b5": False,   # not CDN-distributed
    },
    "compliance_scope": {
        "c1": False,   # no PII, no PHI, no payment
        "c2": False,   # no audit logs or consent records
        "c3": False,   # no cross-border transfer
        "c4": False,   # no accidental PII capture
    },
    "user_facing_impact": {
        "u1": False,   # no UI/copy change for end-users
        "u2": False,   # internal plugin API, no external callers
        "u3": False,   # no email or export format change
        "u4": True,    # discoverability improvement — affects perceived experience, weight 1
    },
    "novelty": {
        "n1": False,   # no prior rollbacks on skill-authoring work
        "n2": False,   # team has done skill authoring many times
        "n3": False,   # multiple priors for skill-agent-authoring archetype
        "n4": False,   # no new external dependency
    },
    "scope_effort": {
        "s1": False,   # ~10-20 files, borderline but <20
        "s2": False,   # single repo
        "s3": False,   # single team
        "s4a": True,   # >5 files across 5 domains — weight 1
        "s4b": False,  # not >20 files and not multi-service — weight 2
    },
    "state_complexity": {
        "sc1": False,  # no schema migration
        "sc2": False,  # no serialization format change
        "sc3": False,  # no cache strategy change
        "sc4": False,  # no persistent state reads changed
    },
    "operational_risk": {
        "o1": False,   # no hot-path network calls added
        "o2": False,   # no queue/rate-limit changes
        "o3": False,   # no new runtime deps
        "o4": False,   # no retry/timeout changes
        "o5": False,   # skill files, not a production deploy
    },
    "coordination_cost": {
        "cc1": False,  # crew + engineering, ≤2 specialists
        "cc2": False,  # no contract negotiation needed
        "cc3": True,   # design (surface review) + build (implementation) handoff — weight 2
        "cc4": False,  # product alignment not required
    },
}


def test_cluster_a_reversibility_is_high():
    """AC-5: cluster-A canned answers yield reversibility=HIGH (git-revertable skill files)."""
    rubric = _rubric_for("reversibility")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["reversibility"])
    assert reading == "HIGH"


def test_cluster_a_blast_radius_is_medium():
    """AC-5: cluster-A canned answers yield blast_radius=MEDIUM (multi-command plugin change)."""
    rubric = _rubric_for("blast_radius")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["blast_radius"])
    assert reading == "MEDIUM"


def test_cluster_a_compliance_scope_is_high():
    """AC-5: cluster-A canned answers yield compliance_scope=HIGH (no regulated data → HIGH)."""
    rubric = _rubric_for("compliance_scope")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["compliance_scope"])
    # All-no = 0 pts = HIGH (best / least risky reading)
    assert reading == "HIGH"


def test_cluster_a_user_facing_impact_is_medium():
    """AC-5: cluster-A canned answers yield user_facing_impact=MEDIUM (perceived experience)."""
    rubric = _rubric_for("user_facing_impact")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["user_facing_impact"])
    assert reading == "MEDIUM"


def test_cluster_a_novelty_is_high():
    """AC-5: cluster-A canned answers yield novelty=HIGH (no risk flags answered yes)."""
    rubric = _rubric_for("novelty")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["novelty"])
    assert reading == "HIGH"


def test_cluster_a_scope_effort_is_medium():
    """AC-5: cluster-A canned answers yield scope_effort=MEDIUM (4-20 files across domains)."""
    rubric = _rubric_for("scope_effort")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["scope_effort"])
    assert reading == "MEDIUM"


def test_cluster_a_state_complexity_is_high():
    """AC-5: cluster-A canned answers yield state_complexity=HIGH (no state changes → best reading)."""
    rubric = _rubric_for("state_complexity")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["state_complexity"])
    assert reading == "HIGH"


def test_cluster_a_operational_risk_is_high():
    """AC-5: cluster-A canned answers yield operational_risk=HIGH (no runtime changes)."""
    rubric = _rubric_for("operational_risk")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["operational_risk"])
    assert reading == "HIGH"


def test_cluster_a_coordination_cost_is_medium():
    """AC-5: cluster-A canned answers yield coordination_cost=MEDIUM (design+build handoff)."""
    rubric = _rubric_for("coordination_cost")
    reading, _ = score_factor(rubric, _CLUSTER_A_ANSWERS["coordination_cost"])
    assert reading == "MEDIUM"


def test_cluster_a_score_all_returns_full_block():
    """AC-5: score_all on cluster-A answers returns all 9 factor keys with valid readings."""
    result = score_all(_CLUSTER_A_ANSWERS)
    assert set(result.keys()) == CANONICAL_FACTORS
    for name, entry in result.items():
        assert entry["reading"] in ("HIGH", "MEDIUM", "LOW"), (
            f"unexpected reading '{entry['reading']}' for factor '{name}'"
        )


# ---------------------------------------------------------------------------
# C1: scope_effort s4 split — 50-file / 3-service change scoring (#626)
# ---------------------------------------------------------------------------

def test_scope_effort_s4_split_handles_large_changes():
    """C1: 50-file 3-service change (s4a=YES, s4b=YES) yields at most MEDIUM
    (ideally LOW). Under the old compound-range s4 the answer was NO → 0 pts → HIGH,
    which silently underscored every large change.
    """
    rubric = _rubric_for("scope_effort")
    # 50-file change touching 3 services: s4a YES (1pt) + s4b YES (2pt) = 3 pts total.
    # medium_threshold=1, low_threshold=5 → 3 pts → MEDIUM.
    answers = {"s4a": True, "s4b": True}
    reading, why = score_factor(rubric, answers)
    assert reading in ("MEDIUM", "LOW"), (
        f"50-file 3-service change must score MEDIUM or LOW, got {reading!r}. "
        f"Pre-fix this was HIGH (compound-range s4 answered NO). Trace: {why}"
    )


# ---------------------------------------------------------------------------
# C2: compliance_scope c4 factual phrasing (#626)
# ---------------------------------------------------------------------------

def test_compliance_c4_factual_phrasing():
    """C2: c4 question text must not contain speculative language.
    Speculative words ('could', 'might', 'may', 'potentially', 'accidentally')
    make the question unanswerable from description content alone.
    """
    rubric = _rubric_for("compliance_scope")
    c4 = next(q for q in rubric.questions if q.id == "c4")
    speculative_words = {"could", "might", "may", "potentially", "accidentally"}
    found = speculative_words & set(c4.q.lower().split())
    assert not found, (
        f"c4 question contains speculative language {found!r}: {c4.q!r}. "
        f"Reframe to factual phrasing that is answerable from the description."
    )


# ---------------------------------------------------------------------------
# C3: FactorRubric.__post_init__ threshold guard (#626)
# ---------------------------------------------------------------------------

def test_factor_rubric_rejects_invalid_thresholds():
    """C3: FactorRubric raises ValueError when low_threshold <= medium_threshold."""
    with pytest.raises(ValueError, match="thresholds must satisfy"):
        FactorRubric(
            name="bad_factor",
            questions=(Question("x1", "Any question?", 1),),
            medium_threshold=5,
            low_threshold=3,  # violates low_threshold > medium_threshold
        )


def test_factor_rubric_rejects_zero_weight_question():
    """C3: FactorRubric raises ValueError when any question has yes_weight=0."""
    with pytest.raises(ValueError, match="yes_weight values must be > 0"):
        FactorRubric(
            name="bad_factor",
            questions=(
                Question("x1", "A real question?", 1),
                Question("x2", "A zero-weight question?", 0),  # violation
            ),
            medium_threshold=1,
            low_threshold=2,
        )


# ---------------------------------------------------------------------------
# C4: risk_level field — direction-explicit risk language (#626)
# ---------------------------------------------------------------------------

def test_score_all_includes_risk_level():
    """C4: every factor entry from score_all includes a risk_level field
    with values in {low_risk, medium_risk, high_risk}.
    """
    result = score_all({})
    valid_risk_levels = {"low_risk", "medium_risk", "high_risk"}
    for name, entry in result.items():
        assert "risk_level" in entry, f"factor '{name}' missing 'risk_level' field"
        assert entry["risk_level"] in valid_risk_levels, (
            f"factor '{name}' risk_level={entry['risk_level']!r} not in {valid_risk_levels}"
        )


def test_risk_level_inversion_correctness():
    """C4: risk_level correctly inverts Reading direction.
    Reading=HIGH (safest) → risk_level=low_risk.
    Reading=LOW  (riskiest) → risk_level=high_risk.
    """
    # Force HIGH reading: all-no on reversibility (0 pts < medium_threshold=1)
    result_high = score_all({"reversibility": {q.id: False for q in QUESTIONNAIRE["reversibility"].questions}})
    assert result_high["reversibility"]["reading"] == "HIGH"
    assert result_high["reversibility"]["risk_level"] == "low_risk", (
        "Reading=HIGH must map to risk_level=low_risk"
    )

    # Force LOW reading: all-yes on reversibility (8 pts >= low_threshold=3)
    result_low = score_all({"reversibility": {q.id: True for q in QUESTIONNAIRE["reversibility"].questions}})
    assert result_low["reversibility"]["reading"] == "LOW"
    assert result_low["reversibility"]["risk_level"] == "high_risk", (
        "Reading=LOW must map to risk_level=high_risk"
    )


# ---------------------------------------------------------------------------
# Issue #628 — plugin-scope calibration field-test pinning
#
# Field-tested 2026-04-25 on 3 plugin-scope + 1 SaaS-control descriptions.
# Result: b4, b5, sc4 behaved correctly at current weights — NO calibration
# needed. These tests pin the observed correct behavior so a future accidental
# recalibration of these weights fails loudly.
#
# For each candidate question, two tests:
#   - plugin_scope: the typical plugin-only answer must NOT produce an inflated reading
#   - saas_scale: SaaS-scale all-signal answer must still produce the riskier reading
# ---------------------------------------------------------------------------

# --- b4 pinning ---

def test_blast_radius_b4_only_plugin_scope_is_medium():
    """Issue #628 pin: b4 alone (additive plugin surfaces) → MEDIUM, not LOW.

    b4 weight=2 + medium_threshold=2 → exactly MEDIUM when only b4 fires.
    A plugin adding multiple new surfaces simultaneously is correctly MEDIUM risk,
    not LOW — LOW requires b4 + at least 3 more points from b1/b2/b3/b5.
    """
    rubric = _rubric_for("blast_radius")
    # Only b4 fires: adding 3 agents + 1 skill simultaneously
    reading, why = score_factor(rubric, {"b4": True})
    assert reading == "MEDIUM", (
        f"b4 alone (2pts) must yield MEDIUM for plugin multi-surface work, got {reading!r}. "
        f"Trace: {why}"
    )


def test_blast_radius_b4_saas_scale_all_signals_is_low():
    """Issue #628 pin: b4 + b1 + b2 + b3 (SaaS-scale auth migration) → LOW.

    Confirms that the SaaS path to LOW blast is still reachable and b4
    participates correctly in the full-signal scenario.
    """
    rubric = _rubric_for("blast_radius")
    # b1(3) + b2(3) + b3(2) + b4(2) = 10 pts >= low_threshold=5 → LOW
    reading, why = score_factor(rubric, {"b1": True, "b2": True, "b3": True, "b4": True})
    assert reading == "LOW", (
        f"SaaS-scale all-surface signals must yield LOW blast_radius, got {reading!r}. "
        f"Trace: {why}"
    )


# --- b5 pinning ---

def test_blast_radius_b5_alone_plugin_scope_is_high():
    """Issue #628 pin: b5 alone (marketplace distribution, no other risk) → HIGH.

    b5 weight=1 < medium_threshold=2 — cannot tip blast_radius past HIGH on its own.
    Every plugin change trips b5 YES; this must NOT escalate to MEDIUM without corroboration.
    """
    rubric = _rubric_for("blast_radius")
    # Only b5 fires: any plugin change distributed via marketplace install
    reading, why = score_factor(rubric, {"b5": True})
    assert reading == "HIGH", (
        f"b5 alone (1pt) must yield HIGH blast_radius for plugin-only distribution, got {reading!r}. "
        f"b5 is a low-weight amplifier, not a standalone escalator. Trace: {why}"
    )


def test_blast_radius_b5_plus_b4_plugin_scope_is_medium():
    """Issue #628 pin: b4 + b5 together (additive multi-surface + marketplace) → MEDIUM, not LOW.

    For a plugin adding new agents/skills: b4(2) + b5(1) = 3pts < low_threshold=5 → MEDIUM.
    Confirms the combined plugin-scope scenario stays below LOW.
    """
    rubric = _rubric_for("blast_radius")
    # b4(2) + b5(1) = 3 pts; medium_threshold=2, low_threshold=5 → MEDIUM
    reading, why = score_factor(rubric, {"b4": True, "b5": True})
    assert reading == "MEDIUM", (
        f"b4+b5 together (3pts) must yield MEDIUM blast_radius, got {reading!r}. "
        f"Trace: {why}"
    )


def test_blast_radius_b5_saas_scale_contributes_to_low():
    """Issue #628 pin: b5 contributes correctly to LOW in a full SaaS-scale scenario.

    b1(3)+b2(3)+b3(2)+b4(2)+b5(1) = 11pts >= low_threshold=5.
    b5 doesn't single-handedly cause LOW but participates in the total.
    """
    rubric = _rubric_for("blast_radius")
    all_yes = {q.id: True for q in rubric.questions}
    reading, _ = score_factor(rubric, all_yes)
    assert reading == "LOW", (
        "All blast_radius questions YES must yield LOW; b5 contributes 1pt to full signal."
    )


# --- sc4 pinning ---

def test_state_complexity_sc4_alone_plugin_scope_is_medium():
    """Issue #628 pin: sc4 alone (new read-only query, no structural change) → MEDIUM.

    sc4 weight=1 + medium_threshold=1 → exactly MEDIUM when only sc4 fires.
    A plugin adding a read-only DomainStore lookup is correctly MEDIUM (not LOW),
    because structural changes (sc1/sc2) are absent.
    """
    rubric = _rubric_for("state_complexity")
    # Only sc4 fires: new read-only state access added to plugin code
    reading, why = score_factor(rubric, {"sc4": True})
    assert reading == "MEDIUM", (
        f"sc4 alone (1pt) must yield MEDIUM state_complexity, got {reading!r}. "
        f"Pure read-only state access without schema changes is correctly MEDIUM. "
        f"Trace: {why}"
    )


def test_state_complexity_sc4_no_fires_for_pure_extraction_is_high():
    """Issue #628 pin: pure code extraction (no new state reads) sc4=NO → HIGH.

    A refactor that moves existing code to a new file without adding any new
    DomainStore/SQLite reads must answer sc4=NO. The scorer then reads HIGH.
    This pins the expected answer for docs-only and pure structural refactors.
    """
    rubric = _rubric_for("state_complexity")
    # Pure structural refactor: no schema, no serialization, no cache, no new reads
    reading, why = score_factor(rubric, {})
    assert reading == "HIGH", (
        f"Pure extraction with sc4=NO must yield HIGH state_complexity, got {reading!r}. "
        f"Trace: {why}"
    )


def test_state_complexity_sc4_saas_scale_combined_with_sc1_is_low():
    """Issue #628 pin: sc4 + sc1 (schema migration with read-only audit queries) → LOW.

    SaaS-scale control: sc1(4) + sc4(1) = 5pts >= low_threshold=4 → LOW.
    Confirms sc4 participates correctly in the full-signal path to LOW.
    """
    rubric = _rubric_for("state_complexity")
    # sc1(4) + sc4(1) = 5 pts >= low_threshold=4 → LOW
    reading, why = score_factor(rubric, {"sc1": True, "sc4": True})
    assert reading == "LOW", (
        f"sc1+sc4 (schema migration + read-only queries) must yield LOW, got {reading!r}. "
        f"Trace: {why}"
    )
