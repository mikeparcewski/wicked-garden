# Gate Policy — Human-Readable Description

**This file is documentation only.** The runtime source of truth is
`.claude-plugin/gate-policy.json`. The function `_resolve_gate_reviewer(gate_name,
rigor_tier)` in `scripts/crew/phase_manager.py` loads that JSON and returns the
dispatch block. This markdown description must stay in sync with the JSON but is
never read by code.

---

## Gate × Rigor Reviewer Matrix

Each cell shows: reviewer(s), dispatch mode, and fallback agent.

| Gate | Tier | Reviewer(s) | Mode | Fallback |
|------|------|-------------|------|---------|
| requirements-quality | minimal | _(none — primary specialist inline)_ | self-check | requirements-analyst |
| requirements-quality | standard | `requirements-quality-analyst` | sequential | requirements-analyst |
| requirements-quality | full | `product-manager` + `requirements-analyst` | council | senior-engineer |
| design-quality | minimal | _(none — primary specialist inline)_ | self-check | solution-architect |
| design-quality | standard | `solution-architect` | sequential | senior-engineer |
| design-quality | full | `solution-architect` + `security-engineer` + `product-manager` + `risk-assessor` | council | senior-engineer |
| testability | minimal | _(none — primary specialist inline)_ | self-check | test-strategist |
| testability | standard | `test-strategist` | sequential | senior-engineer |
| testability | full | `test-strategist` + `risk-assessor` | parallel | senior-engineer |
| code-quality | minimal | _(none — senior-engineer R1-R6 lint inline)_ | self-check | senior-engineer |
| code-quality | standard | `senior-engineer` | sequential | senior-engineer |
| code-quality | full | `senior-engineer` + `security-engineer` | parallel | senior-engineer |
| evidence-quality | minimal | _(none — primary specialist inline)_ | self-check | test-strategist |
| evidence-quality | standard | `test-strategist` | sequential | senior-engineer |
| evidence-quality | full | `test-strategist` + `production-quality-engineer` | parallel | senior-engineer |
| final-audit | minimal | _(none — senior-engineer inline)_ | self-check | senior-engineer |
| final-audit | standard | `senior-engineer` | sequential | independent-reviewer |
| final-audit | full | `senior-engineer` + `independent-reviewer` | sequential | human |

---

## Dispatch modes

- **self-check** — the primary specialist for the phase runs the gate check inline as
  part of their normal work. No separate Task dispatch. The verdict (APPROVE /
  CONDITIONAL / REJECT) must still appear in the phase deliverable.
- **sequential** — agents run in order; each sees prior output before rendering verdict.
- **parallel** — agents run concurrently; results are merged before a final verdict.
- **council** — dispatched via `wicked-garden:jam:council`. Requires ≥ 2 reviewers.
  Used at full rigor for gates with cross-functional stakeholders (requirements-quality,
  design-quality).

---

## Fallback policy

When a named reviewer is unavailable (e.g., agent not installed, dispatch fails),
`_resolve_gate_reviewer` returns the `fallback` agent name. The fallback agent runs
in `sequential` mode. `"human"` as a fallback means escalate to the user.

---

## Self-check clarification

`minimal` rigor always maps to `self-check` with an empty reviewers list. This is
the only case where an empty reviewers list is valid. `_resolve_gate_reviewer` does
not raise on an empty reviewers list when `mode == "self-check"`.

---

## Source of truth

Runtime decisions are made from `.claude-plugin/gate-policy.json`. A CI unit test
(`scripts/ci/test_gate_policy.py`) asserts that all 18 `(gate, rigor_tier)`
combinations resolve to a non-empty reviewer list or `mode: "self-check"`.

The facilitator rubric reads gate names from the gate catalog above when emitting
phase-boundary-gate tasks. The reviewer assignment is deferred to approve time —
the plan does NOT embed reviewer names, only gate names.
