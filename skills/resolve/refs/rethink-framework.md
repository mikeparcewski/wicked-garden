# Rethink Framework

When to step back from fixing and consider redesigning. Not every issue needs a
rethink — but every issue deserves the question.

## The Rethink Test

Answer these five questions. If 3+ are "yes", consider a structural change:

1. **Recurrence**: Has this type of issue come up before in this area?
2. **Complexity**: Is the fix more complex than the thing it patches?
3. **Fragility**: Would the fix make things harder to change next time?
4. **Workaround**: Are we working around the design rather than with it?
5. **Regret**: If we'd known this need earlier, would we have built it differently?

## Rethink Strategies

### Invert the Dependency

**When**: A depends on B's internals, and the problem is in the coupling.
**How**: Have B expose what A needs. Or invert — have B call A.
**Risk**: Touches both sides. Test carefully.

### Split the Responsibility

**When**: One thing does too many jobs, and the problem is in their interaction.
**How**: Separate into distinct pieces with clear interfaces.
**Risk**: More pieces, but each is simpler. Split along natural boundaries.

### Replace Conditionals with Structure

**When**: Problem in a complex if/else chain handling different cases.
**How**: Define a base type and specialized variants. Route via registry/factory.
**Risk**: Over-engineering if only 2-3 cases. Good when cases grow.

### Make Invalid States Impossible

**When**: Problem from something being in a state that shouldn't exist.
**How**: Use types, enums, or state machines to constrain what's possible.
**Risk**: May require interface changes. Worth it for core concepts.

### Extract the Policy

**When**: Rules are embedded in infrastructure.
**How**: Pull rules into a separate, testable policy object.
**Risk**: Adds indirection. Justified when rules change frequently.

### Simplify by Removing

**When**: Problem is in unused or rarely-used functionality.
**How**: Delete it. Check usage, deprecate if needed, then remove.
**Risk**: Low — less surface area = fewer problems.

## Cost-Benefit Check

Before proposing a rethink, estimate:

```
Rethink Cost  = (things touched x complexity) + (test rewrite) + (review overhead)
Ongoing Cost  = (similar issues per quarter x fix time) + (confusion x ramp-up time)

If annualized Ongoing Cost > 2x Rethink Cost → rethink now
If Ongoing Cost < Rethink Cost → fix and document the debt
```

## Scope Control

Rethinks can expand without bounds. Constrain them:

1. **Time-box**: Set a maximum. If it takes longer, it's a separate project.
2. **Blast radius cap**: Touch at most N things. If more, split into phases.
3. **Quality parity**: New approach must have equal or better coverage before shipping.
4. **Rollback plan**: Ensure the old approach can be restored if needed.
