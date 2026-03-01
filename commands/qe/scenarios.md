---
description: Generate test scenarios with happy paths, edge cases, and error conditions
argument-hint: "<feature, function, or user story>"
---

# /wicked-garden:qe:scenarios

Generate comprehensive test scenarios for a feature, function, or user story. Covers happy paths, edge cases, error conditions, and boundary cases.

## Instructions

### 1. Parse the Input

Identify what needs scenarios:
- **Function**: specific function/method behavior
- **Feature**: user-facing feature with flows
- **User Story**: acceptance criteria driven
- **API Endpoint**: request/response scenarios

### 2. Read Related Code

If implementation exists, read it to understand:
- Input parameters and types
- Validation rules
- Business logic branches
- Error handling paths
- Dependencies and side effects

### 3. Dispatch to Test Strategist

```
Task(
  subagent_type="wicked-garden:qe:test-strategist",
  prompt="""Generate comprehensive test scenarios.

## Target
{feature/function description}

## Code Context
{relevant code}

## Scenario Requirements
Generate comprehensive scenarios covering:
1. Happy path scenarios - Normal, expected usage
2. Edge cases - Boundaries, empty/null values, limits
3. Error conditions - Invalid input, failures, exceptions
4. Concurrent/timing scenarios - Race conditions, timeouts (if applicable)
5. Security scenarios - Auth, injection, access control (if applicable)

## Return Format
Provide scenarios organized by category with Given/When/Then format:
- Happy Path: HP-1, HP-2, etc.
- Edge Cases: EC-1, EC-2, etc.
- Error Conditions: ERR-1, ERR-2, etc.
- Security: SEC-1, SEC-2, etc.

Include test data examples and why each scenario matters.
"""
)
```

### 4. Categorize Scenarios

Organize scenarios by type:

**Happy Path** - Normal, expected usage
**Edge Cases** - Boundary conditions, limits
**Error Handling** - Invalid input, failures
**Security** - Auth, injection, access control
**Performance** - Load, timeout, resource limits

### 5. Present Scenarios

```markdown
## Test Scenarios: {feature/function}

### Happy Path Scenarios

#### HP-1: {scenario name}
**Given**: {preconditions}
**When**: {action}
**Then**: {expected outcome}
**Test Data**: {example input → output}

#### HP-2: {scenario name}
...

### Edge Cases

#### EC-1: {scenario name}
**Given**: {preconditions}
**When**: {boundary condition}
**Then**: {expected behavior}
**Why**: {why this matters}

#### EC-2: Empty input
**Given**: {preconditions}
**When**: Empty/null/undefined input provided
**Then**: {expected handling}

#### EC-3: Maximum values
**Given**: {preconditions}
**When**: Input at maximum allowed size/value
**Then**: {expected behavior}

### Error Conditions

#### ERR-1: {error scenario}
**Given**: {preconditions}
**When**: {invalid condition}
**Then**: {error response/exception}
**Error**: `{ErrorType}` with message "{message}"

#### ERR-2: Dependency failure
**Given**: {external dependency}
**When**: Dependency fails/times out
**Then**: {graceful handling}

### Security Scenarios

#### SEC-1: Unauthorized access
**Given**: User without required permissions
**When**: Attempts to {action}
**Then**: Access denied with 403

#### SEC-2: Input injection
**Given**: Malicious input containing {type}
**When**: Processed by system
**Then**: Input sanitized, no injection

### Scenario Summary

| Category | Count | Priority |
|----------|-------|----------|
| Happy Path | {n} | P1 |
| Edge Cases | {n} | P2 |
| Error Handling | {n} | P1 |
| Security | {n} | P1 |

### Coverage Notes
- {areas well covered}
- {gaps or areas needing more scenarios}
```

### 6. Optional: Export Format

If user needs specific format:
- **Gherkin**: Convert to Given/When/Then feature files
- **Table**: Condensed table format
- **Code**: Generate test function stubs
- **wicked-scenarios**: Convert to executable wicked-scenarios markdown format (see Step 7)

