# User Story Template

Standard template for creating well-formed user stories with complete traceability.

## Basic Template

```markdown
### US-{ID}: {Story Title}

**As a** {specific persona}
**I want** {specific capability}
**So that** {specific benefit/value}

**Priority**: {P0/P1/P2/P3}
**Complexity**: {S/M/L/XL}
**Status**: {Draft/Ready/In Progress/Done}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}
2. Given {error condition}, When {action}, Then {error handling}
3. Given {edge case}, When {action}, Then {graceful behavior}

**Dependencies**: {Other stories, systems, or prerequisites}
**Assumptions**: {What we're assuming to be true}
**Open Questions**: {What needs clarification}
```

## Field Definitions

### Story ID (US-{ID})
- Unique identifier for traceability
- Format: `US-{number}` or `US-{project}-{number}`
- Example: `US-123`, `US-AUTH-42`

### Story Title
- Brief, descriptive name (3-7 words)
- Action-oriented
- Example: "Customer Registration", "Password Reset Flow"

### Persona
- Specific user role or type
- Not generic "user" unless truly universal
- Common: customer, admin, support agent, visitor, subscriber
- Can be system/API for technical stories

### Capability
- What the persona wants to do
- Stated from user's perspective
- Action verb + object
- Example: "log in with email", "export report to CSV"

### Benefit
- Why the capability is valuable
- Business or user outcome
- Starts with "so that"
- Example: "so that I can access my account", "so that I can analyze trends offline"

### Priority

| Level | Meaning | When to Use |
|-------|---------|-------------|
| **P0** | Critical | Blocks other work, security, data loss prevention |
| **P1** | High | Core functionality, common user flows |
| **P2** | Medium | Nice to have, quality of life improvements |
| **P3** | Low | Future enhancement, edge cases |

### Complexity

| Size | Time | Characteristics |
|------|------|-----------------|
| **S** | 1-2 days | Single component, clear scope, minimal dependencies |
| **M** | 3-5 days | Multiple components, moderate complexity |
| **L** | 1-2 weeks | Cross-cutting, significant integration |
| **XL** | 2+ weeks | Epic - should be broken down |

### Status

- **Draft**: Initial capture, not fully defined
- **Ready**: Acceptance criteria complete, ready for implementation
- **In Progress**: Actively being developed
- **Done**: All acceptance criteria met, shipped

## Acceptance Criteria Guidelines

Every story must have testable acceptance criteria in Given/When/Then format.

### Minimum Coverage

1. **Happy Path**: Normal, expected flow
2. **Error Handling**: Invalid input, failed dependencies
3. **Edge Cases**: Boundary conditions, rare scenarios
4. **Non-Functional**: Performance, security, usability (when applicable)

### Example: Login Story

```markdown
**Acceptance Criteria**:
1. Given valid email and password
   When I submit login form
   Then I am redirected to my dashboard

2. Given invalid password
   When I submit login form
   Then I see "Invalid email or password" error

3. Given account locked (3+ failed attempts)
   When I submit login form
   Then I see "Account locked. Reset password to unlock" message

4. Given successful login
   When I close browser and return within 24 hours
   Then I am still logged in (session persistence)
```

## Enhanced Template (Complex Stories)

For stories requiring additional detail:

```markdown
### US-{ID}: {Story Title}

**As a** {specific persona}
**I want** {specific capability}
**So that** {specific benefit/value}

**Priority**: {P0/P1/P2/P3}
**Complexity**: {S/M/L/XL}
**Status**: {Draft/Ready/In Progress/Done}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}
2. Given {error}, When {action}, Then {handling}

**Non-Functional Requirements**:
- Performance: {response time, throughput, etc.}
- Security: {authentication, authorization, data protection}
- Usability: {accessibility, mobile support, etc.}
- Reliability: {uptime, error recovery, etc.}

**Dependencies**:
- {US-XXX}: {Brief description of dependent story}
- {External System}: {API, service, or data dependency}

**Assumptions**:
- {Assumption 1}
- {Assumption 2}

**Open Questions**:
- [ ] {Question requiring stakeholder input}
- [ ] {Technical decision needed}

**Test Data Requirements**:
- {Data or state needed for testing}

**Out of Scope**:
- {Explicitly not included in this story}

**Notes**:
{Additional context, links to designs, related discussions}
```

