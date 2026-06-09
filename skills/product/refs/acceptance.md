# Acceptance Criteria Rubric (Given/When/Then)

Apply this inline. Generate testable acceptance criteria from requirements/design.
`product:acceptance` **defines criteria** (what done looks like); to **run** tests
against them, use `/wicked-testing:execution`. (For full requirements-graph AC nodes,
see the `acceptance-criteria` skill.)

## Process

1. **Identify scenarios** — happy path, error conditions, edge cases, non-functional.
2. **Write criteria** — Given {context}, When {action}, Then {outcome}.
3. **Prioritize** — P0 (must-have) vs P1 (nice-to-have).
4. **Validate** — testability + completeness (each AC is unambiguous and verifiable).
5. **Specify test data** — what data is needed to exercise each AC.
6. **QE handoff notes** — special considerations for test implementation.

Apply parameters: `--story US-ID`, `--feature name`, `--format gherkin|table|markdown`.

## Output

```markdown
## Acceptance Criteria
### US1: {Story Title}
**Happy Path (P0)**: AC1: Given {context}, When {action}, Then {outcome}
**Error Conditions (P0)**: AC2: Given {error}, When {action}, Then {handling}
**Edge Cases (P1)**: AC3: Given {edge}, When {action}, Then {behavior}
**Non-Functional (P1)**: AC4: Given {load}, When {action}, Then {performance}
**Test Data Required**: {data}
**QE Handoff Notes**: {special considerations}
```

## Optional: `--scenarios` (wicked-testing tie-in)

When `--scenarios` is passed, convert each story's AC into wicked-scenarios stubs.

**Priority -> difficulty**: P0 -> basic/intermediate; P1 -> intermediate/advanced.

**AC type -> category / tools**:
| AC Type | Category | Tools |
|---------|----------|-------|
| Happy Path | api | curl, hurl |
| Error Conditions | api | curl |
| Edge Cases | api | curl, hurl |
| Non-Functional (perf) | perf | k6, hey |
| Non-Functional (a11y) | a11y | pa11y |
| Non-Functional (browser/UX) | browser | playwright, agent-browser |

**Conversion rules**: Given -> Setup / prerequisite state; When -> request or browser
action; Then -> expected response code / body / behavior. Test data -> env vars or
Setup commands. If an AC can't be made CLI-executable (manual judgment), note it as
a comment.

**Stub format**:
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
### Step 1: {AC1 Given/When/Then summary} ({tool})
```bash
{executable CLI command derived from the AC}
```
**Expect**: {Then condition as exit-code / output expectation}
````

## Handoff

AC feed into `/wicked-testing:plan` (generate scenarios, create cases, validate
coverage). Persist via `TaskCreate`/`TaskUpdate` with `metadata={event_type:"task",
chain_id:"{project}.clarify", source_agent:"requirements-analyst", phase:"clarify"}`
for traceability.
