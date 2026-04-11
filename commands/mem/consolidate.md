---
description: Manually trigger memory consolidation across tiers
argument-hint: ""
---

# /wicked-garden:mem:consolidate

Run memory consolidation — archive noise, promote patterns, merge duplicates. Delegates to wicked-brain's consolidate agent.

## Execution

Invoke the brain consolidate agent:

```
Skill(skill="wicked-brain-agent", args="dispatch consolidate")
```

This runs a 4-pass pipeline:
1. **Archive**: TTL-expired chunks, noise, low-value items
2. **Promote**: Recurring patterns from episodic → semantic tier
3. **Merge**: Near-duplicate memories into single entries
4. **Synonym-learn**: Extract new synonyms from merged content

## When to Use

- After long sessions with many working memories
- Periodically to promote recurring patterns
- Before important sessions where you want consolidated knowledge
- Note: Working memory consolidation runs automatically on session end
