# Security Scan Output Format

```markdown
## Security Scan Results

**Scan Date**: {date}
**Target**: {path/component}
**Compliance**: OWASP Top 10 - {PASS/FAIL}

### Critical Findings

| Severity | Type | CWE | Location | Description |
|----------|------|-----|----------|-------------|
| CRITICAL | SQL Injection | CWE-89 | `file:line` | Unsanitized user input in query |
| HIGH | Secrets Exposure | CWE-798 | `file:line` | Hardcoded API key in source |

### Secure Patterns Observed

- Proper parameterized queries in user service
- OIDC authentication for cloud deployments
- Secrets managed via environment variables

### Recommendations

1. **CRITICAL: Fix SQL Injection**
   - Location: `src/db/users.js:42`
   - Current: `SELECT * FROM users WHERE id = ${userId}`
   - Fix: Use parameterized queries: `SELECT * FROM users WHERE id = ?`
   - Impact: Immediate exploitation risk

2. **HIGH: Remove Hardcoded Secret**
   - Location: `.env.example:5`
   - Current: API key exposed in example file
   - Fix: Use placeholder value, document in README
   - Impact: Credential compromise

### Additional Hardening

- Enable dependabot for automated dependency updates
- Add SAST scanning to CI/CD pipeline
- Implement security headers (CSP, HSTS)
- Consider adding SCA (Software Composition Analysis)

### Dependency Vulnerabilities

{npm audit or pip-audit output summary}

### Next Steps

1. Address CRITICAL and HIGH findings before deployment
2. Schedule review of MEDIUM findings
3. Add automated security scanning to pipeline
```
