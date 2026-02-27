---
description: Security review and vulnerability assessment
argument-hint: "<path, PR, or 'full' for comprehensive scan> [--scenarios]"
---

# /wicked-garden:platform:security

Perform security review with OWASP compliance, secrets detection, and vulnerability assessment.

## Instructions

### 1. Determine Scope

Parse the argument to determine review scope:
- **Path**: Security review of specific file/directory
- **PR number**: Review changes in pull request
- **"full"**: Comprehensive codebase security scan

### 2. Dispatch to Security Engineer

```python
Task(
    subagent_type="wicked-garden:platform/security-engineer",
    prompt="""Perform comprehensive security review.

Scope: {determined scope}

Assessment Checklist:
1. OWASP Top 10 vulnerabilities (injection, broken auth, XSS, etc.)
2. Secrets and credentials in code (API keys, tokens, passwords)
3. Injection vulnerabilities (SQL, XSS, command injection)
4. Authentication and authorization issues
5. Insecure dependencies and outdated packages
6. Security misconfigurations (overly permissive settings)

Return Format:
- Risk level (CRITICAL/HIGH/MEDIUM/LOW)
- Findings by severity with file:line references
- OWASP compliance matrix
- Prioritized recommendations
"""
)
```

### 3. Scan for Common Issues

Use wicked-search to find patterns:

```bash
# Secrets detection
grep -E "(api[_-]?key|secret|password|token|credential)" --include="*.{js,ts,py,go,java}"

# SQL injection risks
grep -E "execute\(|query\(.*\+" --include="*.{js,ts,py}"

# Command injection
grep -E "exec\(|spawn\(|system\(" --include="*.{js,ts,py,go}"
```

### 4. Check Dependencies

```bash
# Node.js
npm audit --json

# Python
pip-audit

# Go
govulncheck ./...
```

### 5. Deliver Security Report

```markdown
## Security Review Report

**Scope**: {what was reviewed}
**Risk Level**: [CRITICAL | HIGH | MEDIUM | LOW]

### Findings

#### Critical
- {finding with file:line}

#### High
- {finding with file:line}

#### Medium
- {finding with file:line}

### OWASP Compliance
| Category | Status | Issues |
|----------|--------|--------|
| Injection | {status} | {count} |
| Broken Auth | {status} | {count} |
| XSS | {status} | {count} |

### Recommendations
1. {priority fix}
2. {improvement}
```

### 6. Optional: Generate Wicked-Scenarios Format

When `--scenarios` is passed, generate wicked-scenarios format test scenarios that verify the vulnerability and its fix.

**Severity → scenario mapping:**

| Finding Severity | Scenario Category | Tools | What to Test |
|-----------------|-------------------|-------|-------------|
| CRITICAL (injection, auth bypass) | security | semgrep | Parameterized queries, input sanitization |
| HIGH (XSS, SSRF, exposed secrets) | security | semgrep | Output encoding, SSRF prevention, secret rotation |
| MEDIUM (missing rate limiting, verbose errors) | api | curl | Rate limit enforcement, error message content |
| Dependency vulnerabilities | infra | trivy | Container/dependency scanning |

For each CRITICAL/HIGH finding, produce a wicked-scenarios block:

````markdown
---
name: {scope-kebab}-security
description: "Security scenarios from review of {scope}"
category: security
tools:
  required: [semgrep]
difficulty: intermediate
timeout: 60
---

## Steps

### Step 1: {OWASP category} - {finding title} (semgrep)

```bash
# Scan for the vulnerability pattern in code
semgrep --config p/{owasp-rule} --json {scope}
```

**Expect**: Exit code 0 — vulnerability pattern not found (fix verified)

### Step 2: {next finding} (semgrep)

```bash
# Verify secure coding pattern is in place
semgrep --config {custom-rule} --json {scope}
```

**Expect**: Exit code 0 — secure pattern confirmed
````

**OWASP → semgrep rule patterns (security category):**
- **SQL Injection** → `semgrep --config p/sql-injection` to verify parameterized queries
- **XSS** → `semgrep --config p/xss` to verify output encoding
- **Command Injection** → `semgrep --config p/command-injection` to verify input sanitization
- **Secrets** → `semgrep --config p/secrets` to verify no hardcoded credentials

**Dynamic HTTP testing (generate as separate `api` category scenarios with `curl`):**
- **Broken Auth** → `curl` without auth token, expect 401
- **SSRF** → `curl` with internal IP payload, expect rejection
- **Rate limiting** → `curl` rapid requests, expect 429

**Dependency scanning (generate as separate `infra` category scenarios):**
- **Dependency vulns** → `trivy fs .` to verify patched dependencies

## Example

```
User: /wicked-garden:platform:security src/api/

Claude: I'll perform a security review of the API directory.

[Spawns security-engineer agent]
[Scans for OWASP vulnerabilities]
[Checks for secrets]

## Security Review: src/api/

**Risk Level**: HIGH

### Critical Findings

1. **SQL Injection** - `src/api/users.ts:45`
   ```typescript
   // VULNERABLE
   db.query(`SELECT * FROM users WHERE id = ${userId}`)
   ```
   Fix: Use parameterized queries

2. **Hardcoded Secret** - `src/api/auth.ts:12`
   ```typescript
   const API_KEY = "sk-prod-abc123..."
   ```
   Fix: Move to environment variable

### Medium Findings

1. **Missing rate limiting** on `/api/login` endpoint
2. **Verbose error messages** exposing stack traces

### Recommendations
1. Immediately rotate exposed API key
2. Implement parameterized queries
3. Add rate limiting to auth endpoints
```
