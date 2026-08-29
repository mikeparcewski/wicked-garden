# qe Domain Integration Contract

This document defines the **public surface** that wicked-garden (and any other
consumer) depends on. Everything here is stable across minor versions — breaking
changes require a major bump.

Anything **not** listed here is an internal implementation detail. Consumers must
not depend on SQL schema, file paths inside `lib/`, or skill definition contents.

---

## 1. Namespace

All user-facing surface is in-catalog wicked-garden skills (dash-form names —
see CLAUDE.md "Naming Conventions"). Everything is a skill — there are no
separate agent or command component types.

- Router skill: `wicked-garden-qe` with actions (`setup`, `plan`, `author`,
  `execute`, `accept`, `review`, `insight`)
- Specialist worker skills: `wicked-garden-qe-<role>` (context:fork), e.g.
  `wicked-garden-qe-test-strategist`

The retired wicked-testing package's `wicked-testing:<name>` colon namespace is <!-- historical -->
gone (Phase 6c); this contract maps its former surfaces to the in-catalog names.

---

## 2. Core Skills (Tier 1 — stable)

Five skills form the public surface. Consumers may reference these by name.

| Skill                     | Purpose                                                        |
|---------------------------|----------------------------------------------------------------|
| `wicked-garden-qe` `plan`     | Test strategy, risk, testability, requirements quality         |
| `wicked-garden-qe` `author`| Scenario writing, test code generation, test data / fixtures   |
| `wicked-garden-qe` `execute`| Run tests, collect evidence, write to ledger                   |
| `wicked-garden-qe` `review`   | Independent verdict, semantic review, test-quality audit       |
| `wicked-garden-qe` `insight`  | Stats, reports, flaky detection, coverage archaeology          |

Each Tier-1 skill **internally** dispatches Tier-2 specialist skills
(ui-component-test-engineer, load-performance-engineer, etc.) into isolated
forked contexts (`context: fork`) based on the nature of the work. Consumers
do not invoke Tier-2 specialists directly — they always go through Tier-1.

This keeps the integration contract narrow. Adding a new Tier-2 specialist
is not a breaking change.

---

## 3. Core Worker Skills (Tier 1 — stable dispatch names)

Consumers (notably the crew gate) dispatch these forked worker skills by their
dash-form names (Phase 6c: the former `wicked-testing:<role>` dispatch strings <!-- historical -->
map 1:1 to `wicked-garden-qe-<role>`). This list is frozen; renames require
a major version.

| Skill (dispatch name)                              | Owning Skill   |
|----------------------------------------------------|----------------|
| `wicked-garden-qe-test-strategist`                   | plan           |
| `wicked-garden-qe-testability-reviewer`              | plan           |
| `wicked-garden-qe-requirements-quality-analyst`      | plan           |
| `wicked-garden-qe-risk-assessor`                     | plan           |
| `wicked-garden-qe-test-designer`                     | authoring      |
| `wicked-garden-qe-test-automation-engineer`          | authoring      |
| `wicked-garden-qe-acceptance-test-writer`            | authoring      |
| `wicked-garden-qe-scenario-executor`                 | execution      |
| `wicked-garden-qe-acceptance-test-executor`          | execution      |
| `wicked-garden-qe-contract-testing-engineer`         | execution      |
| `wicked-garden-qe-acceptance-test-reviewer`          | review         |
| `wicked-garden-qe-semantic-reviewer`                 | review         |
| `wicked-garden-qe-code-analyzer`                     | review         |
| `wicked-garden-qe-production-quality-engineer`       | review         |
| `wicked-garden-qe-test-oracle`                       | insight        |

Tier-2 specialist skills (integration, ui-component, e2e, visual, a11y, load,
chaos, fuzz, mutation, i18n, data-quality, observability, flaky-hunter, etc.)
are **not** part of the public contract. They are dispatched by Tier-1 skills.

---

## 4. Bus Events (public contract)

