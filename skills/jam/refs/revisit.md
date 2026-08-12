---
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---
# jam revisit — Decision Outcome Workflow

Revisit a past brainstorm decision to record whether it was validated,
invalidated, or modified. Light workflow — run it inline, no fork needed.

## Instructions

### 1. Recall Past Decision

Search for the decision via the wicked-garden-mem skill

```
Skill(
  skill="wicked-garden-mem",
  args="recall \"jam decision related to: {topic}\""
)
```

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

Store the outcome via the wicked-garden-mem skill

```
Skill(skill="wicked-garden-mem", args="store \"Outcome: {topic}\nOriginal decision: {chosen}\nResult: {validated/invalidated/modified}\nReason: {user's explanation}\nLessons: {what we learned}\" (kind=fact, about=[jam, outcome, {topic-keywords}])")
```

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
