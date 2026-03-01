---
description: Build unified index for code and documents in a directory
argument-hint: <path> [--derive] [--derive-all]
---

# /wicked-garden:search:index

Build a unified index of code symbols and document content, with optional automatic derivation of lineage paths and service maps.

## Arguments

- `path` (required): Directory to index
- `--derive` (optional): Auto-derive lineage paths after indexing
- `--derive-all` (optional): Auto-derive lineage paths AND service map after indexing

## Instructions

1. Run the indexer (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py index "<path>"
   ```

2. If `--derive` or `--derive-all` is specified, also run:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python lineage_tracer.py --db "<db_path>" --derive-all --save
   ```

3. If `--derive-all` is specified, additionally run:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python service_detector.py --db "<db_path>" --source all --save
   ```

4. Report the results showing:
   - Code files indexed
   - Doc files indexed
   - Code symbols found
   - Doc sections found
   - Cross-references detected
   - Lineage paths computed (if --derive)
   - Services detected (if --derive-all)

## Examples

```bash
# Basic indexing only
/wicked-garden:search:index /path/to/project

# Index and compute lineage paths
/wicked-garden:search:index /path/to/project --derive

# Full indexing with lineage and service map
/wicked-garden:search:index /path/to/project --derive-all
```

## Notes

- First run may install dependencies automatically
- Index is stored at `~/.something-wicked/wicked-garden/local/wicked-search/`
- Re-running only updates changed files (incremental indexing)
- Document extraction uses kreuzberg (included as a core dependency)
- The `--derive` options add computation time but enable richer queries
- Use `--derive-all` for full reasoning capabilities (lineage, impact, service-map, coverage)
