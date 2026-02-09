---
description: Security review and vulnerability assessment
argument-hint: "<path, PR, or 'full' for comprehensive scan>"
---

# /wicked-platform:security

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
    subagent_type="wicked-platform:security-engineer",
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

## Example

```
User: /wicked-platform:security src/api/

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
