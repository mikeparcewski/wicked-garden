---
description: Show available memory commands and usage
---

# /wicked-garden:mem:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-mem Help

Brain-backed persistent memory across sessions — store decisions, recall context, and manage institutional knowledge.

Memories are stored as markdown chunk files in `~/.wicked-brain/memories/` organized by tier (working/episodic/semantic) and indexed via the brain API for fast search.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:mem:store <content>` | Store a new memory (writes chunk file + brain index) |
| `/wicked-garden:mem:recall [query]` | Search memories via brain API |
| `/wicked-garden:mem:review` | Browse and manage stored memory chunk files |
| `/wicked-garden:mem:stats` | Show memory statistics (brain + file counts) |
| `/wicked-garden:mem:forget <id>` | Delete a memory (chunk file + brain index) |
| `/wicked-garden:mem:consolidate` | Compile wiki from memories + lint expired chunks |
| `/wicked-garden:mem:retag` | Backfill search tags on under-tagged memories |
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
/wicked-garden:mem:review --tier semantic
```

### Cleanup
```
/wicked-garden:mem:forget mem-abc123
/wicked-garden:mem:consolidate
/wicked-garden:mem:retag --dry-run
```

## Memory Types

| Type | Use For |
|------|---------|
| `decision` | Architecture choices, trade-off outcomes |
| `episodic` | Bug fixes, debugging sessions, incidents |
| `procedural` | How-to steps, workflows, patterns |
| `preference` | User preferences, style choices |

## Storage

Memories are stored as markdown files with YAML frontmatter:
- **Path**: `~/.wicked-brain/memories/{tier}/mem-{uuid}.md`
- **Tiers**: working (transient), episodic (sprint-level), semantic (permanent)
- **Index**: Brain API at `http://localhost:4242/api` for full-text search

## Integration

- **wicked-smaht**: Auto-recalls relevant memories for every prompt
- **wicked-crew**: Persists decisions and context across phases
- **wicked-brain**: Chunk storage, search index, compile, and lint
- **jam**: Stores brainstorming insights
```
