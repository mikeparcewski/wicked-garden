# Crew Core Capabilities

## Overview

wicked-crew is the orchestration framework. It has:

1. **Orchestrator Skill** — Rules and smart decisioning
2. **Built-in Subagents** — Minimal fallbacks when specialists unavailable
3. **Hook System** — Event-driven coordination

## Orchestrator Skill

The brain of crew — determines what specialists to engage.

### Phase Rules

Each phase has defined:
- **Purpose** — What this phase accomplishes
- **Inputs** — What's needed to start
- **Outputs** — What must be produced
- **Gate criteria** — What's checked before advancing

```yaml
phases:
  clarify:
    purpose: "Define what success looks like"
    inputs: [user_request]
    outputs: [outcome.md]
    gate: [outcome_defined, scope_clear]
    enhancers: [wicked-jam, wicked-product]

  research:
    purpose: "Understand existing context"
    inputs: [outcome]
    outputs: [research_findings]
    gate: [context_gathered]
    enhancers: [wicked-search, wicked-analyst]

  design:
    purpose: "Plan the approach"
    inputs: [outcome, research]
    outputs: [architecture, approach]
    gate: [approach_defined, risks_identified]
    enhancers: [wicked-product, wicked-engineering]

  gate:
    purpose: "Decide if ready to proceed"
    inputs: [phase_outputs]
    outputs: [gate_decision]
    gate: [criteria_evaluated]
    enhancers: [wicked-qe, wicked-compliance]

  build:
    purpose: "Implement the solution"
    inputs: [design, test_strategy]
    outputs: [implementation, tests]
    gate: [tests_pass, build_succeeds]
    enhancers: [wicked-engineering, wicked-platform]

  review:
    purpose: "Validate the work"
    inputs: [implementation]
    outputs: [review_findings, approval]
    gate: [issues_resolved]
    enhancers: [wicked-qe, wicked-product]
```

### Smart Decisioning

Crew analyzes input to determine specialists needed:

```python
def decide_specialists(user_input, context):
    specialists = []

    # Complexity signals
    if is_complex(user_input):
        specialists.append("wicked-delivery")  # Track progress

    # Security signals
    if has_security_signals(user_input):
        specialists.append("wicked-platform")
        specialists.append("wicked-compliance")

    # Ambiguity signals
    if is_ambiguous(user_input):
        specialists.append("wicked-jam")  # Brainstorm

    # Product signals
    if has_product_signals(user_input):
        specialists.append("wicked-product")

    # Filter to available
    return filter_available(specialists)
```

### Signal Detection

| Signal Type | Keywords/Patterns | Specialists |
|-------------|-------------------|-------------|
| Security | auth, encrypt, PII, credentials, token | devsecops, compliance |
| Performance | scale, load, optimize, latency | appeng, qe |
| Product | user, experience, flow, requirement | product, strategy |
| Compliance | SOC2, HIPAA, GDPR, audit, policy | compliance |
| Ambiguity | ?, maybe, either, could, should we | jam |
| Complexity | multiple, system, integration, migrate | pmo, analyst |

## Built-in Subagents

When specialists aren't available, crew uses minimal built-in agents.

### Facilitator (Clarify Fallback)

**When**: No wicked-jam available

**Capabilities**:
- Structured questioning
- Outcome definition
- Scope boundaries

```markdown
# Facilitator Agent

You help clarify project outcomes.

## Process
1. Ask clarifying questions about the goal
2. Define success criteria
3. Establish scope boundaries
4. Document assumptions

## Output
- outcome.md with success criteria
```

### Researcher (Research Fallback)

**When**: No wicked-analyst available

**Capabilities**:
- Codebase exploration (uses wicked-search if available)
- Pattern identification
- Dependency mapping

```markdown
# Researcher Agent

You explore the codebase to understand context.

## Process
1. Search for related code
2. Identify existing patterns
3. Map dependencies
4. Document findings

## Output
- Research summary
- Relevant file list
```

### Reviewer (Review Fallback)

**When**: No wicked-qe or wicked-product available

**Capabilities**:
- Basic code review
- Obvious issue detection
- Checklist validation

```markdown
# Reviewer Agent

You perform basic code review.

## Process
1. Read changed files
2. Check for obvious issues
3. Validate against requirements
4. Note concerns

## Output
- Review findings
- Pass/fail recommendation
```

### Implementer (Build Fallback)

**When**: No wicked-engineering available

**Capabilities**:
- Code implementation
- Basic test writing
- Build execution

```markdown
# Implementer Agent

You implement the designed solution.

## Process
1. Follow design/architecture
2. Write implementation
3. Add tests
4. Run build

## Output
- Working code
- Passing tests
```

## Gate Enforcement

Crew enforces gates between phases.

### Simplified Review (Built-in)

When no advanced specialists:

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

### Enhanced Review (With Specialists)

When wicked-qe available:

```yaml
gate_check:
  - specialist: "wicked-qe"
    trigger: "crew:gate:review:requested"
    wait_for: "qe:gate:verdict"
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
{specialist}:*:completed    # Specialist work done
{specialist}:gate:verdict   # Gate decision from specialist
{specialist}:issue:raised   # Problem detected
```

### Coordination Flow

```
Crew                          Specialist (e.g., wicked-qe)
  │                                │
  │ crew:gate:review:requested     │
  ├───────────────────────────────>│
  │                                │ (performs advanced review)
  │                                │
  │     qe:gate:verdict:pass       │
  │<───────────────────────────────┤
  │                                │
  │ crew:gate:passed               │
  ├───────────────────────────────>│
```

## Command Interface

### Basic Usage

```bash
# Crew decides everything
/wicked-crew:start "Add user authentication"
```

### With Specialist Hints

```bash
# Suggest specialists
/wicked-crew:start --specialists qe,devsecops "Payment integration"

# Advanced QE
/wicked-crew:start --qe advanced "Critical path feature"

# Specific personas
/wicked-crew:start --personas security,compliance "PII handling"
```

### Workflow Presets

```bash
# Security-focused (engages devsecops, compliance, qe)
/wicked-crew:start --workflow security "Auth system"

# Research-focused (engages analyst, jam)
/wicked-crew:start --workflow research "Evaluate new framework"

# Fast (minimal gates)
/wicked-crew:start --workflow fast "Quick bug fix"
```

## Degradation Model

```
┌─────────────────────────────────────────────────────────┐
│                    Full Ecosystem                        │
│  All specialists + utilities available                   │
│  → Maximum capability, rich personas, advanced gates     │
├─────────────────────────────────────────────────────────┤
│                    Partial Ecosystem                     │
│  Some specialists available                              │
│  → Mixed: specialists where available, built-in fallback │
├─────────────────────────────────────────────────────────┤
│                    Core Only                             │
│  Just wicked-crew + utilities                            │
│  → Built-in subagents, simplified gates                  │
├─────────────────────────────────────────────────────────┤
│                    Standalone                            │
│  Just wicked-crew                                        │
│  → Minimal capability, basic workflow                    │
└─────────────────────────────────────────────────────────┘
```

The framework is designed to work at any level, getting better with more plugins.
