# plan — implementation planning rubric

Checklist and output format for generating detailed implementation plans with file changes,
risk assessment, and test recommendations before writing code.

## Pre-plan exploration checklist

Before drafting a plan, explore the codebase to understand:

- [ ] Files that implement the functionality being changed
- [ ] Direct callers and consumers of those files (blast radius)
- [ ] Existing patterns and conventions (naming, error handling, module structure)
- [ ] Test patterns and coverage for affected areas
- [ ] Any feature flags or config that gates the change

Use `wicked-garden:search:blast-radius {symbol}` to find all call sites. Fall back to
`wicked-brain:search` or Grep when the index is unavailable.

## Risk assessment checklist

For each change, evaluate:

| Risk Category | Questions to ask |
|---------------|-----------------|
| Breaking changes | Does this change any public interface, event schema, or API contract? |
| Performance | Does this add I/O, a loop, or a DB query to a hot path? |
| Security | Does this touch auth, session, credentials, or user-supplied input? |
| Data integrity | Does this touch a migration, schema, or data transform? |
| Test gaps | Are there untested edge cases that the change could break? |
| Deployment | Does this require a coordinated deploy (e.g. schema before code)? |

## Implementation plan output format

```markdown
## Implementation Plan: {title}

### Summary
{1-2 sentence overview of what changes and why}

### Scope
- **In scope**: {what will change}
- **Out of scope**: {explicitly NOT changing}

### Changes Required

#### 1. {path/to/file.ext}
**Purpose**: {why this file changes}
**Changes**:
- {Specific change — e.g., "Add null check before accessing `.id`"}
- {Add / Modify / Remove — be concrete}

#### 2. {path/to/another-file.ext}
**Purpose**: {why}
**Changes**:
- {change}

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| {risk} | Low/Med/High | Low/Med/High | {action} |

### Test Plan

- [ ] Unit: {what unit behavior to cover}
- [ ] Integration: {what flow to exercise end-to-end}
- [ ] Manual verification: {scenario to check in the running app}
- [ ] Regression: {existing tests to re-run}

### Rollout Considerations

{Any deployment notes: feature flags, migration order, canary, backward compatibility window}

### Open Questions

- {Question that needs resolution before implementation starts}
```

## Planning heuristics

**Start with the test** — if you can't describe what test would fail without this change,
the requirement isn't specific enough yet.

**One file at a time** — each file in "Changes Required" should have its own purpose;
if two files have the same purpose, merge them in the plan.

**Flag unauthorized scope** — if exploration reveals the change will require touching
files well outside the stated scope, surface this before proceeding.

**Security checklist for any change touching auth, input, or data**:
- [ ] No credentials logged
- [ ] Input validated before use
- [ ] Authorization checked (not just authentication)
- [ ] SQL/injection-safe if DB queries change
- [ ] No plaintext secrets in new config

**Performance checklist for any change on a hot path**:
- [ ] No new synchronous I/O added to request path
- [ ] No N+1 query pattern introduced
- [ ] Timeout specified on any new external call
- [ ] No unbounded collection loaded into memory

## After presenting the plan

Ask:
> Ready to proceed with implementation, or would you like to adjust the approach?

If approved, execute using `engineering:apply` or the build archetype
(`/wicked-garden-archetype build`).
