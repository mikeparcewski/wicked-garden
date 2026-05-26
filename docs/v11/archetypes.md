# v11 — Work-shape archetypes

This is the design note for the v11 reframe. It explains **why** the
universal pipeline went away and what replaced it. For **how** to use
v11 day-to-day, see the README and `.claude/CLAUDE.md`.

## The problem v11 solves

Through v6–v10, wicked-garden organized work around a fixed pipeline:

```
clarify → design → test-strategy → challenge → build → test → review → operate
```

The shape of work was modulated by a **rigor tier dial** (`minimal | standard | full`).

This worked well for medium-complexity feature work. It worked poorly
for everything else:

- **A typo fix** went through clarify (write `objective.md`), design
  (write `architecture.md`), build, test, review — even at `minimal`
  rigor.
- **A schema migration** had to absorb its expand/backfill/cutover/
  contract phases into the universal pipeline's `build` phase, where
  no hooks understood them as such.
- **A spec elicitation** had no place — `clarify` was a phase of
  something else, not its own work shape.
- **A production incident** had to go through `clarify` before
  mitigating, because `clarify` was always first.
- **A design decision** (ADR) had no native shape — it got bundled
  into `design`, where it shared phase artifacts with implementation
  design.
- **A code review** of someone else's work was supposed to be
  triggered by gate transitions, not as a primary work shape.

The rigor dial didn't fix the shape problem; it only adjusted gate
strictness within the same shape. Setup all looked the same regardless
of what kind of work was happening.

## The dogfood that surfaced the structural issue

