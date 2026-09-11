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

Dispatch uses the Skill tool on Claude Code (a fresh forked context). On any other harness, open the named skill's `SKILL.md` from your skills catalog and carry out its instructions inline with the given args, then continue here.

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
1. Detect the project's test harness if not specified (`package.json`
   `scripts.test` / `test:e2e`, `vitest.config.*`, `jest.config.*`,
   `playwright.config.*`, `pyproject.toml` with pytest, an existing `e2e/`
   rig) and name the exact run command. Match what is there — never add a runner.
2. For every public function / endpoint / component in scope, produce a
   BEHAVIOUR test that exercises a happy path AND at least one negative /
   edge case — assert on what the caller observes, not on internal structure.
3. Use existing fixtures where present; don't hand-roll test data if the
   project has factories.
4. Follow the project's file-layout convention (co-located vs `tests/`).
5. RUN every file you produced with the harness's real command and record
   file · exact command · result (`N passed / N failed`) in the PLAN's
   execution table. A file you did not run is `unverified` — never `covered`,
   never "passes". Pre-existing coverage is claimed only with `path:line`.
   A test that needs a server, seed data or a build is `needs-fixture` with
   how to start it — run it against that fixture before you claim it.
6. Do NOT `git push`, `gh pr create` or merge — the run's deliver phase
   opens the PR; leave the files on the working tree and report the paths.

Return the path(s) written, the execution table, the `unverified` and
`not covered` rows, and a one-line per-file summary."""
)
```

Specialized dispatches swap the `skill` id for the right worker (see the
table above). For an OpenAPI spec, use `wicked-garden-qe-contract-testing-engineer`; for the
3-role acceptance pipeline's test-plan phase, use `wicked-garden-qe-acceptance-test-writer`.
Instructions 1, 5 and 6 travel with EVERY code-producing dispatch (not the
acceptance writer — its plans are run by the executor) — a fork worker sees only
its args, so the contract below is copied into them, not assumed.

## Verified-test contract (binding for every produced test)

Written after the wave-6 acceptance review of a governed "New test" run (R4-r2 /
F-7R2-015): the worker shipped a Playwright suite it never executed (it failed on
its first line when run independently), sold 22 pre-existing tests as a
"29-scenario suite", described waits it had not written, and opened the PR
itself. None of that is authoring. Every dispatch in this playbook carries the
rules below, and the `review` action (`refs/review.md` § Reviewing produced
tests) re-derives each one.

1. **Detect the harness before writing a line.** Read `package.json` `scripts`
   (`test`, `test:e2e`, `typecheck`), `vitest.config.*` / `jest.config.*` /
   `playwright.config.*`, `pyproject.toml` `[tool.pytest.ini_options]` /
   `pytest.ini` / `conftest.py`, an `e2e/` or `tests/e2e/` directory and how its
   existing rigs start their fixture, `Cargo.toml`, `go.mod`. Name the harness
   and the exact command in the PLAN. Match what is there; never add a runner.
2. **Behaviour, not implementation.** Assert what a user or caller observes —
   rendered DOM, response status/body, file contents, exit code, the arguments a
   mocked boundary received. Not internal structure, not "the mock was called",
   never a snapshot of a mock. For each test, know the change to the source that
   would make it fail; a test with no such change is tautological — drop it.
3. **Run what you write — before you claim it.** Execute every produced test
   file with the harness's real command (`npx vitest run <file>`,
   `python -m pytest <file>`, `npx playwright test <file>`, the rig's own
   `python3 e2e/<rig>.py`). Record in the PLAN's execution table: file, exact
   command, result (`N passed / N failed`, duration), commit or timestamp. A
   test you did not execute is `unverified` — never `covered`, never "passes".
   A failing test is fixed and re-run, or shipped as `failing` with the reason
   — never described as green. "All tests pass" without the table is a claim,
   not evidence.
4. **Cite pre-existing coverage or don't claim it.** A `covered` row for a
   test you did not write carries `path:line` of the `it` / `test` /
   `def test_` and what it asserts. No citation → `unverified`. Report
   "N new" and "M pre-existing (cited)" as separate counts — never a padded
   total.
5. **Fixture-bound e2e is labelled and started.** A browser or API test that
   needs a server, seed data or a build is `needs-fixture`; the PLAN says how
   to start it (build step, command, port, env) — copy the repo's own rig
   convention. Run it against that fixture before claiming; verify every
   selector, test id and text against the source (`grep` the `data-testid`,
   read the render rule that produces the text). If the fixture cannot start
   here, the row is `unverified — fixture unavailable: <reason>` and the reply
   says so.
6. **Say what you did not cover.** The PLAN carries `not covered` rows for
   every part of the intent without a test — no UI control exists, out of
   scope, blocked — with the reason. Silence is a false claim.
7. **Delivery belongs to the run, not to you.** Leave the tests on the working
   tree / run branch and report the paths. Never `git push`, `gh pr create`,
   `gh pr merge`, or any remote-writing command — inside a wicked-crew run the
   run's deliver phase opens the PR (evaluator ≠ creator: the acceptance gate
   reads the evidence the deliver phase records); standalone, the human opens
   it.

### PLAN execution table (required shape)

| Row | Status | Evidence the row must carry |
|---|---|---|
| a test you wrote | `covered` | `<file>` · `<exact command>` · `<N passed / N failed>` · `<sha or time>` |
| a pre-existing test | `covered` | `<path:line>` · what it asserts |
| written, not executed | `unverified` | why (not run / `fixture unavailable: <reason>`) |
| needs a server / build / seed | `needs-fixture` | how to start it · then its execution row |
| executed and red | `failing` | the failure and why it ships red |
| an intent gap | `not covered` | why (no control exists / out of scope / blocked) |

The status vocabulary is closed. `covered` requires an execution row (new) or a
`path:line` citation (pre-existing); the reviewer FAILS a PLAN that breaks it,
and FAILS any PLAN whose e2e has no execution row.

## Tier-2 specialists this skill routes to

For domain-specific test authoring, dispatch the matching specialist with the
block above — instructions 1, 5 and 6 included. Each specialist's own SKILL.md
also carries the contract's run-before-claim / cite / never-ship block, so a
direct invocation on any CLI is bound the same way. Each returns test code
and/or scenarios in its domain — do not merge their output verbatim; fold it
into the authoring reply:

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
- For test code, ALWAYS a PLAN carrying the execution table above — harness +
  command, per-file results, `unverified` / `needs-fixture` / `not covered`
  rows — in the run's deliverable, or where the repo already keeps test prose
  (`docs/`, `.product/`); inside the test tree only if the repo already does that

Emits `wicked.qe.scenario.authored` and/or `wicked.test.strategy.generated` on the
bus when present. The authoring reply never says a test passes without its
execution row, and never opens or pushes a PR — the run's deliver phase does.

## Legacy invocations (absorbed in 0.4.0)

| Old command | Ask authoring instead |
|-------------|-----------------------|
| `scenarios` | "write/edit a scenario for <X>" — authoring writes scenario files in the format in `SCENARIO-FORMAT.md` |
| `automate`  | "scaffold browser automation for <X>" — authoring generates the Playwright/Cypress/k6 harness; tool *detection* lives in the `wicked-garden-qe` setup action |

## References

- [refs/integration.md](refs/integration.md)
- [refs/scenario-format.md](refs/scenario-format.md)
- `wicked-garden-qe-test-automation-engineer`, `wicked-garden-qe-acceptance-test-writer`,
  `wicked-garden-qe-contract-testing-engineer`
