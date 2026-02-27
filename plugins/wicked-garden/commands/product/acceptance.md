---
description: Define acceptance criteria from requirements and design
argument-hint: "<requirements/design path> [--story US-ID] [--feature name] [--format gherkin|table|markdown] [--scenarios]"
---

# /wicked-garden:product-acceptance

Generate testable acceptance criteria from requirements and design documents.

## Usage

```bash
# From design documents
/wicked-garden:product-acceptance phases/design/

# From specific user story
/wicked-garden:product-acceptance --story US-123

# From requirements doc
/wicked-garden:product-acceptance requirements.md

# For specific feature
/wicked-garden:product-acceptance --feature "authentication"
```

## Parameters

- **target** (optional): Path to requirements/design docs
- **--story**: Specific user story ID
- **--feature**: Feature name to focus on
- **--format**: Output format (gherkin, table, markdown)
- **--scenarios**: Generate wicked-scenarios format scenario stubs
- **--output**: Where to save (default: console + kanban)

## Process

1. **Read Input**: Requirements, design documents, or user story references
2. **Dispatch to Requirements Analyst**: Generate acceptance criteria with scenarios
3. **Present Results**: Format AC with priority, test data, and QE handoff notes
4. **Update Kanban**: Store for QE handoff

## Instructions

### 1. Read Input

Read requirements, design documents, or user story references. Parse parameters:
- `--story`: Specific user story ID
- `--feature`: Feature name to focus on
- `--format`: Output format (gherkin, table, markdown)

### 2. Dispatch to Requirements Analyst

```
Task(
  subagent_type="wicked-garden:product/requirements-analyst",
  prompt="""Generate testable acceptance criteria from the following input.

## Input
{requirements, design docs, or user story content}

## Parameters
- Story ID: {if specified}
- Feature: {if specified}
- Format: {gherkin, table, or markdown}

## Task

1. **Identify Scenarios**: Happy path, error conditions, edge cases, non-functional requirements
2. **Write Criteria**: Given/When/Then format
3. **Prioritize**: Mark P0 (must-have) vs P1 (nice-to-have)
4. **Validate**: Ensure testability and completeness
5. **Specify Test Data**: What data is needed for testing
6. **QE Handoff Notes**: Special considerations for test implementation

## Return Format

Provide:
- User Story title
- Acceptance Criteria count
- Happy Path (P0) criteria
- Error Conditions (P0) criteria
- Edge Cases (P1) criteria
- Non-Functional (P1) criteria
- Test Data Required
- QE Handoff Notes
"""
)
```

### 3. Present Results

Format the agent's output into the standard acceptance criteria structure.

## Output

```markdown
## Acceptance Criteria

### US1: {Story Title}

**Happy Path (P0)**:
- AC1: Given {context}, When {action}, Then {outcome}

**Error Conditions (P0)**:
- AC2: Given {error}, When {action}, Then {handling}

**Edge Cases (P1)**:
- AC3: Given {edge}, When {action}, Then {behavior}

**Non-Functional (P1)**:
- AC4: Given {load}, When {action}, Then {performance}

**Test Data Required**:
- {Data needed for testing}

**QE Handoff Notes**:
- {Special considerations}
```

## Integration

Automatically:
- **wicked-kanban**: Stores AC with traceability
- **wicked-qe**: AC available for test scenario generation
- **Event**: Emits `[product:acceptance:defined:success]`

## Example

```bash
$ /wicked-garden:product-acceptance phases/design/architecture.md

Analyzing design documents...
[Dispatches to requirements-analyst agent]
[Agent generates acceptance criteria]

User Story: US1 - User Authentication
Acceptance Criteria Defined: 8

Happy Path (P0):
AC1: Given valid email/password, When submit, Then redirect to dashboard
AC2: Given successful login, When check session, Then session valid 30 min

Error Handling (P0):
AC3: Given invalid password, When submit, Then show "Invalid credentials"
AC4: Given locked account, When submit, Then show "Account locked"

Edge Cases (P1):
AC5: Given empty email, When submit, Then show "Email required"
AC6: Given malformed email, When submit, Then show "Invalid format"

Non-Functional (P1):
AC7: Given 1000 concurrent logins, When load, Then response < 2 sec
AC8: Given login attempt, When check, Then password encrypted

Stored in kanban: US-001
Ready for QE test scenario generation
Event emitted: [product:acceptance:defined:success]
```

### 4. Optional: Generate Wicked-Scenarios Format

When `--scenarios` flag is passed, convert the acceptance criteria into wicked-scenarios format scenario stubs.

For each user story's acceptance criteria, produce a wicked-scenarios markdown block:

**Priority → difficulty mapping:**
- P0 (must-have) → `basic` or `intermediate`
- P1 (nice-to-have) → `intermediate` or `advanced`

**AC type → wicked-scenarios category mapping:**

| AC Type | wicked-scenarios category | Tools |
|---------|--------------------------|-------|
| Happy Path | api | curl, hurl |
| Error Conditions | api | curl |
| Edge Cases | api | curl, hurl |
| Non-Functional (perf) | perf | k6, hey |
| Non-Functional (a11y) | a11y | pa11y |
| Non-Functional (browser/UX) | browser | playwright, agent-browser |

**Output format:**

````markdown
---
name: {story-kebab}-acceptance
description: "Acceptance scenarios for {story title}"
category: {mapped category}
tools:
  required: [{primary tool}]
  optional: [{secondary tools}]
difficulty: {mapped difficulty}
timeout: 60
---

## Steps

### Step 1: {AC1 - Given/When/Then summary} ({tool})

```bash
{executable CLI command derived from acceptance criterion}
```

**Expect**: {Then condition as exit code expectation}
````

**Conversion rules:**
- **Given** → Setup section or prerequisite state
- **When** → curl/hurl request or browser action
- **Then** → Expected response code, body content, or behavior
- Test data from AC → environment variables or Setup commands
- Non-functional criteria map to their canonical categories: performance→perf (k6/hey), accessibility→a11y (pa11y), browser/UX→browser (playwright)
- If an AC can't be converted to CLI (e.g., manual judgment call), note it as a comment

## QE Handoff

Acceptance criteria feed into:
```bash
/wicked-garden:qe-analyze --gate strategy
```

QE uses AC to:
- Generate test scenarios (or use `--scenarios` to generate wicked-scenarios format directly)
- Create test cases
- Validate coverage
