# Audit Evidence Checklists

Comprehensive checklists for collecting audit evidence by framework.

## SOC2 Type II Audit Evidence

### Design Evidence

- [ ] System architecture diagrams
- [ ] Network diagrams
- [ ] Data flow diagrams
- [ ] Security policies and procedures
- [ ] Incident response plan
- [ ] Business continuity plan
- [ ] Disaster recovery plan
- [ ] Change management procedures
- [ ] Vendor management policy
- [ ] Access control policy

### Implementation Evidence

- [ ] Authentication code and configuration
- [ ] Authorization/RBAC implementation
- [ ] Encryption at rest implementation
- [ ] Encryption in transit configuration
- [ ] Logging and monitoring setup
- [ ] Backup and recovery scripts
- [ ] Security configurations (firewalls, IDS/IPS)
- [ ] Key management implementation
- [ ] Session management code
- [ ] Input validation code

### Operational Evidence

- [ ] Access logs (90+ days)
- [ ] Audit logs (90+ days)
- [ ] Security event logs
- [ ] Change logs
- [ ] Incident reports
- [ ] Access review reports
- [ ] Vulnerability scan reports
- [ ] Penetration test results
- [ ] Training completion records
- [ ] Vendor assessment reports

### Process Evidence

- [ ] Access request/approval records
- [ ] User onboarding checklists
- [ ] User offboarding checklists
- [ ] Incident response procedures
- [ ] Evidence of log review
- [ ] Evidence of access reviews
- [ ] Security awareness training materials
- [ ] Background check procedures

## HIPAA Audit Evidence

### Administrative Safeguards Evidence

- [ ] Security management process documentation
- [ ] Risk analysis (annual)
- [ ] Risk management plan
- [ ] Sanction policy
- [ ] Information system activity review procedures
- [ ] Security training materials
- [ ] Security awareness program
- [ ] Contingency plan
- [ ] Business associate agreements (BAA)
- [ ] Workforce clearance procedures
- [ ] Termination procedures

### Physical Safeguards Evidence

- [ ] Facility access control procedures
- [ ] Visitor logs
- [ ] Workstation use policy
- [ ] Workstation security procedures
- [ ] Device inventory
- [ ] Media disposal procedures
- [ ] Media re-use procedures
- [ ] Backup procedures
- [ ] Physical access logs

### Technical Safeguards Evidence

- [ ] Unique user ID assignment process
- [ ] Authentication implementation
- [ ] Emergency access procedures
- [ ] Session timeout configuration
- [ ] Encryption implementation (if used)
- [ ] Audit controls implementation
- [ ] PHI access logging
- [ ] Integrity control mechanisms
- [ ] Person/entity authentication
- [ ] Transmission security (TLS configs)

### PHI Protection Evidence

- [ ] PHI inventory
- [ ] Minimum necessary analysis
- [ ] Data classification scheme
- [ ] PHI handling procedures
- [ ] De-identification procedures (if applicable)
- [ ] PHI disposal/destruction logs
- [ ] Breach notification procedures
- [ ] Breach log/register

### Documentation Evidence

- [ ] HIPAA policies and procedures manual
- [ ] Privacy notices
- [ ] Authorization forms
- [ ] Patient rights materials
- [ ] Privacy officer designation
- [ ] Security officer designation

## GDPR Audit Evidence

### Lawfulness of Processing Evidence

- [ ] Legal basis documentation for each processing activity
- [ ] Consent forms (if consent-based)
- [ ] Consent withdrawal mechanism
- [ ] Records of processing activities (Article 30)
- [ ] Legitimate interest assessments (if applicable)
- [ ] Contracts with data processors
- [ ] Privacy notices
- [ ] Cookie consent mechanism (if applicable)

### Data Subject Rights Evidence

- [ ] Data access request procedures
- [ ] Data portability export capability
- [ ] Data rectification procedures
- [ ] Data erasure procedures
- [ ] Processing restriction procedures
- [ ] Objection handling procedures
- [ ] Automated decision-making disclosures
- [ ] Response time tracking (30-day compliance)

### Data Protection Principles Evidence

- [ ] Data minimization analysis
- [ ] Purpose limitation documentation
- [ ] Data accuracy procedures
- [ ] Storage limitation/retention policies
- [ ] Security measures (Article 32)
- [ ] Accountability documentation
- [ ] Privacy by design assessments
- [ ] Privacy by default configurations

### Security Measures Evidence

- [ ] Pseudonymization/encryption implementations
- [ ] Access control mechanisms
- [ ] Backup and recovery procedures
- [ ] Security testing reports
- [ ] Vulnerability assessments
- [ ] Penetration test results
- [ ] Disaster recovery tests
- [ ] Security incident log

### International Transfers Evidence

