---
description: GitHub Actions workflow generation and optimization
argument-hint: "<generate|optimize|troubleshoot> [workflow file]"
---

# /wicked-garden:platform:actions

Generate, optimize, and troubleshoot GitHub Actions workflows.

## Instructions

### 1. Parse Mode

Determine operation mode:
- **generate**: Create new workflow from stack detection
- **optimize**: Improve existing workflow performance/security
- **troubleshoot**: Debug failing workflow

### 2. For Generate Mode: Dispatch to DevOps Engineer

If generating complex workflow:
```python
Task(
    subagent_type="wicked-garden:platform:devops-engineer",
    prompt="""Generate GitHub Actions workflow for this project.

Project Stack: {detected from package.json, pyproject.toml, etc.}

Workflow Requirements:
1. Explicit permissions (security best practice)
2. Caching enabled (performance)
3. Concurrency control (cancel stale runs)
4. Timeout limits (prevent hanging)
5. Path filtering (skip irrelevant changes)
6. Action versions pinned
7. No secrets in logs

Return Format:
- Complete workflow YAML
- Security features explained
- Performance optimizations noted
- File path: .github/workflows/{name}.yml
"""
)
```

For simple generation, stay inline and detect stack:
```bash
# Check for stack indicators
ls package.json pyproject.toml Cargo.toml go.mod pom.xml
```

Then generate workflow with security and performance features.

### 3. For Optimize Mode: Dispatch to DevOps Engineer

```python
Task(
    subagent_type="wicked-garden:platform:devops-engineer",
    prompt="""Optimize GitHub Actions workflow for security and performance.

Workflow File: {specified file path}

Optimization Checklist:
- [ ] Explicit permissions declared
- [ ] Action versions pinned
- [ ] Caching configured
- [ ] Concurrency group set
- [ ] Timeout specified
- [ ] Path filtering applied
- [ ] No secrets in logs

Return Format:
- Optimized workflow YAML
- Changes made with rationale
- Performance improvements estimated
- Security enhancements highlighted
"""
)
```

### 4. For Troubleshoot Mode: Stay Inline

```bash
# Get recent failure
gh run list --status failure --limit 1 --json databaseId -q '.[0].databaseId'

# Get failure logs
gh run view {id} --log-failed
```

Analyze error and provide fix directly (simple gh operations, no dispatch needed).

### 5. Deliver Output

For generate/optimize, provide complete workflow YAML.
For troubleshoot, provide root cause and fix.

## Example

```
User: /wicked-garden:platform:actions generate

Claude: I'll generate a GitHub Actions workflow for your project.

[Detects Node.js project from package.json]
[Checks for test scripts]

## Generated Workflow: .github/workflows/ci.yml

```yaml
name: CI

on:
  push:
    branches: [main]
    paths-ignore:
      - '**.md'
      - 'docs/**'
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npm test

      - name: Run linter
        run: npm run lint
```

### Security Features
- Explicit `contents: read` permission
- Actions pinned to major versions
- No secret interpolation in run commands

### Performance Features
- npm caching enabled (~30s savings)
- Concurrency cancels stale runs
- Path filtering skips docs-only changes

Shall I write this to `.github/workflows/ci.yml`?
```
