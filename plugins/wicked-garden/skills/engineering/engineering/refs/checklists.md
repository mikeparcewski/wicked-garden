# Engineering Review Checklists

## Structure Checklist
- [ ] Follows established patterns
- [ ] Appropriate abstraction level
- [ ] Clear boundaries/interfaces
- [ ] No circular dependencies
- [ ] Separation of concerns

## Quality Checklist
- [ ] Clear naming
- [ ] No unnecessary duplication
- [ ] Appropriate comments (not excessive)
- [ ] Consistent style
- [ ] Single responsibility

## Error Handling Checklist
- [ ] Errors handled appropriately
- [ ] No swallowed exceptions
- [ ] Meaningful error messages
- [ ] Recovery strategies

## Maintainability Checklist
- [ ] Easy to understand
- [ ] Easy to modify
- [ ] No magic numbers/strings
- [ ] Configuration externalized

## Performance Checklist
- [ ] No obvious N+1 queries
- [ ] Appropriate data structures
- [ ] No unnecessary computation
- [ ] Caching where appropriate

## Common Issues to Watch For

### Code Smells
- Magic numbers/strings (use constants)
- Long functions (break into smaller)
- Deep nesting (refactor to early returns)
- Duplicated code (extract to shared)
- Poor naming (rename for clarity)
- Missing error handling
- Resource leaks (unclosed connections)

### Good Patterns
- Single responsibility
- Clear separation of concerns
- Defensive programming
- Meaningful abstractions
- Consistent error handling

## Agent Overstepping Checklist

Detect patterns where AI agents make changes beyond what was requested:

### Unnecessary Changes (HIGH)
- [ ] Code modified that wasn't part of the task scope
- [ ] Working logic replaced with "simplified" alternatives
- [ ] Variable/function renames unrelated to the task
- [ ] Import reorganization or style changes outside scope
- [ ] Added abstractions or helpers for one-time operations

### Commented-Out Code (HIGH)
- [ ] Working code commented out instead of removed
- [ ] Logic replaced with TODO comments
- [ ] Conditional blocks disabled via comments
- [ ] Backward-compatibility shims with "// removed" markers

### Over-Engineering (MEDIUM)
- [ ] New configuration options nobody asked for
- [ ] Feature flags for non-flagged features
- [ ] Added error handling for impossible scenarios
- [ ] Premature abstractions ("just in case" utilities)
- [ ] Extra validation layers beyond system boundaries

### Scope Creep Indicators
- [ ] Files modified that weren't mentioned in the task
- [ ] Refactoring mixed into bug fixes
- [ ] Style changes bundled with feature work
- [ ] Documentation updates for unchanged code

## Severity Guidelines

- **HIGH**: Will cause bugs, broken patterns, production issues, major maintainability problems
- **MEDIUM**: Should fix, not blocking, tech debt accumulation
- **LOW**: Nice to have, style preferences, minor improvements
