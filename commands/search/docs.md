---
description: Search documents only (PDF, Office docs, markdown)
argument-hint: "<query>"
---

# /wicked-garden:search:docs

Search documents only (PDF, Office docs, markdown) via the unified index.

## Arguments

- `query` (required): Search terms

## Instructions

1. **Search via brain** (unified knowledge layer):
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<query>","limit":10}}'
   ```
   Filter results to document types (.md, .txt, .html, .csv, .json).

2. **If brain is unavailable** (connection refused or empty results):
   Fall back to native tools — use Grep with `--glob "*.md"` or `--glob "*.txt"` to search documents.
   Suggest: `wicked-brain:ingest` to index the codebase for richer search.

3. Report matching document sections with source file locations.

## Example

```
/wicked-garden:search:docs "security requirements"
/wicked-garden:search:docs "API design"
```
