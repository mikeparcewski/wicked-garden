---
description: Search code symbols only (functions, classes, methods)
argument-hint: "<query>"
---

# /wicked-garden:search:code

Search code symbols only (functions, classes, methods) via the knowledge graph.

## Arguments

- `query` (required): Search terms

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the code search via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py code "<query>" --path "${PWD}"
   ```

3. If the control plane is available, also query it for additional results:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>" --type code
   ```
   Merge CP results with local results, deduplicating by file+line.

4. Parse results. Each contains: `name`, `type`, `file`, `line`, `score`.

5. Report matching symbols with file locations and types.

## Example

```
/wicked-garden:search:code "UserService"
/wicked-garden:search:code "authenticate"
```
