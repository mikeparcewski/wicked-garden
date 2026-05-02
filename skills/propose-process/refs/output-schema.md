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
    "reversibility":      {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "blast_radius":       {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "compliance_scope":   {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "user_facing_impact": {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "novelty":            {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "scope_effort":       {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "state_complexity":   {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "operational_risk":   {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "coordination_cost":  {"reading": "LOW|MEDIUM|HIGH", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."}
  },
  "specialists": [
    {"name": "requirements-analyst", "why": "one sentence"},
    {
      "name": "backend-engineer",
      "domain": "engineering",
      "subagent_type": "wicked-garden:engineering:backend-engineer",
      "why": "one sentence"
    }
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
  ],

  "affected_repos": ["repo-foo", "repo-bar"]
}
```

## affected_repos (advisory, optional)

Optional `affected_repos: [string]` field added by Issue #722. When
the archetype is `multi-repo`, populate this list with the repository
short-names the project touches. Crew core treats it as **read-only
advisory metadata**:

- `crew:status` and `smaht:briefing` surface a single advisory line
  (`Affected repos: foo, bar (advisory — see docs/v9/sibling-plugin-monorepo.md)`).
- Validator rules: must be a list of non-empty strings if present;
  empty list / missing field are both valid (backward-compatible).
- No DAG, no worktree provisioning, no merge-order validation, no
  cross-repo evidence aggregation. Those workflows are deferred to the
  `wicked-garden-monorepo` sibling v9 plugin —
  see `docs/v9/sibling-plugin-monorepo.md` for the design brief.

Note: each factor entry carries BOTH `reading` (HIGH/MEDIUM/LOW; HIGH = safest,
LOW = riskiest, for backward compatibility) AND `risk_level`
(`low_risk`/`medium_risk`/`high_risk`, direction-explicit and user-facing).
Internal logic may still use `reading`, but any human-readable output should use
`risk_level` to avoid the inversion footgun. `reading` remains a candidate for
future deprecation.

---

## Required vs. optional fields

**Always required**:

- `project_slug`, `summary`, `factors`, `specialists`, `phases`, `rigor_tier`,
  `complexity`, `tasks`.

### Specialist pick forms (Issue #573)

Each entry in `specialists[]` may be emitted in either form; both are accepted by
`scripts/crew/validate_plan.py`:

| Form          | Shape                                                              |
|---------------|--------------------------------------------------------------------|
| Short         | `{"name": "<role>", "why": "..."}`                                 |
| Expanded      | `{"name": "<role>", "domain": "<d>", "subagent_type": "<st>", "why": "..."}` |

**Resolution rules**:

- The short form is expanded at validation time by
  `scripts/crew/specialist_resolver.py`, which walks `agents/**/*.md` frontmatter
  and maps bare role → `wicked-garden:{domain}:{role}`.
- In the expanded form, any declared `domain` / `subagent_type` must agree with the
  resolver's reading of the on-disk agent. Silent drift is rejected to preserve the
  invariant the engagement tracker depends on (Issue #573: bare roles used to leak
  past `_parse_specialist_from_agent_type` and drop engagement events).
- Unknown `name` values are rejected with `difflib.get_close_matches` suggestions.

**Present when applicable**:

- `priors` — empty array if search returned nothing.
- `open_questions` — empty array if no ambiguity.
- `re_evaluation` — only in `re-evaluate` mode; otherwise omit.
- `anticipated_reevaluations` — optional in `propose` mode. List of `{trigger, likely_impact}` entries describing conditions that should cause re-evaluation (e.g. "if design reveals schema migration needed"). Zero-cost in the initial plan; makes forward planning auditable when re-evaluation fires. Omit if no plausible triggers.

**Phase-boundary gate tasks**:

Each phase in the task chain should include a corresponding gate task with
`event_type: "gate-finding"`. Gate tasks carry additional metadata keys:

```json
{
  "event_type": "gate-finding",
  "source_agent": "facilitator",
  "verdict": "APPROVE | CONDITIONAL | REJECT",
  "min_score": 0.7,
  "score": 0.85
}
```

The facilitator emits the gate task shell at plan time with only
`chain_id`, `event_type`, `source_agent`, and `phase`. `verdict`,
`min_score`, and `score` are filled in by the reviewer agent at approve
time via `TaskUpdate(status="completed")`; the PreToolUse validator
enforces their presence on that completion transition, not on the
initial shell (Issue #570). `_resolve_gate_reviewer()` in
`phase_manager.py` determines the reviewer from `gate-policy.json` —
the plan embeds the gate name, not the reviewer name.

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
