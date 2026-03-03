---
description: Search across all code and documents
argument-hint: <query>
---

# /wicked-garden:search:search

Search across both code symbols and documents via the unified index.

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the unified search via the local index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python unified_search.py search "<query>"
   ```

2. If the control plane is available, also query for additional results:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>"
   ```
   Merge CP results with local results, deduplicating by file+line.

3. Report results grouped by type (code symbols vs documents), with relevance context:
   - Symbol name and type
   - File location
   - Score
   - Description snippet

## Example

```
/wicked-garden:search:search "authentication"
/wicked-garden:search:search "error handling"
```
