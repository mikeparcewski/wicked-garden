# wicked-scenarios

E2E testing written as human-readable markdown scenarios that orchestrate 9 lightweight CLI tools — curl, hurl, playwright, agent-browser, hey, k6, trivy, semgrep, and pa11y. Cover API, browser, performance, security, and accessibility testing without framework lock-in or test runner dependencies.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-scenarios:run` | Execute a test scenario |
| `/wicked-scenarios:list` | List available scenarios with tool availability |
| `/wicked-scenarios:check` | Validate scenario format |

## Categories

| Category | CLI Tools | What to Test |
|----------|-----------|-------------|
| api | curl, hurl | Health checks, API contracts |
| browser | playwright, agent-browser | Page load, interactions |
| perf | k6, hey | Load testing, response times |
| infra | trivy | Container/IaC scanning |
| security | semgrep | Static code analysis |
| a11y | pa11y | WCAG accessibility |

## Quick Start

```bash
# List available scenarios and tool status
/wicked-scenarios:list

# Run a scenario
/wicked-scenarios:run scenarios/api-health-check.md

# Validate scenario format
/wicked-scenarios:check scenarios/
```

## Writing Scenarios

See the [scenario-authoring skill](skills/scenario-authoring/SKILL.md) for the full authoring guide.
