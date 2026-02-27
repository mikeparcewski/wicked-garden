---
name: workflow-troubleshooting
title: GitHub Actions Workflow Debugging
description: Diagnose and fix failing GitHub Actions workflows with root cause analysis and targeted fixes
type: devops
difficulty: intermediate
estimated_minutes: 10
---

# GitHub Actions Workflow Debugging

This scenario demonstrates wicked-platform's ability to diagnose failing CI/CD workflows, identify root causes from logs, and provide targeted fixes.

## Setup

Create a project with a failing GitHub Actions workflow:

```bash
# Create test project
mkdir -p ~/test-wicked-platform/failing-ci
cd ~/test-wicked-platform/failing-ci

# Initialize git repo
git init

# Create package.json
cat > package.json << 'EOF'
{
  "name": "failing-ci-demo",
  "version": "1.0.0",
  "scripts": {
    "test": "jest",
    "lint": "eslint src/",
    "build": "tsc"
  },
  "dependencies": {
    "express": "^4.18.2"
  },
  "devDependencies": {
    "jest": "^29.5.0",
    "typescript": "^5.0.0",
    "eslint": "^8.40.0"
  }
}
EOF

# Create a problematic workflow with common issues
mkdir -p .github/workflows
cat > .github/workflows/ci.yml << 'EOF'
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
      - run: npm install
      - run: npm test
      - run: npm run build

  deploy:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - run: |
          echo "Deploying to $DEPLOY_ENV"
          curl -X POST https://api.example.com/deploy \
            -H "Authorization: Bearer ${{ secrets.DEPLOY_TOKEN }}" \
            -d '{"env": "${{ github.event.inputs.environment }}"}'
EOF

# Create src directory with TypeScript
mkdir -p src
cat > src/index.ts << 'EOF'
import express from 'express';

const app = express();
app.get('/', (req, res) => res.send('Hello'));
app.listen(3000);
EOF

# Create a test file with intentional failure
mkdir -p __tests__
cat > __tests__/index.test.ts << 'EOF'
describe('API', () => {
  it('should return hello', () => {
    expect('Hello').toBe('Hello');
  });

  it('should handle edge case', () => {
    // This test is flaky - passes locally, fails in CI
    const date = new Date();
    expect(date.getTimezoneOffset()).toBe(0); // Assumes UTC
  });
});
EOF

git add -A
git commit -m "Initial commit with CI workflow"
```

## Steps

### 1. Diagnose Workflow Failure

Simulate having a failed workflow and troubleshoot it:

```bash
/wicked-platform:actions troubleshoot
```

**Expected**:
- Examines workflow configuration
- Identifies common issues
- Checks for security problems
- Analyzes potential failure points

### 2. Review Workflow Issues

The troubleshooting should identify:

**Security Issues**:
- [ ] Unpinned action version (`actions/checkout@main`)
- [ ] Missing explicit permissions
- [ ] Potential secret exposure in curl command

**Configuration Issues**:
- [ ] Using `npm install` instead of `npm ci`
- [ ] No caching configured
- [ ] No timeout specified
- [ ] No concurrency control

**Potential Runtime Issues**:
- [ ] Flaky test depending on timezone
- [ ] Missing TypeScript types for jest

### 3. Simulate Log Analysis

```bash
# Create simulated failure log
cat > workflow-failure.log << 'EOF'
2024-01-15T14:30:00Z Run actions/checkout@main
2024-01-15T14:30:05Z Checking out repository
2024-01-15T14:30:10Z Run actions/setup-node@v4
2024-01-15T14:30:15Z Setup Node.js 18.x
2024-01-15T14:30:20Z Run npm install
2024-01-15T14:31:00Z npm WARN deprecated package@1.0.0
2024-01-15T14:31:30Z added 523 packages in 70s
2024-01-15T14:31:35Z Run npm test
2024-01-15T14:31:40Z PASS __tests__/index.test.ts
2024-01-15T14:31:40Z   API
2024-01-15T14:31:40Z     ✓ should return hello (2 ms)
2024-01-15T14:31:40Z     ✕ should handle edge case (5 ms)
2024-01-15T14:31:40Z
2024-01-15T14:31:40Z   ● API › should handle edge case
2024-01-15T14:31:40Z
2024-01-15T14:31:40Z     expect(received).toBe(expected)
2024-01-15T14:31:40Z
2024-01-15T14:31:40Z     Expected: 0
2024-01-15T14:31:40Z     Received: -480
2024-01-15T14:31:40Z
2024-01-15T14:31:40Z       at Object.<anonymous> (__tests__/index.test.ts:9:39)
2024-01-15T14:31:40Z
2024-01-15T14:31:40Z Test Suites: 1 failed, 1 total
2024-01-15T14:31:40Z Tests:       1 failed, 1 passed, 2 total
2024-01-15T14:31:40Z Error: Process completed with exit code 1.
EOF

/wicked-platform:actions troubleshoot --logs workflow-failure.log
```

**Expected**:
Root cause analysis from logs:

