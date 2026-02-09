---
name: guide
description: |
  Provides personalized learning paths and first task recommendations. Use when a
  developer needs guidance on what to learn next, suggestions for first contributions,
  or milestone tracking. Creates actionable learning roadmaps.
---

# Learning Guide Skill

Accelerate developer ramp-up through personalized learning paths and actionable next steps.

## When to Use

- Developer asks "what should I work on?"
- Need suggestions for first contribution
- User says "guide", "learning path", "what's next", "where do I start"
- Onboarding checkpoint or milestone completion

## Guidance Types

**First Tasks**: Specific, achievable tasks (< 1 day) to build confidence
**Learning Path**: Phased roadmap (days to weeks) for skill building
**Milestones**: Progress tracking with checkpoints

## Guidance Framework

### Profile Developer

**Beginner**: New to stack/domain - needs hand-holding, docs first
**Intermediate**: Knows stack - can navigate, needs domain context
**Advanced**: Experienced - skip basics, suggest complex tasks

### Assess Codebase

**Simple** (< 1000 LOC): Contribute day 1
**Moderate** (1000-10000 LOC): 2-3 days exploration
**Complex** (> 10000 LOC): 1-2 weeks orientation

### Match Tasks

**Beginners**: Documentation, tests, logging
**Intermediate**: Bug fixes, small features, refactoring
**Advanced**: Architecture, performance, mentoring

## Task Discovery

### Find Good First Issues

1. Issue tracker: "good-first-issue" labels
2. TODO comments: `grep -r "TODO"`
3. Test coverage: Low coverage areas
4. Documentation: Outdated or missing
5. Code quality: Refactoring opportunities

### Validate Suitability

Good tasks have:
- ✓ Clear scope (< 1 day)
- ✓ Success criteria
- ✓ Limited dependencies
- ✓ Tests

Avoid:
- ✗ Vague requirements
- ✗ Cross-cutting changes
- ✗ Performance-critical
- ✗ No tests

## Output Templates

See [templates.md](refs/templates.md) for detailed first task and learning path templates.

Quick reference:

**First Tasks**: Profile → Quick wins → How to start → Success criteria → Resources

**Learning Path**: Phases (Foundation → Exploration → Contribution → Ownership) → Progress tracking

**Milestone**: Achievement → Learned → Next level → Progress

## Common Scenarios

**Brand New**: Orient → Fix typo → Add test → good-first-issue

**Stuck After Setup**: Trivial change → Trace flow → Read tests → Improve area

**Ready for Work**: Pick issue → Reproduce → Fix/test → Submit PR

**Experienced/New Domain**: Skip setup → Domain concepts → Business flows → Medium issue

## Integration

### With wicked-mem

```python
# Track progress
if has_plugin("wicked-mem"):
    progress = recall("onboarding_progress")
    if progress: "Last: {milestone}. Next: {next}?"

    # Store milestones
    store({"type": "milestone", "task": name, "completed": now()})
```

### With wicked-search

```bash
/wicked-search:code "TODO|FIXME"      # Find tasks
/wicked-search:docs "getting started" # Find resources
```

## Quality Checklist

- [ ] Tasks specific (file paths, commands)
- [ ] Time estimates realistic
- [ ] Success criteria measurable
- [ ] Resources linked
- [ ] Progressive difficulty
- [ ] Celebrates progress
- [ ] Provides escape hatches

## Reference

- [Templates](refs/templates.md) - Detailed output templates
- [Onboarding Checklist](../orient/refs/checklist.md) - Comprehensive day-by-day guide
