---
description: File a GitHub issue for a bug, UX friction point, or unmet outcome
argument-hint: "[bug | ux-friction | unmet-outcome | --list-unfiled]"
allowed_tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /wicked-garden:report-issue

File a structured GitHub issue with acceptance criteria, steps to reproduce, and desired outcome.

## Instructions

### 1. Parse Arguments

Determine issue type from arguments:
- `bug` → Bug Report (label: `bug`)
- `ux-friction` → UX Friction Report (label: `ux`)
- `unmet-outcome` → Unmet Outcome Report (label: `gap`)
- `--list-unfiled` → List and optionally file unfiled issues from fallback queue
- No argument → Ask user to select type

If `--list-unfiled` was provided, skip to Section 5.

### 2. Collect Fields

Gather information interactively based on issue type.

**Bug Report**:
- Title: Short summary of the bug
- Steps to Reproduce: What actions led to the bug
- Expected Behavior: What should have happened
- Actual Behavior: What actually happened
- Impact: How severe is this (optional)

**UX Friction**:
- Title: Short summary of the friction
- What You Tried: The intent and actions taken
- What Happened Instead: The confusing or unexpected result
- Suggested Improvement: How it could be better (optional)

**Unmet Outcome**:
- Title: Short summary of the gap
- Goal: What the session was trying to achieve
- What Happened: The actual result
- What Would Have Helped: Suggestions (optional)

### 3. Compose Issue

Build the issue body using the template from the skill's `refs/templates.md`. Include:
- Reporter info (Claude Code manual report)
- All collected fields
- Acceptance criteria checklist
- Desired outcome statement

Auto-detect the repo:
```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

### 4. Confirm and File

Show the composed issue to the user:

```markdown
## Issue Preview

**Title**: {title}
**Label**: {label}
**Repo**: {repo}

{body}

---
File this issue? (Approve to submit via gh, or cancel)
```

On confirmation:
- If `gh` is available and repo detected:
  - Write body to a temp file
  - Run: `gh issue create --repo {repo} --title "{title}" --body-file {tmpfile} --label "{label}"`
  - Report the issue URL to the user
  - Clean up temp file
- If `gh` unavailable or no repo:
  - Display the formatted issue as markdown for manual copy
  - Save to `~/.something-wicked/wicked-garden/unfiled-issues/{timestamp}.json`
  - Tell user: "Issue saved to unfiled queue. Install and authenticate `gh` CLI, then run `/wicked-garden:report-issue --list-unfiled` to file."

### 5. List Unfiled Issues (--list-unfiled)

If `--list-unfiled` was provided:

1. Read all JSON files from `~/.something-wicked/wicked-garden/unfiled-issues/`
2. If empty: report "No unfiled issues found."
3. If found: display a summary table:

```markdown
| # | Title | Type | Date |
|---|-------|------|------|
| 1 | Tool failure: Bash (3x) | bug | 2026-02-17 |
| 2 | Navigation is confusing | ux | 2026-02-16 |
```

4. Ask user which to file (all, specific numbers, or cancel)
5. For each selected: run `gh issue create` with the stored title, body, and label
6. On success: delete the unfiled JSON file
7. Report results
