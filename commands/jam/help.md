---
description: Get help with the wicked-jam plugin
---

# /wicked-garden:jam:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-jam Help

AI-powered brainstorming with dynamic focus groups.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:jam:brainstorm <topic>` | Full session (2-3 rounds, 4-6 personas) |
| `/wicked-garden:jam:jam <idea>` | Quick exploration (1 round, 4 personas) |
| `/wicked-garden:jam:perspectives <decision>` | Multiple viewpoints without synthesis |
| `/wicked-garden:jam:help` | This help message |

## Options

- `--personas <list>`: Specify persona types (comma-separated)
- `--rounds <n>`: Number of discussion rounds (default: 2)

## Examples

### Full Brainstorm
```
/wicked-garden:jam:brainstorm "authentication approaches"
/wicked-garden:jam:brainstorm "error handling strategy" --rounds 3
```

### Quick Exploration
```
/wicked-garden:jam:jam "should we use TypeScript?"
/wicked-garden:jam:jam "Redis vs Memcached for caching"
```

### Get Perspectives
```
/wicked-garden:jam:perspectives "GraphQL vs REST"
/wicked-garden:jam:perspectives "Monolith vs microservices"
```

### Custom Personas
```
/wicked-garden:jam:brainstorm "testing strategy" --personas "QA,Developer,DevOps"
```

## Persona Archetypes

| Archetype | Example Personas |
|-----------|------------------|
| Technical | Architect, Debugger, Optimizer, Security Reviewer |
| User-Focused | Power User, Newcomer, Support Rep |
| Business | Product Manager, Skeptic, Evangelist |
| Process | Maintainer, Tester, Documentarian |

## Integration

- **wicked-mem**: Recalls prior context, stores insights
- **wicked-crew**: Called during clarify phase

## Tips

- Use `/jam` for quick decisions
- Use `/brainstorm` for important decisions needing depth
- Use `/perspectives` when you want to think it through yourself
- Custom personas work best when they have genuine different views
```
