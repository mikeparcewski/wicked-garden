# Testing Lens

Additional questions for the five lenses when the work involves test failures,
test strategy, coverage gaps, or quality processes.

## Lens 1 Additions: Is This Real?

- Is the test failing because the code is wrong, or because the test is wrong?
- Is this a flaky test, or is there a real intermittent bug?
- Is the coverage gap real, or is the code already tested indirectly?
- Is the quality concern based on evidence (bugs, incidents) or on metrics (coverage %)?

## Lens 2 Additions: What's Actually Going On?

- Is the test testing behavior, or testing implementation details?
- Is the flakiness from timing, ordering, shared state, or environment?
- Is the test pyramid balanced, or are we heavy on the wrong level?
- Is the test infrastructure the problem, not the tests themselves?

## Lens 3 Additions: What Else Can We Fix?

- Are other tests in this suite suffering from the same fragility?
- Are there test utilities/helpers that could reduce duplication?
- Is there missing test infrastructure (fixtures, factories, mocks) that would
  make testing easier across the board?
- Can we add property-based tests or fuzzing to catch classes of bugs?

## Lens 4 Additions: Should We Rethink?

- Should this be tested at a different level? (unit vs. integration vs. e2e)
- Would making the code more testable (DI, pure functions) be better than
  writing more complex tests?
- Should we replace manual test orchestration with a test framework feature?
- Would contract tests replace fragile integration tests?

## Lens 5 Additions: Better Way?

- Can we use snapshot/golden-file testing instead of manual assertions?
- Can we use the type system to eliminate the need for this test?
- Can we test this via a linter/static analysis rule instead of a runtime test?
- Can we make the untestable code testable instead of working around it?
