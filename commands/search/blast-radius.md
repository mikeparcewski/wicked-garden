---
description: |
  Use when you need to know what would break or be affected by changing a symbol — traces both
  dependencies (what this uses) and dependents (what uses this) via the graph index.
  NOT for full data lineage tracing (use search:lineage) or general code search (use wicked-brain:search).
argument-hint: "<symbol> [--depth N]"
---

# /wicked-garden:search:blast-radius

Analyze what would be affected if you changed a symbol. Shows both what this symbol depends on and what depends on it.

> **Scope**: `blast-radius` answers "what breaks if I change X?" — impact of changing a symbol (dependents graph).
> For **data flow tracing** (UI field → DB column or reverse), use `/wicked-garden:search:lineage` instead.

## Arguments

- `symbol` (required): The symbol to analyze
- `--depth` (optional): How deep to traverse dependencies (default: 2)

## Instructions

1. **Search via brain** for reference discovery:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<symbol>","limit":30}}'
   ```
   Use matching chunks as the starting set for blast radius analysis.

2. **Expand with native tools**: Use Grep to find transitive dependencies at the requested depth. For each direct reference found, search for its callers/importers to build the dependency graph.

3. **If brain is unavailable**: Use Grep and Glob exclusively to trace the dependency chain.
   Suggest: `wicked-brain:ingest` for richer graph-based analysis.

3. Report the impact assessment:
   - **Dependencies** (outgoing): What this symbol uses/imports
   - **Dependents** (incoming): What uses this symbol (direct and transitive)
   - Total blast radius count
   - Files affected

## Example

```
/wicked-garden:search:blast-radius DatabaseConnection --depth 3
/wicked-garden:search:blast-radius UserService
```

## Use Cases

- **Pre-refactoring**: Know what will break before changing code
- **Safe changes**: Identify low-risk symbols to modify
- **Tech debt prioritization**: Focus on high-impact components

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Deeper depth = more complete but slower analysis
- For data lineage tracing (UI → DB), use `/wicked-garden:search:lineage` instead
