---
description: Search across all code and documents
argument-hint: "<query>"
---

# /wicked-garden:search:search

Search across both code symbols and documents via the unified index.

## Arguments

- `query` (required): Search terms

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the unified search via the local index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py search "<query>" --path "${PWD}"
   ```

3. If the control plane is available, also query for additional results:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/cp.py knowledge graph search --q "<query>"
   ```
   Merge CP results with local results, deduplicating by file+line.

4. Report results grouped by type (code symbols vs documents), with relevance context:
   - Symbol name and type
   - File location
   - Score
   - Description snippet

## Example

```
/wicked-garden:search:search "authentication"
/wicked-garden:search:search "error handling"
```
