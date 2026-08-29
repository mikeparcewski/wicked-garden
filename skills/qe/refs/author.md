---
phase_relevance: ["design", "build"]
archetype_relevance: ["build", "specify"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     the retired wicked-testing plugin's `authoring` orchestrator). Loaded on demand <!-- historical -->
     via Read() from the router's `author` action — not a skill. -->


# qe author — full playbook

Turns a plan or a diff into runnable tests. Two modes: scenario authoring
(markdown files the executor runs later) and test code generation (pytest /
jest / etc. that runs in CI).

## Usage

```
wicked-garden-qe author [target] [--framework <name>] [--scenario] [--code]
```

- `target` — file path, feature description, or scenario name
- `--framework` — force a specific framework (autodetected otherwise)
- `--scenario` — produce a scenario file only
- `--code` — produce test code only (both if neither flag is passed)

## When to use

- You have a strategy from `wicked-garden-qe plan` and need the actual tests
- You're mid-build and need unit / integration tests for the last change
- You need to convert an existing scenario into framework-specific code
- You need fixtures or anonymized sample data

## How it dispatches

| Input                                                | Dispatch                                     |
|------------------------------------------------------|----------------------------------------------|
| "write scenarios" / plan in hand                     | `wicked-garden-qe-test-strategist` → scenario authoring flow |
| "generate jest tests" / "add pytest"                 | `wicked-garden-qe-test-automation-engineer`    |
| "author an acceptance test plan" (3-agent pipeline)  | `wicked-garden-qe-acceptance-test-writer`      |
| "build fixtures" / "need test data"                  | `wicked-garden-qe-test-data-manager`           |
| Contract work (OpenAPI, Pact, gRPC, GraphQL)         | `wicked-garden-qe-contract-testing-engineer`   |
| "write a scenario" / "edit scenario"                 | scenario-authoring flow (markdown per SCENARIO-FORMAT.md) |
| "scaffold playwright/cypress/k6" / "browser test"    | `wicked-garden-qe-e2e-orchestrator` (run) / harness scaffold; detection via the `wicked-garden-qe` setup action |
| A diff                                               | tests for the changed lines (`wicked-garden-qe-test-automation-engineer`, scoped to the diff) |

### Dispatch block (executable)

Every id in the tables above is a forked worker skill (`context: fork`) —
invoke it with the Skill tool so it runs in an isolated context:

```
Skill(
  skill="wicked-garden-qe-test-automation-engineer",
  args="""Generate tests for the target below in the project's detected
framework.

## Target
{file path or feature description}

## Scope
- {--scenario only | --code only | both}
- Framework: {jest | pytest | playwright | vitest | go test | ... | detect from project}

## Instructions
1. Detect the project's test framework if not specified (presence of
   `vitest.config.*`, `jest.config.*`, `pyproject.toml` with pytest, etc.).
2. For every public function / endpoint / component in scope, produce a test
   that exercises a happy path AND at least one negative / edge case.
3. Use existing fixtures where present; don't hand-roll test data if the
   project has factories.
4. Follow the project's file-layout convention (co-located vs `tests/`).

Return the path(s) written and a one-line per-file summary."""
)
```

Specialized dispatches swap the `skill` id for the right worker (see the
table above). For an OpenAPI spec, use `wicked-garden-qe-contract-testing-engineer`; for the
3-role acceptance pipeline's test-plan phase, use `wicked-garden-qe-acceptance-test-writer`.

## Tier-2 specialists this skill routes to

For domain-specific test authoring, dispatch the matching specialist. Each
returns test code and/or scenarios in its domain — do not merge their output
verbatim; fold it into the authoring reply:

| Trigger                                              | Specialist                                  |
|------------------------------------------------------|---------------------------------------------|
| Component test (React Testing Library etc.)          | `wicked-garden-qe-ui-component-test-engineer` |
| Service-integration test (testcontainers, compose)   | `wicked-garden-qe-integration-test-engineer`  |
| Full user-journey Playwright test                    | `wicked-garden-qe-e2e-orchestrator`           |
| Visual-regression baseline (Playwright + pixelmatch) | `wicked-garden-qe-visual-regression-engineer` |
| Accessibility test (axe-core / pa11y)                | `wicked-garden-qe-a11y-test-engineer`         |
| Load / perf test (k6 / locust / hey)                 | `wicked-garden-qe-load-performance-engineer`  |
| Property-based / round-trip test                     | `wicked-garden-qe-fuzz-property-engineer`     |
| Pseudolocalization / RTL / CLDR plural test          | `wicked-garden-qe-localization-test-engineer` |
| Log / metric / trace assertion test                  | `wicked-garden-qe-observability-test-engineer` |
| Data migration forward+rollback test                 | `wicked-garden-qe-data-quality-tester`        |

Scenario files use the format in [refs/scenario-format.md](refs/scenario-format.md).

## Output

- A scenario file (markdown) in `scenarios/`, OR
- Test code in the project's test directory matching the project's framework,
  OR
- Both, when authoring scenarios that have automated companions

Emits `wicked.qe.scenario.authored` and/or `wicked.test.strategy.generated` on the
bus when present.

## Legacy invocations (absorbed in 0.4.0)

| Old command | Ask authoring instead |
|-------------|-----------------------|
| `scenarios` | "write/edit a scenario for <X>" — authoring writes scenario files in the format in `SCENARIO-FORMAT.md` |
| `automate`  | "scaffold browser automation for <X>" — authoring generates the Playwright/Cypress/k6 harness; tool *detection* lives in the `wicked-garden-qe` setup action |

## References

- [refs/integration.md](refs/integration.md)
- [refs/scenario-format.md](refs/scenario-format.md)
- `../../qe-test-automation-engineer/SKILL.md`, `../../qe-acceptance-test-writer/SKILL.md`,
  `../../qe-contract-testing-engineer/SKILL.md`
