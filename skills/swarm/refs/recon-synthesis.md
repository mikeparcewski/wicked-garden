# Recon-first → synthesize → checkpoint

Before an expensive fan-out, spend a little to learn a lot: run a parallel
**recon wave**, synthesize the findings into a fit-matrix + relevance tiers, and
**checkpoint scope with the user in a single structured question**. This is the
swarm's analogue of the `deliberate` skill's "is this real / what's the blast
radius" lenses, applied across many units at once.

## The recon wave

Dispatch parallel `agents/crew/researcher.md` subagents — read-only, one per
unit (or one per concept you're trying to map). Each researcher:

- profiles its unit: stack, conventions, test command, risk surfaces, owners,
- maps where the candidate change would land and what it would touch,
- writes a **per-unit profile** to disk and returns a concise summary.

Recon agents are read-only, so they fan out freely with no isolation concerns.

## Synthesize

Once recon returns, the orchestrator synthesizes — this is *your* job, not a
subagent's, because it's the cross-unit view:

1. **Concept catalog** — the set of candidate changes / patterns / findings,
   each named once with a stable id.
2. **Per-unit profiles** — one row per unit (already on disk from recon).
3. **Fit-matrix** — concept × unit. For each cell, does this concept apply to
   this unit? Mark `GAP` (missing, should add) / `PARTIAL` (half-there) /
   `ALREADY-COVERED` (unit is already ahead). See `refs/receipts-and-evidence.md`
   for the honest-marking discipline — do not inflate the matrix.
4. **Relevance tiers** — rank units/concepts so the fan-out spends effort where
   it matters: Tier 1 (high impact, do now) → Tier 2 (worth doing) → Tier 3
   (defer / log). A short true Tier-1 list beats a long speculative one.

## The single checkpoint question

A fan-out is expensive (N implementer + M verifier agents). Before you spend it,
ask the user **one structured question** that pins scope:

```
Recon is done. Here's the fit-matrix and tiers:
  Tier 1 (propose to do now): <units/concepts>
  Tier 2 (worth doing):       <units/concepts>
  Tier 3 (defer):             <units/concepts>
Proceed with Tier 1 as the fan-out scope, or adjust?
```

One question, structured, scoped. Not a stream of clarifications.

**Under an explicit goal / full latitude, skip the checkpoint and proceed** —
the user already authorized the spend. (If `AskUserQuestion` is unavailable in
dangerous mode, fall back to a plain-text question and wait — per the garden's
AskUserQuestion fallback rule.)

## Scratch-dir layout (the run is auditable from here)

Waves hand off via disk. Lay the scratch dir out so anyone can reconstruct the
run. The worked example this playbook was distilled from used `.cross-pollination/`;
any stable scratch dir works (e.g. `.swarm/<run-id>/`):

```
<scratch>/                       e.g. .cross-pollination/  or  .swarm/<run-id>/
├── INDEX.md                     top synthesis: concept catalog + fit-matrix + tiers + run status
├── deferred.md                  deferred-items log — considered-and-rejected, Tier-3, "you're already ahead"
├── <unit-a>/
│   ├── profile.md               recon output (stack, conventions, test cmd, risk)
│   ├── blast-radius.md          implementer impact analysis
│   ├── plan.md                  what will change, scope held to
│   ├── diff.patch               (or recorded commit SHA)
│   ├── test-output.txt          implementer's run (verbatim + exit code)
│   └── receipt.md               VERIFIER's authoritative receipt (the record of truth)
├── <unit-b>/ ...
└── <unit-n>/ ...
```

`INDEX.md` is the front door — it carries the fit-matrix and per-unit status
(recon-done → implemented → verified → shipped). The `deferred.md` log is where
considered-and-rejected items live so they read as **weighed, not missed**.

## Why recon-first

Fanning out before you've profiled the units means every implementer
re-discovers the same context and you can't tell Tier-1 work from Tier-3 noise.
A cheap parallel recon wave + one synthesis pass turns the expensive fan-out
from "discover as you go" into "execute a scoped, tiered plan" — and gives the
user one clean decision point instead of N mid-flight surprises.
