# Workflow Templates

## Overview

Workflow templates define phase sequences for different project types. Crew selects or recommends templates based on project context.

## Template Format

```yaml
name: template-name
description: What this workflow is for
version: "1.0"

phases:
  - id: phase-id
    provider: plugin-name        # Which plugin provides this phase
    required: true|false         # Can phase be skipped?
    gate:
      type: blocking|advisory
      approval: explicit|automatic

conditions:
  suggest_when:                  # When to recommend this template
    - condition description
  avoid_when:
    - condition description
```

## Standard Templates

### Classic

The default workflow for most software development projects.

```yaml
name: classic
description: Traditional software development with QE shift-left
version: "1.0"

phases:
  - id: clarify
    provider: wicked-jam
    required: true
    gate: { type: blocking, approval: explicit }

  - id: design
    provider: wicked-crew        # Built-in design phase
    required: true
    gate: { type: blocking, approval: explicit }

  - id: qe
    provider: wicked-qe
    required: true
    gate: { type: blocking, approval: explicit }

  - id: build
    provider: wicked-crew        # Built-in with implementer agent
    required: true
    gate: { type: blocking, approval: explicit }

  - id: review
    provider: wicked-product
    required: true
    gate: { type: blocking, approval: explicit }

conditions:
  suggest_when:
    - New feature development
    - Significant refactoring
    - Multi-file changes
    - Team collaboration needed
  avoid_when:
    - Simple bug fixes
    - Documentation-only changes
```

### Simple

Minimal workflow for straightforward changes.

```yaml
name: simple
description: Streamlined flow for small, well-understood changes
version: "1.0"

phases:
  - id: clarify
    provider: wicked-jam
    required: false              # Can skip if scope is clear
    gate: { type: advisory, approval: automatic }

  - id: build
    provider: wicked-crew
    required: true
    gate: { type: blocking, approval: explicit }

  - id: review
    provider: wicked-product
    required: true
    gate: { type: blocking, approval: explicit }

conditions:
  suggest_when:
    - Bug fix with known cause
    - Minor enhancements
    - Single-file changes
    - Clear requirements provided
  avoid_when:
    - Complex features
    - Architectural changes
    - Uncertain scope
```

### Research

For exploratory work where the path isn't clear.

```yaml
name: research
description: Exploratory workflow with iteration
version: "1.0"

phases:
  - id: clarify
    provider: wicked-jam
    required: true
    gate: { type: blocking, approval: explicit }

  - id: explore
    provider: wicked-search      # Research phase
    required: true
    gate: { type: advisory, approval: automatic }

  - id: prototype
    provider: wicked-crew
    required: true
    gate: { type: advisory, approval: explicit }

  - id: validate
    provider: wicked-qe
    required: false
    gate: { type: advisory, approval: automatic }

  - id: iterate
    provider: wicked-crew        # Can loop back to explore
    required: false
    gate: { type: advisory, approval: explicit }

conditions:
  suggest_when:
    - New technology evaluation
    - Architecture exploration
    - Spike or proof-of-concept
    - Uncertain feasibility
  avoid_when:
    - Well-understood domain
    - Production-critical path
```

### Security-First

For security-sensitive development.

