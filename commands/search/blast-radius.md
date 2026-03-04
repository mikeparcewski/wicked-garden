---
description: Analyze dependencies and dependents of a symbol
argument-hint: "<symbol> [--depth N]"
---

# /wicked-garden:search:blast-radius

Analyze what would be affected if you changed a symbol. Shows both what this symbol depends on and what depends on it.

## Arguments

- `symbol` (required): The symbol to analyze
- `--depth` (optional): How deep to traverse dependencies (default: 2)

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the blast radius analysis via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py blast-radius "<symbol>" --depth "${depth:-2}" --path "${PWD}"
   ```

3. If the control plane is available, also query the graph for additional transitive dependencies:
   a. Resolve symbol to UUID:
      ```bash
      python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<symbol>" --limit 5
      ```
   b. Traverse from UUID:
      ```bash
      python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph traverse "<uuid>" --direction both --depth "${depth:-2}"
      ```
   Merge CP results with local results.

4. Report the impact assessment:
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
- For lineage-based impact (UI → DB tracing), use `/wicked-garden:search:impact` instead
