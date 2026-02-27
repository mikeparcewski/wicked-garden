---
name: acceptance-criteria
description: |
  Define testable acceptance criteria from requirements and design.
  Bridge product requirements with QE test scenarios.

  Use when: "define acceptance criteria", "how do we know it's done",
  "what should QE test", "definition of done"
---

# Acceptance Criteria Skill

Transform requirements into testable acceptance criteria.

## Core Concept

Acceptance criteria are the contract between product and delivery:
- Product: "Here's what success looks like"
- QE: "Here's how we verify it"
- Engineering: "Here's what we must deliver"

## Given/When/Then Format

```
Given [precondition/context]
When [action/event]
Then [expected outcome]
```

**Why this format?**
- Forces specificity
- Testable by definition
- Clear success criteria
- Language-agnostic

## Process

### 1. Read Requirements

Understand:
- User stories
- Design documents
- Business rules
- Constraints

### 2. Identify Scenarios

For each requirement, consider:
- **Happy path**: Normal, expected flow
- **Error conditions**: Invalid inputs, failures
- **Edge cases**: Boundaries, empty states
- **Non-functional**: Performance, security, usability

### 3. Write Criteria

Format each scenario:
```
Given [specific context]
When [specific action]
Then [specific, measurable outcome]
```

### 4. Validate

Check each criterion:
- [ ] Specific (not vague)
- [ ] Testable (can verify)
- [ ] Measurable (clear pass/fail)
- [ ] Independent (standalone)
- [ ] Complete (covers scenario)

### 5. Organize by Priority

- **P0**: Must have (blocker if missing)
- **P1**: Should have (important)
- **P2**: Nice to have (enhancement)

## Example: Login Feature

```markdown
### US1: User Authentication

**Happy Path (P0)**:
AC1: Given valid credentials, When user submits login, Then user redirected to dashboard
AC2: Given successful login, When checking session, Then session valid for 30 minutes

**Error Handling (P0)**:
AC3: Given invalid password, When user submits login, Then error message "Invalid credentials"
AC4: Given account locked, When user submits login, Then error message "Account locked"
AC5: Given 3 failed attempts, When user tries again, Then account locked for 15 minutes

**Edge Cases (P1)**:
AC6: Given empty email field, When user submits, Then error "Email required"
AC7: Given malformed email, When user submits, Then error "Invalid email format"
AC8: Given concurrent logins, When second login occurs, Then first session invalidated

**Non-Functional (P1)**:
AC9: Given 1000 concurrent logins, When system under load, Then response time < 2 seconds
AC10: Given login attempt, When credentials checked, Then password encrypted in transit
```

## Common Patterns

**Data Creation**:
```
Given user on create form
When user enters valid data and submits
Then new record saved and confirmation shown
```

**Data Validation**:
```
Given user on form with required fields
When user submits without filling required field
Then error message shown and form not submitted
```

**Authorization**:
```
Given user without admin role
When user attempts admin action
Then access denied message shown
```

**API Response**:
```
Given valid API request
When endpoint called
Then 200 status and expected JSON schema returned
```

## Integration with QE

Acceptance criteria feed directly into test scenarios:

```bash
# Product defines AC
/wicked-garden:product-acceptance phases/design/

# QE generates test scenarios from AC
/wicked-garden:qe-analyze --gate strategy
```

**Flow**:
1. Product: Write acceptance criteria
2. QE: Review and generate test scenarios
3. Engineering: Implement to meet criteria
4. QE: Verify against criteria

## Quality Checklist

Good acceptance criteria:
- [ ] Use Given/When/Then format
- [ ] Specific and unambiguous
- [ ] Testable with clear pass/fail
- [ ] Cover happy path, errors, edges
- [ ] Include non-functional requirements
- [ ] Prioritized by criticality
- [ ] Reviewed by QE for testability

## Output Format

```markdown
## Acceptance Criteria

### User Story: {Story Title}

**Happy Path**:
- AC1: Given {context}, When {action}, Then {outcome} [P0]

**Error Conditions**:
- AC2: Given {error}, When {action}, Then {handling} [P0]

**Edge Cases**:
- AC3: Given {edge}, When {action}, Then {behavior} [P1]

**Non-Functional**:
- AC4: Given {load}, When {action}, Then {performance} [P1]

**Test Data Requirements**:
- {Data needed for testing}

**QE Handoff Notes**:
- {Special testing considerations}
```

## Progressive Disclosure

- **SKILL.md** (this file): Quick reference
- **refs/ac-examples.md**: More examples by domain
- **refs/ac-anti-patterns.md**: Common mistakes to avoid
