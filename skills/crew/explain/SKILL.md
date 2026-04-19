---
name: explain
description: |
  Translate jargon-heavy crew output into plain language. Input is typically a
  gate finding, reviewer brief, phase summary, or process plan containing
  specialist vocab (RED, BLOCK, convergence, blast radius, parallelization_check,
  CONDITIONAL, BLEND rule, etc.). Output is 2-4 sentences at a grade-8 reading
  level with no specialist vocab left behind.

  Use when: "explain this", "in plain English", "what does this mean",
  "translate for me", "simplify", "dumb this down", or any request to render
  crew jargon into language a non-practitioner can act on. Also used
  automatically by the orchestrator when `crew.output_style = paired` or
  `plain-only` — the skill produces the `**Plain:**` line.
---

# /wicked-garden:crew:explain

Convert crew output to plain language. Grade-8 reading level. No jargon.

## When to invoke

- A gate finding with terms like REJECT, CONDITIONAL, BLOCK, convergence
- A reviewer brief that references BLEND rule, parallelization_check,
  dispatch_log, conditions-manifest, etc.
- A process plan that uses rigor tiers, blast radius, reversibility scores
- Anyone asking "in plain English" or "what does this actually mean"

## Output rules

- **Length**: 2-4 sentences. Never more.
- **Reading level**: Grade 8. Short sentences. Plain verbs.
- **No specialist vocab**. Do not use any of:
  - REJECT, APPROVE, CONDITIONAL → say "blocked", "cleared", "needs fixes"
  - BLEND rule, min_score, per_reviewer_verdicts → say "the reviewers agreed"
  - convergence, Integrated, Wired → say "the code is hooked up" / "still missing"
  - blast radius → say "what else this change could break"
  - rigor tier, complexity score → say "how careful we're being"
  - dispatch, council, parallel → say "we asked more than one reviewer"
  - conditions-manifest, addendum, JSONL → say "the fix list" / "the log"
- **Tell them what to DO next**, not what the system computed.

## Output styles (orchestrator `crew.output_style`)

The skill supports three modes set by `crew.output_style` in project config:

| Mode | Behavior |
|------|----------|
| `paired` (default) | Keep the original jargon block, append `**Plain:**` line |
| `terse` | Jargon only — skill is not invoked |
| `plain-only` | Replace jargon entirely with the plain-language version |

When invoked by the orchestrator, it passes the current mode in the prompt.
When invoked directly by a user, default to `plain-only`.

## Process

1. Read the jargon-heavy input block.
2. Identify the decision or state (did something pass, fail, or need work?).
3. Identify the next action (what the user should do).
4. Write 2-4 sentences:
   - Sentence 1: what happened / what the state is
   - Sentence 2 (optional): why it matters in one human concern
   - Sentence 3-4: what to do next — concrete, actionable
5. Scan the draft for specialist vocab (see list above). Replace anything that
   survived with plain-English equivalents. Re-check grade level.
6. Emit the final block in the format dictated by `crew.output_style`.

## Example — paired mode

**Input (jargon):**

```
Gate: code-quality — verdict: CONDITIONAL (score 0.62, min 0.70)
  per_reviewer_verdicts:
    - senior-engineer: CONDITIONAL — "god function in handler.py:process()"
    - security-engineer: APPROVE
  conditions-manifest.json written with 1 condition.
```

**Output:**

```
Gate: code-quality — verdict: CONDITIONAL (score 0.62, min 0.70)
  per_reviewer_verdicts:
    - senior-engineer: CONDITIONAL — "god function in handler.py:process()"
    - security-engineer: APPROVE
  conditions-manifest.json written with 1 condition.

**Plain:** One reviewer flagged that `handler.py` has a giant function that
does too much. Security was fine. Split the function into smaller pieces,
then re-run the gate to clear the finding before moving to the next phase.
```

## Example — plain-only mode

**Input (jargon):** same as above.

**Output:**

```
One reviewer flagged that `handler.py` has a giant function that does too
much. Security was fine. Split the function into smaller pieces, then re-run
the gate to clear the finding before moving to the next phase.
```

## What NOT to do

- Don't editorialize ("this is concerning", "surprisingly"). Stick to facts.
- Don't add new recommendations the original output didn't contain.
- Don't drop to sub-grade-8 (child-like) — aim for clear adult language.
- Don't use more than 4 sentences. If the source has 10 findings, group them:
  "Three reviewers found issues in X, Y, and Z."

## Configuration

Project-level configuration lives in the orchestrator config under
`crew.output_style`:

```json
{
  "crew": {
    "output_style": "paired"
  }
}
```

Valid values: `terse` | `paired` | `plain-only`. Default: `paired`.
