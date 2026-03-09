# Architectural Patterns: Advanced & Selection Guide

Serverless, Clean Architecture, CQRS, Service Mesh, pattern selection guide, and evolution strategy.

## Serverless Architecture

### Structure

```
┌─────────┐      ┌─────────────┐      ┌──────────┐
│ Client  │─────▶│ API Gateway │─────▶│ Lambda 1 │
└─────────┘      └─────────────┘      └────┬─────┘
                                            │
                        ┌───────────────────┤
                        │                   │
                  ┌─────▼─────┐      ┌─────▼─────┐
                  │ DynamoDB  │      │    S3     │
                  └───────────┘      └───────────┘
```

### When to Use

- Variable, unpredictable load
- Event-driven workloads
- Want minimal operations
- Pay-per-use model preferred
- Rapid prototyping

### Trade-offs

**Pros**:
- Auto-scaling
- Pay per execution
- No server management
- Fast deployment
- Built-in high availability

**Cons**:
- Cold start latency
- Vendor lock-in
- Debugging challenges
- Execution time limits
- Stateless constraints

## Clean Architecture

### Structure

```
┌────────────────────────────────────────┐
│         Frameworks & Drivers           │  (External)
│    Web, DB, UI, External Interfaces    │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│      Interface Adapters               │  (Adapters)
│   Controllers, Gateways, Presenters   │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│       Application Business Rules       │  (Use Cases)
│          Use Cases, Services           │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│     Enterprise Business Rules          │  (Entities)
│          Domain Entities               │
└────────────────────────────────────────┘

Dependencies point inward
```

### Dependency Rule

**Inner layers don't know about outer layers**
- Entities don't know about use cases
- Use cases don't know about controllers
- Controllers know about use cases

### When to Use

- Long-lived applications
- Complex business rules
- Need maximum testability
- Want framework independence

## CQRS (Command Query Responsibility Segregation)

### Structure

```
                    ┌──────────┐
                    │  Client  │
                    └─────┬────┘
                          │
              ┌───────────┴───────────┐
              │                       │
         ┌────▼─────┐           ┌────▼────┐
         │ Commands │           │ Queries │
         │  (Write) │           │  (Read) │
         └────┬─────┘           └────┬────┘
              │                      │
         ┌────▼─────┐           ┌────▼────┐
         │ Write DB │           │ Read DB │
         │ (Normal) │───sync───▶│(Denorm) │
         └──────────┘           └─────────┘
```

### When to Use

- Different read/write patterns
- High read/write ratio
- Complex queries needed
- Performance critical
- Event sourcing

### Trade-offs

**Pros**:
- Optimized reads and writes separately
- Scalability
- Clear separation
- Flexibility in models

**Cons**:
- Eventual consistency
- More complex
- Sync overhead
- Duplicate data

## Service Mesh

### Structure

```
┌─────────────────────────────────────────┐
│          Service Mesh Control Plane     │
│              (Istio, Linkerd)           │
└────────────┬────────────────────────────┘
             │ Configuration
┌────────────┼────────────────────────────┐
│            │                            │
│   ┌────────▼────────┐   ┌──────────┐   │
│   │  Service A      │   │ Service B│   │
│   │  ┌──────────┐   │   │┌────────┐│   │
│   │  │ Business │   │   ││Business││   │
│   │  │  Logic   │   │   ││ Logic  ││   │
│   │  └──────────┘   │   │└────────┘│   │
│   │  ┌──────────┐   │   │┌────────┐│   │
│   │  │  Sidecar │◄──┼───┼┤Sidecar ││   │
│   │  │  Proxy   │   │   ││ Proxy  ││   │
│   │  └──────────┘   │   │└────────┘│   │
│   └─────────────────┘   └──────────┘   │
└─────────────────────────────────────────┘
```

### When to Use

- Microservices at scale
- Need observability
- Complex routing/security
- Polyglot services

### Provides

- Service discovery
- Load balancing
- Circuit breaking
- Encryption (mTLS)
- Distributed tracing
- Traffic management

## Pattern Selection Guide

| Requirement | Recommended Pattern |
|-------------|-------------------|
| Simple CRUD app | Layered |
| Enterprise monolith | Clean/Hexagonal |
| Multiple teams | Microservices |
| Async workflows | Event-Driven |
| Minimal ops | Serverless |
| High read/write split | CQRS |
| Polyglot services | Microservices + Service Mesh |
| Domain complexity | Domain-Driven Design + Hexagonal |
| Variable load | Serverless or Event-Driven |
| Strict consistency | Layered or Monolithic |

## Anti-Patterns to Avoid

### Big Ball of Mud
Everything coupled, no clear structure
**Fix**: Introduce layers or hexagonal

### Golden Hammer
Using one pattern for everything
**Fix**: Match pattern to problem

### Analysis Paralysis
Over-architecting before understanding
**Fix**: Start simple, evolve

### Distributed Monolith
Microservices that must deploy together
**Fix**: Better boundaries or merge services

### Premature Optimization
Choosing complex patterns too early
**Fix**: YAGNI - start simple

## Combining Patterns

Patterns often work together:

- **Microservices + Event-Driven**: Services communicate via events
- **Hexagonal + DDD**: Isolated domain logic
- **CQRS + Event Sourcing**: Events as source of truth
- **Layered + Clean**: Clean architecture within layers
- **Microservices + Service Mesh**: Manage service complexity

## Evolution Strategy

```
Phase 1: Modular Monolith (Layered/Hexagonal)
    ↓
Phase 2: Extract High-Change Services
    ↓
Phase 3: Microservices for Core
    ↓
Phase 4: Event-Driven for Integration
    ↓
Phase 5: CQRS for Performance
```

Start simple, evolve based on real pain points.
