---
description: Find where a symbol is referenced and documented
argument-hint: <symbol>
---

# /wicked-garden:search-refs

Find all references to/from a code symbol, including documentation cross-references.

## Arguments

- `symbol` (required): The symbol name to look up (function, class, method)

## Instructions

1. Run the refs search (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py refs "<symbol>"
   ```

2. Report the relationships found:
   - **Documented in**: Docs that mention this symbol
   - **Called by**: Functions/methods that call this
   - **Calls**: Functions/methods this calls
   - **Inherited by**: Classes that extend this
   - **Inherits from**: Classes this extends
   - **Defines**: Methods this class defines
   - **Defined by**: Class this method belongs to

## Example

```
/wicked-garden:search-refs UserRepository
```

## Notes

- Requires indexing first with `/wicked-garden:search-index`
- Shows bidirectional relationships (both incoming and outgoing edges)
