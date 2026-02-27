# Compliance Checklists

Detailed verification checklists for each framework.

## SOC2 Compliance Checklist

### Access Controls (CC6.1)

- [ ] User authentication implemented
- [ ] Multi-factor authentication for privileged access
- [ ] Role-based access control (RBAC) defined
- [ ] Least privilege principle enforced
- [ ] Regular access reviews scheduled
- [ ] Terminated user access removed within 24 hours
- [ ] Shared accounts prohibited
- [ ] Session timeout configured

### Encryption (CC6.6, CC6.7)

- [ ] Data at rest encrypted (AES-256 or equivalent)
- [ ] TLS 1.2+ for data in transit
- [ ] Encryption key management documented
- [ ] Key rotation schedule defined
- [ ] Weak ciphers disabled
- [ ] Certificate validation enabled
- [ ] API authentication secured

### Monitoring (CC7.2)

- [ ] Security event logging enabled
- [ ] Log aggregation configured
- [ ] Monitoring alerts configured
- [ ] Anomaly detection implemented
- [ ] Log retention policy (90+ days)
- [ ] Log integrity protected
- [ ] Regular log review process

### System Operations

- [ ] Change management process
- [ ] Backup and recovery tested
- [ ] Incident response plan
- [ ] Business continuity plan
- [ ] Vendor management process

## HIPAA Compliance Checklist

### Administrative Safeguards

- [ ] Security management process documented
- [ ] Risk analysis conducted annually
- [ ] Risk management strategy implemented
- [ ] Sanction policy for violations
- [ ] Information system activity review
- [ ] Security training for workforce
- [ ] Contingency plan tested
- [ ] Business associate agreements (BAA) executed

### Physical Safeguards

- [ ] Facility access controls
- [ ] Workstation use policy
- [ ] Workstation security implemented
- [ ] Device and media controls
- [ ] Disposal procedures for ePHI
- [ ] Media re-use procedures
- [ ] Data backup procedures

### Technical Safeguards

- [ ] Unique user identification
- [ ] Emergency access procedures
- [ ] Automatic logoff configured
- [ ] Encryption implemented (addressable)
- [ ] Audit controls logging access to ePHI
- [ ] Integrity controls for ePHI
- [ ] Person/entity authentication
- [ ] Transmission security (encryption)

### PHI Protection

- [ ] PHI identified and inventoried
- [ ] Minimum necessary standard applied
- [ ] PHI not in logs or error messages
- [ ] Screen display protections
- [ ] Secure PHI deletion process
- [ ] De-identification procedures (if applicable)

### Breach Notification

- [ ] Breach detection procedures
- [ ] Breach assessment process
- [ ] Notification procedures (<60 days)
- [ ] Breach log maintained

## GDPR Compliance Checklist

### Lawful Basis

- [ ] Legal basis identified for each processing activity
- [ ] Consent mechanism implemented (if consent-based)
- [ ] Consent is freely given, specific, informed
- [ ] Easy consent withdrawal mechanism
- [ ] Records of processing activities (Article 30)

### Data Subject Rights

- [ ] Right to access - data export capability
- [ ] Right to rectification - data correction process
- [ ] Right to erasure - data deletion capability
- [ ] Right to restriction - processing limitation
- [ ] Right to data portability - machine-readable export
- [ ] Right to object - opt-out mechanism
- [ ] Respond within 30 days of request

### Data Protection Principles

- [ ] Data minimization enforced
- [ ] Purpose limitation documented
- [ ] Accuracy maintenance procedures
- [ ] Storage limitation (retention policies)
- [ ] Integrity and confidentiality (security measures)
- [ ] Accountability (documentation and evidence)

### Security Measures (Article 32)

- [ ] Pseudonymization and encryption
- [ ] Ongoing confidentiality measures
- [ ] Availability and resilience
- [ ] Restore capability after incident
- [ ] Regular testing and evaluation
- [ ] Data protection impact assessment (DPIA) when required

### International Transfers

- [ ] Adequacy decision confirmed (if applicable)
- [ ] Standard contractual clauses (SCC) implemented
- [ ] Binding corporate rules (BCR) if applicable
- [ ] Transfer impact assessment conducted

### Organizational Requirements

- [ ] Data Protection Officer (DPO) appointed if required
- [ ] Privacy notice published and accessible
- [ ] Privacy by design implemented
- [ ] Privacy by default configured
- [ ] Vendor (processor) agreements executed

### Breach Response

- [ ] Breach detection capability
- [ ] 72-hour notification process to supervisory authority
- [ ] Individual notification process for high-risk breaches
- [ ] Breach documentation and logs

