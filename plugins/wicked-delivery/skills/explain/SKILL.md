---
name: explain
description: |
  Provides deep explanations of code components, flows, and patterns. Use when a
  developer needs to understand how something works, why design decisions were made,
  or how components relate. Transforms code into understandable narratives.
---

# Code Explanation Skill

Transform complex code into clear, contextual narratives.

## When to Use

- Developer asks "how does X work?"
- Need to understand component before modifying
- Debugging requires understanding code flow
- User says "explain", "walk through", "how does", "what is"
- Before code review or feature implementation

## Explanation Types

**Component**: Single unit (class, module, function) - what, why, how
**Flow**: End-to-end process - data transformation, decisions, errors
**Pattern**: Recurring structure - recognition, purpose, tradeoffs

## Framework

Every explanation uses "What, Why, How, Related":

```markdown
## {Name}

### What
{Purpose and role - 1-2 sentences}

### Why
- Problem: {What solved}
- Design: {Why this approach}
- Tradeoffs: {Chosen vs sacrificed}

### How
{Step-by-step mechanics}

### Related
- Similar: {Other components}
- Dependencies: {What it uses/used by}
- Next: {What to explore}
```

## Best Practices

### Use Concrete Examples
- Not: "Processes data"
- Yes: "Takes user ID '12345', fetches name 'Alice'"

### Show the Code
```python
user = db.get(user_id)  # ← Explain this
return verify_hash(password, user.hash)  # ← And this
```

### Explain the "Why"
- How: Uses Redis caching
- Why: Response time 200ms → 50ms

### Connect the Dots
> "This follows the Repository pattern like UserRepository. Understand one, understand all."

## Output Templates

See [templates.md](refs/templates.md) for full component, flow, and pattern templates.

Quick reference:

**Component**: Location → Purpose → Context → Methods → Dependencies → Testing → Related

**Flow**: Overview → Step-by-step → Decisions → Errors → Example trace → Testing

**Pattern**: Recognition → Purpose → Structure → Advantages → Cautions → Evolution

## Integration

### With wicked-search

```bash
/wicked-search:refs {function}  # Find callers
/wicked-search:code "{pattern}" # Find similar
/wicked-search:docs "{topic}"   # Related docs
```

### With wicked-mem

```python
# Recall prior explanations
if has_plugin("wicked-mem"):
    prior = recall("explanation", component=name)
    if prior: "Previously covered: {summary}"

# Store for reference
store({"type": "explanation", "component": name})
```

## Customization

**Beginners**: More context, domain concepts, analogies, resources
**Experts**: Skip basics, focus on novel aspects, compare to industry patterns
**Debugging**: Data flow, state changes, error conditions, edge cases
**Modification**: Extension points, test coverage, coupled components, breaking changes

## Quality Checklist

- [ ] Purpose stated clearly (what)
- [ ] Context provided (why)
- [ ] Mechanics explained (how)
- [ ] Connections shown (related)
- [ ] Concrete examples included
- [ ] Code snippets with file paths
- [ ] Next steps suggested

## Reference

- [Templates](refs/templates.md) - Detailed output templates
- [Examples](refs/examples.md) - Real-world explanation patterns
