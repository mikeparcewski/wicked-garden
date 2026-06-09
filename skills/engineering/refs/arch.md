# arch — architecture analysis rubric

Full checklist and output format for architecture review at module/service/system scope.
Use `engineering:arch` for component/system-level review; use `engineering:review` for code-level review.

## Scope routing

- `--scope module` or `--scope service`: evaluate component boundaries and responsibilities
- `--scope system`: evaluate decomposition, communication patterns, and data architecture
- Infer from context if absent (single directory = module; multiple services = system)

## Module / service analysis checklist

### Boundaries and responsibilities
- [ ] Component responsibility is clearly scoped (single reason to change)
- [ ] No responsibility bleed — one component isn't doing another's job
- [ ] Interface contracts explicit: public API vs internals clearly separated
- [ ] Information hiding: internal implementation not exposed through boundaries

### Coupling and cohesion
- [ ] High cohesion — related things grouped together
- [ ] Low coupling — minimal dependencies on other components
- [ ] Coupling type: prefer Data > Message > no coupling; avoid Common/Content coupling
- [ ] No circular dependencies; clear dependency direction

### Dependency management
- [ ] Dependencies declared, not implicit
- [ ] No version mismatches or conflicting transitive deps
- [ ] Abstraction layers used to isolate external dependencies

### If reviewing a diff
- [ ] No unauthorized new boundaries added without approval
- [ ] No communication pattern changes (sync→async, REST→event) without ADR
- [ ] No new external dependencies added outside change scope
- [ ] No scope creep ("while I'm here" restructuring)

### Output format — module/service

```markdown
## Architecture Review: {name} (module/service)

### Strengths
- {strength with evidence}

### Concerns

| Severity | Concern | Location | Recommendation |
|----------|---------|----------|----------------|
| HIGH/MED/LOW | {concern} | `{file or component}` | {action} |

### Recommendations
1. {primary with rationale}
2. {secondary}

### Trade-off Table
| Option | Pros | Cons |
|--------|------|------|
```

## System analysis checklist

### Decomposition
- [ ] Service boundaries align with domain/team ownership
- [ ] Each service independently deployable and rollback-able
- [ ] Services not chatty (many synchronous calls = consider merge or BFF)
- [ ] No distributed monolith (services coupled by shared DB or step-lock deployments)

### Communication patterns
- [ ] Sync (REST/gRPC) vs async (events/queue) chosen deliberately per use case
- [ ] Event contracts versioned and documented
- [ ] Circuit breakers and timeouts on all sync calls
- [ ] Idempotency for all async consumers

### Data architecture
- [ ] Each service owns its data — no shared DB across service boundaries
- [ ] Data residency and replication strategy documented
- [ ] CQRS / event sourcing used only where justified, not default
- [ ] Eventual consistency acknowledged where applicable

### Scalability and operations
- [ ] Stateless services where possible (state in DB/cache, not local)
- [ ] Horizontal scaling possible for each service
- [ ] Observability: each service emits structured logs, metrics, traces
- [ ] Failure modes documented: what degrades gracefully vs fails hard

### If reviewing a diff
- [ ] No new inter-service synchronous dependencies added
- [ ] No shared state introduced across service boundaries
- [ ] No scope creep beyond the stated system change

### Output format — system

```markdown
## Architecture Review: {name} (system)

### Overview
{one paragraph system description}

### Strengths
- {strength}

### Concerns

| Severity | Concern | Service/Component | Recommendation |
|----------|---------|-------------------|----------------|
| HIGH/MED/LOW | {concern} | {target} | {action} |

### Strategic Recommendations
1. {primary — long-term direction}
2. {secondary}

### Trade-off Table
| Decision | Current | Alternative | When to revisit |
|----------|---------|-------------|-----------------|

### ADR Candidates
- {decision worth recording as an ADR}
```

## Architecture principles (apply to both scopes)

- **SOLID**: Single responsibility, open/closed, Liskov, interface segregation, dependency inversion
- **DRY** (applied judiciously): don't force DRY across unrelated domains
- **YAGNI**: flag speculative generality — build for now, not speculation
- **Least Privilege**: minimal permissions and surface area
- **Fail-fast over silent corruption**: errors should surface immediately, not propagate silently
