---
description: File a GitHub issue for a bug, UX friction point, or unmet outcome
argument-hint: "[bug | ux-friction | unmet-outcome | --list-unfiled]"
allowed_tools:
  - Bash
  - Read
  - Write
  - Grep
  - AskUserQuestion
  - Skill
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

If `--list-unfiled` was provided, skip to Section 7.

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

### 3. Research Before Filing

After collecting the title and initial description, run three research steps. All findings are additive — they enrich the issue body but do not block filing.

#### 3a. Duplicate Detection

Search existing open issues for the same or similar problem:

```bash
gh issue list --repo {repo} --search "{title keywords}" --state open --json number,title,state --limit 10
```

- If `gh` is unavailable or the repo is not detected, skip this step.
- If potential duplicates are found (titles with significant keyword overlap), note them:
  ```
  Potential duplicates found — will link in issue body: #123, #456
  ```
- If no duplicates found, note: "No open duplicates detected."
- Append to issue body as a **Duplicate Check** section:
  ```markdown
  ## Duplicate Check

  <!-- Searched: "{keywords}" -->
  - Potential duplicates: #123 "{title}", #456 "{title}"
  <!-- OR -->
  - No open duplicates detected.
  ```

#### 3b. Codebase Research

Search the codebase for files and symbols related to the issue keywords:

```bash
# Use Grep to find files relevant to the issue description
grep -r --include="*.md" --include="*.py" --include="*.js" --include="*.ts" -l "{keyword1}\|{keyword2}" . --max-count=1 | head -10
```

If relevant files are found (up to 5 most relevant), list them as **Related Code**. If no relevant files are found, omit this section.

Append to issue body when files are found:
```markdown
## Related Code

Files likely relevant to this issue:
- `{path/to/file.py}`
- `{path/to/other.md}`
```

#### 3c. Memory Recall

Recall any past context about this area from the memory store:

```
Skill(skill="wicked-garden:mem:recall", args="{issue title keywords}")
```

If memories are returned that are relevant to the issue, summarize them as **Prior Context**. If no relevant memories exist, omit this section.

Append to issue body when memories are found:
```markdown
## Prior Context

From memory store:
- {memory summary 1}
- {memory summary 2}
```

### 4. Validate Acceptance Criteria (SMART)

Before composing the final issue, validate each acceptance criterion against SMART criteria:

**Specific**: The AC must reference a concrete behavior, file, command, or measurable artifact.
- Fail: "should work better", "improves performance", "feels right"
- Pass: "Bash hook returns `{\"ok\": true}` on success", "no grep results for hardcoded paths"

**Measurable**: The AC must include a verifiable assertion — something that can be confirmed true or false without ambiguity.
- Fail: "works as expected", "no errors occur"
- Pass: "passes `/wg-check`", "exit code 0", "output contains 'No issues found'"

For each AC that fails either check:
- **In just-finish / auto mode**: Auto-improve the AC. Rewrite it to be specific and measurable using context from the issue description. Log the change: `[SMART] Improved AC: "{original}" → "{improved}"`
- **In interactive mode**: Warn the user and suggest an improved version. Ask if they'd like to use the improved version or keep the original.

### 5. Compose Issue

Build the issue body using the template from the skill's `refs/templates.md`. Include:
- Reporter info (Claude Code manual report)
- All collected fields
- Research findings (Duplicate Check, Related Code, Prior Context) appended after main body
- Acceptance criteria checklist (SMART-validated)
- Desired outcome statement

Auto-detect the repo:
```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

### 6. Quality Gate and File

#### 6a. Quality Gate (advisory — warns only, does not block filing)

Run these checks before filing. Log any warnings but proceed regardless:

| Check | Criteria | Warning Message |
|-------|----------|-----------------|
| Title length | Under 80 characters | "Title is {N} chars — consider shortening for readability" |
| Title descriptiveness | Not a single word or generic phrase | "Title may be too vague — add more context" |
| Steps to reproduce | For bugs: at least 2 numbered steps | "Bug report has fewer than 2 reproduction steps" |
| Acceptance criteria count | At least 2 ACs | "Only {N} acceptance criteria — add at least 2" |
| AC verb prefix | Each AC starts with an action verb | "AC '{text}' does not start with a verb" |
| AC independence | Each AC is independently verifiable (no 'and' combining two checks) | "AC '{text}' may combine multiple assertions — split for clarity" |
| Duplicate check | Duplicate search was completed | "Duplicate check was skipped — search for existing issues manually" |

Display warnings (if any) before the preview:
```markdown
## Quality Warnings

- Title is 92 chars — consider shortening for readability
- AC 'Root cause identified' does not start with a verb
```

If no warnings, skip the Quality Warnings block.

#### 6b. Confirm and File

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
  1. **Print to screen**: Display the full issue as formatted markdown:
     ```markdown
     ## Issue: {title}
     **Label**: {label}
     **Repo**: {repo or "unknown"}

     {body}
     ```
  2. **Generate GitHub URL**: Build a pre-filled issue creation URL using Python:
     ```python
     import urllib.parse
     title_enc = urllib.parse.quote(title)
     body_enc = urllib.parse.quote(body)
     label_enc = urllib.parse.quote(label)
     url = f"https://github.com/{owner}/{repo}/issues/new?title={title_enc}&body={body_enc}&labels={label_enc}"
     print(url)
     ```
     Display the URL to the user with instructions: "Open this URL to file the issue directly in your browser."
  3. **Ask to save locally**: Ask the user: "Save this issue locally for later filing with `/wicked-garden:report-issue --list-unfiled`? (yes/no)"
     - If yes: Resolve path `UNFILED=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden unfiled-issues)` and save to `${UNFILED}/{timestamp}.json`
     - If no: Skip caching. Done.

### 7. List Unfiled Issues (--list-unfiled)

If `--list-unfiled` was provided:

1. Resolve path: `UNFILED=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden unfiled-issues)`
2. Read all JSON files from `${UNFILED}/`
3. If empty: report "No unfiled issues found."
4. If found: display a summary table:

```markdown
| # | Title | Type | Date |
|---|-------|------|------|
| 1 | Tool failure: Bash (3x) | bug | 2026-02-17 |
| 2 | Navigation is confusing | ux | 2026-02-16 |
```

5. Ask user which to file (all, specific numbers, or cancel)
5. For each selected: run `gh issue create` with the stored title, body, and label
6. On success: delete the unfiled JSON file
7. Report results
