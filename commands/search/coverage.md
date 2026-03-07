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

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the coverage report via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py coverage --path "${PWD}"
   ```

3. If the control plane is available, also query for enrichment:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/cp.py knowledge symbols list ${project:+--project "${project}"} ${type:+--type "${type}"}
   ```
   This step is optional — the local index is fully functional without CP.

4. Classify each symbol:
   - **Full coverage**: Complete lineage from UI to database (or reverse)
   - **Partial coverage**: Some connections exist but gaps in the chain
   - **Orphan**: No lineage connections found

5. Report the coverage analysis:

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
