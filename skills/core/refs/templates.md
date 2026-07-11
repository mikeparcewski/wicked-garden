# Issue-body templates (report-issue action)

Loaded by `refs/report-issue.md` § 5 (Compose Issue). Pick the template that
matches the issue type parsed in § 1, fill the fields collected in § 2, then
append the research findings from § 3 and the SMART-validated acceptance
criteria from § 4. `{…}` are fill-ins; drop any **optional** line the user
left blank; drop any research section that found nothing.

Every issue body opens with the same reporter line and closes with the same
acceptance-criteria + desired-outcome block.

## Header (all types)

```markdown
> Reported via Claude Code (wicked-garden-core `report-issue`, manual report).
```

## Bug Report (label: `bug`)

```markdown
> Reported via Claude Code (wicked-garden-core `report-issue`, manual report).

## Steps to Reproduce
1. {step 1}
2. {step 2}
3. {…}

## Expected Behavior
{what should have happened}

## Actual Behavior
{what actually happened}

## Impact
{severity / who is affected — omit if not provided}
```

## UX Friction Report (label: `ux`)

```markdown
> Reported via Claude Code (wicked-garden-core `report-issue`, manual report).

## What You Tried
{the intent and actions taken}

## What Happened Instead
{the confusing or unexpected result}

## Suggested Improvement
{how it could be better — omit if not provided}
```

## Unmet Outcome Report (label: `gap`)

```markdown
> Reported via Claude Code (wicked-garden-core `report-issue`, manual report).

## Goal
{what the session was trying to achieve}

## What Happened
{the actual result — where it fell short}

## What Would Have Helped
{suggestions — omit if not provided}
```

## Research findings (append after the type-specific body)

Append only the sections that produced results in § 3. Use the exact section
markup already specified in `refs/report-issue.md` §§ 3a–3c:

- **Duplicate Check** — `## Duplicate Check` (always appended; states matches or
  "No open duplicates detected.")
- **Related Code** — `## Related Code` (only when relevant files were found)
- **Prior Context** — `## Prior Context` (only when relevant memories were found)

## Closing block (all types)

```markdown
## Acceptance Criteria
- [ ] {SMART-validated criterion 1}
- [ ] {SMART-validated criterion 2}
- [ ] {…}

## Desired Outcome
{one-sentence statement of the outcome that would close this issue}
```
