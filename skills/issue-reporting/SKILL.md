---
name: issue-reporting
description: |
  Automated GitHub issue detection and filing from Claude sessions. Tracks tool
  failures and task completion mismatches. Files issues automatically at session
  end or on demand via /wicked-garden:report-issue.
  Use when filing a bug, reporting UX friction, or logging unmet outcomes.
triggers:
  - "file github issue"
  - "report bug"
  - "create issue"
  - "something went wrong"
  - "log this as a bug"
  - "tool kept failing"
  - "report issue"
  - "ux friction"
  - "not working as expected"
---

# Issue Reporting

Detects and reports bugs, UX friction, and unmet outcomes as structured GitHub issues.

## How It Works

### Automatic Detection (Hooks)

Three hooks monitor your session:

| Hook | Watches For | Action |
|------|------------|--------|
| PostToolUseFailure | Same tool failing 3+ times | Queues issue for session end |
| PostToolUse(TaskUpdate) | Task completed with mismatch signals | Logs mismatch for review |
| Stop (async) | Session end | Files queued issues via `gh` |

Auto-filed issues include acceptance criteria, failure details, and session context.

### Manual Filing

```bash
/wicked-garden:report-issue bug          # File a bug report
/wicked-garden:report-issue ux-friction  # Report UX friction
/wicked-garden:report-issue unmet-outcome # Log an unmet outcome
/wicked-garden:report-issue --list-unfiled # View/file unfiled issues
```

## Issue Types

| Type | Label | When To Use |
|------|-------|-------------|
| Bug Report | `bug` | Tool failures, crashes, incorrect behavior |
| UX Friction | `ux` | Confusing workflows, missing feedback, rough edges |
| Unmet Outcome | `gap` | Session goal not achieved, partial results |

Each issue type has a structured template requiring:
- Steps to reproduce or context
- Expected vs actual behavior
- Acceptance criteria for the fix
- Desired outcome

## Configuration

| Setting | Default | Override |
|---------|---------|---------|
| Failure threshold | 3 | `WICKED_ISSUE_THRESHOLD` env var |
| Max issues per session | 3 | Hardcoded in session_outcome_checker.py |
| Stale session cleanup | 48h | Hardcoded in auto_issue_reporter.py |

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth login`)
- Current directory is a GitHub repository

Without `gh`, issues are saved to `~/.something-wicked/wicked-garden/unfiled-issues/` for later filing.

## Unfiled Issues

When `gh` is unavailable, issues are queued locally:

```bash
# View unfiled issues
ls ~/.something-wicked/wicked-garden/unfiled-issues/

# File them later
/wicked-garden:report-issue --list-unfiled
```

## References

- [Issue Templates](refs/templates.md) — Full body templates for all three issue types
