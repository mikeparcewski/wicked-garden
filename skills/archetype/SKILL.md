---
name: wicked-garden-archetype
context: fork
user-invocable: true
description: |
  v11 work-shape archetype runner. When a prompt has been routed to one
  of the archetypes (triage, explore, specify, decide, ship, review,
  incident, build, migrate, modernize), this skill is the entry point. It
  picks the right per-archetype playbook from refs/ and executes the phase
  shape declared in `.claude-plugin/archetypes.json`.

  Use when: a `<wg archetype="X">` or `<wg archetypes>` system-reminder
  tag appears, an explicit "let's run the X archetype" request, or a
  direct per-archetype ask — "triage this prompt", "review this PR /
  artifact", "build this feature", "decide between these options",
  "explore this problem", "handle this incident", "run this migration",
  "modernize / port this legacy app", "ship this release", "write
  acceptance criteria" (invoke with archetype=<name> plus the user's
  args — see the Direct invocation table).
allowed-tools: ["*"]
---

# wicked-garden-archetype

v11 entry point for **work-shape archetypes**. Each archetype is a complete
unit with its own phase shape, produces, HITL discipline, and cost band.
There is no universal pipeline.

## When to use this skill

Invoke when:
- A `<wg archetype="X">` or `<wg archetypes>` system-reminder tag appears
  (emitted by the v11 prompt hook).
- The user explicitly asks to "run the {archetype} archetype" or "do this
  as a {archetype}" workflow.
- You're routing from `triage` to a real archetype after classifying the
  work.

Do **not** use this skill for:
- Continuation tokens ("yes", "ok", "do it"). Those carry no new shape;
  keep going on the current archetype.
- Simple-edit work (typos, single-line fixes, cosmetic changes). The v11
  hook already suppresses archetype tags on `simple-edit` intent.

## The archetypes

| Archetype | Phases                                                    | Produces                        | HITL                  |
|-----------|-----------------------------------------------------------|---------------------------------|-----------------------|
| triage    | classify                                                  | routing decision                | none                  |
| explore   | frame → diverge → converge                                | option set / hypothesis         | continuous            |
| specify   | elicit → structure → validate                             | SMART acceptance criteria       | discrete:validate     |
| decide    | brief → options → score → record                          | ADR / decision artifact         | discrete:select       |
| ship      | canary → ramp → full → soak                               | rollout verdict / SLO snapshot  | discrete:ramp         |
| review    | scope → assess → findings → remediate-or-accept           | verdict / remediation list      | hard:final-verdict    |
| incident  | triage → investigate → mitigate → resolve → followup      | mitigation / RCA / followup     | hard:mitigate         |
| build     | plan → implement → test → review                          | shipped code / test report      | discrete:review       |
| migrate   | plan → expand → backfill → cutover → contract             | shape change / rollback proof   | hard:cutover          |
| modernize | discover → extract → blueprint → transform → parity → cutover | modernization blueprint / parity proof | hard:cutover  |

## Direct invocation

This skill is also the user-facing entry point for each archetype
(replacing the former `/wicked-garden:archetype:{name}` slash commands).
Invoke it with `archetype=<name>` plus the user's arguments; the skill
loads `refs/{name}.md` and runs that playbook.

| archetype | argument hint | description |
|-----------|---------------|-------------|
| triage    | `[prompt]` | Classify a prompt into a work-shape archetype and route to its playbook. When the prompt is empty, run the detector against the conversation context. |
| explore   | `[problem statement]` | Explore an open problem space — diverge then converge. Produces an option set or hypothesis, NOT a decision. |
| specify   | `[ask]` | Turn an ask into SMART acceptance criteria. |
| decide    | `[decision context]` | Pick between options with an ADR-shaped decision artifact. |
| ship      | `[release / change ref]` | Roll out an already-built change with widening blast radius. |
| review    | `[artifact / PR / commit]` | Independent assessment with hard verdict (APPROVE/CONDITIONAL/REJECT) — the only review producing a binding verdict (scope notes in `refs/review.md`). |
| incident  | `[INC-id or symptom]` | Live-fire production incident response — mitigate first, RCA second. |
| build     | `[work description]` | Implement and ship a feature or fix — test rigor scales with signals. |
| migrate   | `[migration description]` | Schema/API/data shape change with expand-contract pattern. |
| modernize | `[modernization target, e.g. "port this AngularJS app to Angular"]` | Port a legacy codebase to a new stack — legacy→new-stack porting, NOT in-place shape change (that is `migrate`). |

## Procedure

1. **Identify the archetype.** Read the `<wg archetype>` tag in the system
   reminder OR ask the user which archetype they want when ambiguous.
2. **Load the playbook.** Read `refs/{archetype}.md` for the phase-by-phase
   playbook, the produces contract, and the HITL discipline.
3. **Execute the phases.** Run each phase in order. At each phase boundary
   ask: "do I have what this phase produces?" Don't move on until yes.
4. **Honor HITL.** When the playbook marks a gate as `hard:*`, **stop and
   ask the user** before proceeding. `discrete:*` gates may auto-pass when
   the produces contract is met. `none` and `continuous` carry no gate.
5. **Multi-archetype prompts.** When the hook emitted `<wg archetypes>`
   with two co-firing matches (e.g. `build + migrate` for a schema-change
   feature), run them in dependency order: `migrate` shape work first, then
   `build` integration work. The dependency graph lives in each archetype's
   `next_archetypes` field in the catalog.

## Catalog source of truth

`.claude-plugin/archetypes.json` is canonical. The detector lives at
`scripts/crew/archetypes_v11.py`. The CLI shim:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/archetypes_v11.py" \
  detect --prompt "<text>" --signals '{"production_impact": true}' --steering
```

## Refs

- `refs/triage.md` — entry classification
- `refs/explore.md` — diverge/converge for open problems
- `refs/specify.md` — elicit + structure + validate ACs
- `refs/decide.md` — ADR-shaped option scoring
- `refs/ship.md` — canary/ramp rollout
- `refs/review.md` — independent assessment with verdict
- `refs/incident.md` — live-fire response
- `refs/build.md` — plan/implement/test/review (the common case)
- `refs/migrate.md` — expand/backfill/cutover/contract (in-place shape change)
- `refs/modernize.md` — discover/extract/blueprint/transform/parity/cutover (legacy→new-stack port)

## What v11 archetypes are NOT

- They are **not** the v6.3 target-kind archetypes (`code-repo`, `docs-only`,
  `config-infra`, etc.). Those classify *what is being changed*; v11
  classifies *what shape of work is happening*. Both stay; they answer
  different questions.
- They are **not** rigor tiers (`minimal | standard | full`). v11 obsoletes
  the rigor-tier dial: each archetype owns its own cost band and HITL.
- They are **not** phase slots in a universal pipeline. Each archetype's
  phases live only inside that archetype.
