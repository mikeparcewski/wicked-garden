---
description: Generate test code from scenarios or test plan
argument-hint: "<test plan file or scenarios> [--framework pytest|jest|go] [--output path]"
---

# /wicked-garden:qe:automate

Generate runnable test code from test scenarios or a QE test plan. Converts Given/When/Then scenarios into actual test implementations.

## Instructions

### 1. Identify Input

Determine what to convert:
- **Scenarios output**: From `/wicked-garden:qe:scenarios`
- **QE plan**: From `/wicked-garden:qe:qe-plan`
- **Manual scenarios**: User-provided test cases

If no input provided, check recent conversation for scenarios.

### 2. Detect Test Framework

If `--framework` not specified, auto-detect from project:

```
Search for existing test patterns:
- package.json → Jest/Vitest/Mocha
- pyproject.toml/setup.py → Pytest
- go.mod → Go testing
- pom.xml → JUnit
```

Note existing test file patterns and conventions.

### 3. Dispatch to Test Automation Engineer

```
Task(
  subagent_type="wicked-garden:qe/test-automation-engineer",
  prompt="""Generate runnable test code from scenarios.

## Scenarios to Implement
{scenarios or test plan}

## Framework
{detected or specified framework}

## Existing Patterns
{test file conventions found}

## Output Path
{specified or default test directory}

## Code Generation Requirements
Generate:
1. Test file(s) with all scenarios implemented
2. Fixtures/setup code as needed
3. Mocks for external dependencies
4. Clear Arrange-Act-Assert structure
5. Follow existing project test conventions

## Return Format
Provide complete test files ready to run, with setup instructions.
"""
)
```

### 4. Write Test Files

Create test files following project conventions:
- JavaScript/TypeScript: `*.test.ts`, `*.spec.ts`
- Python: `test_*.py`, `*_test.py`
- Go: `*_test.go`

### 5. Add Test Infrastructure (if needed)

If no test config exists, create:
- **Jest**: `jest.config.js`
- **Pytest**: `pytest.ini` or `pyproject.toml` section
- **Go**: No config needed

### 6. Present Summary

```markdown
## Test Automation Complete

### Files Created
| File | Tests | Coverage Target |
|------|-------|-----------------|
| {path} | {count} | {component} |

### Run Tests
```bash
{command to run tests}
```

### Run with Coverage
```bash
{coverage command}
```

### Next Steps
- [ ] Review generated tests
- [ ] Add missing edge cases
- [ ] Configure CI pipeline
```

## Example

```
User: /wicked-garden:qe:automate --framework pytest

Claude: I'll generate pytest tests from the scenarios we created earlier.

[Spawns test-automation-engineer with scenarios]
[Creates test files with fixtures]

## Test Automation Complete

### Files Created
| File | Tests | Coverage Target |
|------|-------|-----------------|
| tests/test_auth.py | 8 | Authentication flow |
| tests/test_user.py | 5 | User management |
| tests/conftest.py | - | Shared fixtures |

### Run Tests
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```
```

## Workflow Integration

This command is typically used after:
1. `/wicked-garden:qe:scenarios` - Generate test scenarios
2. `/wicked-garden:qe:qe-plan` - Create comprehensive test plan

Full QE workflow:
```
/wicked-garden:qe:scenarios User login flow
/wicked-garden:qe:automate --framework jest
/wicked-garden:qe:qe-review tests/
```
