# Gate 4 Phase 1 — Facilitator Smoke Plan

**Goal**: prove the facilitator rubric produces reasonable plans on inputs it has never seen, before we delete the v5 rule engine. This is complementary to the 10 canonical scenarios at Gate 1, which were fixed calibration targets. The smoke suite here uses fresh unseen inputs.

**Scope**: 3 project descriptions spanning trivial / feature / cross-domain. Each one is captured as a facilitator plan (rubric-driven JSON matching `refs/output-schema.md`) and compared against a human-written expectation rubric. Legacy-engine output is captured alongside for qualitative comparison only — the engine's numbers are not ground truth.

---

## Inputs

Located under `scripts/ci/gate4_smoke_inputs/`:

| ID | Slug | Surface area | Why it's not in the canonical 10 |
|----|------|--------------|-----------------------------------|
| `smoke-01` | `feature-flag-expiry-sweeper` | trivial / platform | A cleanup script: simple scope, operational-risk hook (deletes stale flags), but minimal in everything else. Canonical trivial (01-trivial-typo, 07-docs-only) are UI/docs surfaces. |
| `smoke-02` | `webhook-retry-queue` | feature / backend + data | New async component with state_complexity + blast_radius considerations. Canonical feature (03-feature-midscale) is closer to CRUD; this exercises a durable-state design without being an auth rewrite. |
| `smoke-03` | `multi-tenant-search-index-shard` | cross-domain / data + platform + product | Spans data-pipeline, infra, and UX considerations simultaneously. Canonical cross-domain (04-auth-rewrite, 10-compliance-gdpr) are security-first; this one is scale-first and tenant-isolation-first. |

Each input is a single markdown file with:
- a one-paragraph description (what a user would type into `/wicked-garden:crew:start`)
- an `expected_outcome` YAML block listing the pass rubric
- a `notes` section explaining what a reasonable plan looks like

---

## Capture

For each input, the smoke suite:

1. Loads the markdown file, extracts the `description` paragraph.
2. Captures a facilitator plan by applying the rubric (`skills/crew/propose-process/SKILL.md` + refs). In this phase, the capture is a hand-curated JSON the operator (Claude) writes out by reasoning over the description as the facilitator would.
3. Writes the JSON to `scripts/ci/facilitator_outputs/smoke-NN-<slug>.json` matching `refs/output-schema.md`.
4. Runs the legacy rule engine for comparison:
   ```bash
   sh scripts/_python.sh scripts/crew/smart_decisioning.py --json "<description>"
   ```
   and captures the JSON alongside the facilitator output for qualitative diff.
5. Scores the facilitator plan against the `expected_outcome` block using the same dimensions as `measure_facilitator.py` (specialists, phases, evidence_required, test_types, complexity, rigor_tier).
6. Emits pass/fail per input + an overall verdict.

---

## Pass rubrics

Per-input rubrics (also embedded in the input file's `expected_outcome` block):

### smoke-01 — feature-flag-expiry-sweeper
A cron-style cleanup of stale feature flags. Reasonable plan:
- Rigor: `minimal` or `standard` (not `full` — no compliance, no auth).
- Phases: at least `build` + `review`. `test` acceptable for the sweeper itself. `test-strategy` acceptable. Not `full` rigor — this is utility plumbing.
- Specialists: `platform` engineer or `backend-engineer`; optional `sre` if operational_risk is read as MEDIUM.
- Complexity: 2–3. Tasks: ≤4.
- Evidence: unit-results or integration-results. `performance-baseline` allowed but not required.

### smoke-02 — webhook-retry-queue
A new durable retry queue for outbound webhooks with exponential backoff + dead-letter. Reasonable plan:
- Rigor: `standard` or `full`. `minimal` would be wrong (state_complexity is real).
- Phases: `clarify` or `design` (at least one), `test-strategy`, `build`, `test`, `review`.
- Specialists: `backend-engineer`, `test-strategist` or `test-designer`, `sre` or `platform`; `data-engineer` if persistence is called out.
- Complexity: 4–5. Tasks: ≥5.
- Evidence: unit-results + integration-results + performance-baseline (retry policy validation).

### smoke-03 — multi-tenant-search-index-shard
Shard a shared search index by tenant to prevent cross-tenant leakage in results. Reasonable plan:
- Rigor: `full` (tenant isolation + data scope = security concern even without explicit PII).
- Phases: `clarify`, `design`, `test-strategy`, `build`, `test`, `review` (full lifecycle).
- Specialists: `solution-architect`, `data-engineer`, `security-engineer` (or compliance-officer if privacy is read as MEDIUM+), `sre` or `platform`, `test-strategist`.
- Complexity: 6–7. Tasks: ≥7.
- Evidence: unit-results + integration-results + migration-rollback-plan + security-scan + performance-baseline.

---

## How to re-run

```bash
cd /path/to/wicked-garden
python3 scripts/ci/gate4_smoke.py --capture                   # capture facilitator outputs + run pass/fail
python3 scripts/ci/gate4_smoke.py --capture --with-legacy     # also run smart_decisioning.py for comparison
python3 scripts/ci/gate4_smoke.py                             # re-score already-captured outputs
python3 scripts/ci/gate4_smoke.py --input smoke-02            # single input
```

Exit codes: `0` all inputs pass · `1` at least one fails · `2` configuration error (missing input file, malformed JSON, etc.).

Output lands in:
- `scripts/ci/facilitator_outputs/smoke-NN-<slug>.json` — facilitator plan
- `scripts/ci/facilitator_outputs/smoke-NN-<slug>.legacy.json` — legacy engine plan (when `--with-legacy`)
- `scripts/ci/gate4-smoke-results.md` — human-readable assessment

---

## Why 3 inputs

10 canonical scenarios calibrated Gate 1. They stay fixed. The smoke suite's job is to catch regressions and surface-level blind spots with unseen inputs. Three is enough to hit the trivial / feature / cross-domain spread without re-litigating the calibration.
