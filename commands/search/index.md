---
description: Build unified index for code and documents in a directory
argument-hint: "<path>"
---

# /wicked-garden:search:index

Build a searchable index of code symbols and document content. Indexing is now handled by the brain knowledge layer.

## Arguments

- `path` (required): Directory to index

## Instructions

1. **Delegate to brain ingest** — all indexing now goes through `wicked-brain:ingest`:

   Tell the user:
   > Indexing is now handled by the brain. Running `wicked-brain:ingest` to index your codebase.

   Then invoke `/wicked-brain:ingest` with the provided path.

2. **Verify the index** by checking brain stats:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"stats","params":{}}'
   ```

3. Report the results showing chunk and tag counts from the brain stats response.

## Examples

```bash
# Basic indexing
/wicked-garden:search:index /path/to/project

# This is equivalent to:
/wicked-brain:ingest /path/to/project
```

## Notes

- Re-running only updates changed files (incremental)
- Check `/wicked-garden:search:stats` to verify indexing results
