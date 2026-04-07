---
description: Show index statistics
argument-hint: "[--project <name>]"
---

# /wicked-garden:search:stats

Show statistics about the indexed search database.

## Arguments

- `--project` (optional): Filter to a specific project

## Instructions

1. **Get brain stats** (unified knowledge layer):
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"stats","params":{}}'
   ```

2. **If brain is unavailable**, report that no index is available and suggest:
   > Run `wicked-brain:ingest` to build the search index.

3. Report:
   - Brain status (online/offline)
   - Total chunks, wiki articles, memories
   - Database size, last indexed timestamp

## Example

```
/wicked-garden:search:stats
/wicked-garden:search:stats --project my-app
```
