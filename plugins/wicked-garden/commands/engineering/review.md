---
description: Code review with senior engineering perspective on quality, patterns, and maintainability
argument-hint: "[file or directory path] [--focus security|performance|patterns|tests] [--scenarios]"
---

# /wicked-garden:engineering-review

Perform a thorough code review with senior engineering perspective. Evaluates code quality, architecture patterns, maintainability, and provides actionable feedback.

Use `--focus` to dive deeper into a specific area:
- **security** — input validation, injection, auth, sensitive data handling
- **performance** — N+1 queries, unnecessary iterations, memory leaks, caching
- **patterns** — design patterns, SOLID, abstraction levels, coupling
- **tests** — test value and quality. The core question: "What should break in the product for this test to fail?" If the answer is "nothing meaningful", the test is low-value. Favors fewer, higher-quality tests where each test is simple and focuses on one thing.

## Instructions

### 1. Determine Scope

If path provided, focus on that file/directory.
If no path, check for:
- Uncommitted changes: `git diff --name-only`
- Recent commits: `git log --oneline -5`
- Ask user what to review

### 2. Understand the application

Create a fast/shallow base report with your understanding to help with the

Before your deep review, inspect the application to quickly understand it's:
- Languages and frameworks
- Design approach
- Development style
- Key components
- Hotspots (most connected)
- Areas of complexity

**Important:** This is meant to be a fast/shallow review, just to get bearings.

NOTE: When available, use the wicked-* marketplace tools to speed up discovery.

### 3. Application Review

```python
Task(
    subagent_type="wicked-garden:engineering/senior-engineer",
    prompt="""Review this code for quality, patterns, and maintainability.

## Target
{code content}

## Context
{file purpose, related files, traced request paths}

## Focus Areas
1. Code clarity and readability
2. Error handling completeness — what happens when a call fails mid-chain?
3. Contract enforcement — do callers validate what callees return?
4. Context/data optimization — is unnecessary data being passed between components?
5. Failure recovery — where would failures cascade silently?
6. Naming and conventions
7. Potential bugs or edge cases
8. Performance considerations
9. Test quality — for each test ask "what product bug would make this fail?" Flag tests that assert their own inputs back or mirror implementation logic. Prefer fewer, focused tests over many low-value ones

## Return Format
Cite file:line for each finding. Structure as:
- Critical Design Gaps
- Silent Failure Risks
- Context Optimization Opportunities
- Suggestions
"""
)
```

### 4. Optional: Focused Analysis

If `--focus` specified:

**security**: Security review
```python
Task(
    subagent_type="wicked-garden:qe/code-analyzer",
    prompt="""Security-focused analysis of code.

## Target
{files}

## Security Checklist
- Input validation
- Injection vulnerabilities
- Auth/authz issues
- Sensitive data handling

## Return Format
List findings with file:line references and severity.
"""
)
```

**performance**: Performance issues
```python
Task(
    subagent_type="wicked-garden:engineering/backend-engineer",  # or frontend-engineer based on stack
    prompt="""Performance analysis of code.

## Target
{files}

## Performance Checklist
- N+1 queries
- Unnecessary iterations
- Memory leaks
- Caching opportunities

## Return Format
List findings with file:line references and impact estimates.
"""
)
```

**patterns**: Architecture and design patterns
```python
Task(
    subagent_type="wicked-garden:engineering/solution-architect",
    prompt="""Pattern analysis of code.

## Target
{files}

## Pattern Checklist
- Design pattern usage
- SOLID principles adherence
- Abstraction levels
- Coupling and cohesion

## Return Format
Evaluate each pattern with examples from code.
"""
)
```

