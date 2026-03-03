---
description: Find where a symbol is referenced and documented
argument-hint: "<symbol>"
---

# /wicked-garden:search:refs

Find all references to/from a code symbol, including documentation cross-references.

## Arguments

- `symbol` (required): The symbol name to look up (function, class, method)

## Instructions

1. Run the refs lookup via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python unified_search.py refs "<symbol>"
   ```

2. If the control plane is available, also query the graph for additional relationships:
   a. Resolve symbol to UUID:
      ```bash
      python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<symbol>" --limit 5
      ```
   b. Traverse from UUID:
      ```bash
      python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph traverse "<uuid>" --direction both --depth 1
      ```
   Merge CP results with local results.

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
