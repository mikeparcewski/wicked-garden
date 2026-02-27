---
description: Elicit and document requirements through structured discovery
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
- **--output**: Where to save results (default: console + kanban)

## Process

1. **Read Context**: Parse target documents or accept interactive mode
2. **Dispatch to Requirements Analyst**: Elicit requirements, identify gaps, generate user stories
3. **Present Results**: Format user stories with acceptance criteria and open questions
4. **Update Kanban**: Store requirements for traceability

## Instructions

### 1. Read Context

Read target document(s) or accept interactive mode parameters:
- `--personas`: Comma-separated list of user personas
- `--scope`: Focus area
- `--interactive`: Interactive clarification mode

### 2. Dispatch to Requirements Analyst

```
Task(
  subagent_type="wicked-garden:product/requirements-analyst",
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
4. **Define Acceptance Criteria**: Given/When/Then format for each story
5. **Provide Recommendations**: Next steps for requirements refinement

## Return Format

Provide:
- User Stories count
- Acceptance Criteria count
- Open Questions count
- Individual user stories with AC
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
- **wicked-kanban**: Stores requirements as comments
- **wicked-mem**: Learns requirements patterns
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

Stored in kanban: task-001
Event emitted: [product:requirements:elicited:success]
```
