---
description: Recall memories matching a query
argument-hint: "[query] [--tags tag1,tag2] [--type episodic|decision|procedural|preference] [--tier working|episodic|semantic]"
---

# /wicked-garden:mem:recall

Recall memories matching search criteria. Results are ranked by access frequency
with tier weighting: semantic (1.3x), episodic (1.0x), working (0.8x).

## Arguments

Parse the arguments from: $ARGUMENTS

- `query` (optional): Free-text search query
- `--type`: Filter by memory type (episodic, decision, procedural, preference)
- `--tier`: Filter by consolidation tier (working, episodic, semantic)
- `--tags`: Comma-separated tags to filter by
- `--limit`: Maximum results (default: 10)
- `--all-projects`: Search across all projects

## Execution

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python3 scripts/mem/memory.py recall \
  --query "QUERY_HERE" \
  --type TYPE_HERE \
  --tier TIER_HERE \
  --tags "TAG1,TAG2" \
  --limit 10
```

Note: This script uses only standard library - no package manager needed.

Omit flags that are not specified by the user.

## Output

For each memory, display:
- ID, type, tier, and project label
- Tags
- Summary (first 100 chars)
