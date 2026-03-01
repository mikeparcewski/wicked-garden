---
description: Regulatory compliance check (SOC2, HIPAA, GDPR, PCI)
argument-hint: "<framework: soc2|hipaa|gdpr|pci> [path]"
---

# /wicked-garden:platform:compliance

Check code and architecture against regulatory compliance frameworks.

## Instructions

### 1. Parse Framework

Determine which compliance framework to check:
- **SOC2**: Security, availability, processing integrity
- **HIPAA**: Protected health information (PHI)
- **GDPR**: Personal data protection (EU)
- **PCI**: Payment card data security

### 2. Dispatch to Compliance Officer

```python
Task(
    subagent_type="wicked-garden:platform:compliance-officer",
    prompt="""Perform regulatory compliance assessment.

Framework: {selected framework}
Scope: {path or full codebase}

Evaluation Checklist:
1. Data classification - Identify PII, PHI, payment data handling
2. Access control implementation - Authentication and authorization
3. Encryption at rest and in transit - TLS, database encryption
4. Audit logging presence - Who accessed what, when
5. Data retention policies - How long data is kept
6. Consent mechanisms - User consent for data processing (GDPR)

Return Format:
- Compliance status (COMPLIANT/PARTIAL/NON-COMPLIANT)
- Sensitive data inventory with locations
- Control assessment matrix
- Gaps requiring remediation
- Prioritized remediation steps
"""
)
```

### 3. Scan for Sensitive Data

Use wicked-search to identify sensitive data handling:

```bash
# PII patterns
grep -E "(ssn|social.?security|email|phone|address)" --include="*.{js,ts,py}"

# PHI patterns (HIPAA)
grep -E "(patient|diagnosis|treatment|medical)" --include="*.{js,ts,py}"

# Payment data (PCI)
grep -E "(card.?number|cvv|expir)" --include="*.{js,ts,py}"
```

### 4. Check Controls

Verify required controls are present:
- [ ] Authentication mechanism
- [ ] Authorization checks
- [ ] Encryption configuration
- [ ] Audit logging
- [ ] Input validation
- [ ] Error handling (no data leaks)

### 5. Deliver Compliance Report

```markdown
## Compliance Assessment: {Framework}

**Scope**: {what was reviewed}
**Compliance Status**: [COMPLIANT | PARTIAL | NON-COMPLIANT]

### Sensitive Data Inventory
| Type | Location | Protection | Status |
|------|----------|------------|--------|
| {type} | {file:line} | {encryption} | {status} |

### Control Assessment
| Control | Required | Implemented | Evidence |
|---------|----------|-------------|----------|
| Access Control | Yes | {status} | {location} |
| Encryption | Yes | {status} | {location} |
| Audit Logging | Yes | {status} | {location} |

### Gaps
1. {gap description}
2. {gap description}

### Remediation
1. {priority fix}
2. {improvement}
```

## Example

```
User: /wicked-garden:platform:compliance hipaa src/medical/

Claude: I'll assess HIPAA compliance for the medical module.

[Spawns compliance-officer agent]
[Scans for PHI handling]
[Checks required controls]

## HIPAA Compliance Assessment

**Scope**: src/medical/
**Status**: PARTIAL COMPLIANCE

### PHI Inventory
| Data Type | Location | Encrypted | Access Controlled |
|-----------|----------|-----------|-------------------|
| Patient records | records.ts:34 | Yes | Yes |
| Diagnosis codes | diagnosis.ts:12 | No | Yes |

### Control Assessment
| Control | Status | Evidence |
|---------|--------|----------|
| Access Control | PASS | Role-based auth at middleware level |
| Encryption at Rest | PARTIAL | Records encrypted, diagnosis not |
| Audit Logging | FAIL | No audit trail for data access |
| Minimum Necessary | PASS | API returns only required fields |

### Critical Gaps
1. **Missing audit logging** - No record of who accessed PHI
2. **Unencrypted diagnosis codes** - Sensitive data stored in plaintext

### Remediation
1. Implement audit logging for all PHI access
2. Add encryption for diagnosis code storage
3. Add access logs to compliance monitoring
```
