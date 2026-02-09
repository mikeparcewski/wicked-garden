---
description: Generate comprehensive QE test plan for a feature or change
argument-hint: "<feature or change description> [--scope unit|integration|e2e|all]"
---

# /wicked-qe:qe-plan

Generate a comprehensive Quality Engineering test plan for a feature, change, or component. Identifies what to test, risk areas, and test coverage strategy.

## Instructions

### 1. Understand the Feature

Parse the feature/change description to identify:
- Core functionality to test
- User-facing behaviors
- Edge cases and error conditions
- Integration points

If a code path is provided, read it to understand the implementation.

### 2. Explore Existing Tests

Search for existing test patterns:
```
Glob: **/*.test.*, **/*.spec.*, **/test_*.py, **/*_test.go
```

Note:
- Test framework in use
- Test organization patterns
- Existing coverage for related code
- Mocking/fixture patterns

### 3. Dispatch to Test Strategist and Risk Assessor (Parallel)

```
Task(
  subagent_type="wicked-qe:test-strategist",
  prompt="""Create comprehensive test strategy.

## Feature Description
{description}

## Implementation
{key files and logic}

## Existing Tests
{relevant test files}

## Strategy Requirements
Generate:
1. Test categories needed (unit, integration, e2e)
2. Critical paths that must be tested
3. Edge cases and error scenarios
4. Risk-based test prioritization

## Return Format
Provide test coverage matrix, unit/integration/e2e test breakdowns, and prioritized test list.
"""
)

Task(
  subagent_type="wicked-qe:risk-assessor",
  prompt="""Identify testing risks for this feature.

## Feature Description
{description}

## Components Affected
{affected files}

## Risk Assessment Checklist
1. High-risk areas needing thorough testing
2. Failure modes to cover in tests
3. Dependencies that could fail
4. Data edge cases and boundary conditions

## Return Format
Provide risk areas table with severity, test coverage needs, and confidence levels.
"""
)
```

### 5. Generate Test Plan

```markdown
## QE Test Plan: {feature}

### Overview
**Feature**: {description}
**Scope**: {unit|integration|e2e|all}
**Risk Level**: {low|medium|high}

### Test Coverage Matrix

| Component | Unit | Integration | E2E | Priority |
|-----------|------|-------------|-----|----------|
| {component} | ✓ | ✓ | - | P1 |

### Unit Tests

#### {Component/Function}
| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_{name}` | {what it verifies} | P1 |
| `test_{name}_error` | {error case} | P2 |

**Edge Cases:**
- {edge case to test}

### Integration Tests

#### {Integration Point}
| Test Case | Description | Dependencies |
|-----------|-------------|--------------|
| `test_{flow}` | {what it verifies} | {mocks needed} |

### E2E Tests

#### {User Flow}
| Scenario | Steps | Expected Outcome |
|----------|-------|------------------|
| {scenario} | {steps} | {result} |

### Risk Mitigation

| Risk | Test Coverage | Confidence |
|------|---------------|------------|
| {risk} | {tests that cover it} | High/Med/Low |

### Test Data Requirements
- {data setup needed}
- {fixtures to create}

### Environment Requirements
- {services needed}
- {configuration}

### Acceptance Criteria
- [ ] All P1 tests pass
- [ ] {coverage threshold}% coverage on new code
- [ ] No critical/high severity bugs
```

### 6. Optional: Generate Test Stubs

If user wants test implementation:
```
Task(
  subagent_type="wicked-qe:test-automation-engineer",
  prompt="""Generate test stubs from this test plan.

## Test Plan
{test plan}

## Framework
Use: {detected framework}

## Existing Patterns
Follow patterns from: {existing test files}

## Return Format
Provide test file structure with stubs for all test cases in the plan.
"""
)
```