```markdown
### Workflow Failure Analysis

**Failed Step**: npm test
**Exit Code**: 1 (test failure)

#### Root Cause

Test `should handle edge case` failed due to timezone assumption.

```
Expected: 0 (UTC offset)
Received: -480 (PST offset, GitHub runner uses different TZ)
```

**Issue**: Test assumes system timezone is UTC, but GitHub runners may use different timezones.

#### Fix

```typescript
// Option 1: Mock timezone in test
beforeAll(() => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date('2024-01-15T12:00:00Z'));
});

// Option 2: Use UTC explicitly
it('should handle edge case', () => {
  const date = new Date();
  const utcOffset = date.getTimezoneOffset(); // Could be any value
  expect(typeof utcOffset).toBe('number'); // Test behavior, not timezone
});

// Option 3: Set TZ in workflow
env:
  TZ: UTC
```
```

### 4. Get Optimized Workflow

```bash
/wicked-platform:actions optimize .github/workflows/ci.yml
```

**Expected**:
Improved workflow addressing all issues:

```yaml
name: CI

on:
  push:
    branches: [main]
    paths-ignore:
      - '**.md'
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  TZ: UTC  # Consistent timezone for tests

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4  # Pinned version

      - uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'  # Enable caching

      - name: Install dependencies
        run: npm ci  # Deterministic installs

      - name: Run tests
        run: npm test

      - name: Build
        run: npm run build

  deploy:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    environment: production  # Requires approval
    permissions:
      contents: read
      deployments: write
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Deploy
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
        run: |
          curl -X POST https://api.example.com/deploy \
            -H "Authorization: Bearer $DEPLOY_TOKEN" \
            -d '{"env": "production"}'
```

### 5. Verify Fixes

Review the changes made:

```markdown
### Changes Applied

| Issue | Before | After | Impact |
|-------|--------|-------|--------|
| Unpinned checkout | @main | @v4 | Security |
| No permissions | implicit | explicit read | Security |
| npm install | npm install | npm ci | Reliability |
| No caching | none | npm cache | -40s build |
| No timeout | unlimited | 15min | Cost control |
| No concurrency | none | cancel stale | Cost control |
| Flaky timezone | system TZ | TZ: UTC | Reliability |
| Secret in command | inline | env var | Security |
```

## Expected Outcome

Complete troubleshooting report:

```markdown
## Workflow Troubleshooting Report

**Workflow**: .github/workflows/ci.yml
**Status**: Multiple issues found

### Test Failure Root Cause

**Failed Test**: `should handle edge case`
**Reason**: Timezone assumption (expected UTC, got local TZ)
**Fix**: Set `TZ: UTC` in workflow environment

### Security Issues (3)

1. **Unpinned action**: `actions/checkout@main`
   - Risk: Supply chain attack
   - Fix: Pin to `@v4` or SHA

2. **No permissions declared**
   - Risk: Overprivileged workflow
   - Fix: Add `permissions: contents: read`

3. **Secret in command output**
   - Risk: Token visible in logs
   - Fix: Use environment variable

### Performance Issues (2)

1. **No caching**: npm downloads on every run
   - Impact: +60s per build
   - Fix: Enable npm cache in setup-node

2. **No concurrency**: Stale runs continue
   - Impact: Wasted CI minutes
   - Fix: Add concurrency group

### Reliability Issues (2)

1. **npm install vs npm ci**
   - Risk: Non-deterministic installs
   - Fix: Use `npm ci`

2. **No timeout**
   - Risk: Hung jobs consume minutes
   - Fix: Add `timeout-minutes: 15`

### Recommended Workflow

[Optimized workflow YAML provided]

### Estimated Improvement

- Build time: -60s (caching)
- Security: 3 vulnerabilities fixed
- Cost: ~30% reduction in CI minutes
- Reliability: Flaky test fixed
```

## Success Criteria

- [ ] Workflow issues correctly identified
- [ ] Test failure root cause found (timezone)
- [ ] Security issues flagged (unpinned action, permissions, secrets)
- [ ] Performance optimizations suggested (caching, concurrency)
- [ ] Reliability issues identified (npm ci, timeout)
- [ ] Optimized workflow generated
- [ ] All changes explained with rationale
- [ ] Impact of changes quantified

## Value Demonstrated

**Problem solved**: Debugging CI/CD failures is time-consuming. Engineers stare at logs, try random fixes, and often miss underlying issues. Workflow security problems go unnoticed until audit.

**Why this matters**:

1. **Root cause, not symptoms**: Instead of re-running until tests pass, identify why the test failed (timezone assumption) and fix it permanently.

2. **Security audit included**: Every troubleshooting session also reviews security posture. Catch unpinned actions and permission issues.

3. **Quantified improvements**: Not just "add caching" but "-60s per build, ~30% CI cost reduction." Makes the ROI clear.

4. **Learning opportunity**: Explanations of why each fix matters help developers improve their CI/CD knowledge.

5. **Comprehensive review**: A human might fix the test and move on. The plugin reviews the entire workflow holistically.

This replaces the frustrating CI debugging loop where:
- Developer re-runs workflow hoping it passes
- Eventually searches Stack Overflow for error message
- Fixes one thing, misses three security issues
- Workflow works but costs 2x what it should

The `/actions troubleshoot` command brings CI/CD expertise to every failed build.
