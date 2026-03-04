---
description: Search documents only (PDF, Office docs, markdown)
argument-hint: "<query>"
---

# /wicked-garden:search:docs

Search documents only (PDF, Office docs, markdown) via the unified index.

## Arguments

- `query` (required): Search terms

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the doc search via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py docs "<query>" --path "${PWD}"
   ```

3. If the control plane is available, also query for additional results:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>" --type document
   ```
   Merge CP results with local results, deduplicating by file+section.

4. Report matching document sections with source file locations.

## Example

```
/wicked-garden:search:docs "security requirements"
/wicked-garden:search:docs "API design"
```
