# Spec Quality Rubric — Human-Readable Description

**This file is documentation.** The runtime source of truth is
`scripts/crew/spec_rubric.py`. The function `_apply_spec_rubric` in
`scripts/crew/phase_manager.py` consumes the rubric breakdown attached to
clarify-phase gate results and adjusts the verdict when the score falls below
the tier-specific threshold.

---

## Why a scored rubric?

Spec quality is the primary determinant of implementation quality. Holistic
prose review (the pre-v6.2 default) left too much room for a spec with
unnumbered requirements or unverifiable acceptance criteria to pass the clarify
gate and then produce drift in the build phase. The rubric forces the
reviewer to grade ten specific dimensions on a 0-2 scale and exposes the
breakdown in the gate result so it is inspectable and evolvable.

---

## The ten dimensions (0-2 pts each, 20 total)

| # | Dimension | Max | What a 2 looks like |
|---|-----------|-----|---------------------|
| 1 | User story present | 2 | `As a <role>, I want <capability>, so that <outcome>` — actor + motivation clearly named. |
| 2 | Context framed | 2 | Problem statement, current state, and scope boundaries stated. Non-goals listed when ambiguous. |
| 3 | Numbered functional requirements | 2 | FRs enumerated with stable IDs (`FR-N` or `REQ-{domain}-{n}`) so tests and design can cite them. |
| 4 | NFRs with measurable targets | 2 | Performance, reliability, security, a11y, compliance carry quantitative targets or cite explicit standards. |
| 5 | Acceptance criteria | 2 | SMART (specific, measurable, achievable, relevant, testable). Happy-path **and** ≥1 failure/edge case. |
| 6 | Gherkin scenarios | 2 | Given/When/Then scenarios for key behaviors including negative paths. |
| 7 | Test plan outline | 2 | Test levels (unit, integration, acceptance) and evidence types sketched. |
| 8 | API contract (if applicable) | 2 | Request/response shape and error cases pinned down. Non-API work scores automatically full credit. |
| 9 | Dependencies identified | 2 | Upstream tickets, external systems, libraries, data sources listed. Unknowns surfaced as open questions. |
| 10 | Design section | 2 | Preliminary design sketch (components, data flow, signatures) — enough that an engineer can start. |

### Scoring bands per dimension

| Score | Meaning |
|-------|---------|
| 2 | Fully satisfied. No work needed. |
| 1 | Partially satisfied. Gap is specific and addressable (e.g. ACs listed but one is not measurable). |
| 0 | Missing, ambiguous, or unverifiable. |

---

## Tier thresholds and grade

Rubric total determines a grade and whether the clarify gate can advance at
the project's `rigor_tier`.

| Grade | Score | Interpretation |
|-------|-------|----------------|
| A | 18-20 | Spec is ready for full-rigor work. |
| B | 15-17 | Spec is acceptable for standard rigor. |
| C | 12-14 | Spec is acceptable only for minimal rigor. |
| D | 9-11 | Spec is too thin — rework required. |
| F | 0-8 | Spec is unfit for implementation. |

| Rigor tier | Minimum score | Grade floor |
|------------|---------------|-------------|
| minimal | 12 | C |
| standard | 15 | B |
| full | 18 | A |

---

## Enforcement (v6.2+)

`_apply_spec_rubric` in `phase_manager.py` runs at clarify-gate approve time
when the gate result carries a `rubric_breakdown` dict. The rubric is **not**
advisory:

- **minimal / standard below threshold** → verdict is downgraded to
  `CONDITIONAL` and the failing dimensions are added to `conditions`. The
  existing `_write_conditions_manifest` path persists them — the next phase
  cannot start until they are verified.
- **full below threshold** → verdict is escalated to `REJECT`. Clarify does
  not advance. Rework required.
- **at or above threshold** → verdict is preserved (APPROVE stays APPROVE).

The existing `min_gate_score` check in `phases.json` still runs alongside the
rubric check, so pre-rubric projects continue to be governed by the older
threshold. A gate result without `rubric_breakdown` is unchanged by
`_apply_spec_rubric`.

---

## Gate result shape

The `requirements-quality-analyst` agent emits a gate result with these fields
(existing fields plus four new rubric fields):

```json
{
  "result": "APPROVE",
  "reviewer": "wicked-garden:product:requirements-analyst",
  "score": 0.78,
  "rubric_breakdown": {
    "user_story":                     {"score": 2, "notes": "clear role + outcome"},
    "context_framed":                 {"score": 2, "notes": "scope + non-goals"},
    "numbered_functional_requirements": {"score": 2, "notes": "FR-1..FR-6"},
    "measurable_nfrs":                {"score": 1, "notes": "latency target; no reliability target"},
    "acceptance_criteria":            {"score": 2, "notes": "SMART, happy + 2 error cases"},
    "gherkin_scenarios":              {"score": 2, "notes": "3 positive + 2 negative"},
    "test_plan_outline":              {"score": 1, "notes": "unit/integration named; acceptance TBD"},
    "api_contract":                   {"score": 2, "notes": "not applicable"},
    "dependencies_identified":        {"score": 2, "notes": "upstream ticket + 1 external library"},
    "design_section":                 {"score": 1, "notes": "components listed; data flow missing"}
  }
}
```

After `_apply_spec_rubric` runs, the result gains:

```json
{
  "rubric_score": 17,
  "rubric_max_score": 20,
  "rubric_grade": "B",
  "rubric_rigor_tier": "standard",
  "rubric_threshold": 15
}
```

If the score had been below the threshold, the result would also gain
`rubric_adjustment: {from, to, reason}` and the `result` field would be
rewritten to `CONDITIONAL` or `REJECT`.

---

## CLI helper

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/spec_rubric.py" \
    path/to/breakdown.json \
    --rigor-tier standard \
    --output markdown
```

Prints the markdown grid, verdict, and conditions. Useful for reviewer
dry-runs before writing `gate-result.json`.
