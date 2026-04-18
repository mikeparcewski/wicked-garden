# TDD Patterns Reference

## Fake It Till You Make It

Start with hardcoded values, generalize as tests demand.

```javascript
// Test 1
test('parse returns empty for empty input', () => {
  expect(parse('')).toEqual([]);
});
// Implementation: return []

// Test 2
test('parse returns single item', () => {
  expect(parse('a')).toEqual(['a']);
});
// Implementation: return input ? [input] : []
```

**Why**: prevents over-engineering. You only generalize when a second test
forces you to. Keeps the cycles tight and the code minimal.

## Triangulation

Add tests from different angles to drive the design. Each test pulls the
implementation toward a more general form.

```javascript
test('sum of empty array is 0', () => {
  expect(sum([])).toBe(0);
});

test('sum of [5] is 5', () => {
  expect(sum([5])).toBe(5);
});

test('sum of [1,2,3] is 6', () => {
  expect(sum([1,2,3])).toBe(6);
});
```

After three tests like this, the only implementation that satisfies all of
them is the real one.

## Obvious Implementation

If the solution is obvious, write it. Don't force Fake-It when the real code
is as simple as the fake.

```javascript
test('max returns larger number', () => {
  expect(max(5, 10)).toBe(10);
});

function max(a, b) {
  return a > b ? a : b; // Obvious
}
```

**Signal that the implementation is "obvious"**: you can see the answer in
under 10 seconds and it fits in under 5 lines.

## When to Use Which

| Pattern | Use When |
|---------|----------|
| Fake It | You're unsure of the general shape; start concrete |
| Triangulation | You want multiple tests to drive a clean abstraction |
| Obvious Implementation | The answer is trivial and writing a fake is wasted motion |

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

## Common Anti-Patterns

### Writing too much test
```javascript
// Bad: tests three behaviors in one
test('calculator works', () => {
  expect(add(1, 2)).toBe(3);
  expect(subtract(5, 2)).toBe(3);
  expect(multiply(2, 3)).toBe(6);
});
```

Split into three tests, one behavior each.

### Writing too much implementation
```javascript
// Test says: sum of empty array is 0
function sum(items) {
  // Resisting the urge to write a full reduce is the discipline
  if (!items.length) return 0;
  return items.reduce((a, b) => a + b, 0);  // too much
}

// Correct TDD-GREEN response:
function sum(items) {
  return 0;
}
```

### Test-after TDD
Writing the implementation first and tests after is not TDD. The whole point
of RED is that you confirm the test catches the absence of the feature.

### Skipping REFACTOR
Going RED → GREEN → RED → GREEN without refactoring accumulates duplication
and ugly code even though tests pass. Refactor whenever duplication or
unclear naming appears.

## Coaching Output Template

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

Optionally append progress to the active task via `TaskUpdate`:

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

## Teaching Moments Checklist

When coaching, actively watch for and surface:

- [ ] Developer wrote production code first → reset, start with a test
- [ ] Test covers multiple behaviors → split into smaller tests
- [ ] Test uses real time / randomness → inject a clock / seed
- [ ] Test depends on other tests → isolate with fresh fixtures
- [ ] Test name is "test_1" or "it works" → describe the behavior
- [ ] Implementation has code the tests don't require → delete it
- [ ] GREEN phase writes the "real" solution → let triangulation drive it
- [ ] Refactor introduces a new behavior → that's a new test, not a refactor
- [ ] Tests are slow → separate unit vs integration; move slow ones out
- [ ] Too much code at once → suggest smaller steps
- [ ] Missing edge cases → suggest additional test cases
- [ ] Duplication appears → suggest refactoring phase
- [ ] Hardcoded value after test passes → that's fine for now; the NEXT test
      will force generalization (triangulation)
