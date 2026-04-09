---
name: qe-strategy
description: |
  Shift-left QE strategy for test planning and quality analysis.
  This skill should be used when the user needs test scenarios, risk assessment,
  test plans, or coverage analysis outside of a crew workflow context.

  Use when: "test strategy", "what should I test", "test scenarios", "shift-left testing",
  "generate test plan", "test coverage", "risk assessment", "how do I test this"
---

# QE Strategy

Quality Engineering enables **faster delivery** by catching issues early when they're cheap to fix.

## Core Philosophy

> **Test everything. Test it directly. Test both sides.**

QE is aggressive by design. Every feature gets tested. Every test has a positive and negative scenario. UI tests check for JS errors. API tests hit real endpoints. Effort scales dynamically to match the actual scope of changes — not a fixed checklist.

### Three Non-Negotiables

1. **Positive AND negative for every scenario** — if you test that login works, you also test that bad credentials fail. No exceptions.
2. **Direct testing** — UI tests run in a real browser and check for JS errors. API tests make real HTTP calls and verify status codes. Mocks are for isolation, not for skipping verification.
3. **Dynamic effort** — a 3-line fix gets 3 focused scenarios. A new feature gets exhaustive coverage. The test strategist reads the actual diff and calibrates.

## Two-Pass Test Strategy

The test strategist operates at two points in the workflow:

### Pass 1: Pre-Build (Design Phase)

**Input**: Engineer's predicted change manifest OR requirements/acceptance criteria.
**Output**: Initial test strategy scoped to predicted changes.

During design, an engineer (or architect) should produce an **expected changes manifest** — a list of files, APIs, UI components, and data models that will change. The test strategist uses this to:
- Classify change type (UI, API, both, data, config)
- Identify mandatory test categories
- Generate initial positive+negative scenario pairs
- Flag predicted changes that seem risky or under-specified

### Pass 2: Post-Build (Before Test Execution)

**Input**: Actual git diff of implemented changes.
**Output**: Recalibrated test strategy based on what really changed.

After the engineer finishes, the test strategist:
- Runs `git diff` to see actual changes
- Compares actual vs. predicted changes — flags surprises
- Adds scenarios for unanticipated changes
- Removes scenarios for predicted changes that didn't happen
- Adjusts effort up or down based on actual scope

**Pass 2 always runs.** Even if Pass 1 was thorough, the diff may reveal changes the engineer didn't predict.

## Capabilities

### Test Scenario Generation
Generate aggressive test scenarios with mandatory positive+negative pairing:
- **Happy paths** — Expected behavior works (positive) + invalid input rejected (negative)
- **Edge cases** — Boundary conditions handled (positive) + beyond-boundary input caught (negative)
- **Error conditions** — Error handling activates (positive) + cascading failures contained (negative)
- **Security scenarios** — Auth works for valid users (positive) + unauthorized access blocked (negative)
- **UI-specific** — Features work, no JS errors (positive) + error boundaries catch failures (negative)
- **API-specific** — Endpoints return correct responses (positive) + bad requests return proper errors (negative)

Use: `/wicked-garden:qe:scenarios <feature>`

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

Use: `/wicked-garden:qe:qe <target> --focus <area>`

### Test Planning
Generate comprehensive test plans with coverage matrix, risk assessment, and test data requirements.

Use: `/wicked-garden:qe:qe-plan <feature>`

### Test Automation
Convert scenarios into runnable test code. Supports pytest, jest, go test, and more.

Use: `/wicked-garden:qe:automate --framework <framework>`

### Test Quality Review
Review existing test code for quality, coverage gaps, test smells, and flakiness patterns.
Also detects **agent test manipulation**: tests weakened to pass, missing assertions, reduced coverage, and tests that always pass.

Use: `/wicked-garden:qe:qe-review <test-path>`

### Acceptance Testing (Evidence-Gated)
Three-agent pipeline that separates test writing, execution, and review:
- **Writer**: Reads scenario + implementation → evidence-gated test plan
- **Executor**: Follows plan, collects artifacts — no judgment
- **Reviewer**: Evaluates evidence against assertions independently

Catches specification bugs, runtime bugs, and semantic bugs that self-grading misses.

Use: `/wicked-garden:qe:acceptance <scenario>`

## Workflows

### Code Testing Workflow
```
/wicked-garden:qe:scenarios Feature X        # 1. Generate scenarios
/wicked-garden:qe:qe-plan src/feature/       # 2. Create test plan
/wicked-garden:qe:automate --framework jest   # 3. Generate test code
/wicked-garden:qe:qe-review tests/           # 4. Review quality
```

