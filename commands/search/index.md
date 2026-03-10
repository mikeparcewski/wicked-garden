---
description: Build unified index for code and documents in a directory
argument-hint: "<path> [--derive] [--derive-all]"
---

# /wicked-garden:search:index

Build a unified index of code symbols and document content in the local SQLite database. Optionally sync to the control plane knowledge graph if available.

## Arguments

- `path` (required): Directory to index
- `--derive` (optional): Auto-derive lineage paths after indexing
- `--derive-all` (optional): Auto-derive lineage paths AND service map after indexing
- `--project` (optional): Project name for multi-codebase isolation

## Instructions

1. Build the local unified index (primary — always runs). Pass `--derive` or `--derive-all` if the user requested them:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py index "<path>" ${project:+--project "${project}"} ${derive:+--derive} ${derive_all:+--derive-all}
   ```

2. Verify the local index:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py stats
   ```

3. Report the results showing:
   - Code files indexed
   - Doc files indexed
   - Code symbols found
   - Doc sections found
   - Cross-references detected

## Examples

```bash
# Basic indexing
/wicked-garden:search:index /path/to/project

# Index with lineage derivation
/wicked-garden:search:index /path/to/project --derive

# Full indexing with lineage and service map
/wicked-garden:search:index /path/to/project --derive-all

# Index for a named project
/wicked-garden:search:index /path/to/project --project my-app
```

## Notes

- Re-running only updates changed files (incremental indexing)
- The `--derive` options add computation time but enable richer queries (lineage, impact, coverage)
- Use `--project` to isolate multiple codebases in the same knowledge graph
- Check `/wicked-garden:search:stats` to verify indexing results
