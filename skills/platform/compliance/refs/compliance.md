# Regulatory Compliance Check Rubric

Check code and architecture against regulatory compliance frameworks: SOC2, HIPAA, GDPR, PCI.

## Step 1: Parse Framework and Scope

`$ARGUMENTS` = `<framework> [path]`
- Framework: `soc2` | `hipaa` | `gdpr` | `pci`
- Scope: path to check, or full codebase if omitted

## Step 2: Data Classification

Identify sensitive data handling:
```bash
# PII patterns (GDPR/SOC2)
grep -rn "ssn\|social.?security\|email\|phone\|address\|first.?name\|last.?name" --include="*.py" --include="*.ts" --include="*.js" -l

# PHI patterns (HIPAA)
grep -rn "patient\|diagnosis\|treatment\|medical\|health.?record\|phi" --include="*.py" --include="*.ts" -l

# Payment data (PCI)
grep -rn "card.?number\|cvv\|expir\|pan\b" --include="*.py" --include="*.ts" -l
```

## Step 3: Control Verification Checklist

- [ ] **Authentication** — is authentication required for sensitive data access?
- [ ] **Authorization (RBAC)** — are authorization checks enforced?
- [ ] **Encryption at rest** — is sensitive data encrypted in the database/storage?
- [ ] **Encryption in transit** — is TLS enforced on all endpoints?
- [ ] **Audit logging** — is access to sensitive data logged?
- [ ] **Input validation** — is user input validated before processing?
- [ ] **Error handling** — do errors leak sensitive data?

## Step 4: Framework-Specific Checks

### SOC2 (Trust Service Criteria)
| Control | Focus | Check |
|---------|-------|-------|
| CC6.1 | Logical access controls | Auth + RBAC present |
| CC6.6 | Encryption of confidential data | AES-256 / KMS |
| CC6.7 | Transmission security | TLS 1.2+ on all endpoints |
| CC7.2 | System monitoring | Security event logging |

### HIPAA
| Safeguard | Requirement | Check |
|-----------|-------------|-------|
| 164.308(a)(3) | Workforce security | RBAC, access reviews |
| 164.308(a)(4) | Access management | Auth, session management |
| 164.312(a)(1) | Access controls | Unique user IDs, session timeout |
| 164.312(e)(1) | Transmission security | TLS, encryption in transit |

### GDPR
| Article | Requirement | Check |
|---------|-------------|-------|
| Art 5 | Principles (minimization, accuracy) | Only necessary data collected |
| Art 6 | Lawful basis for processing | Consent or contract documented |
| Art 17 | Right to erasure | User deletion capability |
| Art 32 | Security of processing | Encryption, pseudonymization |

### PCI DSS
| Requirement | Focus | Check |
|-------------|-------|-------|
| Req 3 | Protect stored cardholder data | PAN masked/encrypted |
| Req 4 | Encrypt transmission | TLS for cardholder data |
| Req 8 | Identify and authenticate access | Unique IDs, MFA |
| Req 10 | Track and monitor access | Audit logging |

Full checklists per framework: `refs/checklists.md`
Framework-specific compliance patterns: `refs/frameworks.md`

## Step 5: Bus Events

After the pass/fail decision, emit ONE event:
```bash
# On pass (no P0/P1 gaps, all controls verified):
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_bus_emit.py" wicked.compliance.passed '{"framework":"{soc2|hipaa|gdpr|pci}","checks_passed_count":{N},"chain_id":"{chain_id}"}' 2>/dev/null || true

# On fail (any gap found):
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_bus_emit.py" wicked.compliance.failed '{"framework":"{soc2|hipaa|gdpr|pci}","gap_count":{N},"severity_max":"{critical|high|medium|low}","chain_id":"{chain_id}"}' 2>/dev/null || true
```

## Output Format

```markdown
## Compliance Assessment: {Framework}

**Scope**: {what was reviewed}
**Compliance Status**: [COMPLIANT | PARTIAL | NON-COMPLIANT]
**Confidence**: {HIGH | MEDIUM | LOW}

### Sensitive Data Inventory
| Type | Location | Protection | Status |
|------|----------|------------|--------|
| {type} | {file:line} | {encryption/masking} | {status} |

### Control Assessment
| Control | Required | Status | Evidence |
|---------|----------|--------|----------|
| Access Control | Yes | {PASS/FAIL} | {file:line or "MISSING"} |
| Encryption at rest | Yes | {PASS/FAIL} | {file:line or "MISSING"} |
| Encryption in transit | Yes | {PASS/FAIL} | {config:line or "MISSING"} |
| Audit Logging | Yes | {PASS/FAIL} | {file:line or "MISSING"} |

### Gaps

#### Critical (P0) — Must Fix
1. **{violation}** — {Control} — Location: {file:line}
   Impact: {description}. Remediation: {specific steps}

#### High Priority (P1) — Should Fix
1. **{gap}** — Recommendation: {guidance}

### Remediation Plan
1. **P0**: {action}
2. **P1**: {action}
```
