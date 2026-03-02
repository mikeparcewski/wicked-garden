---
description: Find where a symbol is referenced and documented
argument-hint: <symbol>
---

# /wicked-garden:search:refs

Find all references to/from a code symbol, including documentation cross-references.

## Arguments

- `symbol` (required): The symbol name to look up (function, class, method)

## Instructions

1. Resolve the symbol name to a graph node UUID:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<symbol>" --limit 5
   ```
   Find the matching node in the results and extract its `id` (UUID).

2. Run the graph traversal using the resolved UUID:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph traverse "<uuid>" --direction both --depth 1
   ```

3. Parse the response. The `data` object contains:
   - `nodes`: Connected nodes (symbols, doc sections), with the target node included
   - `edges`: Typed relationships between them

3. Report the relationships found, grouped by type:
   - **Documented in**: Docs that mention this symbol (edges with type `documents`)
   - **Called by**: Functions/methods that call this (incoming `calls` edges)
   - **Calls**: Functions/methods this calls (outgoing `calls` edges)
   - **Inherited by**: Classes that extend this (incoming `extends` edges)
   - **Inherits from**: Classes this extends (outgoing `extends` edges)
   - **Imports**: Modules this imports (outgoing `imports` edges)
   - **Imported by**: Modules that import this (incoming `imports` edges)

## Example

```
/wicked-garden:search:refs UserRepository
/wicked-garden:search:refs authenticate
```

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Shows bidirectional relationships (both incoming and outgoing edges)
