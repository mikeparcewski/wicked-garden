---
description: Trace data lineage from source to sink (UI → DB or reverse)
argument-hint: <symbol> [--direction upstream|downstream|both] [--depth N]
---

# /wicked-garden:search:lineage

Trace data lineage paths through the knowledge graph. Follow data flow from UI fields to database columns (downstream) or reverse (upstream).

## Arguments

- `symbol` (required): The symbol ID to trace from
- `--direction` (optional): Direction to trace (default: downstream)
  - `downstream`: Source → sink (e.g., UI field → DB column)
  - `upstream`: Sink → source (e.g., DB column → UI fields)
  - `both`: Trace in both directions
- `--depth` (optional): Maximum traversal depth (default: 10)

## Instructions

1. Run the lineage search via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge lineage search "<symbol_id>" --direction "${direction:-downstream}" --depth "${depth:-10}"
   ```

2. Parse the response `data` which contains lineage paths.

3. Report the lineage paths found:
   - Show each path with steps from source to sink
   - Include confidence level and completeness status
   - Note any gaps in the lineage chain

## Examples

```bash
# Trace downstream from a UI field
/wicked-garden:search:lineage form_binding::person.firstName --direction downstream

# Find all UI fields that use a database column
/wicked-garden:search:lineage column::USERS.EMAIL --direction upstream

# Trace both directions
/wicked-garden:search:lineage entity_field::User.email --direction both
```

## Output

### Table Format
```
| # | Source | Sink | Steps | Confidence | Complete |
|---|--------|------|-------|------------|----------|
| 1 | firstName | FIRST_NAME | 3 | high | yes |
| 2 | lastName | LAST_NAME | 3 | medium | yes |
```

## Use Cases

- **Impact analysis**: Before changing a database column, find all UI fields that use it
- **Data flow documentation**: Understand how data flows through the system
- **Debugging**: Trace why a UI field isn't displaying expected data
- **Compliance**: Document which UI fields expose sensitive database columns

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Use `/wicked-garden:search:impact` for reverse lineage (upstream consumers)
