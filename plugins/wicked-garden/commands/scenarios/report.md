---
description: File GitHub issues from acceptance test failures with deduplication and grouping
arguments:
  - name: results
    description: "Acceptance test results to report. Pass --auto to skip prompts, or --dry-run to preview without filing."
    required: false
---

# /wicked-garden:scenarios-report

File GitHub issues for acceptance test failures. Handles deduplication against existing open issues, groups multiple failures per plugin into single issues, and supports both interactive and automatic modes.

## Usage

```
/wicked-garden:scenarios-report [--auto] [--dry-run]
```

This command is designed to be called **after** acceptance testing completes (via `/wicked-garden:qe-acceptance` or `/wg-test`). It reads the test results from the current conversation context.

## Instructions

### 1. Parse Arguments and Collect Results

Parse `$ARGUMENTS` for flags:
- `--auto`: File issues for all failures without prompting
- `--dry-run`: Show what would be filed without actually creating issues

The test results should be available in the conversation context from the preceding acceptance run. Extract for each scenario:
- `plugin`: Plugin name
- `scenario`: Scenario name
- `scenario_file`: Path to scenario file
- `overall_verdict`: PASS/FAIL/PARTIAL/INCONCLUSIVE
- `task_verdicts`: Array of per-task results with verdicts, assertions, failure causes
- `acceptance_criteria_verdicts`: Criteria-level results
- `failure_analysis`: Reviewer's cause attribution
- `specification_notes`: Spec mismatches from writer phase

If no results are available in context, report an error:
```
No acceptance test results found. Run /wicked-garden:qe-acceptance (or /wg-test) first, then /wicked-garden:scenarios-report.
```

### 2. Filter to Failures Only

Collect all scenarios with `overall_verdict` of FAIL. Skip PASS, PARTIAL (no hard failures), and INCONCLUSIVE (insufficient evidence to file a bug).

If no failures found:
```markdown
All scenarios passed — no issues to file.
```
Exit.

### 3. Check for Interactive Mode

If `--auto` is NOT set and `--dry-run` is NOT set, ask the user:

```
AskUserQuestion(
  question="N scenario(s) failed. File GitHub issues for the failures?",
  options=[
    "Yes, file issues for all failures",
    "Let me pick which ones",
    "No, just show the results"
  ]
)
```

If "Let me pick", show failures and let user select. If "No", exit with summary only.

### 4. Deduplicate Against Existing Issues

Before filing, check for existing open issues that match:

```bash
gh issue list --state open --search "test(<plugin-name>):" --json number,title --limit 5
```

For each plugin with failures, parse the output. If a matching issue exists (title contains `test(<plugin>):`), note it as a duplicate and skip filing. Report:
```markdown
Skipped: #<number> already tracks <plugin> test failures
```

### 5. Group Failures by Plugin

If multiple scenarios fail for the **same plugin**, combine them into a single issue. This prevents issue spam.

- 1 scenario failure for a plugin → title: `test(<plugin>): <scenario> scenario failure`
- N scenario failures for a plugin → title: `test(<plugin>): N scenario failures`

### 6. File Issues

For each plugin with non-duplicate failures, create a GitHub issue:

```bash
gh issue create \
  --title "<title from step 5>" \
  --label "bug" --label "<plugin-name>" \
  --body "$(cat <<'ISSUE_EOF'
## UAT Scenario Failure

**Plugin**: <plugin-name>
**Scenario(s)**: <scenario-name(s)> (`<scenario-file-path(s)>`)
**Run date**: <UTC timestamp>

## Failed Tasks

| # | Task | Assertion | Verdict | Cause |
|---|------|-----------|---------|-------|
| <n> | <description> | <assertion> | FAIL | <cause from reviewer> |

## Evidence Details

<For each failed task, include key evidence excerpts from the reviewer>

## Failure Analysis

<Reviewer's cause attribution and recommendations>

## Specification Notes

<Any spec mismatches caught by the writer phase, or "None">
ISSUE_EOF
)"
```

If `--dry-run`, show the issue body but do NOT run `gh issue create`. Display:
```markdown
### Dry Run: Would file issue
**Title**: test(<plugin>): <scenario> scenario failure
**Labels**: bug, <plugin-name>
<body preview>
```

### 7. Summary

After filing (or dry-run), display:

```markdown
## Issues Filed

| # | Plugin | Scenarios | Title |
|---|--------|-----------|-------|
| <number> | <plugin> | <count> | <title> |

| Action | Count |
|--------|-------|
| Filed | N |
| Skipped (duplicate) | N |
| Skipped (user choice) | N |
```

## Graceful Degradation

- If `gh` CLI is not available, report error and suggest installing GitHub CLI
- If not authenticated (`gh auth status` fails), report and suggest `gh auth login`
- If label creation fails (label doesn't exist), file without labels and note the issue
