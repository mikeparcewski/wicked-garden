# Specialist Selection (~70-agent roster map)

Discover at call time via `Glob agents/**/*.md` and read the `description:` +
"Use when:" lines. This ref is the default map — if an agent disappears or moves,
the Glob still works.

Per the Jam-1 roster decision (`memory/v6-specialist-agent-roster-decision.md` in the
wicked-garden brain), the v6 roster targets ~70 agents with differentiated
descriptions. This list is the POST-Gate-2-surgery map. Some agents listed below
(e.g. `migration-engineer`, `observability-engineer`, `chaos-engineer`,
`contract-testing-engineer`, `devex-engineer`) are newly added in Gate 2. If an agent
is missing in the current checkout, fall back to the closest match — never invent.

---

## Roster map by signal

Each row lists: factor(s) that tend to require it → specialist → one-line WHY.

### Product / UX
- user-facing IMPACT medium+ → `ux-designer` (flow + interaction)
- user-facing HIGH + visual change → `ui-reviewer` (visual polish + consistency)
- HIGH compliance (a11y) or a11y-required surface → `a11y-expert`
- ambiguous requirements → `requirements-analyst` (user stories + AC)
- goals / trade-offs across stakeholders → `product-manager`
- market/customer voice → `user-voice` (post-merge of feedback-analyst + customer-advocate)
- strategy / ROI → `market-strategist` (post-merge of business-strategist + competitive-analyst)
- stakeholder alignment → `value-strategist` (post-merge of alignment-lead + value-analyst)

### Engineering (implementation)
- API endpoints / server logic → `backend-engineer`
- UI code → `frontend-engineer`
- architectural trade-offs → `solution-architect`
- cross-file patterns / maintainability → `senior-engineer`
- schema / migration / backfill → `migration-engineer`
- developer experience / tooling → `devex-engineer`
- system boundaries → `system-designer`
- documentation → `technical-writer` (humans) or `api-documentarian` (SDK/API docs)
- data schemas (data domain) → `data-architect`

### QE
- test planning / scenarios → `test-strategist`
- test writing + execution + review (unified) → `test-designer` (post-merge)
- contract tests between services → `contract-testing-engineer`
- risk classification → `risk-assessor`
- production quality telemetry → `production-quality-engineer`
- testability review → `testability-reviewer`
- TDD mentoring (conditional skill, not always agent) → `tdd-coach`

### Platform / SRE
- OWASP / secrets / auth → `security-engineer`
- GDPR/CCPA/HIPAA/SOC2 → `compliance-officer`
- PII / data subject rights → `privacy-expert`
- audit trails / evidence → `auditor`
- runtime reliability / SLOs → `sre`
- fault injection / resilience → `chaos-engineer`
- observability (metrics/traces/logs) → `observability-engineer`
- release + rollback → `release-engineer`
- infra-as-code → `infrastructure-engineer`
- incident response → `incident-responder`

### Data
- pipelines / ingest → `data-engineer`
- ML training / model review → `ml-engineer`
- analytics / EDA → `data-analyst`

### Delivery
- rollout planning → `rollout-manager`
- A/B / experiment design → `experiment-designer`
- risk / progress tracking → `risk-monitor` / `progress-tracker`
- stakeholder reporting → `stakeholder-reporter`
- cost / FinOps → `cloud-cost-intelligence` (post-merge of finops-analyst + cost-optimizer)
- delivery orchestration → `delivery-manager`

### Crew built-ins (fallbacks)
- ambiguous / brainstorm → `facilitator`
- research / unknown codebase area → `researcher`
- generic review → `reviewer` / `independent-reviewer`
- generic implementation → `implementer`

---

## Selection rules

1. **Factor-first, not keyword-first.** Pick from the factor scores, not from
   matching words in the description. "migrate" in a description doesn't always mean
   `migration-engineer` — if state_complexity is LOW (e.g. "migrate from snake_case to
   camelCase variable names") then it's a refactor, not a migration.

2. **Minimum set that covers the scores.** For each factor that scored MEDIUM or HIGH,
   include ≥1 specialist. Overlap is fine; redundant picks are not.

3. **Full-rigor adds reviewers, not just doers.** Full rigor requires ≥2 reviewers
   (e.g. `senior-engineer` + `security-engineer` + `independent-reviewer`). Standard
   rigor usually has 1. Minimal usually has none beyond the default reviewer.

4. **Compliance scope HIGH** → ALWAYS include `compliance-officer` AND one of
   `privacy-expert` / `auditor` depending on the surface. GDPR → privacy-expert. SOC2
   audit trail → auditor. Both, for data export endpoints.

5. **Tie-breakers when two specialists overlap:**
   - Visual / UI-only review → `ui-reviewer` beats `ux-designer`.
   - Flow / interaction → `ux-designer` beats `ui-reviewer`.
   - Cross-service contract → `contract-testing-engineer` beats generic `test-designer`.
   - Backfill script → `migration-engineer` beats `data-engineer`.

6. **Banned picks:**
   - Do not pick `execution-orchestrator` or `value-orchestrator` — they're deprecated
     v5 routing artifacts per the Jam-1 decision.
   - Do not pick `market-analyst` — subsumed into `market-strategist`.
   - Do not pick `forecast-specialist` — a reporting wrapper; use `stakeholder-reporter`.

7. **Docs-only or content-only work** → `technical-writer` only, no engineering.

8. **Prefer skills over agents** for: onboarding, codebase narration, scenario
   execution. Per the Jam-1 decision, these were demoted from agents to skills in v6.

---

## Fallback resolution

If a listed specialist does not exist in `agents/**/*.md`:

1. Use the closest conceptual match (e.g. `migration-engineer` missing → fall back to
   `senior-engineer` + an explicit `migration-rollback-plan` in evidence_required).
2. Never emit an unresolved specialist name in the task chain.
3. Record the miss in the `process-plan.md` under "Roster gaps" so it can be filled in
   Gate 2 surgery.
