---
description: Show available memory commands and usage
---

# /wicked-garden:mem:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-mem Help

Persistent memory across sessions — store decisions, recall context, and manage institutional knowledge.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:mem:store <content>` | Store a new memory |
| `/wicked-garden:mem:recall [query]` | Recall memories matching a query |
| `/wicked-garden:mem:review` | Browse, understand, and manage stored memories |
| `/wicked-garden:mem:stats` | Show memory statistics |
| `/wicked-garden:mem:forget <id>` | Archive or delete a memory |
| `/wicked-garden:mem:help` | This help message |

## Quick Start

```
/wicked-garden:mem:store "decided to use PostgreSQL for user data" --type decision --tags db,arch
/wicked-garden:mem:recall "database choice"
/wicked-garden:mem:stats
```

## Examples

### Store Memories
```
/wicked-garden:mem:store "API rate limit is 100 req/min" --type procedural
/wicked-garden:mem:store "user prefers concise output" --type preference
/wicked-garden:mem:store "fixed auth bug by refreshing token" --type episodic --tags auth,bug
```

### Recall and Review
```
/wicked-garden:mem:recall --tags auth
/wicked-garden:mem:recall --type decision
/wicked-garden:mem:review --stale
/wicked-garden:mem:review --project my-app
```

### Cleanup
```
/wicked-garden:mem:forget mem_abc123
/wicked-garden:mem:forget mem_abc123 --hard
```

## Memory Types

| Type | Use For |
|------|---------|
| `decision` | Architecture choices, trade-off outcomes |
| `episodic` | Bug fixes, debugging sessions, incidents |
| `procedural` | How-to steps, workflows, patterns |
| `preference` | User preferences, style choices |

## Integration

- **wicked-smaht**: Auto-recalls relevant memories for every prompt
- **wicked-crew**: Persists decisions and context across phases
- **wicked-jam**: Stores brainstorming insights
```
