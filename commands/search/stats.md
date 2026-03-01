---
description: Show index statistics
argument-hint: "[--path <path>]"
---

# /wicked-garden:search:stats

Show statistics about the current index.

## Instructions

1. Run stats (see `skills/unified-search/refs/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python unified_search.py stats
   ```

2. Report:
   - Files indexed (code and docs)
   - Total nodes and edges in graph
   - Code symbols count
   - Doc sections count

## Example

```
/wicked-garden:search:stats
```
