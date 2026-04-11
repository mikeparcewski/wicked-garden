---
description: Interactive memory review - browse, understand, and manage stored memories
argument-hint: "[--type decision|episodic|procedural|preference] [--tier working|episodic|semantic] [--stale]"
---

# /wicked-garden:mem:review

Browse stored memories with filtering by type, tier, and recency. Delegates to wicked-brain:review.

## Arguments

Parse the arguments from: $ARGUMENTS

- `--type`: Filter by memory type (episodic, decision, procedural, preference)
- `--tier`: Filter by tier (working, episodic, semantic)
- `--stale`: Show only memories older than 30 days
- `--limit`: Maximum memories to display (default: 30)

## Execution

Invoke the brain review skill:

```
Skill(skill="wicked-brain-review", args="{--type} {--tier} {--limit}")
```

Brain handles: reading chunk files, parsing frontmatter, filtering, grouping by tier, age computation.

After displaying results, suggest:
- `/wicked-garden:mem:forget <id>` to archive stale items
- `/wicked-garden:mem:consolidate` to synthesize related memories
