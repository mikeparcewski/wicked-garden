# decide — pick between options with an ADR

When 2+ paths are viable AND the choice is load-bearing (changing it later
is expensive). Produces an ADR-shaped artifact that records the chosen
path and the reasons.

## Phase shape

| Phase   | Goal                                                       |
|---------|------------------------------------------------------------|
| brief   | One-paragraph framing: the problem, the stakes, the constraints. |
| options | 2–4 named alternatives, each with a one-paragraph description. |
| score   | Qualitative scoring on the dimensions that matter for this decision. |
| record  | Write the ADR. Pick a path. Note the trade-offs you accepted. |

## Produces

- An **ADR** (Architecture Decision Record) at `docs/decisions/{N}-{slug}.md`
  or `docs/adr/{N}-{slug}.md`, following whatever ADR convention the repo
  uses. New repos: use the standard ADR template.
- A **decision artifact**: which option was picked, and the explicit
  trade-offs accepted by picking it.

## HITL

`discrete:select-gate` — the user (or a council) picks. Don't auto-select.

## How to run

### brief

1. Restate the problem in one paragraph. What changes if we pick wrong?
2. Name the constraints: budget, time, team capability, blast radius,
   reversibility.
3. If reversibility is HIGH and blast radius is LOW, **stop and ask**
   whether this even needs an ADR. Cheap-to-reverse decisions don't
   benefit from this archetype's overhead.

### options

1. Generate 2–4 distinct options. Don't pad — false alternatives weaken
   the decision.
2. For each option:
   - One-paragraph description.
   - Cost: time + complexity + ongoing maintenance.
   - Reversibility: how hard is undoing this in 6 months?
   - Failure mode: what's the worst plausible outcome?

### score

1. Pick 3–5 dimensions that actually matter for this decision (not a
   generic checklist). Examples: latency, operational complexity,
   contract stability, team familiarity, vendor lock-in.
2. Score each option qualitatively (LOW/MEDIUM/HIGH) on each dimension.
3. The score is a *thinking aid*, not a winner-picker. The user picks.

### record

1. Use `wicked-garden:jam:council` for a multi-model second opinion when
   the stakes warrant it.
2. Write the ADR. Sections: context, options considered, decision,
   consequences, trade-offs accepted.
3. Commit the ADR with the implementing change, not separately. The ADR
   is the explanation for the diff.

## When to stop

Decide is done when an ADR is committed and the chosen option is named.
Hand off to `build` (implement the chosen path), `migrate` (when the
choice is a shape change), or `ship` (when the choice is a rollout
strategy).

## Anti-patterns

- **Don't run decide for cheap-reversible choices.** A feature flag that
  defaults to off does not need an ADR. The overhead exceeds the benefit.
- **Don't pad to 4 options.** Three honest options beats four with one
  filler.
- **Don't quantify when you don't have data.** Qualitative scoring is
  fine; spurious numbers are worse than honest LOW/MEDIUM/HIGH.
