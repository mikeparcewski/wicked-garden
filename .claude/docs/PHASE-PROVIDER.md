# Phase Provider Contract

## Overview

A **Phase Provider** is a plugin that implements a workflow phase for wicked-crew. Instead of hardcoding phase logic in crew, providers declare their capabilities via a `phase.json` contract.

## Contract Schema

Each phase provider exposes a `phase.json` file in their plugin root:

```json
{
  "$schema": "https://wicked.garden/schemas/phase-provider.json",
  "version": "1.0",
  "provider": {
    "name": "wicked-qe",
    "phases": ["qe", "validation", "testing"]
  },
  "phases": {
    "qe": {
      "name": "Quality Engineering",
      "description": "Define test strategy and quality gates before building",
      "order": 30,
      "category": "validation",

      "inputs": {
        "required": ["outcome", "design"],
        "optional": ["task-breakdown", "architecture"]
      },

      "outputs": {
        "artifacts": ["test-strategy.md", "gate-summary.md"],
        "signals": ["qe:strategy:completed:*"]
      },

      "gate": {
        "type": "blocking",
        "criteria": [
          "Test strategy document exists",
          "Quality gates defined",
          "Risk assessment complete"
        ],
        "approval": "explicit"
      },

      "execution": {
        "agent": "qe-orchestrator",
        "command": "/wicked-qe:analyze",
        "fallback": {
          "type": "inline",
          "prompt": "Define test strategy based on design artifacts"
        }
      },

      "integrations": {
        "primary": ["wicked-kanban"],
        "optional": ["wicked-product", "wicked-mem"]
      }
    }
  }
}
```

## Schema Fields

### Provider Metadata

| Field | Type | Description |
|-------|------|-------------|
| `provider.name` | string | Plugin name (must match plugin.json) |
| `provider.phases` | string[] | Phase identifiers this plugin provides |

### Phase Definition

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable phase name |
| `description` | string | What this phase accomplishes |
| `order` | number | Position in workflow (10-100, multiples of 10) |
| `category` | string | Phase category: `ideation`, `planning`, `validation`, `execution`, `review` |

### Inputs

| Field | Type | Description |
|-------|------|-------------|
| `inputs.required` | string[] | Artifacts that MUST exist before phase starts |
| `inputs.optional` | string[] | Artifacts that enhance phase if present |

Standard artifact identifiers:
- `outcome` - Desired outcome definition
- `design` - Design/architecture artifacts
- `task-breakdown` - Task list with estimates
- `test-strategy` - QE test strategy
- `build-output` - Build phase deliverables

### Outputs

| Field | Type | Description |
|-------|------|-------------|
| `outputs.artifacts` | string[] | Files created by this phase |
| `outputs.signals` | string[] | Events emitted on completion |

### Gate

| Field | Type | Description |
|-------|------|-------------|
| `gate.type` | string | `blocking` (must pass) or `advisory` (can proceed) |
| `gate.criteria` | string[] | Conditions for gate to pass |
| `gate.approval` | string | `explicit` (user must approve), `automatic` (pass if criteria met) |

### Execution

| Field | Type | Description |
|-------|------|-------------|
| `execution.agent` | string | Agent to dispatch for this phase |
| `execution.command` | string | Skill/command to invoke |
| `execution.fallback` | object | What to do if primary unavailable |
| `execution.fallback.type` | string | `inline` (prompt-based) or `skip` |
| `execution.fallback.prompt` | string | Instructions for inline fallback |

### Integrations

| Field | Type | Description |
|-------|------|-------------|
| `integrations.primary` | string[] | Plugins that SHOULD be available |
| `integrations.optional` | string[] | Plugins that enhance if available |

## Order Guidelines

Phases are ordered by `order` field (10-100):

| Range | Category | Examples |
|-------|----------|----------|
| 10-20 | Ideation | clarify, brainstorm, research |
| 21-40 | Planning | design, architecture, requirements |
| 41-60 | Validation | qe, security-review, accessibility |
| 61-80 | Execution | build, implement, integrate |
| 81-100 | Review | code-review, acceptance, retrospective |

## Discovery

Crew discovers phase providers by:

1. Scanning installed plugins for `phase.json`
2. Validating schema compliance
3. Building phase registry with capabilities

```bash
# Discovery pseudocode
for plugin in $(claude mcp list); do
  if [ -f "$plugin/phase.json" ]; then
    validate_and_register "$plugin/phase.json"
  fi
done
```

