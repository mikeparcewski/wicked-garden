---
description: Search code symbols only (functions, classes, methods)
argument-hint: <query>
---

# /wicked-garden:search:code

Search code symbols only (functions, classes, methods).

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the code search (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py code "<query>"
   ```

2. Report matching symbols with file locations

## Example

```
/wicked-garden:search:code "UserService"
```
