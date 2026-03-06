---
description: Review GitHub issues and resolve them via crew workflow with commit + PR
argument-hint: [--list] [--label <label>] [--limit <n>]
allowed-tools: Read, Write, Edit, Bash(python3:*, git:*, gh:*), Skill, Agent
---

# /wg-issue

Launch an autonomous ralph-loop to review GitHub issues, batch-resolve them via crew workflow, release, and verify.

## Arguments

Parse: $ARGUMENTS

- **--list**: Just list open issues without starting work (skip ralph-loop)
- **--label <label>**: Filter issues by label (e.g., `bug`, `enhancement`)
- **--limit <n>**: Number of issues to show (default: 10)

## If --list

List issues only — do NOT start a ralph-loop:

```bash
gh issue list --state open --limit "${limit:-10}" ${label:+--label "${label}"} --json number,title,labels,assignees,createdAt,updatedAt
```

Present issues in a table and stop.

## Otherwise: Start Ralph Loop

Invoke the ralph-loop skill with the following prompt:

```
/ralph-loop:ralph-loop Review our github issues and
  - pick a group that makes sense to work on at the same time
  - Run a crew to do the work in just finish mode making sure to use council reviews and approvals or to answer questions.
  - When the crew is finished, run wg-release.
  - Validate the release exists in gh

For any failures use the council for support.
```

The ralph-loop will autonomously:
1. Review open GitHub issues and select a cohesive batch
2. Start a crew project in just-finish mode for the batch
3. Use council (jam) reviews for approvals and to answer questions
4. After crew completion, run `/wg-release` (which includes quality gate)
5. Verify the GitHub release was created successfully
6. Use the council for support on any failures
