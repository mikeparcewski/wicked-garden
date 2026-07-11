# GitHub Actions Rubric

Generate, optimize, and troubleshoot GitHub Actions workflows.

## Parse Mode

Determine operation mode from arguments:
- **generate**: Create new workflow from stack detection
- **optimize**: Improve existing workflow performance/security
- **troubleshoot**: Debug failing workflow

## Generate Mode

Detect project stack:
```bash
ls package.json pyproject.toml Cargo.toml go.mod pom.xml 2>/dev/null
```

Generate workflow with all security + performance features:

**Security-First Checklist:**
- [ ] Explicit permissions declared (not `write-all`)
- [ ] Action versions pinned to major or full hash
- [ ] No direct input interpolation (injection risk)
- [ ] Secrets via environment variables only
- [ ] Timeout configured per job
- [ ] Concurrency control enabled

**Performance Checklist:**
- [ ] Dependency caching enabled (`cache: 'npm'` / `actions/cache@v4`)
- [ ] Concurrency group cancels stale runs
- [ ] Path filtering skips doc-only changes
- [ ] Matrix strategy for multi-version only when needed

### Minimal Secure CI Template

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
      - run: npm ci
      - run: npm test
      - run: npm run lint
```

Adapt the setup action and run commands for Python (`setup-python@v5`, `pip install`, `pytest`),
Go (`setup-go@v5`, `go test ./...`), Rust (`cargo test`), etc.

## Optimize Mode

Read the target workflow file. Apply this checklist:

- [ ] `permissions:` block is explicit (remove `write-all` or omit→defaults)
- [ ] All `uses:` actions pinned to a version tag or commit SHA
- [ ] `concurrency:` group configured with `cancel-in-progress: true`
- [ ] `timeout-minutes:` set on each job (default GitHub max is 6h — bad)
- [ ] Dependency cache configured via setup action `cache:` param or `actions/cache@v4`
- [ ] `paths-ignore:` or `paths:` on push/PR triggers for large repos
- [ ] No `${{ github.event.*.body }}` or similar untrusted inputs in `run:` commands
- [ ] No secrets printed or echoed in steps

Return optimized YAML + annotated diff of every change with rationale.

## Troubleshoot Mode

```bash
# Get most recent failure
gh run list --status failure --limit 1 --json databaseId,name,headBranch -q '.[0]'

# Get failure logs
gh run view {id} --log-failed
```

Analyze the error output. Common patterns:
| Error | Cause | Fix |
|-------|-------|-----|
| `Permission denied` on action | Missing `permissions:` | Add explicit block |
| `Secret not found` | Wrong secret name | Check repo settings → Secrets |
| `Cache miss every run` | Wrong key or path | Verify `hashFiles()` target |
| `Process exited with code 1` in build | Test failure or bad cmd | Read log output |
| `No such file` | Wrong working-directory | Add `working-directory:` |

Provide root cause and the exact YAML fix.

## Output Format

**Generate/Optimize**: Provide complete workflow YAML, then a bullet list of security features applied
and performance improvements with estimated savings.

**Troubleshoot**: Root cause + the exact YAML or command fix. Offer `gh run rerun {id}` command.
