---
name: scenario-authoring
description: |
  Guide for writing E2E test scenarios in the wicked-scenarios format.
  Covers scenario structure, frontmatter fields, step format, and best practices.

  Use when:
  - Creating new test scenarios
  - Understanding the scenario format
  - Choosing the right CLI tool for a test category
---

# Scenario Authoring Guide

Write E2E test scenarios as markdown files that both humans and AI agents can execute.

## Quick Start

Create a `.md` file in the `scenarios/` directory with this structure:

```yaml
---
name: my-scenario
description: What this scenario tests
category: api          # api|browser|perf|infra|security|a11y
tools:
  required: [curl]     # Must be installed to run
  optional: [hurl]     # Used if available, skipped if not
difficulty: basic      # basic|intermediate|advanced
timeout: 60            # Max seconds
---
```

Then write steps in the markdown body:

```markdown
## Steps

### Step 1: Description (cli-name)

\`\`\`bash
curl -sf https://example.com/api/health
\`\`\`

**Expect**: Exit code 0, healthy response
```

## Categories and Tools

| Category | Tools | What to Test |
|----------|-------|-------------|
| api | curl, hurl | Health checks, API contracts, response validation |
| browser | playwright, agent-browser | Page load, interactions, content verification |
| perf | k6, hey | Load testing, response time thresholds |
| infra | trivy | Container scanning, IaC security |
| security | semgrep | SAST, code security patterns |
| a11y | pa11y | WCAG compliance, accessibility issues |

## Key Rules

1. **Exit code = pass/fail** — exit 0 is PASS, non-zero is FAIL
2. **One CLI per step** — identify it in the step header parenthetical
3. **Fenced code blocks** — use appropriate language hint (bash, hurl, javascript)
4. **Headless flags** — browser/a11y tools must include headless configuration
5. **Cleanup section** — remove temp files created during execution

## References

- [Format Specification](refs/format-spec.md) — full field reference and validation rules
- [CLI Reference](refs/cli-reference.md) — MVP tool details and example invocations
