# Issue Templates Reference

Body templates used by both auto-reporting hooks and the manual `/wicked-garden:report-issue` command.

The manual command appends three optional research sections after the main body: **Duplicate Check**, **Related Code**, and **Prior Context**. These are omitted when the research step yields no findings.

---

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

- [ ] {ac_1 — SMART-validated: specific and measurable}
- [ ] {ac_2 — SMART-validated: specific and measurable}
- [ ] No regression in related functionality confirmed by /wg-check

## Desired Outcome

{desired_outcome}

---

## Duplicate Check

<!-- Searched: "{title keywords}" -->
- {No open duplicates detected. | Potential duplicates: #{n} "{title}", ...}

## Related Code

Files likely relevant to this issue:
- `{path/to/file.py}`

## Prior Context

From memory store:
- {memory summary}
```

### Auto-Reporter Variant

When filed automatically by the Stop hook, the template is simplified:

- **Description**: "Tool `{tool}` failed {count} times during this session."
- **Steps to Reproduce**: Inferred from tool name and error pattern
- **Error Details**: Last error message (truncated to 500 chars)
- **Environment**: Auto-populated from session context
- Research sections (Duplicate Check, Related Code, Prior Context) are **omitted** — auto-reporter does not run the research pipeline

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

- [ ] {ac_1 — SMART-validated: specific and measurable}
- [ ] {ac_2 — SMART-validated: specific and measurable}
- [ ] No new friction introduced (verified by manual walkthrough of the affected flow)

## Desired Outcome

{desired_outcome}

---

## Duplicate Check

<!-- Searched: "{title keywords}" -->
- {No open duplicates detected. | Potential duplicates: #{n} "{title}", ...}

## Related Code

Files likely relevant to this issue:
- `{path/to/file.md}`

## Prior Context

From memory store:
- {memory summary}
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

- [ ] {ac_1 — SMART-validated: specific and measurable}
- [ ] {ac_2 — SMART-validated: specific and measurable}
- [ ] Gap addressed or documented in refs/ with concrete guidance

## Desired Outcome

{desired_outcome}

---

## Duplicate Check

<!-- Searched: "{title keywords}" -->
- {No open duplicates detected. | Potential duplicates: #{n} "{title}", ...}

## Related Code

Files likely relevant to this issue:
- `{path/to/file.py}`

## Prior Context

From memory store:
- {memory summary}
```

### Auto-Reporter Variant

When filed automatically, the unmet outcome template uses:

- **Session Goal**: Not available (auto-reporter does not access session goals)
- **What Actually Happened**: Task "{subject}" was marked completed with mismatch signal
- **Signal Detected**: Populated from mismatch record (e.g., "blocked", "error")
- Research sections (Duplicate Check, Related Code, Prior Context) are **omitted** — auto-reporter does not run the research pipeline

---

## Research Sections Reference

These sections are appended after the main body during manual filing. Each is omitted when the corresponding research step yields no findings.

### Duplicate Check

```markdown
## Duplicate Check

<!-- Searched: "{title keywords}" -->
- No open duplicates detected.
```

```markdown
## Duplicate Check

<!-- Searched: "{title keywords}" -->
- Potential duplicates: #123 "Similar bug with Bash hook", #456 "Hook returns wrong exit code"
```

### Related Code

```markdown
## Related Code

Files likely relevant to this issue:
- `hooks/scripts/bootstrap.py`
- `scripts/crew/phase_manager.py`
- `commands/report-issue.md`
```

### Prior Context

```markdown
## Prior Context

From memory store:
- Decision (2026-01-15): Hook scripts must be stdlib-only — no external deps allowed
- Pattern (2026-02-03): Bash hook failures often caused by unquoted shell variables
```

---

## SMART Acceptance Criteria Examples

The manual filing command validates every AC for **Specific** and **Measurable** before composing the final issue.

| Criterion | Bad (Fails SMART) | Good (Passes SMART) |
|-----------|-------------------|---------------------|
| Specific | "Should work better" | "Bash hook exits 0 when stdin is valid JSON" |
| Specific | "Improves performance" | "Context assembly completes in under 100ms (FAST path)" |
| Measurable | "No errors occur" | "passes `/wg-check` with exit code 0" |
| Measurable | "Feels right" | "No grep results for hardcoded `~/.something-wicked/` paths in hook scripts" |

When an AC fails, the auto-improved version is logged:
```
[SMART] Improved AC: "Root cause identified" → "Root cause documented in a code comment at the fix site"
```

---

## Field Collection Guide

When using the manual command, collect these fields interactively:

### Bug Report Fields
1. **Title**: Short summary (will become issue title, max 80 chars)
2. **Steps to Reproduce**: Numbered list of actions (at least 2)
3. **Expected Behavior**: What should have happened
4. **Actual Behavior**: What actually happened
5. **Impact**: How this affects the user (optional)

### UX Friction Fields
1. **Title**: Short summary (max 80 chars)
2. **What You Tried**: The user's intent and actions
3. **What Happened**: The unexpected or confusing result
4. **Suggested Improvement**: How it could be better (optional)

### Unmet Outcome Fields
1. **Title**: Short summary (max 80 chars)
2. **Goal**: What the session was trying to achieve
3. **What Happened**: The actual result
4. **What Would Have Helped**: Suggestions for improvement (optional)