### 7. Optional: Generate Wicked-Scenarios Format

When the user requests `--format wicked-scenarios`, convert the Given/When/Then scenarios into executable wicked-scenarios markdown files.

For each scenario category that has relevant CLI tools, produce a wicked-scenarios markdown block:

**Category → wicked-scenarios mapping:**

| QE Category | wicked-scenarios category | Tools |
|-------------|--------------------------|-------|
| Happy Path (HP-) | api | curl, hurl |
| Edge Cases (EC-) | api | curl, hurl |
| Error Conditions (ERR-) | api | curl |
| Security (SEC-) | security | semgrep |
| Performance | perf | k6, hey |

**Output format** — one scenario block per category group:

````markdown
---
name: {feature-kebab}-{category}
description: "{Category} scenarios for {feature}"
category: {mapped category}
tools:
  required: [{primary tool}]
  optional: [{secondary tools}]
difficulty: {basic|intermediate|advanced based on scenario complexity}
timeout: 60
---

## Steps

### Step 1: {HP-1/EC-1/ERR-1 scenario name} ({tool})

```bash
{executable CLI command derived from Given/When/Then}
```

**Expect**: {Then condition mapped to exit code expectation}

### Step 2: {next scenario} ({tool})

```bash
{executable CLI command}
```

**Expect**: {expected outcome}
````

**Conversion rules:**
- **Given** → Setup section or prerequisite commands
- **When** → Step action matching the category tool (curl for api, semgrep for security, k6 for perf)
- **Then** → Expected exit code and output validation
- Test data from scenarios → environment variables in `env:` frontmatter or Setup section
- Group related scenarios (e.g., all HP- scenarios) into a single wicked-scenarios file
- Security (SEC-) scenarios use `semgrep` for static analysis; dynamic HTTP security tests (rate limiting, auth bypass via curl) go in a separate `api` category scenario
- If a scenario can't be converted to a CLI command (e.g., UI-only), note it as a comment and skip

## Example

```
User: /wicked-garden:qe:scenarios User password reset flow

Claude: I'll generate comprehensive test scenarios for the password reset flow.

[Reads password reset implementation]
[Spawns test-strategist for scenario generation]

## Test Scenarios: Password Reset Flow

### Happy Path Scenarios

#### HP-1: Successful password reset
**Given**: User with email "user@example.com" exists
**When**: User requests password reset, receives email, clicks link, enters new password
**Then**: Password updated, user can login with new password
**Test Data**: valid email → reset email sent → token valid 24h → new password accepted

#### HP-2: Reset with valid token
**Given**: Valid reset token exists for user
**When**: User submits new password meeting requirements
**Then**: Password updated, token invalidated, confirmation shown

### Edge Cases

#### EC-1: Token at expiration boundary
**Given**: Reset token created exactly 24 hours ago
**When**: User attempts to use token
**Then**: Token rejected as expired

#### EC-2: Password at minimum length
**Given**: Valid reset token
**When**: User submits 8-character password (minimum)
**Then**: Password accepted

### Error Conditions

#### ERR-1: Non-existent email
**Given**: No user with email "unknown@example.com"
**When**: Password reset requested
**Then**: Same success message shown (no enumeration)

#### ERR-2: Expired token
**Given**: Reset token older than 24 hours
**When**: User attempts to reset password
**Then**: Error "Reset link has expired" shown

#### ERR-3: Already-used token
**Given**: Reset token already used
**When**: User attempts to use again
**Then**: Error "This link has already been used"

### Security Scenarios

#### SEC-1: Input injection
**Given**: Malicious input containing SQL/XSS payload
**When**: Submitted through reset form
**Then**: Input sanitized, no injection executed

#### SEC-2: Token enumeration
**Given**: Attacker with random reset tokens
**When**: Brute-force token guessing attempted
**Then**: Tokens are cryptographically random, guessing infeasible
```