## PCI DSS Compliance Checklist

### Network Security

- [ ] Firewall configuration standards documented
- [ ] Firewall rules reviewed semi-annually
- [ ] Direct public access to CDE prohibited
- [ ] Network segmentation implemented
- [ ] Wireless security (WPA2+, unique keys)
- [ ] Quarterly wireless scans

### Cardholder Data Protection

- [ ] Data retention policy defined and enforced
- [ ] Sensitive auth data not stored post-authorization
- [ ] PAN masked when displayed (show max first 6 + last 4)
- [ ] PAN rendered unreadable everywhere stored
- [ ] Encryption key management procedures
- [ ] Key custodian roles defined
- [ ] Key rotation schedule

### Transmission Security

- [ ] Strong cryptography (TLS 1.2+ minimum)
- [ ] No unencrypted PANs via email, IM, SMS
- [ ] Certificate validation
- [ ] Trusted keys and certificates only

### Access Control

- [ ] Need-to-know access restrictions
- [ ] Access based on job classification
- [ ] Default deny-all policy
- [ ] Unique user IDs assigned
- [ ] Two-factor authentication for remote access
- [ ] Two-factor for admin access to CDE
- [ ] Strong password policy (7+ chars, complex)
- [ ] Account lockout after 6 failed attempts
- [ ] Session timeout (15 min idle max)
- [ ] Physical access controls to CDE

### Monitoring and Testing

- [ ] All access to cardholder data logged
- [ ] Admin actions logged
- [ ] Logs secured and integrity protected
- [ ] Logs reviewed daily
- [ ] Log retention (1 year, 3 months immediately available)
- [ ] Quarterly vulnerability scans (ASV if external)
- [ ] Quarterly internal vulnerability scans
- [ ] Annual penetration testing
- [ ] Intrusion detection/prevention deployed
- [ ] File integrity monitoring on CDE

### Secure Development

- [ ] Vendor-supplied defaults changed
- [ ] Unnecessary services disabled
- [ ] Security patches applied within 1 month of release
- [ ] Secure coding guidelines followed
- [ ] Development/test separate from production
- [ ] Test data doesn't contain live PAN
- [ ] Custom code reviewed for vulnerabilities
- [ ] Change control process implemented

### Policy and Procedures

- [ ] Information security policy established
- [ ] Policy reviewed annually
- [ ] Risk assessment conducted annually
- [ ] Security awareness program implemented
- [ ] Personnel screening procedures
- [ ] Acceptable use policies distributed
- [ ] Incident response plan tested
- [ ] Service provider (vendor) management

## Quick Violation Detection

### Common Anti-Patterns

**PII/PHI in Logs**:
```python
# BAD - logs sensitive data
logger.info(f"Processing SSN: {user.ssn}")

# GOOD - redacted logging
logger.info(f"Processing record: {user.id}")
```

**Hardcoded Secrets**:
```python
# BAD - hardcoded credentials
api_key = "sk_live_123456789"

# GOOD - environment variables
api_key = os.environ.get("API_KEY")
```

**Missing Encryption**:
```python
# BAD - plaintext storage
db.save({"ssn": user_ssn})

# GOOD - encrypted storage
encrypted_ssn = encrypt(user_ssn, kms_key)
db.save({"ssn": encrypted_ssn})
```

**Weak Access Control**:
```python
# BAD - no authorization
def view_records():
    return all_records

# GOOD - RBAC enforced
@require_role("admin")
def view_records():
    return all_records
```

### Scanning Patterns

Search for potential violations:

```bash
# Find potential PII in logs
grep -r "ssn\|social.security\|credit.card\|password" --include="*.log"

# Find hardcoded secrets
grep -r "api[_-]key.*=.*['\"]" --include="*.py" --include="*.js"

# Check for weak encryption
grep -r "DES\|MD5\|SHA1" --include="*.py" --include="*.js"

# Verify TLS version
grep -r "TLSv1\|SSLv" --include="*.conf" --include="*.yaml"
```

## Evidence Collection

### Code Evidence

- Encryption implementations
- Access control decorators/middleware
- Audit logging statements
- Input validation functions
- Error handling (no PII leakage)

### Configuration Evidence

- TLS/SSL settings
- Database encryption settings
- Key management configuration
- Network security rules
- IAM policies

### Documentation Evidence

- Architecture diagrams
- Data flow diagrams
- Security policies
- Incident response plans
- Privacy notices

### Operational Evidence

- Access logs
- Audit logs
- Security monitoring dashboards
- Incident reports
- Training records
