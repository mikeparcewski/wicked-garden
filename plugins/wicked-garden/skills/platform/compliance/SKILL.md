---
name: compliance
description: |
  Compliance analysis for regulatory frameworks (SOC2, HIPAA, GDPR, PCI).
  Checks code and architecture against compliance requirements, detects
  violations, and provides remediation guidance.

  Use when: "compliance check", "SOC2", "HIPAA", "GDPR", "PCI",
  "regulatory requirements", "audit", "is this compliant"
---

# Compliance Skill

Analyze code and systems for regulatory compliance.

## When to Use

- Code handles sensitive data (PII, PHI, payment data)
- Pre-deployment compliance verification
- User mentions regulatory frameworks
- User says "is this compliant", "compliance check", "regulatory requirements"

## Supported Frameworks

| Framework | Focus | Key Requirements |
|-----------|-------|------------------|
| **SOC2** | Security, Availability | Access controls, encryption, logging, monitoring |
| **HIPAA** | Protected Health Info | PHI safeguards, access logs, encryption, BAA |
| **GDPR** | Personal Data | Consent, minimization, deletion, DPO |
| **PCI DSS** | Payment Card Data | Encryption, network segmentation, access control |

See [refs/frameworks.md](refs/frameworks.md) for detailed framework requirements.

## Commands

```bash
/wicked-garden:platform-check [--framework soc2|hipaa|gdpr|pci] [--quick]
```

## Analysis Process

### 1. Identify Sensitive Data

Scan for:
- **PII**: Names, emails, SSN, addresses
- **PHI**: Medical records, health data
- **Payment**: Credit cards, bank accounts
- **Credentials**: Passwords, API keys

### 2. Verify Controls

**Access Control**:
- Authentication required
- Authorization checks (RBAC)
- Least privilege

**Data Protection**:
- Encryption at rest (AES-256)
- Encryption in transit (TLS 1.2+)
- Secure key management

**Logging & Monitoring**:
- Access logs
- Audit trails
- Security events
- Log retention

**Data Lifecycle**:
- Consent mechanisms (GDPR)
- Retention policies
- Secure deletion
- Data minimization

### 3. Detect Violations

Common issues:
- PII/PHI in logs or errors
- Hardcoded secrets
- Missing encryption
- Insufficient access controls
- Missing audit trails

See [refs/checklists.md](refs/checklists.md) for detailed verification checklists.

### 4. Generate Report

Output:
- **Status**: COMPLIANT / NEEDS ATTENTION / NON-COMPLIANT
- **Findings**: Violations by priority (P0, P1, P2)
- **Evidence**: Code references
- **Remediation**: Required fixes

## Integration

### With wicked-crew
Auto-triggered at phase gates

### With wicked-kanban
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-kanban/scripts/kanban.py" add-comment \
  "Compliance Check" "{task_id}" "[compliance] {framework}: {status}"
```

### With wicked-mem
```bash
/wicked-garden:mem-recall "compliance {framework}"
```

### With wicked-product
```bash
/wicked-garden:platform-security {target}
```

## Output Format

```markdown
## Compliance Analysis: {Framework}

**Target**: {scope}
**Status**: {COMPLIANT|NEEDS ATTENTION|NON-COMPLIANT}
**Framework**: {SOC2|HIPAA|GDPR|PCI}

### Critical (P0)
- {violation} - {file}:{line}
  Remediation: {fix}

### High Priority (P1)
- {gap} - {file}:{line}
  Recommendation: {guidance}

### Medium Priority (P2)
- {improvement} - {suggestion}

### Controls Verified
- [x] Encryption at rest
- [ ] Data retention policy

### Next Steps
{Recommended actions}
```

## Automation Script

Use compliance checker:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compliance_checker.py" \
  --target {path} \
  --framework {soc2|hipaa|gdpr|pci}
```

## External Integration Discovery

Compliance checking can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **Security scanning** | `snyk`, `semgrep`, `sast` | Vulnerability detection |
| **Secrets** | `vault`, `secrets` | Credential management audit |
| **SBOM** | `trivy`, `sbom`, `cyclonedx` | Supply chain compliance |

Run `ListMcpResourcesTool` to discover available integrations. Fall back to local compliance_checker.py when none available.

## Quality Standards

Good analysis:
- Specific code references
- Clear violation descriptions
- Actionable remediation
- Prioritized by risk

Bad analysis:
- Generic checklists
- No code evidence
- Vague recommendations
