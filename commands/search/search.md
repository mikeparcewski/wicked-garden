---
description: Search across all code and documents
argument-hint: <query>
---

# /wicked-garden:search:search

Search across both code symbols and documents.

## Arguments

- `query` (required): Search terms

## Instructions

1. Run the search (see `skills/unified-search/refs/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py search "<query>"
   ```

2. Report results with relevance scores

## Example

```
/wicked-garden:search:search "authentication"
```
