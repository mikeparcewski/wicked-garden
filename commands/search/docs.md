---
description: Search documents only (PDF, Office docs, markdown)
argument-hint: "<query>"
---

# /wicked-garden:search:docs

Search documents only (PDF, Office docs, markdown) via the unified index.

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the doc search via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py docs "<query>"
   ```

2. If the control plane is available, also query for additional results:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<query>" --type document
   ```
   Merge CP results with local results, deduplicating by file+section.

3. Report matching document sections with source file locations.

## Example

```
/wicked-garden:search:docs "security requirements"
/wicked-garden:search:docs "API design"
```
