---
description: Search across all code and documents
argument-hint: "<query>"
---

# /wicked-garden:search:search

Search across both code symbols and documents via the unified index.

## Arguments

- `query` (required): Search terms

## Instructions

1. **Search via brain** (unified knowledge layer):
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<query>","limit":10}}'
   ```
   If the response contains `"results"` with entries, report them grouped by type.

2. **If brain is unavailable** (connection refused or empty results):
   Fall back to native tools — use Grep and Glob to search the codebase directly.
   Suggest: `wicked-brain:ingest` to index the codebase for richer search.

3. Report results with:
   - Symbol name and type
   - File location
   - Score / relevance snippet

## Example

```
/wicked-garden:search:search "authentication"
/wicked-garden:search:search "error handling"
```
