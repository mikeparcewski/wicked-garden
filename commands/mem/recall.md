---
description: Recall memories matching a query
argument-hint: "[query] [--tags tag1,tag2] [--type episodic|decision|procedural|preference] [--tier working|episodic|semantic]"
---

# /wicked-garden:mem:recall

Recall memories matching search criteria. Delegates to wicked-brain:memory.

## Arguments

Parse the arguments from: $ARGUMENTS

- `query` (optional): Free-text search query
- `--type`: Filter by memory type (episodic, decision, procedural, preference)
- `--tier`: Filter by consolidation tier (working, episodic, semantic)
- `--tags`: Comma-separated tags to filter by
- `--limit`: Maximum results (default: 10)

## Execution

Invoke the brain memory skill:

```
Skill(skill="wicked-brain-memory", args="recall {query} --filter_type {type} --filter_tier {tier} --limit {limit}")
```

Pass through all arguments. Brain handles FTS search, tier weighting (semantic 1.3x, episodic 1.0x, working 0.8x), and synonym expansion.

## Output

For each memory, display:
- ID, type, tier
- Title
- Tags
- Content summary (first 100 chars)
- Age (from indexed_at)
