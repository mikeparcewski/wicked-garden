# Effective Memory Recall

Strategies for finding relevant context quickly.

## Search Patterns

### By Query (Text Search)

```bash
# Simple keyword
/wicked-mem:recall "authentication"

# Multiple terms (matches any)
/wicked-mem:recall "JWT token validation"

# Phrase matching
/wicked-mem:recall "session middleware"
```

### By Tags

```bash
# Single tag
/wicked-mem:recall --tags auth

# Multiple tags (AND logic)
/wicked-mem:recall --tags auth,security

# Combined with query
/wicked-mem:recall "validation" --tags auth
```

### By Type

```bash
# Only decisions
/wicked-mem:recall --type decision

# Only procedures
/wicked-mem:recall --type procedural

# Combined
/wicked-mem:recall "database" --type decision
```

## Search Strategies

### Starting a Task

Before diving in, check for relevant context:

```bash
# What do we know about this area?
/wicked-mem:recall "feature-name"

# Any past decisions?
/wicked-mem:recall --type decision --tags feature-area

# Similar bugs fixed before?
/wicked-mem:recall "error message" --type episodic
```

### Debugging

```bash
# Check for similar past bugs
/wicked-mem:recall "TypeError" --tags bug-fix
/wicked-mem:recall "auth" --type episodic

# Look for related procedures
/wicked-mem:recall "validation" --type procedural
```

### Making Decisions

```bash
# What did we decide before about similar things?
/wicked-mem:recall --type decision --tags database
/wicked-mem:recall --type decision --tags architecture
```

## Interpreting Results

Results are ranked by relevance. Each memory shows:

```
[mem_abc123] decision: PostgreSQL for ACID compliance
  Tags: db, architecture
  Importance: high | Accessed: 3 times
  Chose PostgreSQL over MongoDB for transaction support...
```

## When No Results Found

1. **Broaden the query**: Use fewer/different keywords
2. **Remove filters**: Drop type or tag constraints
3. **Check synonyms**: "auth" vs "authentication", "db" vs "database"
4. **Use stats**: `/wicked-mem:stats` shows what's available

## Automatic Recall

The memory system automatically injects relevant context:

- **SessionStart**: Loads project-relevant memories
- **UserPromptSubmit**: Searches for query-relevant context

You don't always need explicit `/recall` - context flows naturally.
