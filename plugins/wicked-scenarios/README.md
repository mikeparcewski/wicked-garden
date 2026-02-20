# wicked-scenarios

E2E testing written as human-readable markdown scenarios that orchestrate 9 lightweight CLI tools — curl, hurl, playwright, agent-browser, hey, k6, trivy, semgrep, and pa11y. Cover API, browser, performance, security, and accessibility testing without framework lock-in or test runner dependencies.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-scenarios:run` | Execute a test scenario |
| `/wicked-scenarios:list` | List available scenarios with tool availability |
| `/wicked-scenarios:check` | Validate scenario format |
| `/wicked-scenarios:setup` | Install required CLI tools for scenarios |

## Categories

| Category | CLI Tools | What to Test |
|----------|-----------|-------------|
| api | curl, hurl | Health checks, API contracts |
| browser | playwright, agent-browser | Page load, interactions |
| perf | k6, hey | Load testing, response times |
| infra | trivy | Container/IaC scanning |
| security | semgrep | Static code analysis |
| a11y | pa11y | WCAG accessibility |

## Prerequisites

Scenarios use lightweight CLI tools. Run `/wicked-scenarios:setup` to auto-detect and install missing tools, or install manually:

### macOS (Homebrew)

```bash
brew install hurl hey k6 trivy semgrep
npm i -g pa11y agent-browser
npm i -D @playwright/test && npx playwright install
```

### Linux (apt + npm)

```bash
# npm-based tools (all platforms)
npm i -g pa11y agent-browser
npm i -D @playwright/test && npx playwright install
pip install semgrep

# Platform-specific (see tool docs for latest install instructions)
# hurl: https://hurl.dev/docs/installation.html
# k6:   https://grafana.com/docs/k6/latest/set-up/install-k6/
# hey:  https://github.com/rakyll/hey
# trivy: https://aquasecurity.github.io/trivy/latest/getting-started/installation/
```

### Tool Reference

| Tool | Category | Required By | Install |
|------|----------|-------------|---------|
| curl | api | api-health-check | Pre-installed |
| hurl | api | api-health-check (optional) | `brew install hurl` |
| playwright | browser | browser-page-audit | `npm i -D @playwright/test` |
| agent-browser | browser | browser-page-audit (optional) | `npm i -g agent-browser` |
| hey | perf | perf-load-test | `brew install hey` |
| k6 | perf | perf-load-test (optional) | `brew install k6` |
| trivy | infra | infra-container-scan | `brew install trivy` |
| semgrep | security | security-sast-scan | `brew install semgrep` |
| pa11y | a11y | a11y-wcag-check | `npm i -g pa11y` |

## Quick Start

```bash
# Install missing tools
/wicked-scenarios:setup

# List available scenarios and tool status
/wicked-scenarios:list

# Run a scenario
/wicked-scenarios:run scenarios/api-health-check.md

# Validate scenario format
/wicked-scenarios:check scenarios/
```

## Scenario Format

Scenarios are markdown files with YAML frontmatter and fenced code blocks for each step:

````markdown
---
name: api-health-check
category: api
tools: [curl]
---
# API Health Check

## Step 1: Check health endpoint

```bash
curl -sf http://localhost:3000/health
```

Expected: HTTP 200 with JSON body containing `"status": "ok"`
````

Each step runs independently. Exit code 0 = PASS, non-zero = FAIL.

## Skills

| Skill | Description |
|-------|-------------|
| `scenario-authoring` | Guide for writing E2E test scenarios in wicked-scenarios format |

## Agents

| Agent | Description |
|-------|-------------|
| `scenario-runner` | Autonomous scenario execution agent that reads scenarios, discovers tools, and reports results |

## Integration

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-startah | CLI tool discovery and installation | Manual tool setup |
| wicked-search | Find test targets (endpoints, components) | Manual target identification |
| wicked-qe | Test strategy alignment and coverage analysis | No strategy validation |

## Writing Scenarios

See the [scenario-authoring skill](skills/scenario-authoring/SKILL.md) for the full authoring guide.
