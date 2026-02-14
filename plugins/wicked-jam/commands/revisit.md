---
description: Revisit a past brainstorm decision and record its outcome
argument-hint: <topic or decision keyword>
---

# /wicked-jam:revisit

Revisit a past brainstorm decision to record whether it was validated, invalidated, or modified.

## Instructions

### 1. Recall Past Decision

Search for the decision in wicked-mem:

```
Task(subagent_type="wicked-mem:memory-recaller",
     prompt="Search for decisions tagged with 'jam,decision' related to: {topic}. Return the full decision record including rationale and alternatives.")
```

If no matching decision found, inform the user and suggest running `/wicked-jam:brainstorm` first.

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

Store the outcome in wicked-mem:

```
/wicked-mem:store "Outcome: {topic}\nOriginal decision: {chosen}\nResult: {validated/invalidated/modified}\nReason: {user's explanation}\nLessons: {what we learned}"
  --type decision
  --tags jam,outcome,{topic-keywords}
  --importance high
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

Without wicked-mem: Display a message that decision revisit requires wicked-mem for decision storage. Suggest the user install wicked-mem for full decision lifecycle tracking.
