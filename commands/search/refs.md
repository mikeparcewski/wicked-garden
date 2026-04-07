---
description: Find where a symbol is referenced and documented
argument-hint: "<symbol>"
---

# /wicked-garden:search:refs

Find all references to/from a code symbol, including documentation cross-references.

## Arguments

- `symbol` (required): The symbol name to look up (function, class, method)

## Instructions

1. **Search via brain** (unified knowledge layer):
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<symbol>","limit":20}}'
   ```
   Extract references from the matching chunks.

2. **If brain is unavailable** (connection refused or empty results):
   Fall back to native tools — use Grep to find all references to the symbol across the codebase.
   Suggest: `wicked-brain:ingest` to index the codebase for richer cross-reference search.

3. Report the relationships found, grouped by type:
   - **Documented in**: Docs that mention this symbol
   - **Called by**: Functions/methods that call this
   - **Calls**: Functions/methods this calls
   - **Inherited by**: Classes that extend this
   - **Inherits from**: Classes this extends
   - **Imports**: Modules this imports
   - **Imported by**: Modules that import this

## Example

```
/wicked-garden:search:refs UserRepository
/wicked-garden:search:refs authenticate
```

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Shows bidirectional relationships (both incoming and outgoing edges)
