---
description: Find code that implements a documented feature/section
argument-hint: "<doc-section>"
---

# /wicked-garden:search:impl

Find code that implements a documented feature or section by searching for implementation edges in the knowledge graph.

## Arguments

- `doc-section` (required): Name of the doc section to find implementations for

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the implementation search via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py impl "<doc-section>" --path "${PWD}"
   ```

3. If the control plane is available, also query for additional implementation edges:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/cp.py knowledge graph search --q "<doc-section>" --edge_type implements
   ```
   Merge CP results with local results.

4. Report the code symbols that implement this section, with file locations.

## Example

```
/wicked-garden:search:impl "Repository Layer"
/wicked-garden:search:impl "Security Requirements"
```

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Cross-references are auto-detected during indexing (CamelCase, snake_case, backtick-quoted names)
