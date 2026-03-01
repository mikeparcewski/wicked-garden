---
description: Analyze dependencies and dependents of a symbol
argument-hint: <symbol> [--depth N]
---

# /wicked-garden:search:blast-radius

Analyze what would be affected if you changed a symbol.

## Arguments

- `symbol` (required): The symbol to analyze
- `--depth` (optional): How deep to traverse dependencies (default: 2)

## Instructions

1. Run blast-radius analysis (see `skills/unified-search/refs/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py blast-radius "<symbol>" --depth <n>
   ```

2. Report the impact assessment:
   - **Dependencies**: What this symbol uses/imports
   - **Dependents**: What uses this symbol (direct and transitive)

## Example

```
/wicked-garden:search:blast-radius DatabaseConnection --depth 3
```

## Use Cases

- **Pre-refactoring**: Know what will break before changing code
- **Safe changes**: Identify low-risk symbols to modify
- **Tech debt prioritization**: Focus on high-impact components

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Deeper depth = more complete but slower analysis
