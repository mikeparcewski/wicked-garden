---
description: Review requested changes against codebase and recommend detailed implementation steps
argument-hint: "<change request or issue description>"
---

# /wicked-garden:engineering:plan

Analyze a change request against the current codebase and produce a detailed implementation plan with specific file changes, risk assessment, and test recommendations.

## Instructions

### 1. Understand the Request

Parse the user's change request to identify:
- **Goal**: What outcome is desired
- **Scope**: What areas of the codebase are affected
- **Constraints**: Any limitations or requirements mentioned

If the request is vague, ask clarifying questions before proceeding.

### 2. Explore Affected Code

Use exploration to understand the current state:

```
Explore the codebase to understand:
1. Files that implement the functionality being changed
2. Dependencies and callers of those files
3. Existing patterns and conventions used
4. Test coverage for affected areas
```

Focus on:
- Entry points for the feature
- Data flow through the system
- Related tests and their patterns

### 3. Dispatch Parallel Analysis

Spawn both senior engineer and risk assessor in parallel:

```python
# Dispatch both agents simultaneously
Task(
    subagent_type="wicked-garden:engineering:senior-engineer",
    prompt="""Analyze this change request and recommend implementation approach.

## Change Request
{user's request}

## Codebase Context
- Files: {list key files discovered}
- Patterns: {note existing patterns}
- Tests: {note test patterns}

## Deliverables
1. Recommended approach with rationale
2. Alternative approaches considered
3. Potential risks or gotchas

## Return Format
Structure as: Approach, Alternatives, Risks
"""
)

Task(
    subagent_type="wicked-garden:qe:risk-assessor",
    prompt="""Assess risks for this proposed change.

## Change Summary
{summary of change}

## Affected Files
{list}

## Risk Areas
1. Breaking change risks
2. Performance implications
3. Security considerations
4. Testing gaps

## Return Format
Risk matrix with likelihood, impact, and mitigations.
"""
)
```

### 5. Generate Implementation Plan

Synthesize findings into a structured plan:

```markdown
## Implementation Plan: {title}

### Summary
{1-2 sentence overview}

### Changes Required

#### 1. {filename}
**Purpose**: {why this file needs changes}
**Changes**:
- Line X-Y: {specific change description}
- Add: {new code/function needed}
- Remove: {code to delete if any}

#### 2. {filename}
...

### Risk Mitigation
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| {risk} | Low/Med/High | Low/Med/High | {action} |

### Test Plan
- [ ] Unit tests for {component}
- [ ] Integration test for {flow}
- [ ] Manual verification of {scenario}

### Rollout Considerations
{Any deployment, feature flag, or migration notes}
```

### 6. Present for Approval

After presenting the plan, ask:

> Ready to proceed with implementation, or would you like to adjust the approach?

If approved, the plan can be executed using `/wicked-garden:crew:execute` or manual implementation.

## Example

```
User: /wicked-garden:engineering:plan Add rate limiting to the API endpoints

Claude: I'll analyze the codebase and create an implementation plan for rate limiting.

[Explores API structure, middleware patterns, existing auth flow]
[Spawns senior-engineer for approach recommendation]
[Spawns risk-assessor for risk evaluation]

## Implementation Plan: API Rate Limiting

### Summary
Add configurable rate limiting middleware to protect API endpoints from abuse.

### Changes Required

#### 1. src/middleware/rateLimit.ts (NEW)
**Purpose**: Rate limiting middleware using sliding window algorithm
**Changes**:
- Create RateLimiter class with Redis backend
- Export middleware factory with configurable limits
- Add bypass for internal service calls

#### 2. src/api/index.ts
**Purpose**: Apply rate limiting to routes
**Changes**:
- Line 12: Import rate limiter middleware
- Line 25-30: Apply to public routes with 100 req/min
- Line 45-50: Apply to auth routes with 10 req/min

...
```
