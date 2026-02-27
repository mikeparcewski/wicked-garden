---
name: ci-workflow-generation
title: GitHub Actions CI/CD Pipeline Generation
description: Generate secure, optimized CI/CD workflows for a Node.js project with automatic security best practices
type: devops
difficulty: basic
estimated_minutes: 8
---

# GitHub Actions CI/CD Pipeline Generation

This scenario demonstrates wicked-platform's ability to generate production-ready GitHub Actions workflows with security and performance best practices baked in.

## Setup

Create a realistic Node.js API project:

```bash
# Create test project
mkdir -p ~/test-wicked-platform/nodejs-api
cd ~/test-wicked-platform/nodejs-api

# Initialize Node.js project
cat > package.json << 'EOF'
{
  "name": "customer-api",
  "version": "1.0.0",
  "description": "Customer management API",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "test": "jest",
    "lint": "eslint src/",
    "build": "tsc"
  },
  "dependencies": {
    "express": "^4.18.2",
    "pg": "^8.11.0",
    "jsonwebtoken": "^9.0.0"
  },
  "devDependencies": {
    "jest": "^29.5.0",
    "eslint": "^8.40.0",
    "typescript": "^5.0.0"
  }
}
EOF

# Create basic API structure
mkdir -p src/routes src/middleware
cat > src/index.js << 'EOF'
const express = require('express');
const customerRoutes = require('./routes/customers');
const authMiddleware = require('./middleware/auth');

const app = express();
app.use(express.json());
app.use('/api/customers', authMiddleware, customerRoutes);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on ${PORT}`));
EOF

# Create tsconfig for TypeScript detection
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist",
    "strict": true
  }
}
EOF

# Initialize git
git init
```

## Steps

### 1. Generate CI Workflow

```bash
/wicked-platform:actions generate
```

**Expected**:
- Detects Node.js project from `package.json`
- Identifies test script (`npm test`)
- Identifies lint script (`npm run lint`)
- Generates complete CI workflow

### 2. Review Generated Workflow

Verify the generated workflow includes:

**Security features**:
- [ ] Explicit `permissions: contents: read`
- [ ] Actions pinned to major versions (v4)
- [ ] No secret interpolation in `run:` commands
- [ ] Timeouts specified

**Performance features**:
- [ ] npm caching enabled via `actions/setup-node`
- [ ] Concurrency group with `cancel-in-progress: true`
- [ ] Path filtering to skip docs-only changes

### 3. Generate Deployment Workflow

```bash
/wicked-platform:actions generate deploy
```

**Expected**:
- Creates multi-environment deployment workflow
- Includes staging and production environments
- Uses OIDC for cloud credentials (no secrets stored)
- Requires approval for production

### 4. Optimize Existing Workflow

If you have an existing workflow, optimize it:

```bash
# Create a suboptimal workflow
mkdir -p .github/workflows
cat > .github/workflows/ci.yml << 'EOF'
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - run: npm install
      - run: npm test
EOF

/wicked-platform:actions optimize .github/workflows/ci.yml
```

**Expected**:
- Identifies missing permissions declaration
- Flags unpinned action version (`@main`)
- Recommends `npm ci` over `npm install`
- Suggests adding caching
- Recommends timeout and concurrency

## Expected Outcome

A complete, production-ready GitHub Actions workflow:

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

      - name: Run linter
        run: npm run lint

      - name: Run tests
        run: npm test
```

## Success Criteria

- [ ] Workflow generated without manual intervention
- [ ] Stack correctly detected (Node.js)
- [ ] Security best practices applied automatically
- [ ] Caching enabled for faster builds
- [ ] Concurrency prevents stale runs
- [ ] Path filtering excludes documentation
- [ ] All action versions pinned
- [ ] Workflow passes GitHub Actions validation

## Value Demonstrated

**Problem solved**: Writing secure GitHub Actions workflows requires knowing dozens of best practices. Most developers copy-paste from examples that lack security hardening.

**Why this matters**:

1. **Security by default**: Workflows generated with explicit permissions prevent supply-chain attacks. Pinned action versions prevent malicious updates.

2. **Performance optimization**: Caching reduces build times by 30-60%. Concurrency cancellation saves CI minutes on stale branches.

3. **Consistency**: Every generated workflow follows the same security and performance standards, eliminating "works on my machine" CI configurations.

4. **Time savings**: Developers skip the trial-and-error of configuring CI from scratch. A 30-minute task becomes a 2-minute conversation.

This replaces ad-hoc workflow creation where developers:
- Forget permissions (security risk)
- Use unpinned actions (supply-chain risk)
- Skip caching (waste CI minutes)
- Don't handle concurrency (race conditions)

The `/actions generate` command encapsulates hard-won CI/CD expertise.