### Acceptance Testing Workflow
```
/wicked-garden:qe:acceptance scenario.md --phase write    # 1. Generate evidence-gated test plan
# Review the plan, then:
/wicked-garden:qe:acceptance scenario.md                  # 2. Full Write → Execute → Review pipeline
```

## Evidence Gate Rules

1. Every change MUST have at least one automated verification.
2. "Done" means the evidence gate passes — not just "code written".
3. Autonomous agents must log which evidence gate was satisfied before marking a task complete.
4. If no automated test exists for the change, create one before marking done.

See [`refs/test-type-taxonomy.md`](refs/test-type-taxonomy.md) for the full change-type selection matrix.

## Gate Reviewer Policy

Complexity determines escalation: 0-2 = fast-pass or single specialist, 3-5 = specialist + senior, 6-7 = council + human sign-off. Review phase is never fast-passed. Escalate to council on security/compliance signals, CONDITIONAL gates, or prior REJECT. See [`refs/test-type-taxonomy.md`](refs/test-type-taxonomy.md) for full gate matrix.

## Agents

| Agent | Purpose |
|-------|---------|
| test-strategist | Generate test scenarios, coverage strategy |
| test-automation-engineer | Generate test code, configure infrastructure |
| risk-assessor | Identify risks and failure modes |
| code-analyzer | Static analysis for testability and quality |
| tdd-coach | Guide TDD red-green-refactor workflow |
| acceptance-test-writer | Transform scenarios into evidence-gated test plans |
| acceptance-test-executor | Execute plans, collect artifacts, no judgment |
| acceptance-test-reviewer | Evaluate evidence against assertions independently |

## E2E Scenario Integration

When **wicked-scenarios** is installed, QE auto-discovers scenarios (api, browser, perf, infra, security, a11y), assesses coverage gaps, and executes during gates. Configure via `project.json` `qe_scenarios.execution_mode`: `strict` (blocking), `warn` (advisory), `skip` (informational). Without wicked-scenarios, all QE functionality works identically.

## Testing Pyramid (Crew Integration)

When a crew project reaches the test phase, QE tests **like a product owner** — verifying real user flows before checking unit-level correctness. E2E = product-level testing, not running `pnpm test`.

**Product-first dispatch order:**

| Priority | Group | Layer | Test Types | When Required |
|---|---|---|---|---|
| 1st | P | 5 — Scenario/E2E | Playwright/Cypress, live endpoint curl, acceptance scenarios | All non-trivial changes |
| 1st | P | 3 — Visual | screenshots, interaction flows, a11y, **JS error monitoring** | UI or both changes |
| 2nd | I | 2 — Integration | **direct HTTP** contract/API validation (not mocked) | API or both changes |
| 2nd | I | 4 — Security | auth/input validation, **authz boundary** | API or both changes |
| 3rd | R | 1 — Unit | run existing suite (do NOT generate new unit tests) | Always |
| 3rd | R | 6 — Regression | run full existing suite | Always |

**E2E tool priority**: Playwright/Cypress (if configured) > curl/fetch against live endpoints > `/wicked-garden:qe:run` > `/wicked-garden:qe:acceptance`.

**UI testing standards**:
- Every user-facing feature MUST be exercised — not just the main flow
- Browser console MUST be monitored for JS errors/warnings during all tests
- Any unhandled exception or console.error during normal operation = FAIL
- Accessibility audit runs on every UI change

**API testing standards**:
- Every endpoint tested with direct HTTP calls (curl, httpie, or test client)
- Both valid (200/201/204) and invalid (400/401/403/404/422) responses verified
- Response body shape validated against schema
- Auth boundary tested: unauthenticated → 401, unauthorized → 403

**Evidence package**: The test phase MUST compile `phases/test/evidence/report.md` with screenshots, execution traces, and spec comparison. The review phase evaluates this package. See [`refs/evidence-taxonomy.md`](refs/evidence-taxonomy.md).

See [`refs/test-type-taxonomy.md`](refs/test-type-taxonomy.md) for full layer definitions, agent routing, parallel dispatch rules, and execution details.

## References

- [`refs/test-type-taxonomy.md`](refs/test-type-taxonomy.md) — 10 test types, pyramid layers, change-type matrix, gate verdict format, crew integration

## Integration

Integrates with: **crew** (quality gates), **scenarios** (E2E discovery), **kanban** (task tracking), **product** (requirements/UX), **platform** (deployment), **engineering** (architecture/code quality).
