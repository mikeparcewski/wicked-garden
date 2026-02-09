---
name: qe-strategy
description: >
  Shift-left QE analysis with quality gates.
  Generate test scenarios, assess risks, create test plans, and automate test generation.
  Enables faster delivery through early quality validation.
---

# QE Strategy

Quality Engineering enables **faster delivery** by catching issues early when they're cheap to fix.

## Core Philosophy

> **Testing is what allows you to deliver faster.**

QE is not a gate that slows you down. It's the foundation that enables confident refactoring, fearless deployments, rapid iteration, and reduced debugging time.

## Capabilities

### Test Scenario Generation
Generate comprehensive test scenarios covering:
- **Happy paths** - Expected behavior
- **Edge cases** - Boundary conditions, empty/null
- **Error conditions** - Invalid input, failures
- **Security scenarios** - Auth, injection, access control

Use: `/wicked-qe:scenarios <feature>`

### QE Review
Quality review across the full delivery lifecycle:
| Focus | Reviews |
|-------|---------|
| `requirements` | Testability, clarity, acceptance criteria |
| `ux` | User flows, error handling, edge cases |
| `ui` | Visual consistency, accessibility |
| `arch` | Testability, deployability, observability |
| `code` | Test coverage, code quality |
| `deploy` | Rollback plan, feature flags, monitoring |
| `all` | Full spectrum review |

Use: `/wicked-qe:qe <target> --focus <area>`

### Test Planning
Generate comprehensive test plans with coverage matrix, risk assessment, and test data requirements.

Use: `/wicked-qe:qe-plan <feature>`

### Test Automation
Convert scenarios into runnable test code. Supports pytest, jest, go test, and more.

Use: `/wicked-qe:automate --framework <framework>`

### Test Quality Review
Review existing test code for quality, coverage gaps, test smells, and flakiness patterns.
Also detects **agent test manipulation**: tests weakened to pass, missing assertions, reduced coverage, and tests that always pass.

Use: `/wicked-qe:qe-review <test-path>`

## Workflow

The recommended QE workflow:

```
/wicked-qe:scenarios Feature X        # 1. Generate scenarios
/wicked-qe:qe-plan src/feature/       # 2. Create test plan
/wicked-qe:automate --framework jest   # 3. Generate test code
/wicked-qe:qe-review tests/           # 4. Review quality
```

## Agents

| Agent | Purpose |
|-------|---------|
| test-strategist | Generate test scenarios, coverage strategy |
| test-automation-engineer | Generate test code, configure infrastructure |
| risk-assessor | Identify risks and failure modes |
| code-analyzer | Static analysis for testability and quality |
| tdd-coach | Guide TDD red-green-refactor workflow |

## E2E Scenario Integration

When **wicked-scenarios** is installed, QE automatically:
- **Discovers** available E2E scenarios across categories (api, browser, perf, infra, security, a11y)
- **Assesses coverage** by mapping risks to scenario categories during strategy gates
- **Executes scenarios** during execution gates (configurable: strict/warn/skip)
- **Identifies gaps** where risk areas lack scenario coverage

Configuration via project.json:
```json
{
  "qe_scenarios": {
    "execution_mode": "warn",
    "category_filter": "all"
  }
}
```

Without wicked-scenarios installed, all QE functionality works identically.

## Integration

- **wicked-crew**: Quality gates in delivery phases
- **wicked-scenarios**: E2E scenario discovery and execution (optional)
- **wicked-kanban**: Track QE findings as tasks
- **wicked-product**: Requirements and UX expertise
- **wicked-platform**: Deployment and release expertise
- **wicked-engineering**: Architecture and code quality expertise