```yaml
name: security-first
description: Security-focused development with threat modeling
version: "1.0"

phases:
  - id: clarify
    provider: wicked-jam
    required: true
    gate: { type: blocking, approval: explicit }

  - id: threat-model
    provider: wicked-security    # Future provider
    required: true
    gate: { type: blocking, approval: explicit }
    fallback:
      type: inline
      prompt: "Identify threat vectors and attack surfaces"

  - id: design
    provider: wicked-crew
    required: true
    gate: { type: blocking, approval: explicit }

  - id: security-review
    provider: wicked-product
    config:
      perspectives: [security]
    required: true
    gate: { type: blocking, approval: explicit }

  - id: qe
    provider: wicked-qe
    config:
      focus: [security-tests, penetration]
    required: true
    gate: { type: blocking, approval: explicit }

  - id: build
    provider: wicked-crew
    required: true
    gate: { type: blocking, approval: explicit }

  - id: security-audit
    provider: wicked-product
    config:
      perspectives: [security, dev]
    required: true
    gate: { type: blocking, approval: explicit }

  - id: review
    provider: wicked-product
    required: true
    gate: { type: blocking, approval: explicit }

conditions:
  suggest_when:
    - Authentication/authorization changes
    - Payment or financial features
    - PII handling
    - External API integration
    - Compliance requirements (SOC2, HIPAA, etc.)
  avoid_when:
    - Internal tooling
    - Non-sensitive data
```

### Documentation

For documentation-focused work.

```yaml
name: documentation
description: Documentation and knowledge capture
version: "1.0"

phases:
  - id: clarify
    provider: wicked-jam
    required: true
    gate: { type: advisory, approval: automatic }

  - id: research
    provider: wicked-search
    required: false
    gate: { type: advisory, approval: automatic }

  - id: write
    provider: wicked-crew
    config:
      agent: documentarian       # Future specialized agent
    required: true
    gate: { type: blocking, approval: explicit }

  - id: review
    provider: wicked-product
    config:
      perspectives: [product, dev]
    required: true
    gate: { type: blocking, approval: explicit }

conditions:
  suggest_when:
    - README updates
    - API documentation
    - User guides
    - Architecture decision records
  avoid_when:
    - Code changes
```

## Template Selection

### AI-Driven Selection

Crew analyzes project context to recommend templates:

```
Factors considered:
├── Scope size (files, lines)
├── Change type (feature, bug, refactor, docs)
├── Domain sensitivity (security, compliance)
├── Existing artifacts (design docs, test plans)
├── User history (preferred workflow patterns)
└── Team context (solo vs collaborative)
```

### User Override

Users can always override the recommendation:

```bash
# Explicit template selection
/wicked-crew:start --workflow simple "Fix the login bug"

# Change mid-project
/wicked-crew:workflow research
```

### Template in Project

The active template is stored in project.md:

```yaml
---
name: my-project
workflow: classic    # Active template
current_phase: design
---
```

## Custom Templates

Users can define custom templates in:

```
~/.something-wicked/wicked-crew/templates/
├── my-team-standard.yaml
└── compliance-heavy.yaml
```

### Custom Template Example

```yaml
name: my-team-standard
description: Our team's standard workflow
version: "1.0"
extends: classic                 # Inherit from classic

phases:
  - id: clarify
    provider: wicked-jam
    required: true
    gate: { type: blocking, approval: explicit }

  # Insert architecture review after design
  - id: arch-review
    provider: wicked-product
    config:
      perspectives: [architecture]
    after: design                # Position hint
    required: true
    gate: { type: blocking, approval: explicit }

  # Continue with inherited phases...
```

## Phase Composition

Templates compose phases from available providers. If a provider is unavailable:

| Situation | Behavior |
|-----------|----------|
| Provider installed | Use provider's execution |
| Provider has fallback | Use fallback definition |
| No fallback defined | Use crew's inline fallback |
| Phase marked `required: false` | Skip phase |

## Signals

Workflow events for ecosystem coordination:

```
[crew:workflow:selected:success]    - Template selected
[crew:workflow:phase:started:*]     - Phase execution began
[crew:workflow:phase:completed:*]   - Phase finished
[crew:workflow:gate:passed:*]       - Gate criteria met
[crew:workflow:gate:failed:*]       - Gate criteria not met
[crew:workflow:completed:success]   - All phases complete
```

## Template Validation

The `wg-validate` command checks templates:

1. All phase IDs exist in provider registry
2. Phase ordering is valid
3. Gate configurations are complete
4. Conditions are well-formed
5. No circular dependencies
