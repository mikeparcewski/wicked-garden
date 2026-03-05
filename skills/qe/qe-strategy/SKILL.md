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

> **Testing is what allows you to deliver faster.**

QE is not a gate that slows you down. It's the foundation that enables confident refactoring, fearless deployments, rapid iteration, and reduced debugging time.

## Capabilities

### Test Scenario Generation
Generate comprehensive test scenarios covering:
- **Happy paths** - Expected behavior
- **Edge cases** - Boundary conditions, empty/null
- **Error conditions** - Invalid input, failures
- **Security scenarios** - Auth, injection, access control

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

## Change Type → Test Evidence Matrix

Match the change type to know the minimum required tests and the evidence gate that defines "done".

| Change Type | Example | Required Tests | Evidence Gate |
|---|---|---|---|
| Scenario text fix | Wrong command name in `.md` | Scenario passes | `/wg-test scenarios/{domain}/{scenario}` exits 0 |
| Scoring constant | Weight/threshold change | Unit + scenario | Targeted test confirms new value; all related scenarios pass |
| Short-circuit logic | Guard clause addition | Unit + behavioral | Mock verifies 0 calls to bypassed path; non-short-circuit paths unaffected |
| Schema/format update | Output format change | Integration + scenario | Downstream consumers parse new format; scenario assertions match |
| Parser/adapter fix | Missing AST pattern | Unit + regression | New pattern produces >0 symbols for affected files; existing files unaffected |
| Strategy/docs enhancement | New guidance section | Structural validation | File under line cap; references valid commands/paths |

### Evidence Gate Rules

1. Every change MUST have at least one automated verification.
2. "Done" means the evidence gate passes — not just "code written".
3. Autonomous agents must log which evidence gate was satisfied before marking a task complete.
4. If no automated test exists for the change, create one before marking done.

## Gate Reviewer Policy

Each gate type requires specific reviewers. Complexity determines escalation depth.

| Gate Type | Phase(s) | Complexity 0-2 | Complexity 3-5 | Complexity 6-7 |
|-----------|----------|----------------|----------------|----------------|
| generic | ideate | Fast-pass (no reviewer) | Single specialist subagent | Single specialist subagent |
| value | clarify | `qe-orchestrator` | `qe-orchestrator` + `value-orchestrator` | `qe-orchestrator` + council |
| strategy | design, test-strategy | Single specialist subagent | Specialist + `senior-engineer` | Council (multi-model) |
| execution | build, test, review | `crew:reviewer` subagent | Specialist subagent matching signals | Council + human sign-off |

### Reviewer Selection Rules

1. **Single specialist subagent** — route to the specialist whose `enhances` list includes the current phase. Use `specialist_discovery.py` output. One `Task()` dispatch, synchronous.
2. **Council** — use `/wicked-garden:jam:council` for genuinely independent multi-model evaluation. Required when complexity >= 6 at any execution gate, or >= 5 at strategy gates.
3. **Human sign-off** — required for complexity >= 6 execution gates (build, test, review). Optional but offered for complexity 3-5 when not in just-finish mode.
4. **Fast-pass** — complexity <= 1 with no security/compliance signals. Generic `crew:reviewer` only. Still record gate result.
5. **Review phase is never fast-passed** — always runs at least a specialist subagent, regardless of complexity.

### Escalation Triggers

Even at low complexity, escalate to council when:
- Security or compliance signals are detected
- Gate returns CONDITIONAL (council validates whether conditions are acceptable)
- Previous gate in the same project was REJECTED (council provides independent perspective on rework)

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

## References

| Document | Contents |
|---|---|
| [`refs/test-type-taxonomy.md`](refs/test-type-taxonomy.md) | 10 test types with evidence requirements, change-type selection matrix, evidence gate verdict format, and crew integration pattern |

## Integration

- **wicked-crew**: Quality gates in delivery phases
- **wicked-scenarios**: E2E scenario discovery and execution (optional)
- **wicked-kanban**: Track QE findings as tasks
- **wicked-product**: Requirements and UX expertise
- **wicked-platform**: Deployment and release expertise
- **wicked-engineering**: Architecture and code quality expertise
