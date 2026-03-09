# Audit Evidence: Collection, Organization & Readiness

Evidence collection scripts, organization structure, gap tracking, and audit readiness checklists.

## Evidence Collection Scripts

### Automated Evidence Gathering

**Collect Code Evidence**:
```bash
#!/bin/bash
# Collect encryption implementations
grep -rn "encrypt\|AES\|cipher" src/ > evidence/encryption_code.txt

# Collect access control
grep -rn "authorize\|authenticate\|require_role" src/ > evidence/access_control.txt

# Collect logging
grep -rn "log\|audit" src/ > evidence/logging.txt
```

**Collect Configuration Evidence**:
```bash
#!/bin/bash
# Gather all configs
find . -name "*.yml" -o -name "*.conf" -o -name "*.json" | \
  grep -v node_modules | \
  tar czf evidence/configurations.tar.gz -T -

# Extract TLS configs
grep -r "TLS\|SSL" config/ > evidence/tls_configs.txt
```

**Collect Log Samples**:
```bash
#!/bin/bash
# Recent access logs
tail -n 1000 /var/log/access.log > evidence/access_log_sample.txt

# Recent audit logs
tail -n 1000 /var/log/audit.log > evidence/audit_log_sample.txt

# Security events
tail -n 1000 /var/log/security.log > evidence/security_log_sample.txt
```

## Evidence Organization

### Directory Structure

```
audit-evidence/
├── design/
│   ├── architecture.pdf
│   ├── network_diagram.pdf
│   └── data_flow.pdf
├── code/
│   ├── authentication/
│   ├── authorization/
│   ├── encryption/
│   └── logging/
├── configs/
│   ├── tls/
│   ├── database/
│   └── application/
├── logs/
│   ├── access/
│   ├── audit/
│   └── security/
├── policies/
│   ├── security_policy.pdf
│   ├── incident_response.pdf
│   └── access_control_policy.pdf
└── reports/
    ├── vulnerability_scans/
    ├── penetration_tests/
    └── compliance_assessments/
```

### Evidence Metadata

For each piece of evidence, document:
```yaml
evidence_id: SOC2-CC6.1-001
control: CC6.1 - Access Control
type: code
file: src/auth/middleware.py
lines: 45-67
description: RBAC enforcement middleware
collected_by: John Doe
collected_date: 2025-01-24
status: verified
notes: Integrates with IAM service, role checks enforced
```

## Gap Tracking

### Gap Register Format

```markdown
| Gap ID | Control | Description | Priority | Status | Target Date | Owner |
|--------|---------|-------------|----------|--------|-------------|-------|
| G001 | CC6.1 | Missing MFA for admins | P0 | In Progress | 2025-02-01 | Security Team |
| G002 | 164.312(b) | Incomplete PHI logging | P0 | Not Started | 2025-02-15 | Dev Team |
| G003 | PCI-10 | Log retention < 1 year | P1 | In Progress | 2025-03-01 | Ops Team |
```

## Audit Readiness Checklist

### Pre-Audit Preparation

- [ ] All evidence collected and organized
- [ ] Gap analysis completed
- [ ] Critical gaps (P0) remediated
- [ ] Control documentation updated
- [ ] Policies and procedures reviewed
- [ ] Team trained on audit process
- [ ] Point of contact identified
- [ ] Audit scope agreed upon
- [ ] Sample period defined
- [ ] Evidence access prepared

### During Audit

- [ ] Respond to auditor requests promptly
- [ ] Provide clear, organized evidence
- [ ] Document all auditor interactions
- [ ] Track outstanding requests
- [ ] Escalate issues quickly
- [ ] Maintain audit log of activities

### Post-Audit

- [ ] Review audit findings
- [ ] Prioritize remediation items
- [ ] Create action plans for gaps
- [ ] Update documentation
- [ ] Implement corrective actions
- [ ] Schedule follow-up audits
- [ ] Update compliance status
