---
name: engineering
description: |
  Senior engineering guidance on implementation, code quality, and maintainability. Use when reviewing
  code for R1-R6 standards violations (dead code, bare panics, magic values, swallowed errors,
  unbounded ops, god functions) or getting cross-cutting implementation advice.
  NOT for architecture decisions (use the architecture skill) or debugging (use the debugging skill).
---

# Engineering Skill

Provide senior engineering guidance on code quality, architecture, and implementation.

## What This Skill Does

1. **Implementation Planning** - Guide on how to build features with quality
2. **Code Review** - Assess quality, patterns, maintainability
3. **Architecture Guidance** - Evaluate structure and design decisions
4. **Best Practices** - Share knowledge on conventions and patterns

## Key Principles

### Code Quality
- Clear naming and organization
- DRY (Don't Repeat Yourself)
- SOLID principles
- Consistent style

### Architecture
- Design patterns
- Separation of concerns
- Component boundaries
- Dependency management

### Maintainability
- Easy to understand and modify
- Easy to test
- Well-documented
- Error handling

### Performance
- Efficient algorithms and data structures
- Resource management
- Caching strategies

## Review Process

Use comprehensive checklists covering:
- Structure (patterns, abstractions, dependencies)
- Quality (naming, duplication, style)
- Error handling (recovery, messages)
- Maintainability (clarity, configuration)
- Performance (queries, data structures)
- **Agent overstepping** (unnecessary changes, commented-out code, scope creep)

See [refs/checklists.md](refs/checklists.md) for detailed review checklists and severity guidelines.

## Output Formats

Provide structured guidance for:
- Implementation planning with approach and steps
- Code reviews with strengths, issues, and recommendations

See [refs/templates.md](refs/templates.md) for output templates and focus areas.

## Integration with Specialists

Coordinate with specialized perspectives:
- **/wicked-garden:engineering:frontend** - React, CSS, browser-specific concerns
- **/wicked-garden:engineering:backend** - APIs, databases, server-side patterns
- **/wicked-garden:engineering:debugging** - Error investigation and root cause analysis

## Integration with wicked-crew

Engaged during:
- **Build Phase**: Implementation guidance and pattern recommendations
- **Review Phase**: Code quality and architecture review
- **Error Recovery**: When issues are encountered during development

## Notes

- Always explain the "why" behind recommendations
- Be constructive, not critical
- Offer alternatives with tradeoffs
- Encourage questions and discussion
