# Synthesis Patterns

How to transform raw persona discussions into actionable outcomes.

## Synthesis Structure

Every synthesis follows this skeleton:

```markdown
## Brainstorm: {Topic}

### Key Insights
1. **{Insight}** — {confidence: HIGH/MEDIUM/LOW}
   {1-2 sentences explaining the non-obvious finding}
2. ...
3. ...

### Action Items
1. {Specific, actionable next step} — {who/when if known}
2. ...

### Open Questions
- {What remains unresolved — honest about gaps}

### Tensions
- **{Position A}** vs **{Position B}** — {why this tension matters}
```

## Quality Checklist

A good synthesis has:
- [ ] 3-5 insights (not 10 — information overload kills action)
- [ ] Confidence levels on every insight (HIGH/MEDIUM/LOW)
- [ ] At least 1 non-obvious finding (something no single persona said alone)
- [ ] Prioritized action items (not just a flat list)
- [ ] Honest open questions (admitting what's unknown)
- [ ] Named tensions (disagreements that matter, not smoothed over)

A bad synthesis:
- Just lists what each persona said (that's a transcript, not synthesis)
- Has 8+ insights with no prioritization
- Everything is "MEDIUM" confidence (lazy scoring)
- No action items (interesting but not useful)
- No tensions acknowledged (false consensus)

## Synthesis Techniques

### The Non-Obvious Connection

Look for ideas that emerge from the intersection of two personas' viewpoints — something neither would have said alone.

**Example**: The engineer says "we need a cache layer" and the user researcher says "users hate stale data." The synthesis insight is: "Cache with aggressive invalidation — latency matters but correctness matters more." Neither persona stated this directly.

### The Surprising Agreement

When personas who should disagree actually agree on something, that's a high-confidence signal.

**Example**: The skeptic and the visionary both say "this needs to be simple." That's a stronger signal than either alone.

### The Productive Tension

Some disagreements shouldn't be resolved — they should be named as trade-offs for the decision-maker.

**Example**: "Speed of delivery vs. test coverage. The team lead wants to ship Friday; QE wants integration tests. This is a risk decision, not a right answer."

### The Missing Voice

If no persona raised a concern that seems obvious, note it. The panel may have been wrong for this problem.

**Example**: "No persona discussed data privacy implications. This gap should be addressed before implementation."

## Decision Record Format

When a brainstorm produces a clear decision, store it via wicked-brain:memory:

```
Decision: {what was decided}
Chosen: {the selected option}
Rationale: {why — rooted in evidence from the session}
Alternatives considered: {what was rejected and why}
Confidence: {HIGH/MEDIUM/LOW}
Evidence used: {what data/experience informed the decision}
Personas: {who participated}
Tags: {topic tags for future recall}
```

This format enables future recall: "What did we decide about X?" returns the full decision context.

## Examples of Good Synthesis

### Architecture Decision
> **Key Insight 1**: Event sourcing is the right pattern for audit requirements, but the team has no experience with it — HIGH confidence on the pattern choice, LOW confidence on execution timeline.
>
> **Action**: Spike on event sourcing with a bounded context (2 days) before committing to full adoption.
>
> **Tension**: Architect wants event sourcing everywhere; pragmatist wants it only for the audit domain. Resolve after the spike.

### Product Scope
> **Key Insight 1**: The top 3 requested features serve power users, but 80% of new signups churn before reaching power-user status — HIGH confidence.
>
> **Action**: Prioritize onboarding improvements over feature additions for Q2.
>
> **Open Question**: What does the conversion funnel look like between signup and first value moment? No persona had this data.

### Process Change
> **Key Insight 1**: The team unanimously agrees code review is too slow, but disagrees on the fix. The bottleneck is not the review process — it's that PRs are too large — HIGH confidence.
>
> **Action**: Adopt a "300 lines max" PR policy for 2 sprints as an experiment. Measure review turnaround.
>
> **Tension**: ICs want autonomy on PR size; lead wants consistency. The experiment resolves this empirically.
