---
description: Report on lineage coverage and identify symbols without full traceability
argument-hint: "[--type <symbol_type>] [--show-orphans]"
---

# /wicked-garden:search:coverage

Analyze lineage coverage across the indexed codebase. Identifies symbols without full source-to-sink traceability.

## Arguments

- `--type` (optional): Filter to specific symbol type (e.g., entity_field, column)
- `--show-orphans` (optional): Include list of orphan symbols in output
- `--project` (optional): Filter to specific project

## Instructions

1. Get all symbols from the knowledge graph:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols list ${project:+--project "${project}"} ${type:+--type "${type}"}
   ```

2. For each symbol type that should have lineage (entity_field, column, form_binding), check lineage paths:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge lineage search "<symbol_id>" --direction both --depth 5
   ```

3. Classify each symbol:
   - **Full coverage**: Complete lineage from UI to database (or reverse)
   - **Partial coverage**: Some connections exist but gaps in the chain
   - **Orphan**: No lineage connections found

4. Report the coverage analysis:

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

- Requires indexing with `/wicked-garden:search:index --derive` for lineage data
- High orphan count may indicate incomplete indexing
