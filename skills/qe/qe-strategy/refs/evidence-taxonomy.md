# Evidence Taxonomy

Evidence types for task completion, gate review, and audit trails.

Each evidence type answers a different question for reviewers and future engineers. Collect the types appropriate to the task's complexity and risk level.

## Evidence Types

| Evidence Type | What It Shows | Format | Required For |
|---|---|---|---|
| **Visuals** | UI state, layout, rendering correctness | Screenshot, screen recording, diff image | UI/UX changes, visual regression detection, accessibility review |
| **Payloads** | Request/response data, message structure, API contracts | JSON/XML snippet, curl output, Postman collection export | API changes, integration work, contract testing, event-driven systems |
| **Logging** | Runtime behavior, error paths, audit trail | Log excerpt with timestamps, structured log entry, trace ID | Production incidents, compliance audits, debugging complex flows |
| **Test Results** | Automated verification, regression coverage | Test runner output (pytest, jest, go test), coverage report | All complexity levels 1+ — always required |
| **Code Diff** | What changed, how much, where | File list with modification type (created/modified/deleted), line count, PR link | All complexity levels 1+ — always required |
| **Performance** | Latency, throughput, resource usage under load | Benchmark output (wrk, k6, JMH), p99 latency, RPS, CPU/memory profile | Complexity 5+ (high), performance-signal tasks, load-tested changes |

## When Each Type Is Required

### Complexity 1-2 (Low)

Minimum evidence package for any task:

- **Test Results** — required: at least one passing test proving the change works
- **Code Diff** — required: file references showing what was modified

### Complexity 3-4 (Medium)

All low-complexity evidence plus:

- **Payloads** — required when: API endpoints changed, request/response schema modified, message formats updated
- **Logging** — recommended when: error handling paths added, audit-relevant operations implemented
- Verification step (not a separate evidence type — embed in Test Results or Payloads section)

### Complexity 5+ (High)

All medium-complexity evidence plus:

- **Performance** — required: benchmark or load test showing the change does not degrade p99 latency or throughput
- **Assumptions** — required: documented assumptions about production environment, upstream dependencies, or rollback conditions
- **Visuals** — required for UI changes; optional for backend but useful for architecture diagrams

## Evidence Format in Task Descriptions

When completing a task (TaskUpdate status=completed), include evidence using this structure:

```markdown
## Outcome
{What was accomplished — the problem solved and how}

## Evidence
- Test: {test file or suite} — PASS
- File: {path/to/changed/file.ext} — created/modified/deleted
- Payload: {endpoint} → {status code} {response excerpt}
- Verification: {command and output excerpt}
- Performance: p99 {before}ms → {after}ms at {RPS} RPS
- Log: {log excerpt showing expected behavior}

## Assumptions
- {Assumption 1}: {Rationale}
- {Assumption 2}: {Rationale}
```

## Using Evidence in Gate Reviews

During quality gates (gate.md), reviewers evaluate evidence against complexity-level expectations:

| Gate Type | Minimum Evidence Expected |
|---|---|
| value (clarify) | Outcome statement, success criteria, assumptions |
| strategy (design, test-strategy) | Architecture decision rationale, test coverage plan, risk analysis |
| execution (build, test, review) | Test results + code diff (always), plus payloads/performance/logging as warranted |

**Missing evidence is a gate failure signal.** A task marked completed without verifiable evidence cannot be approved at an execution gate.

## Anti-Patterns

- **Prose-only outcomes**: "I fixed the bug" — no file references, no test results. Not acceptable.
- **Passing tests without file references**: Tests prove the change works but not what changed. Add file list.
- **Performance claims without data**: "It's faster now" — provide benchmark output.
- **High-complexity tasks without assumptions**: Complex tasks always have preconditions; document them so reviewers can verify they hold.