The qe domain emits events to [wicked-bus](https://github.com/mikeparcewski/wicked-bus)
when it is installed. **Emission is best-effort**: if wicked-bus is not present,
the emit is a no-op; the qe domain's own SQLite ledger is always written.

### Conventions

- Event names follow wicked-ecosystem convention: `wicked.<domain>.<noun>.<verb>`
- **Two distinct notions of "domain" — do not conflate them:**
  - The **2nd segment of the event *type*** is the **short** domain slug (`test`), e.g.
    `test` in `wicked.test.run.completed`. This is the compact routing token baked
    into the type string.
  - The **`domain` payload field / SQLite column** is the qe toolchain's
    domain stamp: **`qe`** (was `wicked-testing` pre-6c). It never uses the <!-- historical -->
    type-string token `test`.
  - So a completed run emits type `wicked.test.run.completed` with `domain: qe`.
- `subdomain` scopes by functional area (`ledger`, `scenario`, `testrun`, `verdict`, `evidence`)
- Payload follows the standard tier rules — IDs and outcomes always, small categoricals
  when relevant, never content / diffs / secrets

### Catalog (v1)

| Event Type                    | Subdomain             | Description                                           |
|-------------------------------|-----------------------|-------------------------------------------------------|
| `wicked.test.strategy.generated`  | `scenario.authoring`  | A test strategy document was produced                 |
| `wicked.test.scenario.authored` | `scenario.authoring`  | A scenario file was created or updated                |
| `wicked.test.run.started`       | `testrun`             | A test run began                                      |
| `wicked.test.run.completed`       | `testrun`             | A test run completed (any terminal status)            |
| `wicked.test.verdict.created`       | `verdict`             | A reviewer emitted a verdict (PASS / FAIL / N-A / SKIP)|
| `wicked.test.evidence.captured` | `evidence`            | Evidence artifacts written to disk for a run          |
| `wicked.test.evidence.recorded` | `vault.record`        | A single evidence envelope recorded via `wicked-vault record` |
| `wicked.test.contract.published`| `contract`            | plugin.json manifest synced; full skill/tier roster   |

### QE Gate Events

| Event | Trigger | Key fields |
|-------|---------|------------|
| `wicked.qe.gate.passed` | the qe gate CLI (`scripts/qe/lib/gate.mjs`) on PASS verdict | `run_id`, `context`, `gate_verdict`, `exit_code`, `verdict_summary`, `mode`, `completed_at`, `scenario_count` |
| `wicked.qe.gate.failed` | the qe gate CLI on FAIL verdict | same |
| `wicked.qe.gate.conditional` | the qe gate CLI on CONDITIONAL or SYSTEM_ERROR | same |
| `wicked.qe.deploy.completed` | the qe gate CLI on PASS only | `run_id`, `project_id` |

> **Gate emitter (Phase 6c):** the `wicked-qe gate` binary retired with the
> wicked-testing package. The gate-announcement CLI now ships in-catalog: <!-- historical -->
> `node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/gate.mjs" --project-id <id>
> --run-id <id> --verdict <PASS|FAIL|CONDITIONAL|SYSTEM_ERROR>
> --verdict-summary "<text>"`. Event types and the 8-field payload are a
> STABLE wire contract (wicked-crew's acceptance route folds them) — never
> rename them.

### Campaign → acceptance wiring (TH-6)

The full evidence path from a qe campaign scenario to crew's deny-dominates
acceptance gate — zero new gate or persistence code:

1. **Execute**: the model-free runner (`scripts/qe/runner`) executes the
   agent-authored spec and writes redacted evidence through wicked-ledger —
   a reused `scenarios` row (stable scenario_id = `<capability-id>.<slug>`,
   looked up by name so re-runs accrue flake history), a `runs` row per
   execution, and the evidence bundle + manifest under
   `.wicked-qe/evidence/<run-id>/`. The runner claims; it never grades.
2. **Grade**: the qe `accept` trio reviews the bundle (reviewer sees evidence
   paths only). The reviewer validates the manifest against the ledger
   contract BEFORE grading — a nonconforming bundle grades INCONCLUSIVE
   (TH-5).
3. **Record + announce**: the graded verdict goes through `gate.mjs`, run
   with the SAME cwd / `WICKED_QE_LEDGER_DIR` the runner used (the gate
   resolves the identical ledger root — an env pin is honored with TH-2
   semantics: absolute is the root, relative joins cwd). gate.mjs re-checks
   the manifest contract as a deny-dominates backstop (schema-fail records
   INCONCLUSIVE, never the graded verdict), writes the `verdicts` row keyed
   by the runner's run_id, and emits `wicked.qe.gate.*`.
4. **Re-derive**: crew's `GET /runs/:id/acceptance` reads the repo ledger's
   newest verdict row — a clean PASS flips it to `satisfied: true`, citing
   the verdict; everything else denies with its own reason. The bus events
   only add freshness (`--qe-gate-events`); the ledger stays the system of
   record.

### Payload shape (common fields)

All events include:

```
{
  "event_type": "wicked.test.run.completed",
  "domain": "qe",
  "subdomain": "testrun",
  "emitted_at": "2026-04-20T14:03:12.004Z",
  "project_id": "<uuid>",
  "run_id": "<uuid>",
  "qe_version": "0.1.0"
}
```

### Per-event additional fields

**`wicked.test.strategy.generated`** — `{ strategy_id, project_id, scenario_count }`
**`wicked.test.scenario.authored`** — `{ scenario_id, strategy_id, project_id, format_version }`
**`wicked.test.run.started`** — `{ run_id, scenario_id, project_id, started_at }`
**`wicked.test.run.completed`** — `{ run_id, scenario_id, status, started_at, finished_at, evidence_path }`
**`wicked.test.verdict.created`** — `{ verdict_id, run_id, verdict: "PASS|FAIL|N-A|SKIP", reviewer, evidence_path }`
**`wicked.test.evidence.captured`** — union payload so one subscriber schema serves
both emit sites (the verdict path in `wicked-ledger`'s bus-emit and the manifest path in
`skills/acceptance-testing/SKILL.md`): common `{ project_id, run_id, evidence_path,
qe_version }` plus optional `{ verdict_id, vault_payload_sha,
artifact_count }` — each optional field is `null` when the emitting site lacks it
(the verdict path has `verdict_id` + `vault_payload_sha` but `artifact_count: null`;
the manifest path has `artifact_count` but `verdict_id: null` + `vault_payload_sha: null`).
**`wicked.test.evidence.recorded`** — emitted by `wicked-vault record` (subdomain
`vault.record`) for a single recorded envelope: `{ scope, phase, claim_id, kind,
source, id, envelope_hash, payload_sha256, criteria_authored_by, status_at_record }`.
Distinct from `wicked.test.evidence.captured`, which describes a whole run's artifacts.
**`wicked.test.contract.published`** — `{ version: "<semver>", agents: [{ skill: "wicked-garden-qe-<name>", tier: 1|2 }] }`
(The `agents` / `subagent_type` payload field names are retained for wire
compatibility; each entry describes a forked worker skill and the value is its
skill dispatch name.)

Status values for `wicked.test.run.completed`: `passed | failed | errored | skipped`.

### What consumers get

wicked-garden's crew gate subscribes to `wicked.test.verdict.created` with
`domain: qe`. That's the entire read surface — no SQLite access
required.

---

## 5. Memories (optional enrichment)

When the memory layer (wicked-estate, via the wicked-garden-mem skill) is
reachable, the qe domain writes memories for non-trivial events. Consumers may
recall these memories; the shapes are part of the contract.

### Memory types written by the qe domain

| Memory type       | Written when                                     | Tier       |
|-------------------|--------------------------------------------------|------------|
| `failure-pattern` | `FAIL` verdict on a scenario previously passing  | semantic   |
| `flake-signal`    | Test oscillates pass/fail across runs            | episodic   |
| `coverage-gap`    | Coverage archaeologist finds an untested hotspot | semantic   |
| `test-decision`   | A reviewer CONDITIONAL emits actionable feedback | episodic   |

### Memory frontmatter

```yaml
---
name: <short-title>
description: <one-line summary>
type: failure-pattern | flake-signal | coverage-gap | test-decision
source: qe
source_version: <semver>
project_id: <uuid>
scenario_id: <uuid>    # when applicable
run_id: <uuid>         # when applicable
---
```

If the memory layer is unreachable, memory writes are a no-op.

---

## 6. Evidence Artifact Paths

Evidence lives project-local (not home-global), under `.wicked-qe/evidence/`.
The path is included in every `wicked.test.evidence.captured` and
`wicked.test.verdict.created` event.

```
<project-root>/.wicked-qe/
  evidence/
    <run-id>/
      manifest.json         # verdict + artifact index (schema: schemas/evidence.json)
      artifacts/
        <name>.<ext>        # screenshots, logs, curl output, etc.
```

Consumers **may read `manifest.json`** for any referenced run id — its schema
is public (see [EVIDENCE.md](EVIDENCE.md)). Consumers must not parse artifact
content blindly; use the manifest's `artifacts[]` index.

---

## 7. Graceful Degradation Rules

| Dependency       | Present behavior                          | Absent behavior                          |
|------------------|-------------------------------------------|------------------------------------------|
| SQLite           | Ledger writes + oracle queries            | qe fails loud (required)                |
| wicked-bus       | Emit events on every significant action   | No-op; log a single debug line           |
| wicked-estate    | Write memories on interesting signals     | No-op; log a single debug line           |
| wicked-garden    | Events consumed by crew gate              | N/A (wicked-garden is downstream)        |

The qe domain is usable **standalone** — only SQLite is required.
Bus + brain integration is pure upside when the ecosystem is present.

---

## 8. Version & Compatibility

- The qe surface versions with wicked-garden (semver).
- The surface in this document is stable across **minor** versions.
- Breaking changes to namespace, skill dispatch names, event types, evidence manifest
  schema, or degradation rules require a **major** version.
- wicked-garden pins a minor-version range (`^X.Y`) of wicked-ledger (the qe data layer) in its
  plugin.json's `wicked_ledger_version` field.


---

## 9. What Is NOT the Contract

To prevent coupling rot, these are explicitly internal:

- SQL schema in `lib/schema.sql`
- Any path inside `lib/`, `scripts/`, or `node_modules/`
- Tier-2 specialist skill names
- Internal event payload fields not listed above
- Ledger JSON file format under `.wicked-qe/` (except `evidence/<run>/manifest.json`)
- Oracle query set in `wicked-ledger`'s oracle-queries module

Consumers that reach into internals take on their own breakage risk. File an
issue if you need something promoted to the public contract.
