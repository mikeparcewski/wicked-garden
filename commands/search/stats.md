---
description: Show index statistics
argument-hint: "[--project <name>]"
---

# /wicked-garden:search:stats

Show statistics about the indexed knowledge graph.

## Arguments

- `--project` (optional): Filter to a specific project

## Instructions

1. Run the stats query via the CP proxy:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph stats ${project:+--project "${project}"}
   ```

2. Report:
   - Total symbols indexed
   - Total references/edges in graph
   - Breakdown by symbol type
   - Breakdown by architectural layer
   - Projects indexed

## Example

```
/wicked-garden:search:stats
/wicked-garden:search:stats --project my-app
```
