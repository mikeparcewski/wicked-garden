# Requirements Elicitation Rubric (user stories + AC)

Apply this inline. Turn a vague idea / stakeholder ask into structured user stories
with acceptance criteria. For a full requirements **graph** (complexity >=3 or
compliance), use the `requirements-analysis` / `requirements-graph` skills instead.

## Process

1. **Understand context** — read outcome doc / brief / existing requirements / related issues.
2. **Identify gaps** — who are the users/personas? what are they achieving? why does it
   matter? what constraints? what could go wrong?
3. **Ask questions** — surface anything needing stakeholder input.
4. **Write user stories** — `As a {persona}, I want {capability}, so that {benefit}`.
5. **Assign priority** — P0 (must-have / launch blocker), P1 (important / near-term),
   P2 (nice-to-have / deferrable).
6. **Assign complexity** — S (hours), M (1-2 days), L (3-5 days), XL (week+).
7. **Define dependencies** — story-to-story or system (use story IDs / component names).
8. **Define acceptance criteria** — Given / When / Then per story.
9. **Recommend** next steps for refinement.

## Story quality (INVEST)

- **Independent** — standalone value
- **Negotiable** — not an over-specified contract
- **Valuable** — benefit stated
- **Estimable** — enough clarity to size
- **Small** — completable in an iteration
- **Testable** — completion is verifiable

## Completeness check

Happy-path scenarios · error conditions · edge cases · non-functional requirements
· dependencies · assumptions. Flag every ambiguity.

## Traceability

Assign each requirement a unique ID `REQ-{domain}-{number}` (e.g. `REQ-AUTH-001`).
Note Upstream (business goal / user need this traces to) and Downstream (design
decisions, AC, tests that should verify it).

## Output

```markdown
## Requirements Elicitation Results

### User Stories Defined: {count}   Acceptance Criteria: {count}   Open Questions: {count}

---
### US1: {Story Title}
**As a** {persona} **I want** {capability} **So that** {benefit}
**Priority**: P0|P1|P2   **Complexity**: S|M|L|XL   **Dependencies**: {IDs or None}
**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}

---
### Open Questions
1. {question requiring stakeholder input}

### Recommendations
- {next step}
```

## Persistence (optional)

When a clarify task is active, append the elicited stories to the task via
`TaskUpdate` (`metadata.event_type="task"`) for traceability; store recurring
requirement patterns via `wicked-brain:memory`.