## Phase Provider Examples

### wicked-qe (QE Phase)

```json
{
  "provider": { "name": "wicked-qe", "phases": ["qe"] },
  "phases": {
    "qe": {
      "name": "Quality Engineering",
      "order": 45,
      "category": "validation",
      "inputs": { "required": ["outcome", "design"] },
      "outputs": {
        "artifacts": ["test-strategy.md", "test-matrix.md"],
        "signals": ["qe:strategy:completed:success"]
      },
      "gate": { "type": "blocking", "approval": "explicit" },
      "execution": {
        "agent": "qe-orchestrator",
        "command": "/wicked-qe:analyze"
      }
    }
  }
}
```

### wicked-product (Review Phase)

```json
{
  "provider": { "name": "wicked-product", "phases": ["review"] },
  "phases": {
    "review": {
      "name": "Code Review",
      "order": 85,
      "category": "review",
      "inputs": { "required": ["build-output"] },
      "outputs": {
        "artifacts": ["review-report.md"],
        "signals": ["lens:review:completed:*"]
      },
      "gate": { "type": "blocking", "approval": "explicit" },
      "execution": {
        "command": "/wicked-engineering:review"
      }
    }
  }
}
```

### wicked-jam (Clarify Phase)

```json
{
  "provider": { "name": "wicked-jam", "phases": ["clarify", "brainstorm"] },
  "phases": {
    "clarify": {
      "name": "Clarify & Brainstorm",
      "order": 15,
      "category": "ideation",
      "inputs": { "required": [] },
      "outputs": {
        "artifacts": ["outcome.md", "decisions.md"],
        "signals": ["jam:brainstorm:completed:success"]
      },
      "gate": { "type": "blocking", "approval": "explicit" },
      "execution": {
        "command": "/wicked-jam:brainstorm",
        "fallback": { "type": "inline", "prompt": "Facilitate outcome clarification" }
      }
    }
  }
}
```

## Crew as Orchestrator

With phase providers, crew's responsibilities narrow to:

### Core Orchestrator Functions

1. **Workflow Management**
   - Load workflow template
   - Determine phase sequence
   - Track current phase

2. **Phase Routing**
   - Discover available providers
   - Route `/execute` to appropriate provider
   - Handle provider unavailability

3. **Gate Enforcement**
   - Evaluate gate criteria
   - Block or allow progression
   - Handle explicit approvals

4. **State Management**
   - Maintain project.md state
   - Track phase status
   - Emit coordination signals

### What Crew No Longer Does

- ❌ Implement phase-specific logic
- ❌ Hardcode phase sequence
- ❌ Own phase-specific agents
- ❌ Define phase deliverables

## Workflow Templates

Crew provides workflow templates that compose phases:

### Classic (Default)

```yaml
name: classic
description: Traditional software development flow
phases:
  - clarify   # order: 15
  - design    # order: 30
  - qe        # order: 45
  - build     # order: 70
  - review    # order: 85
```

### Simple

```yaml
name: simple
description: Minimal flow for small changes
phases:
  - clarify   # order: 15
  - build     # order: 70
  - review    # order: 85
```

### Security-First

```yaml
name: security-first
description: Security-focused development
phases:
  - clarify          # order: 15
  - design           # order: 30
  - security-review  # order: 50 (from wicked-security provider)
  - qe               # order: 55
  - build            # order: 70
  - security-audit   # order: 80
  - review           # order: 85
```

## Backward Compatibility

### Classic Mode

Existing projects automatically use classic mode:
- Fixed phase sequence: clarify → design → qe → build → review
- Crew's built-in fallbacks for missing providers
- No configuration required

### Migration

Existing projects work without changes. To opt into new workflows:

```bash
# In project.md frontmatter
---
workflow: simple  # or security-first, custom, etc.
---
```

## Signals

Phase providers emit signals for ecosystem coordination:

```
[provider:phase:action:status]

Examples:
- [qe:strategy:completed:success]
- [lens:review:completed:needs-changes]
- [jam:brainstorm:completed:success]
```

Other plugins can subscribe to these signals via hooks.

## Validation

The `wg-validate` command checks phase.json:

1. Schema compliance
2. Required fields present
3. Order values valid (10-100)
4. No duplicate phase identifiers
5. Execution command exists
