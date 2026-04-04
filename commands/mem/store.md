---
description: Store a new memory
argument-hint: "<content>" [--type episodic|decision|procedural|preference] [--tier working|episodic|semantic] [--tags tag1,tag2]
---

# /wicked-garden:mem:store

Store a memory for persistence across sessions.

## Arguments

Parse the arguments from: $ARGUMENTS

The first quoted string is the content. Extract a short title (5-10 words) from the content.

- `content` (required): The memory content to store (first quoted string)
- `--type`: Memory type - episodic (default), decision, procedural, preference
- `--tier`: Consolidation tier - working, episodic (default), semantic. Auto-detected from type/importance when omitted.
- `--tags`: Comma-separated tags for categorization
- `--importance`: low, medium (default), high

## Execution

Run from the plugin directory using available Python:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python3 scripts/mem/memory.py store \
  --title "SHORT_TITLE_HERE" \
  --content "CONTENT_HERE" \
  --type TYPE_HERE \
  --tags "TAG1,TAG2" \
  --importance medium \
  --tier TIER_HERE
```

Note: This script uses only standard library - no package manager needed.

Note: `--title` is required. Generate a concise title from the content.

## Memory Type Guidelines

| Type | Use When | TTL | Auto Tier |
|------|----------|-----|-----------|
| `episodic` | Recording what happened, debugging sessions, test results | 90 days | episodic |
| `decision` | Architectural choices, technology selections, trade-offs | Permanent | semantic |
| `procedural` | How-to knowledge, patterns, workflows | Permanent | episodic |
| `preference` | User/project preferences, coding style | Permanent | semantic |

## Tier Guidelines

| Tier | Purpose | Recall Weight |
|------|---------|---------------|
| `working` | Transient session context, auto-consolidated on session end | 0.8x |
| `episodic` | Sprint-level patterns and observations (default) | 1.0x |
| `semantic` | Durable project knowledge, prioritized in search results | 1.3x |

## Examples

```bash
# Store a decision
/wicked-garden:mem:store "Chose PostgreSQL for transaction support" --type decision --tags database,architecture

# Store a debugging session outcome
/wicked-garden:mem:store "Fixed auth bug: JWT was expiring too early" --type episodic --tags auth,bugfix

# Store a learned pattern
/wicked-garden:mem:store "Use early returns for validation, then happy path" --type procedural --tags code-style
```

## Output

Confirm storage with:
- Memory ID
- Type and tags
- Storage location
