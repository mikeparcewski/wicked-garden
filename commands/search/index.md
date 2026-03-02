---
description: Build unified index for code and documents in a directory
argument-hint: <path> [--derive] [--derive-all]
---

# /wicked-garden:search:index

Build a unified index of code symbols and document content, then ingest into the knowledge graph via the control plane.

## Arguments

- `path` (required): Directory to index
- `--derive` (optional): Auto-derive lineage paths after indexing
- `--derive-all` (optional): Auto-derive lineage paths AND service map after indexing
- `--project` (optional): Project name for multi-codebase isolation

## Instructions

1. Ingest symbols into the knowledge graph via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols ingest < payload.json
   ```

   The payload should contain the extracted symbols from the target directory. If a local indexing pipeline is available:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python unified_search.py index "<path>" --export-json | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge symbols ingest
   ```

2. Ingest cross-references:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge refs ingest < refs_payload.json
   ```

3. Verify the ingest by checking stats:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph stats ${project:+--project "${project}"}
   ```

4. Report the results showing:
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
