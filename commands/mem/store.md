---
description: Store a new memory
argument-hint: "<content>" [--type episodic|decision|procedural|preference] [--tags tag1,tag2]
---

# /wicked-garden:mem:store

Store a memory for persistence across sessions.

## Arguments

Parse the arguments from: $ARGUMENTS

The first quoted string is the content. Extract a short title (5-10 words) from the content.

- `content` (required): The memory content to store (first quoted string)
- `--type`: Memory type - episodic (default), decision, procedural, preference
- `--tags`: Comma-separated tags for categorization
- `--importance`: low, medium (default), high

## Execution

Run from the plugin directory using available Python:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python3 scripts/memory.py store \
  --title "SHORT_TITLE_HERE" \
  --content "CONTENT_HERE" \
  --type TYPE_HERE \
  --tags "TAG1,TAG2" \
  --importance medium
```

Note: This script uses only standard library - no package manager needed.

Note: `--title` is required. Generate a concise title from the content.

## Memory Type Guidelines

| Type | Use When | TTL |
|------|----------|-----|
| `episodic` | Recording what happened, debugging sessions, test results | 90 days |
| `decision` | Architectural choices, technology selections, trade-offs | Permanent |
| `procedural` | How-to knowledge, patterns, workflows | Permanent |
| `preference` | User/project preferences, coding style | Permanent |

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
