# ADR 0006 — The test harness homes into the four planes as "qe campaign" — no new product

- **Status:** Accepted
- **Date:** 2026-08-29
- **Context owners:** wicked-garden (capability) + wicked-crew/wicked-core (control) + wicked-ledger/wicked-vault (evidence) + wicked-studio (surface)
- **Relates to:** garden `skills/qe/` (the qe domain), `scripts/qe/lib/gate.mjs` (the `wicked.qe.gate.*` wire contract), `schemas/` (contract-schema home); core `src/campaign.rs` + DES-CAMPAIGN-001 (the Campaign DAG scheduler); crew `GET /runs/:id/acceptance` (the deny-dominates gate); ledger `docs/SCHEMA-CONTRACT.md` (evidence-manifest versioning). (Cross-repo references are paths in those repos, not links.)
- **Origin:** 2026-08 test-harness recon (RECON-TEST-HARNESS test-R3); precedent in `scratch/TARGET-ARCHITECTURE.md` Phase 6 (wicked-testing dissolution). <!-- historical -->

## Context

The 2026-08 studio E2E campaign proved a working shape for large-scale, evidence-gated
verification: recon a product's surfaces into a capability inventory, generate a
dependency-ordered scenario ladder, execute deterministically (model-free browser/API
runners, wire capture, read-back assertions), grade through an isolated reviewer, and
land evidence where an acceptance gate can re-derive it. The question this ADR settles
is *where that harness lives*.

The tempting answer — a new standalone product ("interactive test harness",
"wicked-harness") — has already been tried and unwound once. **wicked-testing was <!-- historical -->
retired in 2026-08 (Phase 6) INTO exactly the planes below**, at real cost: npm
deprecation at 0.11.0, install-surface migration, the `wicked.qe.*` event rebrand,
repo archival, site redirects. Its 40 specialists and the acceptance trio became
garden's `qe` domain; its machine gate became crew's `/runs/:id/acceptance`; its data
layer became wicked-ledger + wicked-vault under `.wicked-qe/`. A standalone harness
would recreate the product we just paid to dissolve.

## Decision

**No new product.** The harness is a *campaign* capability distributed across the four
existing planes, under the name **"qe campaign"**.

| Concern | Plane | Home | Rationale |
|---|---|---|---|
| **Executor runtime** (model-free browser/API runner, vendored Playwright, wire-capture/read-back helpers — TH-4) | **Capability** | **wicked-garden**, `scripts/qe/runner` inside the qe domain | The executor is a tool any control plane invokes, like the rest of the qe pipeline (accept trio, gate.mjs) already in garden. Crew runs *governed workers*; it does not own domain tooling. Precedent: wicked-testing's executor skills landed in garden, only the gate landed in crew. | <!-- historical -->
| **Recon + generation** (estate-seeded capability inventory, scenario ladder — TH-7) | **Capability** | wicked-garden qe domain (`campaign` action) | Skill work: reads estate's graph + mem/search, emits scenario format v1 — never a parallel format. |
| **Schemas** (TH-5) | **Capability + Evidence** (two owners, deliberately) | `campaign-recon.schema.json` → **wicked-garden/schemas/** (sits beside assert_contracts.json, health_probe.json, wicked-pack.schema.json); scenario-evidence shape + `claim_level` enum (certified \| machinery-verified \| skipped) → **wicked-ledger manifest 2.1** via SCHEMA-CONTRACT.md | The recon artifact is a capability contract; the evidence shape is the system of record's contract. A single home would create the parallel-format drift the qe domain forbids. Reviewer validates against the ledger's schema before grading; schema-fail = INCONCLUSIVE. |
| **Scheduler** (durable parallel DAG over scenarios — TH-9) | **Control** | **wicked-core** `src/campaign.rs` (`launch_campaign`/`resume_campaign`, already built per DES-CAMPAIGN-001), exposed through **wicked-crew** `POST/GET /api/v1/campaigns` + WS passthrough of the Campaign* events | The scheduler exists; the work is exposure, not construction. Garden gets no scheduler. Governance (evaluator≠creator, deny-dominates, HITL gates) is crew's job by design. |
| **Evidence + acceptance** | **Evidence (foundation)** | **wicked-ledger** rows (scenarios/runs/verdicts) + **wicked-vault** artifacts under `.wicked-qe/evidence/<run-id>/`; crew's `GET /runs/:id/acceptance` re-derives the verdict from them | "Done" is re-derived from evidence, never asserted — the family's founding rule. Zero new gate or persistence code. |
| **Scoreboard** (TH-14) | **Experience** | **wicked-studio**, read-only in v1: scenario ladder, node status from Campaign* WS frames, verdict chips, evidence links, flake/cost trends from ledger insight queries | Studio is a pure client of crew's wire contract; a read surface adds no new authority. Authoring/triage is explicitly phase 2. |

### Naming

- **"qe campaign"** — the garden action a user invokes (extends the existing qe domain vocabulary).
- **"Campaigns"** — the studio surface.
- **`CampaignDef` / Campaign*** — wicked-core's terms, unchanged; core owns them via DES-CAMPAIGN-001.
- **Avoid** "interactive test harness" (collides with the wicked-interactive product) and any revival of the retired "wicked-testing" name. <!-- historical -->

## Consequences

1. **This ADR is the anti-scope-creep anchor.** Every TH task cites its plane
   assignment from the table above: TH-4 (executor) → garden; TH-5 (schemas) → garden
   + wicked-ledger; TH-6 (gate wiring) → garden qe (gate.mjs emit) + ledger + crew acceptance; TH-7 (recon/
   generation) → garden; TH-9 (scheduler exposure) → wicked-core-ts + crew; TH-12
   (intake: plan proposed as a HITL gate) → garden `campaign_intake` glue over crew's
   existing gate wire (elicitation follow-on = crew#358); TH-14
   (scoreboard) → studio. A TH task proposing a new package outside these homes is
   out of contract and needs a superseding ADR.
2. **No new install surface.** The campaign arrives with `wicked-garden` (capability),
   `wicked-crew` (control + API), and the ledger/vault peers users already have.
   Nothing new to publish, deprecate, or redirect later.
3. **Separation of duties is structural.** Garden authors and executes (writes
   evidence, never verdicts of record); the qe accept trio grades in isolation; crew's
   gate re-derives acceptance from ledger evidence, deny-dominates. No plane can
   self-grade.
4. **Costs accepted:** the capability is spread across four repos, so cross-repo
   contract discipline (scenario format v1, `wicked.qe.gate.*` payload, ledger manifest
   versioning, `wicked-crew-api-types`) is load-bearing — schema and floor bumps move
   through their owners' release trains, never ad hoc. Crew-side scheduler exposure is
   a prerequisite for durable parallel runs; until it lands, campaigns run as ordinary
   governed workflows.
