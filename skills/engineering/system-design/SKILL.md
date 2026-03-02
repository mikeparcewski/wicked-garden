---
name: system-design
description: |
  Define component boundaries, module organization, and interface contracts.
  Break down systems into cohesive, loosely-coupled components.

  Use when: "component design", "module boundaries", "how should we organize this",
  "component interfaces", "dependency management", "system decomposition"
---

# System Design Skill

Decompose systems into well-defined components with clear boundaries and interfaces.

## Purpose

Transform architecture into concrete components:
- Component identification and boundaries
- Interface definition
- Dependency management
- Module organization

## Process

### 1. Identify Components

Ask:
- What are major capabilities?
- What changes together?
- What has different scaling needs?
- What domain concepts exist?

### 2. Define Boundaries

Apply:
- **High Cohesion** - Related functionality together
- **Low Coupling** - Minimal dependencies
- **Single Responsibility** - One reason to change
- **Information Hiding** - Encapsulate internals

### 3. Design Interfaces

For each component:
- Public API (what it exposes)
- Dependencies (what it needs)
- Events (what it publishes/subscribes)
- Data contracts (I/O structures)

### 4. Document

Creates in `phases/design/`:
```
design/
├── components/
│   ├── overview.md
│   ├── auth-component.md
│   └── dependencies.mmd
└── interfaces/
    └── component-api.md
```

## Component Patterns

**Layered** - Presentation → Application → Domain → Infrastructure
**Hexagonal** - Business logic with adapter ports
**Plugin** - Core system with pluggable extensions

See component patterns in refs/ (patterns-layered-pattern.md, patterns-facade-pattern.md).

## Dependency Management

### Rules

1. **Acyclic** - No circular dependencies
2. **Unidirectional** - Dependencies flow one way
3. **Stable** - Depend on stable abstractions
4. **Explicit** - Declare in constructor/config

### Common Anti-Patterns

**God Object** - One component does everything
**Fix**: Split by responsibility

**Feature Envy** - Component uses another's data extensively
**Fix**: Move functionality to data owner

**Circular Dependencies** - A depends on B, B depends on A
**Fix**: Extract shared logic or use events

**Leaky Abstraction** - Internal details exposed
**Fix**: Refine public interface

See dependency guides in refs/ (dependencies-dependency-principles.md, dependencies-best-practices.md).

## Integration

### With Architecture Skill

Implements high-level architecture:
- Takes architectural decisions
- Maps to concrete components
- Validates feasibility

### With Integration Skill

Provides boundaries for:
- API design
- Service contracts
- Event schemas

### With wicked-crew

Called during design phase after architecture.

## Events

- `[arch:components:defined:success]` - Components designed
- `[arch:interface:defined:success]` - Interface documented
- `[arch:dependency:analyzed:success]` - Dependencies validated

## Tips

1. **Start with Boundaries** - Define what's in/out first
2. **Think in Interfaces** - Design API before implementation
3. **Keep It Simple** - Don't over-decompose
4. **Test Boundaries** - Use contract tests
5. **Refactor Gradually** - Small, safe steps
6. **Document Dependencies** - Make them explicit

## Reference Materials

- Component Template:
  - [Structure & API](refs/component-template-structure.md)
  - [Lifecycle & Deployment](refs/component-template-lifecycle.md)
  - [Maintenance & Examples](refs/component-template-maintenance.md)
- Interface Template:
  - [Structure & Contracts](refs/interface-template-structure.md)
  - [Testing & Operations](refs/interface-template-lifecycle.md)
  - [Examples & Tips](refs/interface-template-maintenance.md)
- Component Patterns:
  - [Layered](refs/patterns-layered-pattern.md)
  - [Plugin Architecture](refs/patterns-plugin-architecture.md)
  - [Facade](refs/patterns-facade-pattern.md)
  - [Dependency Injection](refs/patterns-dependency-injection.md)
- Dependencies:
  - [Principles](refs/dependencies-dependency-principles.md)
  - [Tracking](refs/dependencies-dependency-tracking.md)
  - [Best Practices](refs/dependencies-best-practices.md)
- Anti-Patterns:
  - [God Object](refs/anti-patterns-god-object.md)
  - [Big Ball of Mud](refs/anti-patterns-big-ball-of-mud.md)
  - [Circular Dependencies](refs/anti-patterns-circular-dependencies.md)
  - [Feature Envy](refs/anti-patterns-feature-envy.md)
