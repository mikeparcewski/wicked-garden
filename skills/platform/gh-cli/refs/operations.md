# GitHub CLI Operations Rubric

Advanced gh CLI operations for workflow debugging, PR management, and release automation.

## Workflow Operations

```bash
# List recent workflow runs (failures first)
gh run list --limit 10

# View a failed workflow with logs
gh run view {run-id} --log-failed

# Re-run only failed jobs
gh run rerun {run-id} --failed

# Trigger a workflow manually
gh workflow run {workflow-name}

# List workflows
gh workflow list
```

## PR Management Operations

```bash
# List open PRs with review status
gh pr list --state open

# View PR details and check status
gh pr view {number} --comments

# Check CI status for a PR
gh pr checks {number}

# Approve a PR
gh pr review {number} --approve

# Merge a PR
gh pr merge {number} --squash

# List PRs needing review
gh pr list --review-requested @me
```

## Release Automation

```bash
# List releases
gh release list

# Create release with auto-generated notes
gh release create v{version} --generate-notes

# Create release with specific notes
gh release create v{version} --notes "..."

# View a release
gh release view {tag}

# Upload artifact to release
gh release upload {tag} {file}

# Delete a release
gh release delete {tag}
```

## Repository Operations

```bash
# Repo overview
gh repo view

# Clone traffic stats
gh api repos/{owner}/{repo}/traffic/clones

# View statistics
gh api repos/{owner}/{repo}/contributors

# List open issues
gh issue list

# Create an issue
gh issue create --title "..." --body "..."

# View issue
gh issue view {number}
```

## Multi-step / Complex Workflow Operations

When the request involves multi-step CI/CD setup, workflow generation from scratch,
or GitLab CI pipeline configuration — apply the workflow design rubric from
`${CLAUDE_PLUGIN_ROOT}/skills/platform/github-actions/refs/actions-rubric.md`
(the github-actions skill).

## Output Format

Results should include:
- Summary of findings (table where appropriate)
- Specific actionable next steps
- Any exact commands to run (copy-pasteable)

For workflow failures: root cause + fix + re-run command.
For PR management: status summary + recommended action.
For releases: release URL when created.
