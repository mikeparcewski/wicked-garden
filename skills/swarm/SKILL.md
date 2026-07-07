---
name: wicked-garden:swarm
context: fork
description: |
  Parallel verification-swarm orchestration playbook: fan out N scoped
  subagents over N units of work (repos / modules / files), then run a
  SEPARATE verifier wave that re-derives each result from a clean state —
  self-graded "done" is rejected. Composes the crew agents, the qe
  semantic-reviewer, /wicked-garden:prove, wicked-vault attestation, and
  the worktrees + deliberate skills rather than reinventing them. This is
  multi-AGENT parallel execution+verification; for independent multi-MODEL
  perspectives use jam:council instead.

  Use when: multi-unit / fan-out work ("review every repo", "resolve the
  backlog with proof", "apply this across all modules", "audit each
  service"), high-blast-radius changes that need independent verification,
  or any run where a claimed "done" must be re-derivable from receipts.
status: stable
phase_relevance: ["build", "test", "review"]
archetype_relevance: ["build", "review", "migrate", "modernize", "incident"]
---

# Swarm — parallel verification swarm

Orchestrate **N units of work in parallel** (one scoped subagent per unit),
then **independently verify** every result with a separate wave of agents that
re-derive "done" from a clean state. The swarm's value is not the parallelism —
it's that **no agent grades its own work**. A claimed "tests pass" / "done" that
can't be re-derived from receipts is rejected.

> **Swarm vs council.** `jam:council` gets independent *multi-model* opinions on
> one decision (different vendors answer the same scaffold). Swarm gets parallel
> *multi-agent* execution + verification over many units. Use council to decide;
> use swarm to execute-and-prove. They compose: run a council inside the verify
> wave for a high-stakes verdict (see `refs/independent-verification.md`).

## Compose, don't reinvent

This skill is orchestration prose. Every primitive it needs already exists in
the garden — reference these, do not duplicate them:

| Need | Use (existing garden piece) |
|------|------------------------------|
| Per-unit implementer subagent | `agents/crew/implementer.md` (already does parallel-when-independent + evidence) |
| Per-unit recon subagent | `agents/crew/researcher.md` (read-only context gathering) |
| Independent semantic verdict | `agents/qe/semantic-reviewer.md` (independent-by-construction; refuses to attest its own work) |
| Fallback reviewer | `agents/crew/reviewer.md` (reviewer-separation + external-review rules baked in) |
| Re-derive a claim (the receipt) | `/wicked-garden:prove` (run + freeze evidence + gate; fail-closed) |
| Hard-gate independent sign-off | `/wicked-garden:prove --with-attestations` → `wicked-vault attest` (evaluator ≠ creator, G10) |
| Blast-radius / scope lens | `wicked-garden:deliberate` (lens 2 + 3) and `/wicked-garden:search:blast-radius` |
| Per-unit isolation + commit hygiene | `wicked-garden:worktrees` (dangling-commit trust-but-verify) |
| Phase shape per unit | `wicked-garden:archetype` refs (`build` / `review` / `migrate`) |
| Multi-model verdict in a wave | `wicked-garden:jam:council` |

## The wave loop

```
0. recon      → parallel researcher agents → concept catalog + per-unit profiles
   synthesize → fit-matrix + relevance tiers
   checkpoint → ONE structured scope question to the user (skip under full latitude)
1. implement  → N parallel implementer agents (one per unit, self-contained brief)
                each writes DETAILED artifacts to disk, returns a ~150-word summary
2. verify     → M parallel verifier agents (SEPARATE from implementers)
                re-run from clean state, read the ACTUAL diff, render PASS/FAIL/PARTIAL
3. receipts   → /wicked-garden:prove per claim; hard gates add --with-attestations
4. ship       → branch per unit, conventional commits, CI-green, independent review,
                clean merge tree, tag-driven release  (only when asked)
```

Each numbered step has a ref. Waves hand off **via disk artifacts**, never via
the orchestrator's context — that is what keeps the parent lean and the run
auditable.

## Orchestrator hygiene (the parent context stays lean)

- **Detail to disk, summary to context.** Subagents write the full profile /
  plan / diff / receipt to the scratch dir and return ≤150 words. Never let a
  subagent dump raw output into your context.
- **One message, many Task calls** for each wave — that is what makes it
  parallel. A serial run with no documented `serial_reason` is a protocol miss
  (same rule `agents/crew/implementer.md` enforces).
- **Background long/external work** and synthesize on completion rather than
  blocking the wave.
- **The verifier is a different agent than the implementer.** If the same agent
  type did the work, the verdict is a self-grade — `agents/qe/semantic-reviewer.md`
  and the vault `attest` both refuse `evaluator == creator`.

## The two reusable briefs

The mechanics that make this repeatable are the **briefs** handed to each wave.
Both live in `refs/fan-out.md` (implementer) and `refs/independent-verification.md`
(verifier) as copy-paste templates. The shape:

- **Implementer brief** (per unit): read THIS unit's own rules/conventions →
  impact analysis (blast radius) BEFORE changing → implement with **in-scope
  tech-debt cleanup only** (no opportunistic refactor sprawl) → functionally
  test **proportional to blast radius** → write artifacts to disk → return a
  concise summary.
- **Verifier brief** (per unit): ignore the implementer's prose → re-run the
  suite/build from clean → read the ACTUAL diff → check over-claims (e.g. a
  claimed "pre-existing failure" must actually fail on the BASE commit) →
  render PASS / FAIL / PARTIAL → write the authoritative receipt.

## Honest marking (no padding)

Mark every finding `GAP` / `PARTIAL` / `ALREADY-COVERED`. Surface
reverse-transfers and "you're already ahead of this" honestly. **A short true
list beats a long speculative one.** Record considered-and-rejected items
explicitly so they read as weighed, not missed. Details in
`refs/receipts-and-evidence.md`.

## Recon-first, then checkpoint

Before an expensive fan-out, run the recon wave and synthesize a fit-matrix +
relevance tiers, then **checkpoint scope with the user in a single structured
question**. Under an explicit goal / full latitude, proceed without asking.
Full procedure in `refs/recon-synthesis.md`.

## Disk-artifact layout (waves hand off here)

A scratch dir (the worked example this playbook was distilled from used
`.cross-pollination/`) with a top synthesis/index doc, per-unit
profile/plan/review/receipt files, and a deferred-items log. Exact tree in
`refs/recon-synthesis.md` §layout and `refs/receipts-and-evidence.md`.

## Refs

- [refs/recon-synthesis.md](refs/recon-synthesis.md) — recon wave, fit-matrix, relevance tiers, the single checkpoint question, scratch-dir layout
- [refs/fan-out.md](refs/fan-out.md) — parallel implementer wave + the **implementer brief template**, impact analysis, in-scope cleanup
- [refs/independent-verification.md](refs/independent-verification.md) — the verifier wave + the **verifier brief template**, isolation, over-claim kills, PASS/FAIL/PARTIAL
- [refs/receipts-and-evidence.md](refs/receipts-and-evidence.md) — verbatim receipts, prove/vault/wicked-testing composition, honest GAP/PARTIAL/ALREADY-COVERED marking
- [refs/ship-discipline.md](refs/ship-discipline.md) — branch-per-unit, conventional commits, CI-green gate, independent review + resolve, clean merge tree, tag-driven release
