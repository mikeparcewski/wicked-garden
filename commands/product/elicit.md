---
description: |
  Use when turning a vague idea or stakeholder ask into structured user stories with acceptance criteria.
  NOT for requirements traceability graphs (use the requirements-graph skill) or UX flows (use product:ux).
---

# /wicked-garden:product:elicit

Elicit requirements and write user stories with acceptance criteria.

## Usage

```bash
# Elicit from outcome document
/wicked-garden:product:elicit outcome.md

# Elicit from project brief
/wicked-garden:product:elicit phases/clarify/brief.md

# Elicit from directory of documents
/wicked-garden:product:elicit docs/requirements/

# Interactive elicitation
/wicked-garden:product:elicit --interactive
```

## Parameters

- **target** (required): Path to document(s) or "--interactive"
- **--personas**: Comma-separated list of user personas
- **--scope**: Focus area (e.g., "authentication", "data-management")
- **--output**: Where to save results (default: console + native task)

## Process

1. **Read Context**: Parse target documents or accept interactive mode
2. **Dispatch to Requirements Analyst**: Elicit requirements, identify gaps, generate user stories
3. **Present Results**: Format user stories with acceptance criteria and open questions
4. **Update Task**: Store requirements via TaskUpdate on the active clarify task for traceability

## Instructions

### 1. Read Context

Read target document(s) or accept interactive mode parameters:
- `--personas`: Comma-separated list of user personas
- `--scope`: Focus area
- `--interactive`: Interactive clarification mode

### 2. Dispatch to Requirements Analyst

```
Task(
  subagent_type="wicked-garden:product:requirements-analyst",
  prompt="""Elicit requirements from the following context.

## Context
{target document content OR interactive parameters}

## Parameters
- Personas: {specified personas or infer from context}
- Scope: {focus area if specified}
- Mode: {interactive or document-based}

## Task

1. **Identify Gaps**: What information is missing or unclear?
2. **Ask Questions**: Surface questions requiring stakeholder input
3. **Write User Stories**: Follow the format:
   - As a {persona}
   - I want {capability}
   - So that {benefit}
4. **Assign Priority**: P0 (must-have/launch blocker), P1 (important/near-term), P2 (nice-to-have/deferrable) for each story
5. **Assign Complexity**: S (hours), M (1-2 days), L (3-5 days), XL (week+) for each story
6. **Define Dependencies**: List formal story-to-story or system dependencies for each story (use story IDs or component names)
7. **Define Acceptance Criteria**: Given/When/Then format for each story
8. **Provide Recommendations**: Next steps for requirements refinement

## Return Format

Provide:
- User Stories count
- Acceptance Criteria count
- Open Questions count
- Individual user stories with priority, complexity, dependencies, and AC
- Open questions list
- Recommendations
"""
)
```

### 3. Present Results

Format the agent's output into the standard elicitation report structure.

## Output

```markdown
## Requirements Elicitation Results

### User Stories Defined: {count}
### Acceptance Criteria: {count}
### Open Questions: {count}

---

### US1: {Story Title}
**As a** {persona}
**I want** {capability}
**So that** {benefit}

**Priority**: P0 | P1 | P2
**Complexity**: S | M | L | XL
**Dependencies**: {story IDs or system components this story depends on, or "None"}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}

---

### Open Questions
1. {Question requiring stakeholder input}

### Recommendations
- {Next step}
```

## Integration

Automatically updates:
- **Native tasks**: Stores requirements via TaskUpdate description appends on the active clarify task
- **wicked-garden:mem**: Learns requirements patterns
- **Event**: Emits `[product:requirements:elicited:success]`

## Example

```bash
$ /wicked-garden:product:elicit outcome.md

Reading outcome.md...
[Dispatches to requirements-analyst agent]
[Agent analyzes requirements and generates user stories]

User Stories Defined: 5
Open Questions: 2

US1: User Login
As a customer
I want to log in with email/password
So that I can access my account

AC1: Given valid credentials, When I submit, Then I access dashboard
AC2: Given invalid password, When I submit, Then I see error

Open Questions:
1. Password complexity requirements?
2. Social login support (Google, GitHub)?

Stored on active task: task-001
Event emitted: [product:requirements:elicited:success]
```
