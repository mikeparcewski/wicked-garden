# Field-Test Descriptions — Issue #628 Plugin-Scope Calibration

Four descriptions used to field-test the scorer against the three candidate
calibration targets (b4, b5, sc4) identified in issue #628.

---

## D1 — skill-agent-authoring

**Archetype**: skill-agent-authoring

Add `product:user-research-suite` — 3 user-research agents (user-interview-guide,
synthesis-reporter, opportunity-mapper) plus a research-synthesis skill, all wired
into the product domain. Introduces new slash commands and subagent_type entries.
~6-8 files added. No existing command renamed or removed. No external runtime
dependency. No DomainStore schema change.

---

## D2 — code-repo (refactor)

**Archetype**: code-repo

Refactor `scripts/crew/phase_manager.py` to extract gate-dispatch logic into a
new module `scripts/crew/gate_dispatch_runner.py`. 5 files touched: phase_manager
(reduced), new gate_dispatch_runner, updated imports in 2 downstream callers, 1
updated test file. No public API change — `score_factor`, `score_all`, and all
existing callers unaffected. Pure structural extraction, identical behavior.

---

## D3 — docs-only

**Archetype**: docs-only

Add `docs/composition/engineering.md`, `docs/composition/platform.md`, and
`docs/composition/product.md` following the cluster-A P3 composition-map template
(already used for jam, crew, smaht). 3 new markdown files. No code change. No
existing doc removed or renamed. No commands, agents, or scripts modified.

---

## D4 — SaaS-scale control (schema-migration)

**Archetype**: schema-migration

Migrate `user_sessions` table to add an `mfa_enforced` column. Backfill 50M existing
rows with `mfa_enforced = false`. Deploy to production with a 2-hour migration window.
Breaking change: unauthenticated session-cookie consumers will receive a different
session shape and must upgrade before the migration window closes. Auth team + DBA +
SRE + product alignment required. No feature flag — the migration window IS the deploy.
