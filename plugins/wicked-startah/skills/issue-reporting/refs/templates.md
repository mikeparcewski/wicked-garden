# Issue Templates Reference

Body templates used by both auto-reporting hooks and the manual `/wicked-startah:report-issue` command.

## Bug Report Template

**Label**: `bug`

```markdown
**Reported by**: Claude Code {reporter_type}
**Session**: {session_id}
**Date**: {date}
**Repo**: {repo}

## Description

{description}

## Steps to Reproduce

1. {step_1}
2. {step_2}
3. {step_3}

## Expected Behavior

{expected_behavior}

## Actual Behavior

{actual_behavior}

## Error Details

```
{error_output}
```

## Environment

- Claude Code session: {session_id}
- Working directory: {cwd}
- Tool: {tool_name}

## Acceptance Criteria

- [ ] Root cause identified
- [ ] Fix verified with test
- [ ] No regression in related functionality

## Desired Outcome

{desired_outcome}
```

### Auto-Reporter Variant

When filed automatically by the Stop hook, the template is simplified:

- **Description**: "Tool `{tool}` failed {count} times during this session."
- **Steps to Reproduce**: Inferred from tool name and error pattern
- **Error Details**: Last error message (truncated to 500 chars)
- **Environment**: Auto-populated from session context

---

## UX Friction Template

**Label**: `ux`

```markdown
**Reported by**: Claude Code {reporter_type}
**Session**: {session_id}
**Date**: {date}
**Repo**: {repo}

## What You Tried

{what_you_tried}

## What Happened Instead

{what_happened}

## Friction Point

{friction_description}

## Suggested Improvement

{suggested_improvement}

## Impact

{impact_description}

## Acceptance Criteria

- [ ] Friction point addressed
- [ ] User flow verified as smooth
- [ ] No new friction introduced

## Desired Outcome

{desired_outcome}
```

---

## Unmet Outcome Template

**Label**: `gap`

```markdown
**Reported by**: Claude Code {reporter_type}
**Session**: {session_id}
**Date**: {date}
**Repo**: {repo}

## Session Goal

{session_goal}

## What Actually Happened

{what_happened}

## Gap Description

{gap_description}

## Signal Detected

{signal}: {detail}

## Acceptance Criteria

- [ ] Outcome verified against original intent
- [ ] Gap addressed or documented
- [ ] Related workflows checked

## Desired Outcome

{desired_outcome}
```

### Auto-Reporter Variant

When filed automatically, the unmet outcome template uses:

- **Session Goal**: Not available (auto-reporter does not access session goals)
- **What Actually Happened**: Task "{subject}" was marked completed with mismatch signal
- **Signal Detected**: Populated from mismatch record (e.g., "blocked", "error")

---

## Field Collection Guide

When using the manual command, collect these fields interactively:

### Bug Report Fields
1. **Title**: Short summary (will become issue title)
2. **Steps to Reproduce**: Numbered list of actions
3. **Expected Behavior**: What should have happened
4. **Actual Behavior**: What actually happened
5. **Impact**: How this affects the user (optional)

### UX Friction Fields
1. **Title**: Short summary
2. **What You Tried**: The user's intent and actions
3. **What Happened**: The unexpected or confusing result
4. **Suggested Improvement**: How it could be better (optional)

### Unmet Outcome Fields
1. **Title**: Short summary
2. **Goal**: What the session was trying to achieve
3. **What Happened**: The actual result
4. **What Would Have Helped**: Suggestions for improvement (optional)
