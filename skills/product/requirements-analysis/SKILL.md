---
name: requirements-analysis
description: |
  Deep requirements elicitation and user story definition.
  Transform vague ideas into clear, testable specifications.

  Use when: "write user stories", "define requirements",
  "what are the acceptance criteria", "clarify scope"
---

# Requirements Analysis Skill

Structured requirements elicitation from discovery through documentation.

## Process

### 1. Context Gathering
- Read project brief, outcome.md, or requirements
- Identify existing documentation
- Note assumptions and constraints

### 2. Stakeholder Identification
- Who are the users/personas?
- Who are secondary stakeholders?
- Who has decision authority?

### 3. Requirements Elicitation

Ask the 5 W's:
- **Who**: Which users/personas?
- **What**: What capabilities needed?
- **When**: What triggers the need?
- **Where**: What context/environment?
- **Why**: What value/benefit?

### 4. User Story Definition

Format: **As a [persona], I want [capability], so that [benefit]**

Quality criteria:
- Specific persona identified
- Capability clearly stated
- Benefit/value articulated
- Testable outcome

### 5. Acceptance Criteria

For each story:
```
Given [context/precondition]
When [action/event]
Then [expected outcome]
```

Include:
- Happy path scenarios
- Error conditions
- Edge cases
- Non-functional requirements

### 6. Validation

Check:
- [ ] All stories have persona, capability, benefit
- [ ] Acceptance criteria are testable
- [ ] Edge cases identified
- [ ] Dependencies mapped
- [ ] Ambiguities flagged

## User Story Template

```markdown
### US{N}: {Story Title}

**As a** {specific persona}
**I want** {specific capability}
**So that** {specific benefit}

**Priority**: {P0/P1/P2}
**Complexity**: {S/M/L/XL}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}
2. Given {error condition}, When {action}, Then {error handling}
3. Given {edge case}, When {action}, Then {graceful handling}

**Non-Functional**:
- Performance: {requirement}
- Security: {requirement}
- Usability: {requirement}

**Dependencies**: {Other stories or systems}
**Assumptions**: {What we're assuming}
**Open Questions**: {What needs clarification}
```

## Common Patterns

**CRUD Operations**:
- Create: As a user, I want to create X, so that I can track Y
- Read: As a user, I want to view X, so that I can understand Y
- Update: As a user, I want to edit X, so that I can correct Y
- Delete: As a user, I want to remove X, so that I can clean up Y

**Authentication/Authorization**:
- Login, logout, password reset
- Role-based access control
- Session management

**Data Validation**:
- Input validation
- Error messaging
- Constraint enforcement

## Integration with Tools

```bash
# Search for similar requirements
/wicked-garden:search:doc "user story" --context requirements

# Store requirements in kanban
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" \
  add-comment "Requirements" "{task_id}" "{user_stories}"

# Recall past patterns
/wicked-garden:mem:recall "requirements for {feature_type}"
```

## Output Format

See: `refs/requirements-output-format.md`
