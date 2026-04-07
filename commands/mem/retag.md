---
description: Backfill search tags on existing memories for better keyword recall
argument-hint: "[--dry-run] [--limit N]"
---

# /wicked-garden:mem:retag

Backfill search tags on memories that have fewer than 5 tags. Improves keyword recall by generating synonyms, abbreviations, and related concepts for each memory.

## Arguments

Parse the arguments from: $ARGUMENTS

- `--dry-run`: Preview tag suggestions without updating memories
- `--limit N`: Maximum number of memories to process (default: 50)

## Execution

### Step 1: Find under-tagged memories

Use Glob to find all memory chunk files across tiers:

- `$HOME/.wicked-brain/memories/working/mem-*.md`
- `$HOME/.wicked-brain/memories/episodic/mem-*.md`
- `$HOME/.wicked-brain/memories/semantic/mem-*.md`

### Step 2: Read and filter

Use the Read tool to read each chunk file. Parse the YAML frontmatter and identify memories with fewer than 5 tags.

Stop after finding `--limit` under-tagged memories.

### Step 3: Generate expanded tags

For each under-tagged memory, read its content and generate additional tags following these rules:
- **Synonyms**: auth/authentication, DB/database, API/endpoint
- **Abbreviations**: JWT, REST, GraphQL, CI/CD, K8s/Kubernetes
- **Related concepts**: "jwt" -> tokens, session, security
- **Domain terms**: specific technology/pattern names
- **Think**: "what would someone search for to find this memory?"

Target 5-8 total tags per memory.

### Step 4: Update chunk files

If NOT `--dry-run`, use the Edit tool to update the `tags:` field in each chunk file's YAML frontmatter. Replace the existing tags list with the expanded one.

Example edit — replace:
```yaml
tags:
  - auth
  - bug
```
with:
```yaml
tags:
  - auth
  - bug
  - authentication
  - security
  - tokens
  - session
```

After editing the chunk file, re-index with the brain API so search picks up new tags:

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"index","params":{"id":"memories/{tier}/mem-{uuid}","path":"memories/{tier}/mem-{uuid}","content":"{title + content + all tags joined}","brain_id":"wicked-brain"}}'
```

### Step 5: Summary

Display a summary table:
- Total memories scanned
- Memories with fewer than 5 tags (processed)
- Memories skipped (already have 5+ tags)
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