## Common Story Patterns

### CRUD Operations

```markdown
### US-XXX: Create {Entity}

**As a** {persona}
**I want to** create a new {entity}
**So that** I can {benefit}

**Acceptance Criteria**:
1. Given all required fields, When I submit, Then {entity} is created
2. Given missing required field, When I submit, Then validation error shown
3. Given duplicate {unique field}, When I submit, Then error "Already exists"
```

### Search/Filter

```markdown
### US-XXX: Search {Entity}

**As a** {persona}
**I want to** search {entities} by {criteria}
**So that** I can quickly find {what I need}

**Acceptance Criteria**:
1. Given search term, When I search, Then matching results displayed
2. Given no matches, When I search, Then "No results" message shown
3. Given multiple filters, When I apply, Then results match all filters
```

### Import/Export

```markdown
### US-XXX: Export {Data}

**As a** {persona}
**I want to** export {data} to {format}
**So that** I can {use it externally}

**Acceptance Criteria**:
1. Given data exists, When I export, Then file downloads with all data
2. Given large dataset, When I export, Then progress indicator shown
3. Given no data, When I export, Then message "No data to export"
```

## Multi-Persona Stories

When one capability serves multiple personas:

```markdown
### US-XXX: View Dashboard

**As a** manager
**I want to** view team performance metrics
**So that** I can identify areas for improvement

**As a** team member
**I want to** view my individual metrics
**So that** I can track my progress

**Acceptance Criteria**:
1. Given I am a manager, When I view dashboard, Then I see all team metrics
2. Given I am a team member, When I view dashboard, Then I see only my metrics
3. Given no data for period, When I view dashboard, Then empty state shown
```

## Template Validation Checklist

Before marking a story as "Ready":

- [ ] Persona is specific and identified
- [ ] Capability is clear and actionable
- [ ] Benefit articulates value
- [ ] At least 3 acceptance criteria (happy path, error, edge case)
- [ ] All criteria are testable (can be verified)
- [ ] Dependencies are documented
- [ ] Ambiguities are captured in open questions
- [ ] Story is small enough (not an epic)
- [ ] Story is independent (or dependencies noted)

## Integration with Tools

### Storing in Kanban

```bash
# Add user story to kanban
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-kanban/scripts/kanban.py" \
  add-task "User Stories" "US-123: Customer Registration" \
  --tags "auth,p0" \
  --description "$(cat story.md)"
```

### Linking to Memory

```bash
# Store story pattern for recall
/wicked-garden:mem-store "auth-stories" "$(cat story.md)"
```

### Traceability

Stories should link to:
- Design documents: `See: phases/design/architecture.md`
- Test scenarios: `See: phases/qe/test-scenarios.md`
- Implementation: `Implemented in: PR-123`
- Kanban tasks: `Tracked: wicked-kanban task-456`

## Examples by Domain

### Authentication
```markdown
### US-AUTH-001: User Registration

**As a** new customer
**I want to** register with email and password
**So that** I can create an account and save my preferences

**Priority**: P0
**Complexity**: M

**Acceptance Criteria**:
1. Given valid email and password (8+ chars), When I register, Then account created
2. Given email already exists, When I register, Then error "Email already registered"
3. Given weak password, When I register, Then strength requirements shown
```

### E-commerce
```markdown
### US-SHOP-042: Add to Cart

**As a** customer
**I want to** add items to my shopping cart
**So that** I can purchase multiple products at once

**Priority**: P1
**Complexity**: S

**Acceptance Criteria**:
1. Given product in stock, When I click "Add to Cart", Then item added
2. Given out of stock, When I click "Add to Cart", Then "Out of Stock" message
3. Given item already in cart, When I add again, Then quantity increments
```

### Data Management
```markdown
### US-DATA-015: Export Report

**As a** manager
**I want to** export monthly sales data to CSV
**So that** I can analyze trends in Excel

**Priority**: P2
**Complexity**: M

**Acceptance Criteria**:
1. Given data exists, When I export, Then CSV downloads with all records
2. Given date range selected, When I export, Then only that period included
3. Given 10k+ records, When I export, Then async with email notification
```

## Template File Location

This template is referenced in:
- `skills/product-management/SKILL.md`
- Available for copy/paste or script generation

For automated generation, use:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/generate-story-template.sh
```
