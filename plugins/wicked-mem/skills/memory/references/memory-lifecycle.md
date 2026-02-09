# Memory Lifecycle Management

Understanding how memories age, decay, and get cleaned up.

## Lifecycle States

```
active → archived → decayed → deleted
```

| State | Description | Visibility |
|-------|-------------|------------|
| `active` | Normal, searchable | Full |
| `archived` | Soft-deleted, recoverable | Hidden from search |
| `decayed` | Past TTL, pending cleanup | Hidden |
| `deleted` | Permanently removed | Gone |

## Decay Calculation

Effective TTL is calculated dynamically:

```
effective_ttl = base_ttl × importance_multiplier × access_boost

importance_multiplier:
  - low: 0.5x
  - medium: 1.0x
  - high: 2.0x

access_boost = 1 + (access_count × 0.1)
```

**Example**: A high-importance memory (2.0x) accessed 5 times (1.5x boost):
- Base TTL: 90 days
- Effective: 90 × 2.0 × 1.5 = 270 days

## Base TTL by Type

| Type | Base TTL |
|------|----------|
| `working` | 1 day |
| `episodic` | 90 days |
| `procedural` | Permanent |
| `decision` | Permanent |
| `preference` | Permanent |

## Manual Management

### Archiving (Soft Delete)

```bash
# Archive a memory (recoverable)
/wicked-mem:forget mem_abc123

# Memory moves to archived state
# Can be restored by editing status in file
```

### Hard Delete

```bash
# Permanently remove
/wicked-mem:forget mem_abc123 --hard

# Cannot be recovered
```

### Checking Health

```bash
/wicked-mem:stats
```

Output shows:
- Total memories by type
- Active vs archived counts
- Memories approaching decay
- Storage usage

## Automatic Maintenance

The `memory-archivist` agent runs automatically:

- **On SessionStart**: Checks for decayed memories
- **Decay process**: Moves past-TTL to archived
- **Cleanup**: Removes long-archived memories

## When to Manually Forget

- Memory contains outdated information
- Decision was reversed
- Pattern no longer applies
- Duplicate or redundant memory

## Recovery

Archived memories live in the same location but with `status: archived`. To recover:

1. Find the memory file in `~/.something-wicked/memory/`
2. Edit YAML frontmatter: `status: active`
3. Memory returns to search results

## Best Practices

1. **Let decay work**: Don't manually delete episodic memories - let them expire naturally
2. **Use importance wisely**: High importance = longer retention
3. **Access matters**: Using memories extends their life
4. **Review stats periodically**: Check for memory bloat
5. **Trust the system**: Automatic hooks handle most lifecycle management
