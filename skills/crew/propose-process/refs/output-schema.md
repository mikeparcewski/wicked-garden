# Output Schema (for measurement)

When the facilitator is invoked with `output=json` (set by
`scripts/ci/measure_facilitator.py`), emit a single JSON object matching this schema
in place of creating tasks. This is the canonical shape the measurement script
compares against.

The JSON is the DRY-RUN form of the plan. It contains everything needed to score the
rubric against a scenario's expected-outcome block.

---

## Schema

```json
{
  "project_slug": "snake_case_short_name",
  "mode": "propose | re-evaluate | yolo",
  "summary": "2-3 sentence read of the description in your own words",
  "priors": [
    {"path": "memory/foo.md", "source_type": "memory", "why": "one sentence"}
  ],
  "factors": {
    "reversibility":      {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "blast_radius":       {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "compliance_scope":   {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "user_facing_impact": {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "novelty":            {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "scope_effort":       {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "state_complexity":   {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "operational_risk":   {"reading": "LOW|MEDIUM|HIGH", "why": "..."},
    "coordination_cost":  {"reading": "LOW|MEDIUM|HIGH", "why": "..."}
  },
  "specialists": [
    {"name": "requirements-analyst", "why": "one sentence"},
    {"name": "backend-engineer",     "why": "one sentence"}
  ],
  "phases": [
    {"name": "clarify", "why": "one sentence", "primary": ["requirements-analyst"]},
    {"name": "build",   "why": "one sentence", "primary": ["backend-engineer"]}
  ],
  "rigor_tier": "minimal | standard | full",
  "rigor_why": "one sentence",
  "complexity": 3,
  "complexity_why": "one sentence",
  "open_questions": [
    "When you say 'faster', do you mean initial paint, TTI, or perceived responsiveness?"
  ],
  "tasks": [
    {
      "id": "t1",
      "title": "Resolve ambiguous scope: performance baseline defined",
      "phase": "clarify",
      "specialist": "requirements-analyst",
      "blockedBy": [],
      "metadata": {
        "chain_id": "<project-slug>.root",
        "event_type": "task",
        "source_agent": "facilitator",
        "phase": "clarify",
        "test_required": false,
        "test_types": [],
        "evidence_required": [],
        "rigor_tier": "standard"
      }
    }
  ],
  "re_evaluation": {
    "pruned": [],
    "augmented": [],
    "re_tiered": []
  },
  "anticipated_reevaluations": [
    {"trigger": "if clarify phase surfaces a bigger scope than expected",
     "likely_impact": "augment with migration-engineer + data specialist"}
  ]
}
```

---

## Required vs. optional fields

**Always required**:

- `project_slug`, `summary`, `factors`, `specialists`, `phases`, `rigor_tier`,
  `complexity`, `tasks`.

**Present when applicable**:

- `priors` — empty array if search returned nothing.
- `open_questions` — empty array if no ambiguity.
- `re_evaluation` — only in `re-evaluate` mode; otherwise omit.
- `anticipated_reevaluations` — optional in `propose` mode. List of `{trigger, likely_impact}` entries describing conditions that should cause re-evaluation (e.g. "if design reveals schema migration needed"). Zero-cost in the initial plan; makes forward planning auditable when re-evaluation fires. Omit if no plausible triggers.

**Yolo mode additions**:

- `mode: "yolo"` + `auto_proceed: true` — facilitator must still emit the full plan;
  yolo only affects gate-verdict handling downstream.

---

## Matching rules (how the measurement script scores)

The script (`scripts/ci/measure_facilitator.py`) compares this output against the
scenario's `expected_outcome` YAML block on these dimensions:

| Dimension             | Match rule                                                    |
|-----------------------|---------------------------------------------------------------|
| specialists           | expected ⊆ picked (extras OK up to +2); banned names → fail.  |
| phases                | expected ⊆ picked, order preserved; extras OK up to +1.        |
| evidence_required     | expected ⊆ union across tasks (scenario spec level).          |
| test_types            | expected ⊆ union across tasks.                                |
| complexity            | abs(expected - actual) <= 1.                                  |
| rigor_tier            | exact match (one of minimal/standard/full).                   |
| re_evaluation         | only scored on scenario 9 (emergent-complexity).              |
| open_questions        | only scored on scenario 8 (ambiguous-ask): expected count ≥1. |

A scenario passes if ≥80% of its applicable dimensions match. The overall Gate-1 pass
threshold is ≥80% of scenarios passing.

---

## Why JSON and not task creations

Tasks are side-effectful; measurement needs to be pure and reproducible. JSON output
lets the script:

1. Run the rubric deterministically (with a fixed LLM seed / mock).
2. Replay scenarios without touching `~/.claude/tasks`.
3. Diff rubric versions as code.

In production (non-measurement) use, the facilitator emits the JSON internally and
then translates to `TaskCreate` calls using the `tasks[]` array.
