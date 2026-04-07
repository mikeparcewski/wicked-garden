---
description: Trace data lineage from source to sink (UI → DB or reverse)
argument-hint: "<symbol> [--direction upstream|downstream|both] [--depth N]"
---

# /wicked-garden:search:lineage

Trace data lineage paths through the codebase. Follow data flow from UI fields to database columns (downstream) or reverse (upstream).

## Arguments

- `symbol` (required): The symbol to trace from
- `--direction` (optional): Direction to trace (default: downstream)
  - `downstream`: Source → sink (e.g., UI field → DB column)
  - `upstream`: Sink → source (e.g., DB column → UI fields)
  - `both`: Trace in both directions
- `--depth` (optional): Maximum traversal depth (default: 10)

## Instructions

1. **Search brain for the symbol** to find its location and references:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<symbol>","limit":20}}'
   ```
   If brain is unavailable or returns no results, fall back to Grep:
   ```
   Grep: <symbol> across all source files
   ```
   If no results at all, suggest: `wicked-brain:ingest` to index the codebase first.

2. **Trace data flow** using Grep to follow the symbol through layers:
   - Search for imports/requires of the file containing the symbol
   - Search for function calls that pass the symbol as an argument
   - Search for assignments, mappings, and transformations of the symbol
   - Follow the chain through controller → service → repository → database layers

3. Report the lineage paths found:
   - Show each path with steps from source to sink
   - Include file locations at each step
   - Note any gaps in the lineage chain

## Examples

```bash
# Trace downstream from a UI field
/wicked-garden:search:lineage firstName --direction downstream

# Find all UI fields that use a database column
/wicked-garden:search:lineage EMAIL --direction upstream

# Trace both directions
/wicked-garden:search:lineage User.email --direction both
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

- Brain search provides indexed symbol locations; Grep traces the connections
- Use `/wicked-garden:search:impact` for reverse lineage (upstream consumers)
