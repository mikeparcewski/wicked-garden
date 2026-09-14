---
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---
# jam revisit — Decision Outcome Workflow

Revisit a past brainstorm decision to record whether it was validated,
invalidated, or modified. Light workflow — run it inline, no hand-off needed.

## Instructions

### 1. Recall Past Decision

**Hand-off** — open the `wicked-garden-mem` skill and run its `recall` action with `jam decision related to: {topic}` as the query; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

If no matching decision found, inform the user and suggest running the jam
skill's `brainstorm` sub-action first.

### 2. Display Decision Summary

Show the user what was decided:

```markdown
## Past Decision: {topic}

**Decided**: {chosen option}
**When**: {date}
**Confidence**: {HIGH/MEDIUM/LOW}
**Rationale**: {key reasoning}
**Alternatives considered**: {other options}
**Personas involved**: {list}
```

### 3. Ask for Outcome

Ask the user:

```markdown
How did this decision work out?

1. **Validated** — The decision was correct and worked well
2. **Invalidated** — The decision was wrong, we had to change course
3. **Modified** — The decision was partially right but needed adjustment
```

### 4. Record Outcome

**Hand-off** — open the `wicked-garden-mem` skill and run its `store` action with the record `Outcome: {topic} / Original decision: {chosen} / Result: {validated/invalidated/modified} / Reason: {user's explanation} / Lessons: {what we learned}` (kind=fact, about=[jam, outcome, {topic-keywords}]); on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

### 5. Report

```markdown
## Outcome Recorded

**Decision**: {topic}
**Result**: {validated/invalidated/modified}
**Lesson**: {what was learned}

This outcome will be surfaced in future brainstorms on similar topics.
```

## Graceful Degradation

Without a reachable memory layer (wicked-estate): display a message that
decision revisit requires the memory layer for decision storage. Suggest
installing wicked-estate for full decision lifecycle tracking.
