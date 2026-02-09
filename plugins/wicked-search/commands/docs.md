---
description: Search documents only (PDF, Office docs, markdown)
argument-hint: <query>
---

# /wicked-search:docs

Search documents only (PDF, Office docs, markdown).

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the doc search (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py docs "<query>"
   ```

2. Report matching document sections

## Example

```
/wicked-search:docs "security requirements"
```
