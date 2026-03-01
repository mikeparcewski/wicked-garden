---
description: Find code that implements a documented feature/section
argument-hint: <doc-section>
---

# /wicked-garden:search:impl

Find code that implements a documented feature or section.

## Arguments

- `doc-section` (required): Name of the doc section to find implementations for

## Instructions

1. Run the impl search (see `skills/unified-search/refs/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py impl "<doc-section>"
   ```

2. Report the code symbols that implement this section

## Example

```
/wicked-garden:search:impl "Repository Layer"
```
