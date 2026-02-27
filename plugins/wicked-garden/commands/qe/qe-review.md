---
description: Review test quality, coverage, and test code best practices
argument-hint: "<test file or directory> [--focus coverage|quality|flakiness]"
---

# /wicked-garden:qe-qe-review

Review test code quality, coverage effectiveness, and adherence to testing best practices. Identifies test smells, coverage gaps, and flaky test patterns.

## Instructions

### 1. Identify Test Files

If path provided, use it. Otherwise search for tests:

```bash
# Find test files
find {project_root} -name "*.test.*" -o -name "*.spec.*" -o -name "test_*.py" -o -name "*_test.go"
```

### 2. Read Test Code

For each test file, analyze:
- Test structure and organization
- Assertion patterns
- Setup/teardown usage
- Mocking approach
- Test naming conventions

### 3. Run Coverage Analysis (if available)

```bash
# Check if coverage tool available
npm test -- --coverage 2>/dev/null || pytest --cov 2>/dev/null
```

Parse coverage output for:
- Overall coverage percentage
- Uncovered lines/branches
- Files with low coverage

### 4. Dispatch to Test Strategist for Review

```
Task(
  subagent_type="wicked-garden:qe/test-strategist",
  prompt="""Review these test files for quality and effectiveness.

## Test Code
{test code}

## Source Code Being Tested
{relevant source files}

## Evaluation Checklist
1. Test coverage completeness - Are all code paths tested?
2. Edge case coverage - Boundary conditions, null/empty, limits?
3. Test isolation and independence - Tests don't depend on each other?
4. Assertion quality - Specific, meaningful assertions?
5. Test naming and readability - Clear intent from names?
6. Potential flakiness patterns - Timing, randomness, external deps?

## Return Format
Provide structured assessment with:
- Coverage completeness score and gaps
- Edge cases missing
- Isolation issues found
- Assertion quality notes
- Flakiness risks identified
"""
)
```

### 5. Check for Agent Test Manipulation

Detect patterns where AI agents weaken tests to make them pass:

**Tests That Always Pass (flag as CRITICAL)**:
- Tests with no assertions or only trivial assertions (`assert True`)
- Try/catch blocks that swallow test failures
- Tests that assert on the mock return value instead of real behavior
- Conditional assertions that skip when conditions aren't met

**Weakened Tests (flag as HIGH)**:
- Assertions changed from strict equality to loose containment
- Expected values updated to match buggy output instead of fixing the bug
- Error assertions removed or replaced with "any error" matchers
- Reduced assertion count compared to previous version
- Timeouts increased dramatically to mask performance regressions

**Coverage Reduction (flag as HIGH)**:
- Test cases deleted without replacement
- Parameterized tests reduced to fewer cases
- Edge case tests removed as "unnecessary"
- Integration tests downgraded to unit tests that mock everything

**Bad Test Practices (flag as MEDIUM)**:
- Tests that test the mock, not the implementation
- Snapshot tests replacing behavioral assertions
- Tests with misleading names (name says one thing, test does another)
- Shared mutable state between tests masking failures

If test manipulation is detected, add a **Test Integrity Concerns** section to the review output with severity and specific evidence.

### 6. Check for Test Smells

Common issues to identify:

**Structural Smells**:
- Tests with no assertions
- Tests with multiple unrelated assertions
- Deeply nested test blocks
- Copy-paste test code
- Magic numbers without context

**Isolation Smells**:
- Shared mutable state between tests
- Order-dependent tests
- Tests that modify global state
- Missing cleanup in teardown

**Flakiness Patterns**:
- Timing-dependent assertions
- Network calls without mocking
- File system dependencies
- Date/time sensitivity
- Race conditions

**Coverage Gaps**:
- Missing error path tests
- No edge case coverage
- Untested public methods
- Missing integration tests

### 6. Optional: Focused Analysis

If `--focus` specified:

**coverage**: Deep coverage analysis
```
Identify:
- Uncovered code paths
- Missing branch coverage
- Untested error handlers
- Dead code indicated by no coverage
```

**quality**: Test code quality
```
Evaluate:
- Arrange-Act-Assert structure
- Test helper reuse
- Fixture quality
- Assertion specificity
```

**flakiness**: Flaky test detection
```
Check for:
- Timing dependencies
- External service calls
- Random data without seeds
- Async race conditions
```

### 7. Present Review

```markdown
## QE Review: {scope}

### Summary
**Overall Quality**: {Good|Needs Work|Poor}
**Coverage**: {percentage}%
**Test Count**: {total tests}

### Test Quality Assessment

| Category | Score | Notes |
|----------|-------|-------|
| Coverage | {1-5} | {notes} |
| Isolation | {1-5} | {notes} |
| Readability | {1-5} | {notes} |
| Maintainability | {1-5} | {notes} |

### Test Smells Found

#### Critical
- **{smell}** in `{file}:{line}` - {description}
  ```{language}
  {problematic code}
  ```
  **Fix**: {recommendation}

#### Warnings
- **{smell}** in `{file}` - {description}

### Coverage Gaps

| Component | Current | Target | Gap |
|-----------|---------|--------|-----|
| {module} | {%} | 80% | {missing areas} |

### Flakiness Risk

| Test | Risk | Reason |
|------|------|--------|
| `{test name}` | High/Med/Low | {why it might flake} |

### Recommendations

#### Immediate (P1)
1. {critical fix}

#### Short-term (P2)
1. {improvement}

#### Long-term (P3)
1. {refactoring suggestion}

### Missing Test Scenarios
- [ ] {scenario not covered}
- [ ] {edge case missing}
```

## Example

```
User: /wicked-garden:qe-qe-review tests/ --focus quality

Claude: I'll review the test quality in the tests/ directory.

[Reads test files]
[Spawns test-strategist for analysis]
[Checks for test smells]

## QE Review: tests/

### Summary
**Overall Quality**: Needs Work
**Coverage**: 67%
**Test Count**: 45 tests

### Test Quality Assessment

| Category | Score | Notes |
|----------|-------|-------|
| Coverage | 3/5 | Missing error paths |
| Isolation | 4/5 | Good fixture usage |
| Readability | 2/5 | Inconsistent naming |
| Maintainability | 3/5 | Some duplication |

### Test Smells Found

#### Critical
- **Test with no assertions** in `test_user.py:45`
  ```python
  def test_create_user():
      user = create_user("test")
      # No assertion!
  ```
  **Fix**: Add `assert user.id is not None`

#### Warnings
- **Magic numbers** in `test_auth.py` - Use named constants

### Recommendations

#### Immediate (P1)
1. Add assertions to 3 empty tests
2. Fix timing-dependent test in test_async.py

#### Short-term (P2)
1. Increase coverage of error handlers to 80%
2. Add edge case tests for boundary conditions
```

## Workflow Integration

Use as part of QE workflow:
```
/wicked-garden:qe-scenarios Feature X      # Generate scenarios
/wicked-garden:qe-automate --framework jest # Generate test code
/wicked-garden:qe-qe-review tests/          # Review quality
```
