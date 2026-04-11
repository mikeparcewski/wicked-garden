---
description: Backfill search tags on existing memories for better keyword recall
argument-hint: "[--dry-run] [--limit N]"
---

# /wicked-garden:mem:retag

Backfill search tags on memories with fewer than 5 tags using synonym expansion. Delegates to wicked-brain:retag.

## Arguments

Parse the arguments from: $ARGUMENTS

- `--dry-run`: Preview tag suggestions without updating
- `--limit N`: Maximum memories to process (default: 50)

## Execution

Invoke the brain retag skill:

```
Skill(skill="wicked-brain-retag", args="{--dry-run} {--limit N}")
```

Brain handles: finding under-tagged memories, synonym expansion via learned synonym map, re-indexing after tag updates.
