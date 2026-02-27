# GitHub Actions Security Reference

## Permissions

### Minimal Permissions Table

| Task | Required Permissions |
|------|---------------------|
| Read code | `contents: read` |
| Push commits | `contents: write` |
| Create/update PRs | `pull-requests: write` |
| Modify issues | `issues: write` |
| Deploy to Pages | `pages: write` |
| OIDC auth | `id-token: write` |
| Create releases | `contents: write` |
| Publish packages | `packages: write` |
| Security alerts | `security-events: write` |

### Permission Blocks

```yaml
# Read-only (safest)
permissions:
  contents: read

# PR automation
permissions:
  contents: read
  pull-requests: write

# Deployment
permissions:
  contents: read
  id-token: write  # For OIDC

# Full release
permissions:
  contents: write
  packages: write
```

## OIDC Authentication

**Never store cloud credentials as secrets.** Use OIDC instead.

### AWS

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ vars.AWS_ROLE_ARN }}
    aws-region: ${{ vars.AWS_REGION }}
```

### Azure

```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ vars.AZURE_CLIENT_ID }}
    tenant-id: ${{ vars.AZURE_TENANT_ID }}
    subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
```

### GCP

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY }}
    service_account: ${{ vars.GCP_SERVICE_ACCOUNT }}
```

## Input Sanitization

### Dangerous

```yaml
# Command injection possible
run: |
  echo "Processing: ${{ github.event.issue.title }}"
  git commit -m "${{ github.event.pull_request.title }}"
```

### Safe

```yaml
# Use env vars to escape properly
env:
  ISSUE_TITLE: ${{ github.event.issue.title }}
  PR_TITLE: ${{ github.event.pull_request.title }}
run: |
  echo "Processing: $ISSUE_TITLE"
  git commit -m "$PR_TITLE"
```

## Pull Request Security

### `pull_request` vs `pull_request_target`

| Event | Fork Access | Secret Access | Use When |
|-------|-------------|---------------|----------|
| `pull_request` | Runs on fork | No secrets | CI testing |
| `pull_request_target` | Runs on base | Has secrets | Label/comment bots |

**Rule:** Only use `pull_request_target` when you need to write to the repo (labels, comments). Never checkout untrusted code with secrets access.

### Safe Pattern for PR Labeling

```yaml
on:
  pull_request_target:
    types: [opened]
permissions:
  pull-requests: write
jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      # Don't checkout code - just use API
      - uses: actions/labeler@v5
```

## Action Pinning

### Pin to SHA (Most Secure)

```yaml
uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608
```

### Find SHA

```bash
gh api repos/actions/checkout/git/refs/tags/v4.1.0 --jq '.object.sha'
```

## Self-Hosted Runner Security

**Never use self-hosted runners for public repos.** Any PR can run arbitrary code.

For private repos:
- Use ephemeral runners
- Isolate with containers
- Limit network access
- Rotate credentials
