---
name: architecture
description: |
  Complete solution architecture design with patterns, decisions, and diagrams.
  Define overall system structure, technology choices, and architectural trade-offs.

  Use when: "design the architecture", "what's the overall structure",
  "architecture patterns", "technology stack", "system architecture"
---

# Architecture Skill

Design end-to-end solutions with clear patterns, decisions, and visual documentation.

## Purpose

Move from requirements to implementable architecture through:
- Pattern selection and justification
- Technology stack decisions
- Cross-cutting concern planning
- Architectural Decision Records (ADRs)

## Process

### 1. Gather Context

- Read outcome document
- Analyze requirements
- Identify constraints
- Understand scale needs

### 2. Select Patterns

Choose architectural style:
- **Monolithic** - Simple deployment, single codebase
- **Microservices** - Independent scaling, team autonomy
- **Serverless** - Event-driven, auto-scaling
- **Event-Driven** - Loose coupling, async
- **Layered** - Clear separation, traditional

### 3. Make Decisions

Recommend stack based on:
- Requirements fit
- Team expertise
- Ecosystem maturity
- Cost considerations

### 4. Document

Creates in `phases/design/`:
```
design/
├── architecture.md
├── decisions/
│   ├── 001-architecture-style.md
│   └── 002-tech-stack.md
└── diagrams/
    └── system-context.mmd
```

## Output Format

See [ADR Template](refs/adr-template.md) for decision records.

See [Architecture Template](refs/architecture-template.md) for full structure.

## Integration

### With wicked-crew

Auto-engaged during design phase.

Publishes: `[arch:design:completed:success]`

### With wicked-qe

Architecture informs test strategy:
- Critical paths
- Failure modes
- Performance targets

### With wicked-kanban

Track work with ADR links:
```bash
TodoWrite "ADR-001" --reference "phases/design/decisions/001.md"
```

## Architectural Thinking

### Balance Trade-offs

- **Simplicity vs Flexibility** - Easy now vs extensible later
- **Performance vs Maintainability** - Fast vs readable
- **Coupling vs Duplication** - DRY vs independent
- **Build vs Buy** - Control vs speed

### Apply Principles

- **SOLID** - Single responsibility, dependency inversion
- **YAGNI** - Build for now, not speculation
- **Separation of Concerns** - Clear boundaries

### Consider NFRs

- **Scalability** - Users, growth rate
- **Security** - Threats, compliance
- **Performance** - Latency, throughput
- **Reliability** - Uptime, DR
- **Maintainability** - Team, skillset

### Detect Scope Creep

When reviewing changes (not greenfield):
- Flag unauthorized architectural changes (new boundaries, changed patterns)
- Flag "while I'm here" improvements beyond the task scope
- Flag components restructured beyond what was requested

## Common Patterns

### Layered
```
UI → Application → Domain → Infrastructure
```
**Use**: Traditional apps, clear separation

### Microservices
```
API Gateway → Services
```
**Use**: Large teams, independent deployment

### Event-Driven
```
Producers → Bus → Consumers
```
**Use**: Async workflows, loose coupling

See [Pattern Catalog](refs/patterns.md) for detailed examples.

## Events

- `[arch:design:completed:success]` - Architecture done
- `[arch:decision:documented:success]` - ADR created
- `[arch:diagram:generated:success]` - Diagram created

## Tips

1. **Start Simple** - Don't over-engineer
2. **Document Decisions** - Future you will thank you
3. **Show Alternatives** - Explain your choices
4. **Use Diagrams** - Visual communication
5. **Make it Scannable** - Quick understanding

## Reference Materials

- [ADR Template](refs/adr-template.md)
- [Architecture Document Template](refs/architecture-template.md)
- [Pattern Catalog](refs/patterns.md)
- Example ADRs:
  - [E-Commerce & Analytics](refs/examples-ecommerce-analytics.md)
  - [SaaS & Trading](refs/examples-saas-trading.md)
