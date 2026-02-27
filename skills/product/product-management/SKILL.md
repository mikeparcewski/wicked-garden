---
name: product-management
description: |
  Strategic product thinking for roadmap, priorities, and business value.
  Elicit requirements, define scope, and align stakeholders.
  Works standalone or integrated with wicked-crew.

  Use when: "product strategy", "requirements", "user stories",
  "what should we build", "prioritize features", "scope definition"
---

# Product Management Skill

Bridge customer needs with delivery execution through structured product thinking.

## Core Concept

Product management is clarity. Transform vague ideas into actionable requirements
with clear acceptance criteria and aligned stakeholders.

## Three Key Activities

| Activity | When | Output |
|----------|------|--------|
| **Elicit** | Early clarify | Requirements, user stories, scope |
| **Acceptance** | Post-design | Acceptance criteria, test scenarios |
| **Align** | Throughout | Stakeholder consensus, trade-offs |

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:product:elicit` | Requirements elicitation |
| `/wicked-garden:product:acceptance` | Define acceptance criteria |
| `/wicked-garden:product:align` | Stakeholder alignment |

## Usage

```bash
# Elicit requirements from brief
/wicked-garden:product:elicit outcome.md

# Define acceptance criteria from design
/wicked-garden:product:acceptance phases/design/

# Facilitate stakeholder alignment
/wicked-garden:product:align --stakeholders "eng,qe,ops"
```

## Elicitation Process

1. **Understand Context**: Read available materials
2. **Ask Questions**: Surface gaps and ambiguities
3. **Write Stories**: As a [persona], I want [capability], so that [benefit]
4. **Define Criteria**: Given/When/Then scenarios
5. **Validate**: Check completeness and testability

## Output Artifacts

Elicitation produces:
- **User Stories**: Persona + capability + benefit
- **Acceptance Criteria**: Testable scenarios
- **Open Questions**: Ambiguities to resolve
- **Kanban Updates**: Traceability

## Quality Checks

Good requirements are:
- **Clear**: No ambiguity
- **Testable**: Can verify completion
- **Valuable**: Clear benefit stated
- **Independent**: Standalone value
- **Small**: Completable in iteration

## Integration

Works with:
- **wicked-crew**: Auto-triggered during clarify phase
- **wicked-kanban**: Stores requirements and acceptance criteria
- **wicked-qe**: Acceptance criteria feed test scenarios
- **wicked-mem**: Cross-project requirements patterns

## Example Flow

```
User: "We need a login feature"

Product: Eliciting requirements...

US1: User Authentication
As a customer
I want to log in with email and password
So that I can access my account securely

Acceptance Criteria:
1. Given valid credentials, When I submit login, Then I access my dashboard
2. Given invalid password, When I submit login, Then I see error message
3. Given account locked, When I submit login, Then I see lockout message

Open Questions:
- Password reset flow?
- Social login support?
- Session timeout duration?
```

## External Integration Discovery

Product management can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **Analytics** | `posthog`, `mixpanel`, `amplitude` | User behavior data |
| **Project management** | `jira`, `linear`, `github` | Existing tickets/context |
| **Customer feedback** | `zendesk`, `intercom` | Support ticket insights |

Run `ListMcpResourcesTool` to discover available integrations. Use wicked-kanban when no project management MCP available.

## Progressive Disclosure

- **SKILL.md** (this file): Overview and quick start
- **refs/user-story-template.md**: Detailed story format
- **refs/acceptance-criteria-guide.md**: Writing testable criteria
