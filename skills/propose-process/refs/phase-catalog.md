# Phase Catalog (templates, soft dependencies)

Phases are templates, not laws. The facilitator picks what applies for THIS work and
may skip, collapse, or insert phases.

---

## Templates

### `ideate`
- **Purpose**: Open-ended exploration when novelty is HIGH or the problem is unframed.
- **Typical primaries**: `facilitator`, `ux-designer`, `product-manager`, `researcher`.
- **Deliverables**: problem framing, 2-3 plausible approaches, one recommended direction.
- **Skip when**: description is crisp AND priors show routine completion pattern.

### `clarify`
- **Purpose**: Turn a fuzzy ask into testable outcomes + acceptance criteria.
- **Typical primaries**: `requirements-analyst`, `product-manager`.
- **Deliverables**: user stories, AC, scope boundaries, success metric.
- **Skip when**: description already contains precise AC (rare; most bugfixes still
  benefit from a crisp success criterion).

### `design`
- **Purpose**: Pick the approach, draw the boxes, name the trade-offs.
- **Typical primaries**: `solution-architect`, `system-designer`, `senior-engineer`.
- **Deliverables**: design doc or ADR, identified risks, chosen approach with rationale.
- **Skip when**: trivial typo / docs / config fix with no decisions to make.

### `test-strategy`
- **Purpose**: Decide what "done" looks like in evidence terms BEFORE building.
- **Typical primaries**: `test-strategist`, `risk-assessor`.
- **Deliverables**: scenarios (happy + edge + error), risk classification, test types
  chosen, out-of-scope noted.
- **Skip when**: test_required is false across the entire chain (docs-only, minimal
  rename refactors). For any work with state_complexity or user-facing impact ≥ MEDIUM,
  do NOT skip.

### `build`
- **Purpose**: Make the change.
- **Typical primaries**: `backend-engineer`, `frontend-engineer`, `migration-engineer`,
  `data-engineer`, `devex-engineer`, or `implementer` as fallback.
- **Deliverables**: the code + inline unit tests (if `test_required`).
- **Skip when**: essentially never. Even docs changes are "build" for task-tracking.

### `test`
- **Purpose**: Execute the test strategy and produce evidence.
- **Typical primaries**: `test-designer`, `contract-testing-engineer`,
  `test-automation-engineer`.
- **Deliverables**: test results, acceptance report, screenshots if UI, perf baselines
  if operational_risk ≥ MEDIUM.
- **Skip when**: same rule as test-strategy — only when test_required is false.

### `review`
- **Purpose**: Multi-perspective validation before acceptance.
- **Typical primaries**: `senior-engineer`, `security-engineer`, `compliance-officer`,
  `independent-reviewer`, `reviewer`.
- **Deliverables**: review findings (APPROVE/CONDITIONAL/REJECT), recommendations.
- **Skip when**: rigor_tier is `minimal` AND factors are all LOW. Standard rigor
  requires at least one reviewer; full rigor requires ≥2.

---

## Soft dependencies

Typical order is `ideate → clarify → design → test-strategy → build → test → review`,
but the facilitator can reorder when the work demands it. A few inviolable rules:

1. `test` cannot run before `build` (you can't test what doesn't exist).
2. `review` runs last before acceptance.
3. `test-strategy` MUST precede `build` when rigor_tier is `full`.
4. When state_complexity is HIGH, a `migrate` sub-phase MAY be inserted between
   `design` and `build`. It's not a separate template — it's a task inside `build`
   with event_type `coding-task` and `evidence_required` including
   `migration-rollback-plan`.
5. When user-facing impact is HIGH, `design` MUST include a UX/UI specialist, not just
   architecture.

---

## Insertions (mini-phases)

These are NOT top-level phases. They are tasks inserted into an existing phase with
distinctive metadata:

- **Migration** — in `build`, `event_type: coding-task`, `evidence_required` includes
  `migration-rollback-plan`.
- **Security scan** — in `review`, `event_type: gate-finding`, specialist is
  `security-engineer`.
- **Compliance traceability** — in `review`, `event_type: gate-finding`, specialist is
  `compliance-officer`.
- **Accessibility audit** — in `test`, `test_types: [a11y]`, specialist is `a11y-expert`.
- **Performance baseline** — in `test`, `test_types: [performance]`, `evidence_required`
  includes `performance-baseline`.

---

## Collapsing

When scope is tiny, phases collapse:

| Scenario                         | Collapsed chain                            |
|----------------------------------|--------------------------------------------|
| Typo in UI copy                  | `build` only                               |
| Small bugfix with crisp repro    | `clarify` + `build` + `test`               |
| Docs update                      | `build` only                               |
| Internal refactor, no behavior   | `design` + `build` + `review`              |
| Feature with AC already written  | `design` + `test-strategy` + `build` + `test` + `review` |

Collapsing is a judgment call. When in doubt, include the phase — the cost of an
unnecessary clarify is small, the cost of a missed one is high.

---

## When a gate finding forces a phase rewind

If a `gate-finding` with verdict REJECT lands on a `build`-phase task, the facilitator
(in `re-evaluate` mode) MAY insert:

- a new `design` task if the root cause is architectural;
- a new `clarify` task if the root cause is requirements ambiguity;
- a re-run of `test-strategy` if the root cause is missing test coverage.

Never silently re-run the failed phase with the same plan; always insert the upstream
correction task first.
