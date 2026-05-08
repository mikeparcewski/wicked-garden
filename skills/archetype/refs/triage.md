# triage — classify and route

The entry archetype. Every prompt that doesn't already carry an archetype tag
starts here. Triage is not a workflow on its own — it's a routing decision.

## Phase shape

| Phase    | Goal                                          |
|----------|-----------------------------------------------|
| classify | Pick the right archetype (or set of archetypes) and hand off. |

## Produces

- A routing decision: which archetype(s) this prompt belongs in.

## HITL

`none` — fully automated. The detector runs, the directive emits, the
agent picks up the playbook from there.

## How to run

1. **Read the prompt.** What is the user actually asking for?
2. **Run the detector.** Call `scripts/crew/archetypes_v11.py detect` with
   the prompt and any known signals.
3. **Inspect the matches.**
   - Single high-confidence match (≥ 0.7): hand off to that archetype's
     playbook.
   - Multiple medium matches (0.5–0.7): pick the one with the strongest
     evidence; if you can't, ask the user which shape they want.
   - Only triage matched: ask a clarifying question naming what's
     missing — usually the work isn't ambiguous, the prompt is.

## When to stop in triage

Triage exits as soon as you've named the next archetype. Do **not**
do work inside triage — every minute spent here is a minute the
real work isn't moving.

## Examples

| Prompt                                            | Routes to            |
|---------------------------------------------------|----------------------|
| "implement caching for the dashboard"             | build                |
| "drop legacy_id column"                           | build + migrate      |
| "checkout is down — 5xx spiking"                  | incident             |
| "redis or memcached for sessions?"                | decide               |
| "review the new auth middleware"                  | review               |
| "what should we do about rate limiting?"          | explore              |
| "write acceptance criteria for the export"        | specify              |
| "kick off canary for the pricing change"          | ship                 |
| "fix typo in README"                              | (suppressed — simple-edit, no archetype) |

## Anti-patterns

- **Don't classify into a tier.** "standard rigor" is not an archetype.
  Triage picks a *shape*, not a depth dial.
- **Don't stack triage onto an active archetype.** If the user is already
  inside `build`, a follow-up "and also run the migration" doesn't restart
  triage — it adds `migrate` as a co-archetype.
- **Don't write code in triage.** If your hands are at the keyboard,
  you've already left triage.
