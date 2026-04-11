---
description: Archive or delete a memory
argument-hint: "<memory_id> [--hard]"
---

# /wicked-garden:mem:forget

Archive a memory (recoverable) or hard-delete it. Delegates to wicked-brain:forget.

## Arguments

Parse the arguments from: $ARGUMENTS

- `memory_id` (required): The memory ID (e.g. `mem-abc123` or full path `memories/episodic/mem-abc123`)
- `--hard`: Permanently delete instead of archiving

## Execution

Invoke the brain forget skill:

```
Skill(skill="wicked-brain-forget", args="{memory_id}")
```

By default brain archives (renames to `.archived-{timestamp}` — recoverable). Pass `--hard` for permanent deletion.

## Output

Confirm with:
- Memory ID and title
- Action taken (archived / deleted)
