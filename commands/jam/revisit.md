---
description: Revisit a past brainstorm decision and record its outcome
argument-hint: "<topic or decision keyword>"
---

# /wicked-garden:jam:revisit

Revisit a past brainstorm decision to record whether it was validated, invalidated, or modified.

## Instructions

### 1. Recall Past Decision

Search for the decision via wicked-brain

```
Skill(
  skill="wicked-brain:memory",
  args="recall \"decisions tagged 'jam,decision' related to: {topic}\" --filter_type decision"
)
```

If no matching decision found, inform the user and suggest running `/wicked-garden:jam:brainstorm` first.

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

Store the outcome in wicked-brain:memory

```
wicked-brain:memory "Outcome: {topic}\nOriginal decision: {chosen}\nResult: {validated/invalidated/modified}\nReason: {user's explanation}\nLessons: {what we learned}"
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

Without wicked-brain: display a message that decision revisit requires wicked-brain for decision storage. Suggest the user install the wicked-brain plugin for full decision lifecycle tracking.
