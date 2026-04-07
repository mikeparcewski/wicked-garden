---
description: Search code symbols only (functions, classes, methods)
argument-hint: "<query>"
---

# /wicked-garden:search:code

Search code symbols only (functions, classes, methods) via the knowledge graph.

## Arguments

- `query` (required): Search terms

## Instructions

1. **Search via brain** (unified knowledge layer):
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<query>","limit":10}}'
   ```
   Filter results to code file types (.py, .js, .ts, .go, .java, .rb, .rs, .sh).

2. **If brain is unavailable** (connection refused or empty results):
   Fall back to native tools — use Grep to search for the symbol/pattern across code files.
   Suggest: `wicked-brain:ingest` to index the codebase for richer search.

3. Report matching symbols with file locations and types.

## Example

```
/wicked-garden:search:code "UserService"
/wicked-garden:search:code "authenticate"
```
