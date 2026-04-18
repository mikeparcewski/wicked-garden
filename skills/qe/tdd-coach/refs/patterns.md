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
