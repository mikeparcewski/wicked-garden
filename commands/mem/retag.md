---
description: Backfill search tags on existing memories for better keyword recall
argument-hint: "[--dry-run] [--limit N]"
---

# /wicked-garden:mem:retag

Backfill search tags on memories that have fewer than 3 tags. Improves keyword recall by generating synonyms, abbreviations, and related concepts for each memory.

## Arguments

Parse the arguments from: $ARGUMENTS

- `--dry-run`: Preview tag suggestions without updating memories
- `--limit N`: Maximum number of memories to process (default: 50)

## Execution

### Step 1: List under-tagged memories

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/mem/memory.py" recall --limit 100
```

### Step 2: Filter and process

From the results, identify memories with fewer than 3 tags. For each one:

1. Read the memory content using:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/mem/memory.py" get --id MEMORY_ID
```

2. Generate 3-5 search tags based on the content. Follow the same tag generation rules as `mem:store`:
   - **Synonyms**: auth/authentication, DB/database, API/endpoint
   - **Abbreviations**: JWT, REST, GraphQL, CI/CD, K8s/Kubernetes
   - **Related concepts**: "jwt" → tokens, session, security
   - **Domain terms**: specific technology/pattern names

3. Merge existing tags with newly generated tags. Deduplicate.

4. If `--dry-run`, display the proposed tags but do NOT update. Otherwise, update the memory:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/mem/memory.py" update --id MEMORY_ID --tags "TAG1,TAG2,TAG3,TAG4,TAG5"
```

### Step 3: Summary

Display a summary table:
- Total memories scanned
- Memories with fewer than 3 tags (processed)
- Memories skipped (already have 3+ tags)
- Tags added (if not dry-run)

## Output

For each processed memory, show:
- Memory ID and title
- Existing tags
- New tags (added)
- Final merged tag list

End with:
- Count of memories updated (or "would update" in dry-run mode)
- Count of memories skipped
