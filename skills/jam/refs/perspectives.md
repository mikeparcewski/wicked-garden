# jam:perspectives — Raw Multi-Perspective Rubric

Full rubric sourced from `commands/jam/perspectives.md`.
Output is raw viewpoints only — no synthesis, no recommendation.

## Purpose

Get 4–6 independent positions on a decision or question for self-directed thinking
and discussion prep. Use when you want the positions without Claude collapsing them
into a recommendation.

## Step 1: Pick 4–6 Personas

Same archetype pool as quick (`jam:quick` rubric), but use 4–6 for richer coverage.
Prefer personas that will genuinely disagree.

## Step 2: Single Round — Perspectives Only

Each persona states:

```
**[Persona Name]** ({archetype})
1. **Position**: {their stance in 1–2 sentences}
2. **Key concern**: {the main risk or trade-off they see}
3. **What would change their mind**: {specific evidence or condition}
```

No back-and-forth. No responses between personas. One pass only.

## Step 3: Present Raw (No Synthesis)

Do NOT synthesize. Do NOT recommend. Present the personas' positions in order,
then stop. The user drives the analysis.

```markdown
## Perspectives: {Topic}

**[Persona 1]** ({archetype})
- Position: …
- Key concern: …
- What would change my mind: …

**[Persona 2]** ({archetype})
…
```

Do NOT store a decision record. Keep it fast (~60 seconds).