Across a single session in May 2026, seven dogfooding bugs were filed
(#846 through #852) and fixed:

1. Hardcoded `architecture.md` deliverable in design phase (#849)
2. Missing `recorded_at` field in qe-orchestrator's gate-result example (#850)
3. Missing `reeval-log.jsonl` auto-generation (#851)
4. `crew:gate` enum vs just-finish gate names diverging (#852)
5. `phase_manager` returning empty `phase_plan` even after the
   facilitator wrote `process-plan.json` (#846)
6. CONDITIONAL findings accumulating without resolution (#848)
7. HITL clarify gate missing scope-ambiguity (#847)

Each fix was correct in isolation. Together they pointed at the
underlying issue: every one of these symptoms came from forcing
heterogeneous work into the same pipeline. The hardcoded deliverable
filename only made sense for one work shape; the gate enum mismatch
came from the just-finish skill needing more granular gates than the
3-name pipeline supplied; the CONDITIONAL findings had no resolution
mechanism because the pipeline didn't know what kind of resolution
the work shape demanded.

The dogfood findings were patches on a foundation that was wrong-shaped.

## The reframe

Instead of one pipeline + a rigor dial, v11 has **9 archetypes**, each
with its own:

- **Phase shape** — the actual phase order for that kind of work.
- **Produces contract** — what the archetype outputs.
- **HITL discipline** — when the human is in the loop, and how hard.
- **Cost band** — rough effort expectation.
- **Maturity** — how confident we are in the playbook (research / piloted / production).

The archetypes:

| Archetype | Phases                                                  | Produces                       | HITL                  |
|-----------|---------------------------------------------------------|--------------------------------|-----------------------|
| triage    | classify                                                | routing decision               | none                  |
| explore   | frame → diverge → converge                              | option set / hypothesis        | continuous            |
| specify   | elicit → structure → validate                           | SMART acceptance criteria      | discrete:validate     |
| decide    | brief → options → score → record                        | ADR / decision artifact        | discrete:select       |
| ship      | canary → ramp → full → soak                             | rollout verdict / SLO snapshot | discrete:ramp         |
| review    | scope → assess → findings → remediate-or-accept         | verdict / remediation list     | hard:final-verdict    |
| incident  | triage → investigate → mitigate → resolve → followup    | mitigation / RCA / followup    | hard:mitigate         |
| build     | plan → implement → test → review                        | shipped code / test report     | discrete:review       |
| migrate   | plan → expand → backfill → cutover → contract           | shape change / rollback proof  | hard:cutover          |

Each archetype is self-contained. Phase names are NOT shared across
archetypes — `plan` in `build` is not `plan` in `migrate`. We
deliberately do not factor "common phases" because that's how the v6
universal pipeline emerged.

## Multi-archetype is normal

A single prompt routes to a SET of archetypes, not one:

- "implement schema change to add tenant_id with backfill"
  → `build + migrate`
- "kick off the canary rollout for the new pricing logic"
  → `ship`
- "review the auth middleware change before we deploy it"
  → `review` (and `ship` after, when the verdict is APPROVE)

Run them in dependency order. The catalog declares `next_archetypes`
per archetype to encode the natural sequence (e.g. `migrate` →
`ship`).

## What replaces gate-policy.json

Each archetype owns its own HITL discipline:

- `none` — no human checkpoint. Fires and is done.
- `continuous` — human is a participant throughout (e.g. brainstorm).
- `discrete:<gate>` — hard stop at the named gate; auto-pass when the
  produces contract is met.
- `hard:<gate>` — like discrete, but the gate cannot be auto-approved
  or bypassed without an explicit override audit log.

There is no global `gate-policy.json`. There is no universal banned-
reviewer list. There is no rigor-tier × gate matrix. Each archetype's
playbook is the policy.

## What "produces contract met" means now

The gating archetypes (`build`, `specify`, `decide`, `ship`, `review`,
`incident`, `migrate`) no longer self-assert "done". A produces gate is
not the agent declaring its own contract satisfied — it is the contract
**re-derived**. The gate runs `scripts/qe/vault_gate.py`, which calls
`wicked-vault cross-check`: it re-hashes the recorded evidence and
**re-runs its verifier** rather than trusting a cached status. A
claimed-but-false "tests pass" is rejected at the gate; a missing vault
**fails closed** — there is no vacuous pass. "Met" means re-derived,
not asserted.

The `hard:*` gates (`review`/final-verdict, `incident`/mitigate,
`migrate`/cutover) additionally require an **independent judgment** —
the evaluator is not the agent that did the work, recorded as a
tamper-evident attestation (`--with-attestations`). Self-graded "done"
cannot clear a hard gate.

This makes **wicked-vault** a required peer alongside wicked-bus,
wicked-brain, and wicked-testing — on npm, `>= 0.3`.

## What replaces propose-process

Nothing, structurally. The `triage` archetype handles classification.
When a prompt is genuinely ambiguous, `explore` is the fallback —
diverge / converge to surface the option space, then route from there.

The 9-factor scoring rubric was useful but oversold its value: it
correctly identified signals, but the only thing it could do with
those signals was pick a tier of the universal pipeline. With work
shapes per archetype, signal classification is simpler — phrase
match + boolean signals → archetype set, with confidence scores.

## What stays the same

- **`Task()` + `TaskCreate`** are still the dispatch primitives.
  v11 doesn't reimplement them.
- **Domain skills + agents** (engineering, platform, data, product,
  jam, search, agentic, persona, delivery) are unchanged. Archetypes
  invoke them as needed.
- **Hooks** still classify intent, track tool use, and run lifecycle
  scripts.
- **wicked-brain** is still the memory layer. **wicked-bus** is still
  the audit substrate.
- **Slim Body Contract** still applies — command/skill bodies stay
  small.
- **Steering, not blocking** is the v10 principle that v11 inherits
  and applies more rigorously.

## What's deleted

See `CHANGELOG.md` v11.0.0 for the comprehensive list. Headlines:

- The `crew/*` pipeline command + agent + skill family (except
  general-purpose `implementer`/`researcher`/`reviewer` agents and
  `archive` command).
- `gate-policy.json`, `phases.json`, `autonomy-policy.json`,
  `finding-classification.json`.
- ~50 legacy scripts in `scripts/crew/` (gate-result schema, dispatch-
  log HMAC, conditions-manifest, content-sanitizer, consensus-gate,
  reconcile, validate-plan, etc.).
- All v6/v7/v8/v9/v10 specific docs (`MIGRATION-v7.md`, `crew-workflow.md`,
  `cross-phase-intelligence.md`, all of `docs/v9/`, etc.).

## How to extend

Adding a 10th archetype:

1. Add an entry to `.claude-plugin/archetypes.json`. Declare phases,
   produces, HITL, signals, etc.
2. Write `skills/archetype/refs/{name}.md` — the playbook for the
   archetype, ~70-100 lines, following the template of the existing 9.
3. Add `commands/archetype/{name}.md` — a 12-line slash command that
   dispatches the archetype skill.
4. Add detection signals to the catalog. Test with
   `scripts/crew/archetypes_v11.py detect --prompt "..."`.
5. Update the README + this design note tables.

That's it. No phase machinery to extend. No gate matrix to update.

## What we got wrong, and what we'd watch for

- **Phrase calibration is hard.** A bad phrase list either over-fires
  (everything routes to `build`) or under-fires (everything routes to
  `triage`). The current calibration (single-phrase match → 0.55 score
  trips MEDIUM threshold) is a starting point. Watch for archetypes
  that never fire vs always fire on small prompts.
- **Multi-archetype dependency order is implicit.** The catalog
  declares `next_archetypes` but doesn't strictly enforce sequencing.
  If two archetypes co-fire and the agent runs them out of order,
  v11 doesn't catch it. We may need an explicit "must come after"
  field if this surfaces as a real issue.
- **HITL `hard:*` enforcement is now code, not just doctrine.**
  `scripts/crew/phase_manager.py` (`_HARD_GATE_PHASES`) refuses to advance
  past a hard gate at runtime, and the produces-gate re-derives evidence
  through wicked-vault (fail-closed) rather than trusting playbook prose
  (see "What 'produces contract met' means now" above). *Discrete* gates
  remain doctrine-driven (auto-pass when the contract is met). Watch that
  the runtime hard-gate map and each archetype's declared HITL stay in
  sync — `_HARD_GATE_PHASES` currently also flags `specify.validate` and
  `decide.record`, which the table lists as `discrete:*`.
- **The `triage` archetype is the safety net for anything else.**
  When the detector returns only `triage`, it means the prompt
  didn't match anything cleanly. The agent should ASK, not GUESS.
  This is the most important behavior to monitor in early v11.
