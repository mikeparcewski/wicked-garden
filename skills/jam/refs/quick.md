# jam:quick — Single-Pass Brainstorm Rubric

Full rubric sourced from `agents/jam/quick-facilitator.md`.
This is a forced-fast session: exactly 4 personas, exactly 1 round, then synthesize.
Do NOT run additional rounds regardless of complexity. Do NOT store anything.

## Constraints (hard)

- EXACTLY 1 round — never extend
- EXACTLY 4 personas — no more, no fewer
- NO transcript storage — ephemeral output
- NO bus events
- NO multi-AI step
- NO evidence gathering (no wicked-brain lookups)
- Synthesis: concise, target ≤ 200 words total

## Step 1: Pick 4 Personas

Select personas that cover the topic's key tensions. Draw from:

- Technical: Architect, Debugger, Optimizer
- User-Focused: Power User, Newcomer, Support Rep
- Business: Product Manager, Skeptic, Cost Optimizer
- Process: Maintainer, Tester, Release Manager

Cover at least 2 different archetype categories. Each persona must have a genuine concern, not a strawman.

## Step 2: Single Round

Each persona speaks in 2–4 sentences:

```
**[Persona Name]** ({archetype})
{Position on topic. Key concern or trade-off. One concrete suggestion.}
```

No back-and-forth. No responses between personas. One pass only.

## Step 3: Synthesis

Write exactly these three sections:

```markdown
## Quick Jam: {Topic}

### Key Insights
- **[Persona]**: {one-line takeaway}
- **[Persona]**: {one-line takeaway}
- **[Persona]**: {one-line takeaway}
- **[Persona]**: {one-line takeaway}

### Action Items
1. {Primary recommendation with rationale — fold the most important risk/tension in}
2. {Secondary option, caveat, or follow-up}

### Open Questions
- {One unresolved question worth tracking if this goes deeper}
```

## Rules

- No padding: if the answer is obvious after 2 personas, the remaining 2 still speak — but synthesis stays concise.
- No convergence check (that's brainstorm-facilitator only).
- Ephemeral by design. Callers wanting storage or multi-round depth → `jam:brainstorm`.
