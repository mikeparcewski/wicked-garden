# Crew Core Capabilities

## Overview

The crew domain is the orchestration framework. It has:

1. **Orchestrator Skill** -- Rules and smart decisioning
2. **Built-in Subagents** -- Minimal fallbacks when specialist domains aren't matched
3. **Hook System** -- Event-driven coordination

## Orchestrator Skill

The brain of crew -- determines what specialist domains to engage.

### Phase Rules

Each phase has defined:
- **Purpose** -- What this phase accomplishes
- **Inputs** -- What's needed to start
- **Outputs** -- What must be produced
- **Gate criteria** -- What's checked before advancing

```yaml
phases:
  clarify:
    purpose: "Define what success looks like"
    inputs: [user_request]
    outputs: [outcome.md]
    gate: [outcome_defined, scope_clear]
    enhancers: [jam, product]

  research:
    purpose: "Understand existing context"
    inputs: [outcome]
    outputs: [research_findings]
    gate: [context_gathered]
    enhancers: [search]

  design:
    purpose: "Plan the approach"
    inputs: [outcome, research]
    outputs: [architecture, approach]
    gate: [approach_defined, risks_identified]
    enhancers: [product, engineering]

  gate:
    purpose: "Decide if ready to proceed"
    inputs: [phase_outputs]
    outputs: [gate_decision]
    gate: [criteria_evaluated]
    enhancers: [qe]

  build:
    purpose: "Implement the solution"
    inputs: [design, test_strategy]
    outputs: [implementation, tests]
    gate: [tests_pass, build_succeeds]
    enhancers: [engineering, platform]

  review:
    purpose: "Validate the work"
    inputs: [implementation]
    outputs: [review_findings, approval]
    gate: [issues_resolved]
    enhancers: [qe, product]
```

### Smart Decisioning

Crew analyzes input to determine specialist domains needed:

```python
def decide_specialists(user_input, context):
    domains = []

    # Complexity signals
    if is_complex(user_input):
        domains.append("delivery")  # Track progress

    # Security signals
    if has_security_signals(user_input):
        domains.append("platform")

    # Ambiguity signals
    if is_ambiguous(user_input):
        domains.append("jam")  # Brainstorm

    # Product signals
    if has_product_signals(user_input):
        domains.append("product")

    # Filter to available personas
    return filter_available(domains)
```

### Signal Detection

| Signal Type | Keywords/Patterns | Specialist Domains |
|-------------|-------------------|-------------------|
| Security | auth, encrypt, PII, credentials, token | platform |
| Performance | scale, load, optimize, latency | engineering, qe |
| Product | user, experience, flow, requirement | product |
| Ambiguity | ?, maybe, either, could, should we | jam |
| Complexity | multiple, system, integration, migrate | delivery |
| Data | pipeline, ETL, analytics, ML | data |
| Architecture | agent, plugin, tool, workflow | agentic, engineering |

## Built-in Subagents

When specialist domains aren't matched, crew uses minimal built-in agents.

### Facilitator (Clarify Fallback)

**When**: No jam domain signals detected

**Capabilities**:
- Structured questioning
- Outcome definition
- Scope boundaries

### Researcher (Research Fallback)

**When**: No specialist research signals

**Capabilities**:
- Codebase exploration (uses search domain if available)
- Pattern identification
- Dependency mapping

### Reviewer (Review Fallback)

**When**: No qe or product domain signals

**Capabilities**:
- Basic code review
- Obvious issue detection
- Checklist validation

### Implementer (Build Fallback)

**When**: No engineering domain signals

**Capabilities**:
- Code implementation
- Basic test writing
- Build execution

## Gate Enforcement

Crew enforces gates between phases.

### Simplified Review (Built-in)

When no specialist domains engaged:

```yaml
gate_check:
  - criterion: "Outcome defined"
    check: "outcome.md exists and has success criteria"
  - criterion: "Design complete"
    check: "Architecture documented, approach defined"
  - criterion: "Tests pass"
    check: "All tests green, no regressions"
  - criterion: "Build succeeds"
    check: "No build errors, lint passes"
```

### Enhanced Review (With Specialist Domains)

When qe domain is engaged:

```yaml
gate_check:
  - domain: "qe"
    enhanced_criteria:
      - test_coverage_threshold
      - risk_assessment_complete
      - edge_cases_documented
      - performance_benchmarks
```

## Hook System

### Crew Publishes

```
crew:project:started
crew:phase:started:{phase}
crew:phase:completed:{phase}
crew:gate:review:requested
crew:gate:passed
crew:gate:failed
crew:project:completed
```

### Crew Subscribes

```
{domain}:*:completed    # Specialist work done
{domain}:gate:verdict   # Gate decision from specialist
{domain}:issue:raised   # Problem detected
```

### Coordination Flow

```
Crew                          Specialist Domain (e.g., qe)
  |                                |
  | crew:gate:review:requested     |
  |------------------------------->|
  |                                | (performs advanced review)
  |                                |
  |     qe:gate:verdict:pass       |
  |<-------------------------------|
  |                                |
  | crew:gate:passed               |
  |------------------------------->|
```

## Command Interface

### Basic Usage

```bash
# Crew decides everything
/wicked-garden:crew:start "Add user authentication"
```

### With Specialist Hints

```bash
# Suggest specialist domains
/wicked-garden:crew:start --specialists qe,platform "Payment integration"

# Specific personas
/wicked-garden:crew:start --personas security "PII handling"
```

### Workflow Presets

```bash
# Security-focused (engages platform, qe)
/wicked-garden:crew:start --workflow security "Auth system"

# Research-focused (engages jam)
/wicked-garden:crew:start --workflow research "Evaluate new framework"

# Fast (minimal gates)
/wicked-garden:crew:start --workflow fast "Quick bug fix"
```

## Degradation Model

```
Full Capability
  All specialist domains matched, rich personas, advanced gates

Partial Capability
  Some specialist domains matched, mixed: specialists where matched + built-in fallback

Minimal Capability
  No specialist signals matched, built-in subagents only, simplified gates
```

Since all domains live in one plugin, degradation is based on signal matching rather than plugin installation. The framework engages specialist personas when signals warrant it.
