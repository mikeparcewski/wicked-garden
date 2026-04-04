---
description: Show memory statistics
argument-hint: ""
---

# /wicked-garden:mem:stats

Show memory statistics including counts by type, status, tier, and tag.

## Execution

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python3 scripts/mem/memory.py stats
```

Note: This script uses only standard library - no package manager needed.

## Output

Display the JSON result with:
- `total`: Total memory count
- `by_type`: Count per memory type (episodic, decision, procedural, preference, working)
- `by_status`: Count per status (active, archived, decayed)
- `by_tier`: Count per consolidation tier (working, episodic, semantic)
- `by_tag`: Count per tag
