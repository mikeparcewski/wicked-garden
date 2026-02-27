---
description: GitHub CLI power utilities for workflows, PRs, and releases
argument-hint: "<operation: workflows|prs|releases|repo> [args]"
---

# /wicked-garden:platform:gh

GitHub CLI operations for workflow debugging, PR management, and release automation.

## Instructions

### 1. Parse Operation

Determine which GitHub operation:
- **workflows**: Debug and manage GitHub Actions
- **prs**: Pull request operations
- **releases**: Release management
- **repo**: Repository health and stats

### 2. Execute Operation

For **simple gh operations**, execute inline:

#### Workflows
```bash
# List recent workflow runs
gh run list --limit 10

# View failed workflow
gh run view {run-id} --log-failed

# Re-run failed jobs
gh run rerun {run-id} --failed
```

#### PRs
```bash
# List open PRs
gh pr list

# View PR details with checks
gh pr view {number} --comments

# Check PR status
gh pr checks {number}
```

#### Releases
```bash
# List releases
gh release list

# Create release
gh release create v{version} --generate-notes

# View release
gh release view {tag}
```

#### Repo
```bash
# Repo stats
gh repo view

# Clone stats
gh api repos/{owner}/{repo}/traffic/clones

# Contributors
gh api repos/{owner}/{repo}/contributors
```

For **complex workflow operations** (multi-step CI/CD setup, workflow generation), dispatch:

```python
Task(
    subagent_type="wicked-garden:platform/devops-engineer",
    prompt="""Handle complex GitHub workflow operation.

Operation: {what user requested}
Context: {repo details, workflow files, etc.}

Task:
{specific multi-step workflow task requiring expertise}

Return Format:
- Summary of actions taken
- Commands executed
- Results and next steps
"""
)
```

### 3. Provide Actionable Output

Format results with:
- Summary of findings
- Specific actions to take
- Commands to run

## Example

```
User: /wicked-garden:platform:gh workflows

Claude: I'll check your GitHub Actions workflows.

[Runs gh run list]
[Identifies failures]

## Workflow Status

### Recent Runs
| Workflow | Status | Duration | Trigger |
|----------|--------|----------|---------|
| CI | success | 4m 32s | push to main |
| Deploy | failure | 2m 15s | push to main |
| Tests | success | 8m 45s | PR #234 |

### Failed: Deploy (run 12345678)

**Error**: Deployment failed at "Deploy to staging" step
```
Error: The process '/usr/bin/docker' failed with exit code 1
```

**Root Cause**: Docker build failed due to missing build argument

**Fix**:
```yaml
# Add missing build arg in workflow
- name: Build
  run: docker build --build-arg VERSION=${{ github.sha }} .
```

**Actions**:
1. Fix the workflow file
2. Re-run: `gh run rerun 12345678`
```
