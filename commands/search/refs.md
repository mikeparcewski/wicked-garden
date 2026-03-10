---
description: Find where a symbol is referenced and documented
argument-hint: "<symbol>"
---

# /wicked-garden:search:refs

Find all references to/from a code symbol, including documentation cross-references.

## Arguments

- `symbol` (required): The symbol name to look up (function, class, method)

## Instructions

1. Check that an index exists for the current project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py stats --path "${PWD}"
   ```
   If the output shows 0 symbols or the index is not found, stop and inform the user:
   > No index found for this directory. Run `/wicked-garden:search:index .` first to build the search index.

2. Run the refs lookup via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py refs "<symbol>" --path "${PWD}"
   ```

3. Report the relationships found, grouped by type:
   - **Documented in**: Docs that mention this symbol
   - **Called by**: Functions/methods that call this
   - **Calls**: Functions/methods this calls
   - **Inherited by**: Classes that extend this
   - **Inherits from**: Classes this extends
   - **Imports**: Modules this imports
   - **Imported by**: Modules that import this

## Example

```
/wicked-garden:search:refs UserRepository
/wicked-garden:search:refs authenticate
```

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Shows bidirectional relationships (both incoming and outgoing edges)