- [ ] Adequacy decision documentation
- [ ] Standard contractual clauses (SCC)
- [ ] Binding corporate rules (BCR) if applicable
- [ ] Transfer impact assessments (TIA)
- [ ] Supplementary measures for transfers

### Organizational Evidence

- [ ] DPO appointment (if required)
- [ ] DPO contact information publication
- [ ] Data protection impact assessments (DPIA) for high-risk processing
- [ ] Processor agreements (Article 28)
- [ ] Joint controller agreements (if applicable)
- [ ] Training records

### Breach Response Evidence

- [ ] Breach detection procedures
- [ ] Breach notification procedures (<72 hours)
- [ ] Breach register/log
- [ ] Supervisory authority notifications
- [ ] Individual notifications (if high risk)
- [ ] Breach impact assessments

## PCI DSS Audit Evidence

### Requirement 1 - Firewall Configuration

- [ ] Firewall configuration standards
- [ ] Current firewall rulesets
- [ ] Firewall rule review logs (semi-annual)
- [ ] Network diagram showing CDE boundaries
- [ ] DMZ configuration
- [ ] Wireless access point configurations
- [ ] Quarterly wireless scans

### Requirement 2 - Configuration Management

- [ ] Configuration standards documentation
- [ ] Hardening guides
- [ ] Baseline configurations
- [ ] System inventory
- [ ] Evidence of vendor default changes
- [ ] Unnecessary services disabled
- [ ] Configuration change logs

### Requirement 3 - Data Protection

- [ ] Data retention and disposal policy
- [ ] Data flow diagram
- [ ] Evidence sensitive auth data not stored
- [ ] PAN masking implementation
- [ ] Encryption implementation
- [ ] Key management procedures
- [ ] Cryptographic key inventory
- [ ] Key custodian assignments
- [ ] Key rotation logs

### Requirement 4 - Transmission Encryption

- [ ] Encryption policy for PAN transmission
- [ ] TLS configuration (1.2+ minimum)
- [ ] Certificate inventory
- [ ] Trusted key and certificate management
- [ ] End-user messaging security (no unencrypted PAN)

### Requirement 5 - Anti-Malware

- [ ] Anti-virus software deployment
- [ ] AV definition update logs
- [ ] AV scan logs
- [ ] AV policy and procedures

### Requirement 6 - Secure Systems

- [ ] Patch management procedures
- [ ] Critical patch deployment records (<30 days)
- [ ] Secure coding guidelines
- [ ] Code review procedures
- [ ] Vulnerability management process
- [ ] Change control procedures
- [ ] Development/test/production separation
- [ ] Test data procedures (no live PAN)

### Requirement 7 - Access Restriction

- [ ] Access control policy
- [ ] Need-to-know documentation
- [ ] Access rights based on job function
- [ ] Default deny-all configuration
- [ ] Access authorization records
- [ ] Privilege assignment documentation

### Requirement 8 - Authentication

- [ ] User identification procedures
- [ ] Unique user ID assignment
- [ ] Two-factor authentication implementation (remote + admin)
- [ ] Password policy (7+ chars, complexity)
- [ ] Account lockout configuration (6 attempts)
- [ ] Session timeout (15 min idle)
- [ ] Password history (4 different)
- [ ] Password change every 90 days
- [ ] Shared account prohibition
- [ ] User account review (quarterly)

### Requirement 9 - Physical Access

- [ ] Facility access controls
- [ ] Visitor authorization and logging
- [ ] Badge system
- [ ] Escort procedures for visitors
- [ ] Media storage controls
- [ ] Secure media destruction procedures
- [ ] Media tracking logs
- [ ] Device inventory

### Requirement 10 - Logging and Monitoring

- [ ] Audit log policy
- [ ] Log configuration (what to log)
- [ ] Cardholder data access logs
- [ ] Admin action logs
- [ ] Log integrity protection
- [ ] Daily log review procedures
- [ ] Log review evidence
- [ ] Log retention configuration (1 year, 3 months online)
- [ ] Time synchronization (NTP)

### Requirement 11 - Security Testing

- [ ] Quarterly external vulnerability scans (ASV)
- [ ] Quarterly internal vulnerability scans
- [ ] Scan remediation tracking
- [ ] Annual penetration testing
- [ ] Penetration test results and remediation
- [ ] IDS/IPS deployment and configuration
- [ ] IDS/IPS alert review logs
- [ ] File integrity monitoring (FIM) configuration
- [ ] FIM alerts and review
- [ ] Change detection procedures

### Requirement 12 - Security Policy

- [ ] Information security policy
- [ ] Policy annual review
- [ ] Risk assessment (annual)
- [ ] Acceptable use policies
- [ ] User acknowledgment of policies
- [ ] Security awareness program materials
- [ ] Training completion records
- [ ] Personnel screening procedures
- [ ] Incident response plan
- [ ] Incident response testing
- [ ] Service provider management procedures
- [ ] Service provider list
- [ ] Service provider assessments

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
