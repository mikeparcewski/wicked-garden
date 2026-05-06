---
description: Security review and vulnerability assessment
argument-hint: "<path, PR, or 'full' for comprehensive scan> [--scenarios]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:security

Security review with OWASP coverage, secrets detection, and dependency assessment. Use for ad hoc vulnerability scans on code, PRs, or full repos. NOT for compliance evidence collection (use platform:audit) or IaC posture (use platform:infra).

## 1. Dispatch

```
Task(subagent_type="wicked-garden:platform:security-engineer",
     prompt="""Security review.

Scope: $ARGUMENTS  (path | PR number | 'full')
Flags: pass --scenarios through if present (emit wicked-scenarios blocks per CRITICAL/HIGH finding).

Run OWASP Top 10 + secrets + injection + auth + dependency-vuln + misconfig assessment.
Return risk level, findings by severity with file:line, OWASP matrix, prioritized fixes.""")
```
