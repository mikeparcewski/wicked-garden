---
description: Manually trigger memory consolidation across tiers
argument-hint: ""
allowed-tools: [Bash, Read]
---

# /wicked-garden:mem:consolidate

Run memory consolidation across all three tiers: working, episodic, and semantic.

## What It Does

1. **Working -> Episodic**: Promotes surviving working-tier memories to episodic.
   Drops transient items (access_count <= 1 and past TTL). Merges similar items.
2. **Episodic -> Semantic**: Promotes episodic memories that appear across 3+ sessions,
   have access_count >= 10, or importance >= 8 to the semantic (permanent) tier.
3. **Deduplication**: Finds near-duplicate memories within each tier using word-overlap
   similarity and merges them (keeps highest importance/access_count).

## Execution

Run from the plugin directory using available Python:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python3 scripts/mem/memory.py consolidate
```

Note: This script uses only standard library - no package manager needed.

## Output

Display the JSON result showing counts for each consolidation pass:
- `working_to_episodic`: {promoted, dropped, merged}
- `episodic_to_semantic`: {promoted, merged, archived}
- `deduplication`: {merged, archived}

## When to Use

- After long sessions with many working memories
- Periodically to keep memory clean and promote recurring patterns
- Before important sessions where you want semantic memories prioritized
- Note: Working -> Episodic consolidation runs automatically on session end
