---
name: issue-reporting
description: |
  Automated GitHub issue detection and filing from Claude sessions. Tracks tool
  failures and task completion mismatches. Files issues automatically at session
  end or on demand via /wicked-garden:report-issue. Includes duplicate detection,
  codebase research, memory recall, SMART criteria validation, and advisory quality
  gate before filing.

  Use when: "file a bug", "report issue", "something went wrong", "not working as expected",
  "create issue", reporting UX friction, logging unmet outcomes, or investigating tool failures.
---

# Issue Reporting

Detects and reports bugs, UX friction, and unmet outcomes as structured GitHub issues. The manual filing command runs research, validates quality, and enriches the issue body before filing.

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

Manual filing runs a full research and quality pipeline before opening the issue:

1. **Collect fields** — interactive prompts by issue type
2. **Research** — duplicate detection, codebase search, memory recall
3. **SMART validation** — acceptance criteria checked for specificity and measurability
4. **Quality gate** — advisory checklist (title length, AC count, verb prefix, etc.)
5. **Confirm and file** — preview shown before any `gh` call

## Issue Types

| Type | Label | When To Use |
|------|-------|-------------|
| Bug Report | `bug` | Tool failures, crashes, incorrect behavior |
| UX Friction | `ux` | Confusing workflows, missing feedback, rough edges |
| Unmet Outcome | `gap` | Session goal not achieved, partial results |

Each issue type has a structured template requiring:
- Steps to reproduce or context
- Expected vs actual behavior
- Acceptance criteria for the fix (SMART-validated)
- Desired outcome

## Research Pipeline (Manual Filing Only)

Before composing the issue body, the command runs three research steps:

### Duplicate Detection

Searches open issues by title keywords:
```bash
gh issue list --repo {repo} --search "{keywords}" --state open --json number,title,state --limit 10
```
Results are appended as a **Duplicate Check** section. Requires `gh` CLI.

### Codebase Research

Greps the repository for files related to the issue keywords. Up to 5 relevant files are listed in a **Related Code** section.

### Memory Recall

Queries the wicked-garden memory store for prior context about the issue area:
```
Skill(skill="wicked-garden:mem:recall", args="{keywords}")
```
Relevant memories are appended as a **Prior Context** section.

All three steps are additive — they never block filing.

## SMART Criteria Validation

Every acceptance criterion is validated before the issue body is finalized:

| Criterion | Requirement | Bad Example | Good Example |
|-----------|-------------|-------------|--------------|
| **Specific** | References a concrete behavior, file, or artifact | "should work better" | "Bash hook returns `{\"ok\": true}`" |
| **Measurable** | Verifiable assertion that is clearly true or false | "no errors occur" | "passes `/wg-check`" |

ACs that fail are auto-improved in non-interactive mode, or surfaced with a suggested rewrite in interactive mode.

## Quality Gate

An advisory checklist runs before the issue preview is shown. All items are warnings only — they never block filing:

| Check | Criteria |
|-------|----------|
| Title length | Under 80 characters |
| Title descriptiveness | Not a single word or generic phrase |
| Steps to reproduce | For bugs: at least 2 numbered steps |
| Acceptance criteria count | At least 2 ACs |
| AC verb prefix | Each AC starts with an action verb |
| AC independence | Each AC is independently verifiable |
| Duplicate check | Duplicate search completed |

## Configuration

| Setting | Default | Override |
|---------|---------|---------|
| Failure threshold | 3 | `WICKED_ISSUE_THRESHOLD` env var |
| Max issues per session | 3 | Hardcoded in session_outcome_checker.py |
| Stale session cleanup | 48h | Hardcoded in auto_issue_reporter.py |

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth login`)
- Current directory is a GitHub repository

Without `gh`, the manual filing fallback uses a three-step sequence (see below).

## Fallback When `gh` Unavailable

When `gh` CLI is not installed or no repo is detected, manual filing follows this order:

1. **Print to screen**: Full issue displayed as formatted markdown (title, body, labels) — immediately visible for copy-paste
2. **Generate GitHub URL**: Pre-filled `issues/new` URL with `urllib.parse.quote()`-encoded title, body, and labels — open in browser to file directly
3. **Ask to save locally**: User chooses whether to cache the issue for later filing

```
https://github.com/{owner}/{repo}/issues/new?title={encoded}&body={encoded}&labels={encoded}
```

If user agrees to save: issue is queued in `{storage_root}/unfiled-issues/` for later filing via `--list-unfiled`.

Note: Hook auto-filing paths (PostToolUseFailure, Stop hook) bypass this flow and silently cache to the unfiled queue without prompting.

## References

- [Issue Templates](refs/templates.md) — Full body templates for all three issue types, including Research and Duplicate Check sections
