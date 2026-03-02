---
name: debugging
description: |
  Systematic debugging and root cause analysis for investigating errors,
  diagnosing complex issues, and performance profiling.

  Use when: "debug this error", "why is this failing", "root cause analysis",
  "fix this bug", "investigate crash", "stack trace", "not working"
---

# Debugging Skill

Systematic debugging, root cause analysis, and error investigation.

## Debugging Approach

### 1. Understand the Problem
- What is expected vs actual behavior?
- When did it start? Can it be reproduced?
- What changed recently?

### 2. Gather Evidence
- Read logs and stack traces
- Review recent changes
- Identify patterns

### 3. Form Hypothesis
- What is the most likely cause?
- What evidence supports this?

### 4. Test Hypothesis
- Design targeted test
- Observe results
- Refine if needed

### 5. Implement Fix
- Develop minimal fix
- Verify resolution
- Add regression tests

### 6. Document
- Root cause and fix
- Add monitoring/alerting

## Issue Categories

- **Logic Errors**: Incorrect conditions, off-by-one, wrong operators
- **State Errors**: Race conditions, stale closures, shared mutable state
- **Integration Errors**: API mismatch, auth issues, timeouts
- **Performance**: N+1 queries, missing indexes, memory leaks
- **Environment**: Config differences, missing vars, permissions

## Systematic Process

Follow the six-step debugging process with:
- Checklists for investigation and evidence gathering
- Severity levels (CRITICAL, HIGH, MEDIUM, LOW)
- Output templates for documentation
- Tools by environment (browser, Node.js, database)

See [refs/process.md](refs/process.md) for detailed process, checklists, and severity guidelines.

## Common Patterns

Debugging techniques and solutions for:
- Null/undefined issues with optional chaining
- Async timing and race conditions
- Scope and closure problems
- Binary search debugging with git bisect
- Performance profiling
- Database query analysis

See [refs/patterns.md](refs/patterns.md) for code examples and debugging techniques.

## External Integration Discovery

Debugging can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **Error tracking** | `sentry`, `rollbar`, `datadog` | Recent errors, stack traces, user context |
| **Observability** | `newrelic`, `dynatrace`, `telemetry` | APM data, traces, metrics |
| **Logging** | `splunk`, `elastic`, `cloudwatch` | Log aggregation, search |

Run `ListMcpResourcesTool` to discover available integrations. Fall back to local log analysis via wicked-search when none available.

## Notes

- Start with the simplest explanation
- Use scientific method: hypothesis, test, refine
- Document your findings for future reference
- Add tests to prevent regression
