---
description: Store a new memory
argument-hint: "<content>" [--type episodic|decision|procedural|preference] [--tier working|episodic|semantic] [--tags tag1,tag2]
---

# /wicked-garden:mem:store

Store a memory for persistence across sessions. Delegates to wicked-brain:memory.

## Arguments

Parse the arguments from: $ARGUMENTS

- `content` (required): The memory content to store (first quoted string)
- `--type`: Memory type - episodic (default), decision, procedural, preference, gotcha, discovery, pattern
- `--tier`: Consolidation tier - working, episodic (default), semantic
- `--tags`: Comma-separated tags for categorization
- `--importance`: low, medium (default), high

## Execution

Invoke the brain memory skill:

```
Skill(skill="wicked-brain-memory", args="store {content} --type {type} --tier {tier} --tags {tags}")
```

Pass through all arguments. If `--type` maps to a brain type differently:
- `procedural` in garden = `pattern` in brain
- All others pass through directly

If `--importance high`, add `--tier semantic` unless tier was explicitly set.

## Memory Type Guidelines

| Type | Use When | TTL | Auto Tier |
|------|----------|-----|-----------|
| `episodic` | Recording what happened, debugging sessions, test results | 90 days | episodic |
| `decision` | Architectural choices, technology selections, trade-offs | Permanent | semantic |
| `procedural` | How-to knowledge, patterns, workflows | Permanent | episodic |
| `preference` | User/project preferences, coding style | Permanent | semantic |
| `gotcha` | Pitfalls, traps, things to watch out for | 30 days | episodic |
| `discovery` | New learnings, findings | 14 days | working |

## Examples

```bash
# Store a decision
/wicked-garden:mem:store "Chose PostgreSQL for transaction support" --type decision --tags database,architecture

# Store a debugging session outcome
/wicked-garden:mem:store "Fixed auth bug: JWT was expiring too early" --type episodic --tags auth,bugfix

# Store a learned pattern
/wicked-garden:mem:store "Use early returns for validation, then happy path" --type procedural --tags code-style
```
