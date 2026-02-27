# ADR Template

Use this template for Architectural Decision Records (ADRs).

## File Naming

```
decisions/NNN-short-title.md
```

Examples:
- `001-architecture-style.md`
- `002-database-choice.md`
- `003-caching-strategy.md`

## Template

```markdown
# ADR-NNN: [Short Title]

**Status**: [Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

**Date**: YYYY-MM-DD

**Decision Makers**: [Who was involved in the decision]

**Tags**: [architecture, database, frontend, etc.]

## Context

What is the issue we're facing? What forces are at play?

- Business requirements
- Technical constraints
- Team capabilities
- Time/budget limitations
- Existing systems/dependencies

Be specific about:
- Why this decision needs to be made now
- What problem we're solving
- Who is affected

## Decision

What are we doing? State the decision clearly and concisely.

Example:
"We will use PostgreSQL as our primary relational database."

## Consequences

What becomes easier or more difficult because of this decision?

### Positive

- Benefit 1
- Benefit 2
- Benefit 3

### Negative

- Trade-off 1
- Trade-off 2
- Limitation 1

### Risks

- Risk 1 and mitigation
- Risk 2 and mitigation

### Migration Path

If replacing an existing system:
- Steps to transition
- Backward compatibility
- Timeline

## Alternatives Considered

### Alternative 1: [Name]

**Description**: Brief explanation

**Pros**:
- Advantage 1
- Advantage 2

**Cons**:
- Disadvantage 1
- Disadvantage 2

**Why rejected**: Clear reason

### Alternative 2: [Name]

[Same structure]

## Research

Links to supporting research:
- Benchmark results
- Documentation
- Blog posts
- Prior art
- Team discussions

## Related Decisions

- ADR-XXX: [Related decision]
- ADR-YYY: [Depends on this]

## Notes

Additional context, meeting notes, follow-up items.
```

## Best Practices

### Keep It Concise

- Focus on "why" not "what"
- One decision per ADR
- 1-2 pages maximum

### Make It Scannable

Use:
- Bullet points over paragraphs
- Headers for structure
- Tables for comparisons
- Diagrams where helpful

### Be Honest

Include:
- Real trade-offs
- What you don't know
- Assumptions made
- Risks accepted

### Show Your Work

Document:
- Alternatives considered
- Research conducted
- Stakeholders consulted
- Criteria used

## Example: Comparison Table

| Criteria | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Performance | High | Medium | Low |
| Cost | $$$ | $$ | $ |
| Team Expertise | Low | High | Medium |
| Scalability | Excellent | Good | Limited |
| **Score** | 7/10 | 8/10 | 5/10 |

## Lightweight vs Detailed

### Lightweight ADR

For minor decisions or rapid iteration:
- Context: 2-3 sentences
- Decision: 1 sentence
- Consequences: 3-5 bullets
- Alternatives: Brief mention

### Detailed ADR

For major architectural decisions:
- Full template with all sections
- Multiple alternatives analyzed
- Research links and data
- Detailed migration path

## Status Lifecycle

```
Proposed → Accepted → Deprecated
                   ↓
              Superseded by ADR-XXX
```

**Proposed**: Under discussion
**Accepted**: Implemented or implementing
**Deprecated**: No longer recommended
**Superseded**: Replaced by newer decision

## Integration with Development

### Link to Code

```markdown
## Implementation

- PR #123: Initial implementation
- File: `src/database/connection.ts`
- Config: `config/database.yml`
```

### Track Progress

```markdown
## Status: Accepted

**Implementation**: In Progress (60%)

- [x] Database installed
- [x] Schema migrated
- [ ] Connection pooling configured
- [ ] Monitoring setup
```

## Common Pitfall: Avoiding

Don't:
- Write what you'll build (that's a design doc)
- Document every small choice
- Skip alternatives section
- Make it a sales pitch
- Leave out trade-offs

Do:
- Explain why this is the right choice
- Show what you considered
- Be honest about downsides
- Make it easy to revisit
- Update status as things evolve

## Templates by Decision Type

### Technology Choice

Focus on:
- Ecosystem fit
- Team expertise
- Long-term support
- License/cost

### Pattern/Approach

Focus on:
- Problem it solves
- When to use/not use
- Examples in codebase
- Trade-offs

### Infrastructure

Focus on:
- Scale requirements
- Cost implications
- Operational complexity
- Disaster recovery

### Integration

Focus on:
- Interface contracts
- Versioning strategy
- Error handling
- Migration path
