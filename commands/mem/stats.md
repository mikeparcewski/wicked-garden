---
description: Show memory statistics
argument-hint: ""
---

# /wicked-garden:mem:stats

Show memory statistics from the brain API and local chunk files.

## Execution

### Step 1: Get brain-level stats

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"stats","params":{}}'
```

Display the brain stats (total chunks, index size, etc.).

### Step 2: Count memory chunks by tier

Use Glob to count memory chunk files in each tier:

- `$HOME/.wicked-brain/memories/working/mem-*.md` -> working count
- `$HOME/.wicked-brain/memories/episodic/mem-*.md` -> episodic count
- `$HOME/.wicked-brain/memories/semantic/mem-*.md` -> semantic count

### Step 3: Sample frontmatter for type breakdown

Read a sample of chunk files (up to 50) across all tiers to extract `memory_type` from frontmatter. Build counts by type (episodic, decision, procedural, preference).

### Step 4: Handle brain unavailability

If the brain API is unreachable, still report file-based stats from Step 2-3 and note that brain stats are unavailable.

## Output

Display:
- **Brain stats**: Total indexed chunks, memory-specific count
- **By tier**: working / episodic / semantic counts
- **By type**: episodic / decision / procedural / preference counts
- **Total memories**: Sum of all chunk files
