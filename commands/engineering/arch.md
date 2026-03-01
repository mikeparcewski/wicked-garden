---
description: Architecture analysis and design recommendations
argument-hint: "[component or system] [--scope module|service|system]"
---

# /wicked-garden:engineering:arch

Analyze architecture of a component, service, or system. Evaluate design decisions, identify improvements, and recommend patterns.

## Instructions

### 1. Define Scope

Determine what to analyze:
- **module**: Single module/package structure
- **service**: Service boundaries and interfaces
- **system**: Full system architecture

If not specified, infer from context or ask.

### 2. Explore Structure

Map the architecture:
- Directory structure and organization
- Key entry points and interfaces
- Dependencies (internal and external)
- Data flow patterns

### 3. Dispatch Architecture Analysis

For module/service scope:
```python
Task(
    subagent_type="wicked-garden:engineering:system-designer",
    prompt="""Analyze the architecture of this component.

## Component
{component name}

## Structure
{directory layout}

## Key Files
{list of important files}

## Evaluation Checklist
1. Component boundaries and responsibilities
2. Interface design and contracts
3. Dependency management
4. Coupling and cohesion

## Return Format
Provide assessment with strengths, concerns, and recommendations.
"""
)
```

For system scope:
```python
Task(
    subagent_type="wicked-garden:engineering:solution-architect",
    prompt="""Analyze the system architecture.

## Components
{list of major components}

## Evaluation Checklist
1. System decomposition
2. Communication patterns
3. Data architecture
4. Scalability considerations
5. Operational concerns

## Return Format
Provide overview, assessment (strengths + concerns), and strategic recommendations.
"""
)
```

### 4. Optional: Data Architecture

If data-heavy system:
```python
Task(
    subagent_type="wicked-garden:engineering:data-architect",
    prompt="""Analyze data architecture for this system.

## Evaluation Areas
- Schema design
- Data flow and ownership
- Storage decisions
- Query patterns

## Return Format
Assess each area with recommendations and trade-offs.
"""
)
```

### 5. Check for Scope Creep and Unauthorized Changes

If reviewing changes (not greenfield design), evaluate:

**Unauthorized Architectural Changes (flag as HIGH)**:
- New service boundaries or abstractions not in the original requirements
- Changed communication patterns (sync→async, REST→GraphQL) without discussion
- Modified data ownership or storage decisions beyond the task scope
- Introduced new dependencies or frameworks not requested

**Scope Creep (flag as MEDIUM)**:
- Components restructured beyond what the task required
- Interface changes that ripple beyond the target area
- "While I'm here" improvements that weren't part of the ask
- Performance optimizations mixed into unrelated feature work

If architectural overstepping is detected, add an **Architectural Scope Concerns** section to the output.

### 6. Present Analysis

```markdown
## Architecture Analysis: {component/system}

### Overview
{high-level description}

### Current Architecture

#### Structure
```
{simplified directory tree or component diagram}
```

#### Key Components
| Component | Responsibility | Dependencies |
|-----------|----------------|--------------|
| {name} | {purpose} | {deps} |

#### Patterns Used
- {pattern}: {where and why}

### Assessment

#### Strengths
- {positive aspect}

#### Concerns
- **{issue}**: {description and impact}

### Recommendations

#### Quick Wins
1. {low-effort improvement}

#### Strategic Changes
1. {larger architectural improvement with rationale}

### Trade-offs
| Decision | Pros | Cons |
|----------|------|------|
| {decision} | {benefits} | {drawbacks} |
```
