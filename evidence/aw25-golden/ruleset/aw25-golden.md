---
id: aw25-golden
title: AW-25 golden-path canary rule
status: active
date: 2026-08-30
enforcement_class: policy
applies_to: [explore, build]
scope: wiki:governance
domain: aw25-golden
confidence: 1.0
---

# AW-25 golden-path canary rule

This doc is the **seed document** of the wiki pipeline's own evidence-gated proof
(TASK-PLAN AW-25 / RECON-ARCH-WIKI arch-R21): a deliberately trivial, deterministic
doctrine whose only purpose is to be ingestable, recallable, enforceable, and citable
end to end. It proves the chain — `rules ingest` → fan-out → `rules.recall` (installed
estate MCP) → a governed crew run trips the trigger → the gate denial cites this doc →
the ConformanceClaim surfaces in `GET /runs/:id/acceptance` — with every hop captured
as evidence, and the verdict re-derived by crew's acceptance view (an evaluator that
did not run the pipeline).

## Why a canary token

A real doctrine statement needs semantic judgement; the golden path must not. The rule
below bans one literal marker token (`AW25-GOLDEN-DENY-ME`) that no legitimate work
ever produces, so the deterministic trigger (a `contains` regex in the paired policy
`policies/POL-2500.json`, same id) fires if and only if the scenario deliberately
plants it in a governed unit's evaluated context. Deny is therefore deterministic,
repeatable, and free of false positives — the properties an acceptance scenario needs.

The gate evaluates the canonical JSON of the unit's whole governance context
(description, work output, tool-call payloads), so the scenario trips the trigger by
carrying the token in the run's intent — no reliance on any worker model choosing to
echo it. The enforceable twin of `POL-2500` is registered on the enforcement lane as a
`wicked-governance` Policy with the same id, so a gate denial's record
(`policy_ids: ["POL-2500"]`) and this doc name each other — the doc↔gate pairing the
governance packs convention requires (`wicked-core/governance/packs/README.md`).

## Rules

- `POL-2500` (critical): The literal marker token AW25-GOLDEN-DENY-ME must never
  appear in a governed unit's evaluated context — tool calls, unit intent, or
  produced output (wiki URI: wiki://aw25-golden#POL-2500). The token exists solely
  to prove the deny path of the wiki pipeline end to end; any occurrence in governed
  work is a deliberate trip of the golden-path acceptance scenario, and the gate must
  refuse it.
- `PAT-2501` (info): The golden-path scenario (wicked-garden
  evidence/aw25-golden + scenarios/qe/aw25-golden-path.md) is re-run after any change
  to rules ingest, fan-out, rules.recall, the gate hook, or the acceptance conformance
  section — the wiki pipeline's own "it works" stays evidence-gated, never asserted
  (wiki URI: wiki://aw25-golden#PAT-2501).
