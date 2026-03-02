---
description: Analyze dependencies and dependents of a symbol
argument-hint: <symbol> [--depth N]
---

# /wicked-garden:search:blast-radius

Analyze what would be affected if you changed a symbol. Shows both what this symbol depends on and what depends on it.

## Arguments

- `symbol` (required): The symbol to analyze
- `--depth` (optional): How deep to traverse dependencies (default: 2)

## Instructions

1. Resolve the symbol name to a graph node UUID:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<symbol>" --limit 5
   ```
   Find the matching node in the results and extract its `id` (UUID).

2. Run the graph traversal using the resolved UUID:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph traverse "<uuid>" --direction both --depth "${depth:-2}"
   ```

3. Parse the response `data` object containing `nodes` and `edges`.

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
- For lineage-based impact (UI → DB tracing), use `/wicked-garden:search:impact` instead
