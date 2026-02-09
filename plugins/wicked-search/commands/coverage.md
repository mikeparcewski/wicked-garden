---
description: Report on lineage coverage and identify symbols without full traceability
argument-hint: [--type <symbol_type>] [--format table|json] [--show-orphans]
---

# /wicked-search:coverage

Analyze lineage coverage across the indexed codebase. Identifies symbols without full source-to-sink traceability and reports coverage gaps.

## Arguments

- `--type` (optional): Filter to specific symbol type (e.g., entity_field, column)
- `--format` (optional): Output format - table, json (default: table)
- `--show-orphans` (optional): Include list of orphan symbols in output

## Instructions

1. Run the coverage reporter (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python coverage_reporter.py --db /path/to/graph.db --format table
   ```

3. Report the coverage analysis:
   - **Summary**: Total symbols, coverage percentage
   - **By Type**: Breakdown by symbol type
   - **Gaps**: Common coverage gaps found
   - **Orphans**: Symbols with no lineage (if --show-orphans)

## Examples

```bash
# Full coverage report
/wicked-search:coverage

# Coverage for entity fields only
/wicked-search:coverage --type entity_field

# Include orphan symbols list
/wicked-search:coverage --show-orphans

# JSON output for tooling
/wicked-search:coverage --format json
```

## Output

### Table Format (default)
```markdown
## Coverage Report

### Summary
- **Total Symbols**: 847
- **Full Coverage**: 612 (72.3%)
- **Partial Coverage**: 156
- **Orphan Symbols**: 79

### Coverage by Type

| Type | Total | Full | Partial | Orphan | Coverage |
|------|-------|------|---------|--------|----------|
| entity_field | 234 | 198 | 28 | 8 | 84.6% |
| form_binding | 156 | 134 | 12 | 10 | 85.9% |
| column | 89 | 72 | 11 | 6 | 80.9% |
| el_expression | 245 | 145 | 67 | 33 | 59.2% |

### Common Gaps

| Gap | Count |
|-----|-------|
| No binding to entity/model | 43 |
| No UI binding found | 28 |
| No database mapping found | 8 |
```

## Coverage Status Definitions

- **Full**: Complete lineage from UI to database (or reverse)
- **Partial**: Some connections exist but gaps in the chain
- **Orphan**: No lineage connections found at all

## Expected Lineage by Symbol Type

| Symbol Type | Expected Upstream | Expected Downstream |
|-------------|-------------------|---------------------|
| UI (form_binding, el_expression) | - | Entity/Model |
| Entity (entity_field) | UI binding | Database column |
| Database (column) | Entity mapping | - |

## Use Cases

- **Migration readiness**: Ensure all symbols have traceability before migration
- **Tech debt tracking**: Identify orphaned code that may be dead
- **Data dictionary**: Find columns without documented UI exposure
- **Compliance**: Verify all PII fields have tracked lineage

## Notes

- Requires indexing first with `/wicked-search:index`
- Run `/wicked-search:lineage` to compute lineage paths before coverage
- High orphan count may indicate incomplete indexing
- Use `--type` to focus on specific layers (entity, UI, database)
