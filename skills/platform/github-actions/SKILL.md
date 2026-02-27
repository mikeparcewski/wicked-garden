---
name: github-actions
description: Write secure, optimized GitHub Actions workflows. Use when creating CI/CD pipelines, automating deployments, or debugging workflow issues. Security-first approach with performance optimization.
---

# GitHub Actions Workflow Writing

Write production-ready GitHub Actions workflows with security and performance built in.

## When to Use

- Creating new CI/CD workflows
- Optimizing slow or expensive workflows
- Adding deployment pipelines
- Security scanning and compliance
- Debugging workflow issues

## Security-First Principles

Every workflow should follow these rules:

### 1. Explicit Permissions

```yaml
# ALWAYS declare permissions explicitly
permissions:
  contents: read  # Minimum needed

# NEVER use write-all or leave permissions implicit
```

### 2. Pin Action Versions

```yaml
# Good - pinned to SHA
uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608  # v4.1.0

# Acceptable - pinned to major version
uses: actions/checkout@v4

# Bad - unpinned
uses: actions/checkout@main
```

### 3. Sanitize Inputs

```yaml
# NEVER interpolate untrusted input directly
run: echo "${{ github.event.issue.title }}"  # DANGEROUS

# Use environment variables instead
env:
  TITLE: ${{ github.event.issue.title }}
run: echo "$TITLE"  # Safe
```

## Core Patterns

### Minimal CI

```yaml
name: CI
on: [push, pull_request]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm test
```

### Multi-Environment Deploy

```yaml
jobs:
  deploy-staging:
    environment: staging
    # ...
  deploy-production:
    needs: deploy-staging
    environment: production
    # Requires approval in GitHub settings
```

### OIDC for Cloud (No Secrets!)

```yaml
permissions:
  id-token: write  # Required for OIDC
  contents: read
steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789:role/github-actions
      aws-region: us-east-1
```

## Performance Optimization

### 1. Caching

```yaml
# Node.js (built into setup-node)
- uses: actions/setup-node@v4
  with:
    cache: 'npm'

# Python
- uses: actions/setup-python@v5
  with:
    cache: 'pip'

# Custom cache
- uses: actions/cache@v4
  with:
    path: ~/.cache/my-tool
    key: ${{ runner.os }}-my-tool-${{ hashFiles('**/lockfile') }}
```

### 2. Concurrency Control

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Cancel stale runs
```

### 3. Path Filtering

```yaml
on:
  push:
    paths:
      - 'src/**'
      - 'package.json'
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

### 4. Matrix Strategy

```yaml
strategy:
  matrix:
    node: [18, 20, 22]
    os: [ubuntu-latest, windows-latest]
  fail-fast: false  # Don't cancel others on failure
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| No timeout | Add `timeout-minutes: 15` |
| No concurrency | Add concurrency group |
| Implicit permissions | Declare explicitly |
| `pull_request_target` misuse | Use `pull_request` unless you need write access |
| Unpinned actions | Pin to SHA or major version |
| Direct input interpolation | Use env vars |

## Workflow Generation

When generating workflows, follow this checklist:

1. **Detect stack** - Check for package.json, requirements.txt, Cargo.toml, etc.
2. **Set permissions** - Start with `contents: read`, add only what's needed
3. **Add caching** - Use built-in cache options when available
4. **Set timeout** - Default 10-15 min for CI, 30 for deploys
5. **Add concurrency** - Cancel stale runs
6. **Document secrets** - Comment required secrets at top

## References

- `refs/security.md` - Detailed security practices
- `refs/templates.md` - Copy-paste templates
- `refs/troubleshooting.md` - Common errors and fixes
