# explore — diverge then converge on open problems

When the problem space is genuinely open and a single answer would be
premature. Produces an option set or hypothesis, **not a decision** — that's
the `decide` archetype's job.

## Phase shape

| Phase    | Goal                                                     |
|----------|----------------------------------------------------------|
| frame    | Name the problem in one sentence. Surface assumptions.   |
| diverge  | Generate 4–8 distinct options. Aim for variety, not quality. |
| converge | Cluster, score qualitatively, and pick a top-3 to take forward. |

## Produces

- **Option set**: 3–8 named alternatives with one-line rationales.
- **Hypothesis** (when the prompt is research-shaped): testable statement
  with a falsification condition.

## HITL

`continuous` — the user is a participant. Don't run explore as a closed
loop; check in after frame, after diverge, before convergence.

## How to run

### frame

1. Restate the problem in one sentence in your own words. Confirm with the user.
2. List 2–4 assumptions you're making. Get the user to mark them
   "true / unknown / false".
3. If a critical assumption is "unknown", branch to `specify` to elicit
   facts before continuing.

### diverge

1. Generate 4–8 options. **Variety beats quality.** Include at least one
   "lazy" option (do nothing) and one "expensive" option (the over-built
   answer).
2. Use `wicked-garden:jam:quick` or `wicked-garden:jam:brainstorm` for
   structured ideation when the surface is unfamiliar.
3. Don't score yet. Just name them.

### converge

1. Cluster the options into 2–3 thematic groups.
2. Pick the top-3 to take forward. Each one needs:
   - A one-line description.
   - A risk note.
   - A reversibility note.
3. Hand off to `decide` if the user wants a verdict, or to `specify` /
   `build` if the path forward is now clear.

## When to stop

Explore is done when the user has a top-3 option set OR a falsifiable
hypothesis they can take forward. Don't keep diverging.

## Anti-patterns

- **Don't pick a winner inside explore.** That's the decide archetype.
- **Don't skip frame.** A bad problem statement makes diverge produce
  noise.
- **Don't rank prematurely.** Convergence is qualitative clustering,
  not quantitative scoring.
