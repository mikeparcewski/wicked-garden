---
name: wicked-garden-platform-compliance
description: |
  Use when checking code or architecture against a regulatory framework (SOC2, HIPAA, GDPR, PCI) or
  translating a policy document into actionable controls — detects violations and provides
  prioritized remediation guidance. NOT for gathering audit evidence artifacts (use platform/audit).

  Use when: "is this compliant", "compliance check", "regulatory requirements",
  "check against SOC2/HIPAA/GDPR/PCI", or any former
  /wicked-garden:platform:compliance invocation.
# TODO #339: When Claude Code supports 'paths' in skill frontmatter for
# file-context auto-activation, add:
#   paths: ["**/compliance/**", "**/audit/**", "**/policy/**", "**/.hipaa*", "**/.gdpr*"]
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
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

## Run it inline (no dispatch)

Invoked as `<framework> [path]`:

1. Parse args: `<framework> [path]` (framework = `soc2|hipaa|gdpr|pci`).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/compliance/refs/compliance.md")` —
   data-classification scan commands, per-framework control matrix
   (SOC2/HIPAA/GDPR/PCI), gap checklist, bus emit, output format.
3. For detailed per-framework checklists:
   `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/compliance/refs/checklists.md")`.
   For framework-specific patterns: `refs/frameworks.md`.
4. Apply the rubric directly: scan for sensitive data, verify each control,
   classify gaps P0/P1/P2, emit the bus event, and produce the compliance
   assessment report.

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

### With native tasks
```
TaskUpdate(
  taskId="{task_id}",
  description="{previous}\n\n[compliance] {framework}: {status}"
)
```

### With wicked-brain
```bash
Skill(skill="wicked-brain:memory", args="recall \"compliance {framework}\"")
```

### With the platform domain skill
For an ad hoc vulnerability scan of the same target, run the `security`
action of `skills/platform/SKILL.md` (real scanners + triage).

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

## External Integration Discovery

Compliance checking can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **Security scanning** | `snyk`, `semgrep`, `sast` | Vulnerability detection |
| **Secrets** | `vault`, `secrets` | Credential management audit |
| **SBOM** | `trivy`, `sbom`, `cyclonedx` | Supply chain compliance |

Discover available integrations via capability detection. When none are available, fall back to manual analysis against the control checklist above.

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
