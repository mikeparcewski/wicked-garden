---
description: Show index statistics
argument-hint: "[--project <name>]"
---

# /wicked-garden:search:stats

Show statistics about the indexed search database.

## Arguments

- `--project` (optional): Filter to a specific project

## Instructions

1. Run the stats query via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python unified_search.py stats
   ```

2. If the control plane is available, also query CP stats:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph stats ${project:+--project "${project}"}
   ```
   Report both local and CP stats if available.

3. Report:
   - Total symbols indexed
   - Total references/edges
   - Breakdown by symbol type
   - Projects indexed

## Example

```
/wicked-garden:search:stats
/wicked-garden:search:stats --project my-app
```
