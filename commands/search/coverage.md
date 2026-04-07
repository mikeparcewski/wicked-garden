---
description: Report on lineage coverage and identify symbols without full traceability
argument-hint: "[--type <symbol_type>] [--show-orphans]"
---

# /wicked-garden:search:coverage

Analyze lineage coverage across the indexed codebase. Identifies symbols without full source-to-sink traceability.

## Arguments

- `--type` (optional): Filter to specific symbol type (e.g., entity_field, column)
- `--show-orphans` (optional): Include list of orphan symbols in output

## Instructions

1. **Query brain for all indexed symbols**:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"class function entity model column field","limit":100}}'
   ```
   If brain is unavailable, fall back to Grep/Glob:
   - Use Glob to find all source files
   - Use Grep to extract class/function/entity definitions
   Suggest `wicked-brain:ingest` to index the codebase first.

2. **For each symbol, trace lineage** using Grep:
   - Search for references to the symbol across all source files
   - Check if it has both upstream (who calls/imports it) and downstream (what it calls/imports) connections
   - Classify coverage:
     - **Full coverage**: Connected in both directions through layers
     - **Partial coverage**: Some connections exist but gaps in the chain
     - **Orphan**: No lineage connections found

3. Report the coverage analysis:

   ```markdown
   ## Coverage Report

   ### Summary
   - **Total Symbols**: {count}
   - **Full Coverage**: {count} ({percentage}%)
   - **Partial Coverage**: {count}
   - **Orphan Symbols**: {count}

   ### Coverage by Type

   | Type | Total | Full | Partial | Orphan | Coverage |
   |------|-------|------|---------|--------|----------|
   | entity_field | 234 | 198 | 28 | 8 | 84.6% |
   ```

## Example

```
/wicked-garden:search:coverage
/wicked-garden:search:coverage --type entity_field
/wicked-garden:search:coverage --show-orphans
```

## Notes

- Brain provides the symbol inventory; Grep traces the connections
- High orphan count may indicate the codebase needs re-indexing via `wicked-brain:ingest`