**tests**: Test quality and value
```python
Task(
    subagent_type="wicked-garden:qe/code-analyzer",
    prompt="""Evaluate test quality. Fewer, higher-quality tests beat many low-value ones.

## Target
{test files}

## Core Question
For each test, ask: "What should break in the product for this test to fail?"
If the answer is "nothing meaningful", the test is low-value.

## Low-Value Test Patterns (flag as issues)
- **Tautological assertions**: constructs object, asserts own inputs back
  (`user = User("alice"); assert user.name == "alice"`)
- **Implementation mirroring**: re-implements production logic to compute expected value
- **Mock-heavy isolation**: everything mocked, test only verifies mocks return what they were told
- **Trivial coverage padding**: testing getters/setters, default constructors, obvious delegation
- **Multiple concerns**: test checks too many things, making failures hard to diagnose

## What Good Tests Do
- Each test is simple and focuses on one thing
- Tests a behavior the user cares about — there's a concrete product scenario
- Would catch a real regression — if someone breaks X, this test turns red
- Tests boundaries and edge cases — empty inputs, error paths, off-by-one

## Return Format
For each test file, list:
- Tests to DELETE (zero value, with reason)
- Tests to REWRITE (has intent but tests the wrong thing, with what to test instead)
- Tests that are GOOD (cite the product behavior they protect)
- Missing tests (real product scenarios with no coverage)

Cite file:line for every finding.
"""
)
```

### 5. Check for Agent Overstepping

Evaluate whether changes stay within the intended scope. Look for these anti-patterns:

**Unnecessary Changes (flag as HIGH)**:
- Code modified that wasn't part of the task (renames, reformatting, refactoring unrelated code)
- Working logic replaced with "simplified" alternatives that change behavior
- Added abstractions, utilities, or helpers for one-time operations
- Import reorganization or style changes outside the task scope

**Commented-Out Code (flag as HIGH)**:
- Working code commented out instead of cleanly removed
- Logic replaced with TODO comments instead of being implemented or left alone
- Backward-compatibility shims like `// removed` or `_unused_var` renames

**Over-Engineering (flag as MEDIUM)**:
- Error handling added for scenarios that can't happen
- Feature flags or configuration for non-configurable features
- Premature abstractions designed for hypothetical future needs
- Extra validation beyond system boundaries (trusting internal code is fine)

**Scope Creep (flag as MEDIUM)**:
- Files modified that weren't mentioned in the original task
- Refactoring mixed into unrelated bug fixes or feature work
- Documentation updates for code that wasn't changed

If agent overstepping is detected, add an **Agent Overstepping** section to the review output.

### 6. Present Findings

```markdown
## Code Review: {scope}

### Summary
{overall assessment - good/needs work/critical issues}

### Strengths
- {what's done well, with file:line references}

### Critical Design Gaps
- **{issue}** in `{file}:{line}` - {description with code evidence}

### Silent Failure Risks
- **{risk}** traced through `{file_a}:{line}` → `{file_b}:{line}` - {what fails and why}

### Context Optimization Opportunities
- **{opportunity}** in `{file}:{line}` - {what's being passed unnecessarily, with size estimate}

### Suggestions
- **{suggestion}** in `{file}:{line}` - {description and recommendation}

### Recommendations
1. {prioritized action item}
2. {next action}
```

### 7. Optional: Generate Wicked-Scenarios Format

When `--scenarios` is passed, generate wicked-scenarios format test scenarios that would catch regressions for the identified review findings.

**Finding type → scenario mapping:**

| Finding Type | Scenario Category | Tools | What to Test |
|-------------|-------------------|-------|-------------|
| Critical Design Gaps | api | curl, hurl | API contract violations, missing validation |
| Silent Failure Risks | api | curl | Error cascade paths, failure recovery |
| Security findings (--focus security) | security | semgrep | Static analysis for injection, auth bypass, data exposure |
| Performance findings (--focus performance) | perf | k6, hey | Load thresholds, response time regression |
| Test gaps (--focus tests) | api | curl, hurl | Missing coverage for product behaviors |

For each actionable finding, produce a wicked-scenarios block:

````markdown
---
name: {scope-kebab}-regression
description: "Regression scenarios from code review of {scope}"
category: {mapped category}
tools:
  required: [{primary tool}]
  optional: [{secondary tools}]
difficulty: intermediate
timeout: 60
---

## Steps

### Step 1: {Finding title} ({tool})

```bash
{CLI command that verifies the fix or tests the vulnerable path}
```

**Expect**: {What correct behavior looks like — exit code, response content}
````

**Conversion rules:**
- Each Critical/High finding with a testable fix → one scenario step
- Silent failure paths → steps that exercise the failure chain and verify graceful handling
- Test gaps → steps that cover the missing product behavior
- If finding is design-level (not testable via CLI), skip it and note why
