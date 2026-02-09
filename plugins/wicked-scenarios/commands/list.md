---
description: List available E2E test scenarios with tool availability status
---

# /wicked-scenarios:list

List available E2E test scenarios with tool availability status.

## Usage

```
/wicked-scenarios:list [--category api|browser|perf|infra|security|a11y]
```

## Instructions

### 1. Find Scenarios

Glob for scenario files:
```
${CLAUDE_PLUGIN_ROOT}/scenarios/*.md
```

### 2. Parse Each Scenario

Read YAML frontmatter from each file to extract:
- `name`
- `description`
- `category`
- `tools.required` + `tools.optional`
- `difficulty`

### 3. Check Tool Availability

Run CLI discovery for all tools referenced across scenarios:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cli_discovery.py"
```

### 4. Apply Category Filter

If `--category` is specified, filter to only matching scenarios.

### 5. Display Results

```markdown
## Available Scenarios

| Scenario | Category | Description | Tools | Status | Difficulty |
|----------|----------|-------------|-------|--------|------------|
| api-health-check | api | Validate API health endpoint | curl ✅, hurl ❌ | Partial | basic |
| browser-page-audit | browser | Page load and interaction check | playwright ✅ | Ready | intermediate |
| perf-load-test | perf | API endpoint load test | k6 ✅ | Ready | intermediate |
| infra-container-scan | infra | Container image vulnerability scan | trivy ✅ | Ready | basic |
| security-sast-scan | security | Static code analysis | semgrep ✅ | Ready | basic |
| a11y-wcag-check | a11y | WCAG compliance check | pa11y ❌ | Not Ready | basic |

### Summary
- **Ready**: {count} scenarios (all tools available)
- **Partial**: {count} scenarios (some tools missing)
- **Not Ready**: {count} scenarios (required tools missing)

### Missing Tools
| Tool | Install | Used By |
|------|---------|---------|
| hurl | `brew install hurl` | api-health-check |
| pa11y | `npm i -g pa11y` | a11y-wcag-check |

### Quick Install
To install all missing tools at once:
```bash
{brew install commands joined with " && "} && {npm install commands joined with " && "}
```
```
