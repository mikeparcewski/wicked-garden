---
name: tdd-coach
description: |
  Guide Test-Driven Development workflow — teach red-green-refactor cycle,
  test-first approach, and TDD best practices. Validate test quality. A
  teaching / coaching flow rather than a persistent role; dispatched on
  demand when a developer wants TDD guidance for a specific feature or
  bug fix.

  Use when: "guide me through TDD", "red-green-refactor", "test-first
  approach", "TDD this feature", "teach me TDD", "coach me on TDD".
---

# TDD Coach

Guides a developer through a Test-Driven Development cycle — writing a failing
test first, making it pass with minimal code, and refactoring while keeping
tests green. Teaches the discipline, reviews test quality, and catches common
TDD anti-patterns.

This is a **coaching flow**, not a persistent role. Dispatch this skill when
someone wants to TDD a specific feature or bug fix. For persistent test
strategy and test automation work, use the test-strategist or
test-automation-engineer agents.

## Quick Start

Invoke this skill when someone says:
- "Guide me through TDD for {feature}"
- "Red-green-refactor this bug fix"
- "Let's TDD the {function name}"
- "Coach me on the next test to write"

Typical output:
- Next test to write (RED phase)
- Review of proposed test quality
- Minimal implementation guidance (GREEN phase)
- Refactor opportunities (REFACTOR phase)
- Next cycle suggestion

## TDD Fundamentals

### Red-Green-Refactor

```
1. RED:      Write a failing test
2. GREEN:    Write minimal code to pass
3. REFACTOR: Improve code quality (tests stay green)
4. REPEAT
```

### Uncle Bob's Three Rules

1. Write no production code except to pass a failing test
2. Write only enough test to fail (compilation failure is failure)
3. Write only enough production code to pass the test

## Process

### 1. Start a Cycle

Ask: **"What should the code do?"**
Guide: **"Let's write a test that describes that behavior first."**

### 2. RED — Write Failing Test

Test quality checklist:
- [ ] Describes desired behavior clearly
- [ ] Would fail if feature doesn't exist
- [ ] Minimal (one behavior)
- [ ] Clear assertion

Good vs bad examples:

```javascript
// Good — describes behavior
test('calculateTotal should sum item prices', () => {
  const items = [{price: 10}, {price: 20}];
  expect(calculateTotal(items)).toBe(30);
});

// Bad — too vague
test('test calculation', () => {
  expect(calculate()).toBeTruthy();
});
```

Verify the test fails:
```bash
npm test -- {test_file}
# Expected: FAIL (the RED)
```

### 3. GREEN — Make It Pass

Guidance:
- Write the simplest code that passes
- Don't overthink the solution
- **Hardcoding is OK initially**
- Focus on making the test green

**Anti-pattern**: writing extra code "just in case"

Example:
```javascript
// First iteration — hardcoded
function calculateTotal(items) {
  return 30; // Passes the one test
}

// Next test forces real implementation
test('works with different prices', () => {
  const items = [{price: 5}, {price: 15}];
  expect(calculateTotal(items)).toBe(20);
});
```

### 4. REFACTOR — Improve Code

Checklist:
- [ ] Tests still passing
- [ ] Remove duplication
- [ ] Improve names
- [ ] Extract functions
- [ ] Apply patterns

**Key rule**: tests stay green during refactoring.

### 5. Repeat

For the next behavior:
1. Add a new test (RED)
2. Implement feature (GREEN)
3. Clean up (REFACTOR)

## Common TDD Scenarios

### New Feature
1. Write test for simplest case
2. Implement minimal solution
3. Write test for next case
4. Enhance implementation
5. Refactor when duplication appears

### Bug Fix
1. Write test that reproduces the bug (fails)
2. Fix the bug (test passes)
3. Refactor if needed
4. Add related edge case tests

### Refactoring
1. Ensure good test coverage first
2. Tests are the safety net
3. Refactor in small steps
4. Run tests after each change
5. Commit when tests green

## Test Quality Assessment

### Good Tests (FIRST)
- **Fast** — milliseconds
- **Isolated** — no dependencies between tests
- **Repeatable** — same result every time
- **Self-validating** — pass/fail, no manual check
- **Timely** — written with or before code

### Test Smells
- Require specific run order
- Depend on external state
- Take seconds to run
- No clear assertion
- Test multiple behaviors

See [refs/patterns.md](refs/patterns.md) for:
- Fake It Till You Make It
- Triangulation
- Obvious Implementation
- Teaching moments for common TDD missteps

## Coaching Output

```markdown
## TDD Coaching Session

**Feature**: {feature_name}
**Current Phase**: RED | GREEN | REFACTOR

### Current Test
\`\`\`{language}
{test_code}
\`\`\`
**Status**: PASS | FAIL

### Next Step
{What to do next in the cycle}

### Tips
- {Specific guidance}

### Coverage
**Lines**: {percentage}%
**Branches**: {percentage}%
```

## Track Progress

Optionally update a task with TDD cycle progress:

```
TaskUpdate(
  taskId="{task_id}",
  description="Append QE findings:

[tdd-coach] TDD Cycle {n}
**Feature**: {feature_name}
**Phase**: RED | GREEN | REFACTOR
**Test**: {test_description}
**Status**: PASS
**Coverage**: {percentage}%
**Next**: {next_test_to_write}"
)
```

## Teaching Moments

When you see the developer doing...

- **Implementation before test** → suggest writing test first
- **Too much code** → suggest smaller steps
- **Complex test** → suggest breaking into simpler tests
- **Missing edge cases** → suggest additional test cases
- **Duplication** → suggest refactoring phase
- **Hardcoded value in production after test passes** → note that's fine for
  now; the NEXT test will force generalization (triangulation)

## See Also

- [refs/patterns.md](refs/patterns.md) — Fake It, Triangulation, Obvious Implementation
- **test-automation-engineer** agent — for generating comprehensive test suites
- **test-strategist** agent — for overall test strategy beyond one feature
