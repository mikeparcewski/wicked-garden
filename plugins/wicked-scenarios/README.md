# wicked-scenarios

Write E2E tests as human-readable markdown that Claude can run, debug, and extend — covering API, browser, performance, security, and accessibility without binding your project to a single test framework.

## Quick Start

```bash
# 1. Install
claude plugin install wicked-scenarios@wicked-garden

# 2. Check which CLI tools are available and install any that are missing
/wicked-scenarios:setup

# 3. Run your first scenario
/wicked-scenarios:run scenarios/api-health-check.md
```

## Workflows

### Run an API health check

Given a scenario file `scenarios/api-health-check.md`:

````markdown
---
name: api-health-check
category: api
tools:
  required: [curl]
---
# API Health Check

## Step 1: Check health endpoint

```bash
curl -sf http://localhost:3000/health
```

Expected: HTTP 200 with JSON body containing `"status": "ok"`
````

Running `/wicked-scenarios:run scenarios/api-health-check.md` produces:

```
SCENARIO: api-health-check
Category: api
Tools: curl

[STEP 1] Check health endpoint
  $ curl -sf http://localhost:3000/health
  {"status":"ok","uptime":3842}
  ✓ PASS (exit 0)

══════════════════════════════
RESULT: PASS (1/1 steps)
══════════════════════════════
```

### Run a full suite and get a JUnit report

```bash
/wicked-scenarios:run scenarios/ --junit report.xml
```

Each step runs independently. Exit code 0 = PASS, non-zero = FAIL. The overall exit code is 0 (all pass), 1 (some fail), or 2 (partial — some steps skipped due to missing optional tools).

### Check what scenarios are available and which tools they need

```bash
/wicked-scenarios:list
```

```
AVAILABLE SCENARIOS

  api-health-check        [api]      tools: curl          ✓ ready
  browser-page-audit      [browser]  tools: playwright    ✓ ready, agent-browser ○ optional
  perf-load-test          [perf]     tools: k6            ✗ missing: k6
  infra-container-scan    [infra]    tools: trivy         ✓ ready
  security-sast-scan      [security] tools: semgrep       ✓ ready
  a11y-wcag-check         [a11y]     tools: pa11y         ✓ ready
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-scenarios:run` | Execute a scenario file or directory of scenarios | `/wicked-scenarios:run scenarios/api-health-check.md --verbose` |
| `/wicked-scenarios:list` | List scenarios with tool availability status | `/wicked-scenarios:list` |
| `/wicked-scenarios:check` | Validate scenario frontmatter and step format | `/wicked-scenarios:check scenarios/` |
| `/wicked-scenarios:setup` | Auto-detect and install missing CLI tools | `/wicked-scenarios:setup` |
| `/wicked-scenarios:report` | File GitHub issues from test failures with deduplication and grouping | `/wicked-scenarios:report --auto` |

## Scenario Format

Scenarios are markdown files. Each fenced bash block is one step:

````markdown
---
name: my-scenario
category: api           # api | browser | perf | infra | security | a11y
tools:
  required: [curl]      # must be present — missing required tool = skip scenario
  optional: [hurl]      # used if available, skipped gracefully if not
env:
  - API_BASE_URL        # required env vars checked before running
timeout: 120            # seconds (default 120)
---

# Scenario Title

## Step 1: Description

```bash
curl -sf $API_BASE_URL/health
```

Expected: HTTP 200
````

Setup and cleanup blocks run before and after all steps (cleanup always runs, like `finally`).

## Categories and CLI Tools

| Category | CLI Tools | What to Test |
|----------|-----------|-------------|
| api | curl, hurl | Health checks, API contracts, response assertions |
| browser | playwright, agent-browser | Page load, interactions, visual regression |
| perf | k6, hey | Load testing, response time SLOs |
| infra | trivy | Container and IaC vulnerability scanning |
| security | semgrep | Static code analysis, SAST rules |
| a11y | pa11y | WCAG 2.1 accessibility compliance |

### Installing CLI Tools

```bash
# macOS
brew install hurl hey k6 trivy semgrep
npm i -g pa11y agent-browser
npm i -D @playwright/test && npx playwright install

# Linux
npm i -g pa11y agent-browser
pip install semgrep
# See tool docs for hurl, k6, hey, trivy platform installs
```

Or run `/wicked-scenarios:setup` to auto-detect and install what's missing.

## Agents

| Agent | What It Does |
|-------|-------------|
| `scenario-runner` | Autonomous execution: reads a scenario file, discovers tools, runs each step, handles graceful degradation for optional tools, and reports structured pass/fail results |

## Skills

| Skill | What It Covers |
|-------|---------------|
| `scenario-authoring` | Full authoring guide — frontmatter schema, step patterns, setup/cleanup lifecycle, non-bash tool wrapping (hurl, k6, playwright), exit code conventions, and best practices for each test category |

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-startah | CLI tool discovery and automatic installation via `/wicked-scenarios:setup` | Manual tool setup and path configuration |
| wicked-search | Find test targets — API endpoints, UI components, entry points — via symbol graph | Manual identification of what to test |
| wicked-qe | `/wicked-qe:acceptance` delegates E2E CLI steps to `/wicked-scenarios:run --json` for machine-readable execution artifacts. QE owns the full acceptance pipeline (Writer/Executor/Reviewer). | Standalone mode: `/wicked-scenarios:run` reports PASS/FAIL directly. No evidence protocol or independent review. |

## License

MIT
