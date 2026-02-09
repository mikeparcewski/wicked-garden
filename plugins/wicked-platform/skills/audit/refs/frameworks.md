# Audit Framework Control Mappings

Framework-specific control testing and evidence requirements.

## SOC2 Type II Control Testing

### Common Criteria Controls

**CC6.1 - Logical and Physical Access Controls**:

**What to Test**:
- Authentication mechanisms exist
- Authorization checks are enforced
- Least privilege is implemented
- Access reviews occur periodically

**Evidence to Collect**:
- Authentication code (login handlers, middleware)
- Authorization decorators/middleware
- RBAC configuration files
- Access review logs/reports
- User provisioning/deprovisioning records

**Test Procedures**:
```bash
# Find authentication implementation
grep -r "authenticate\|login\|session" --include="*.py" --include="*.js"

# Find authorization checks
grep -r "authorize\|require_role\|@permission" --include="*.py"

# Check for RBAC configuration
find . -name "roles.yml" -o -name "permissions.json"
```

**CC6.6 - Encryption of Confidential Information**:

**What to Test**:
- Data at rest is encrypted
- Encryption standards are appropriate (AES-256+)
- Key management is secure

**Evidence to Collect**:
- Database encryption configuration
- File system encryption settings
- Encryption library usage in code
- Key management service configuration
- Key rotation logs

**Test Procedures**:
```bash
# Find encryption implementations
grep -r "encrypt\|AES\|cipher" --include="*.py" --include="*.js"

# Check for weak encryption
grep -r "DES\|MD5\|SHA1" --include="*.py" --include="*.js"

# Find key management
grep -r "KMS\|key.management\|rotation" --include="*.yml" --include="*.json"
```

**CC6.7 - Transmission Security**:

**What to Test**:
- TLS 1.2+ is required
- Weak ciphers are disabled
- Certificate validation is enabled

**Evidence to Collect**:
- TLS/SSL configuration files
- Web server configurations (nginx, apache)
- Application TLS settings
- Certificate management procedures

**Test Procedures**:
```bash
# Check TLS configuration
grep -r "TLS\|SSL" --include="*.conf" --include="*.yml"

# Find weak cipher usage
grep -r "SSLv2\|SSLv3\|TLSv1\." --include="*.conf"
```

**CC7.2 - System Monitoring**:

**What to Test**:
- Security events are logged
- Logs are monitored and reviewed
- Alerting is configured
- Log retention meets requirements

**Evidence to Collect**:
- Logging configuration
- Log aggregation setup (Splunk, ELK, etc.)
- Monitoring dashboards
- Alert configurations
- Log review procedures
- Log retention policies

**Test Procedures**:
```bash
# Find logging implementations
grep -r "log\|logger\|audit" --include="*.py" --include="*.js"

# Check for sensitive data in logs
grep -r "password\|secret\|key.*log" --include="*.py"

# Find monitoring configuration
find . -name "prometheus.yml" -o -name "alertmanager.yml"
```

## HIPAA Control Testing

### Administrative Safeguards (§164.308)

**164.308(a)(4) - Information Access Management**:

**What to Test**:
- Access authorization procedures
- Access modification procedures
- Termination procedures

**Evidence to Collect**:
- IAM policies and roles
- Access request/approval workflows
- User onboarding/offboarding checklists
- Access logs showing authorization changes

**Test Procedures**:
```bash
# Find IAM configurations
find . -name "iam_policy.json" -o -name "rbac.yml"

# Check access control implementation
grep -r "access.control\|authorization" --include="*.py"
```

### Technical Safeguards (§164.312)

**164.312(a) - Access Control**:

**What to Test**:
- Unique user identification
- Emergency access procedures
- Automatic logoff (addressable)
- Encryption (addressable)

**Evidence to Collect**:
- User ID assignment code
- Session management code
- Timeout configurations
- Emergency access procedures documentation

**Test Procedures**:
```bash
# Find session management
grep -r "session\|timeout\|expire" --include="*.py" --include="*.js"

# Check user identification
grep -r "user_id\|unique.identifier" --include="*.py"
```

**164.312(b) - Audit Controls**:

**What to Test**:
- PHI access is logged
- Audit logs are protected
- Logs are regularly reviewed

**Evidence to Collect**:
- Audit logging code
- Log protection mechanisms
- Log review procedures
- Access to PHI tracking

**Test Procedures**:
```bash
# Find PHI access logging
grep -r "audit.*phi\|log.*health" --include="*.py"

# Check log integrity controls
grep -r "log.integrity\|tamper.proof" --include="*.py"
```

**164.312(c) - Integrity Controls**:

**What to Test**:
- Mechanisms to ensure data not altered
- Data authentication

**Evidence to Collect**:
- Data integrity checks (checksums, hashes)
- Digital signature implementations
- Version control for data changes

**Test Procedures**:
```bash
# Find integrity mechanisms
grep -r "checksum\|hash\|integrity" --include="*.py"

# Check for digital signatures
grep -r "signature\|sign.*data" --include="*.py"
```

**164.312(d) - Person/Entity Authentication**:

**What to Test**:
- Identity verification before access

**Evidence to Collect**:
- Authentication code
- Identity verification procedures
- Multi-factor authentication implementation

**164.312(e) - Transmission Security**:

**What to Test**:
- Integrity controls (addressable)
- Encryption (addressable)

**Evidence to Collect**:
- TLS/SSL configurations
- VPN configurations
- Transmission encryption code

## GDPR Control Testing

### Article 30 - Records of Processing Activities

**What to Test**:
- Processing activities are documented
- Data categories are identified
- Purposes are documented
- Recipients are identified
- Retention periods are defined

**Evidence to Collect**:
- Data processing inventory
- Data flow diagrams
- Privacy notices
- Data retention policies

**Test Procedures**:
- Review data processing documentation
- Verify data flow diagrams are current
- Check privacy notices match actual processing

### Article 32 - Security of Processing

**What to Test**:
- Pseudonymization and encryption
- Confidentiality, integrity, availability
- Resilience of systems
- Regular testing and evaluation

**Evidence to Collect**:
- Encryption implementations
- Backup and recovery procedures
- Security testing reports
- Penetration test results
- Disaster recovery test results

**Test Procedures**:
```bash
# Find pseudonymization/anonymization
grep -r "pseudonym\|anonymize\|mask" --include="*.py"

# Check backup procedures
find . -name "backup.sh" -o -name "disaster_recovery.md"
```

### Article 35 - Data Protection Impact Assessment

**What to Test** (if high-risk processing):
- DPIA was conducted
- Risks were identified and mitigated
- DPO was consulted (if applicable)

**Evidence to Collect**:
- DPIA documents
- Risk assessment results
- Mitigation measures implemented
- DPO consultation records

## PCI DSS Control Testing

### Requirement 3 - Protect Stored Cardholder Data

**What to Test**:
- Data retention is minimized
- Sensitive auth data is not stored
- PAN is masked when displayed
- PAN is unreadable when stored

**Evidence to Collect**:
- Data retention policy
- Data disposal procedures
- PAN masking code
- Encryption implementations
- Data storage configurations

**Test Procedures**:
```bash
# Check for stored auth data violations
grep -r "cvv\|cvc\|track.data\|pin" --include="*.py" --include="*.sql"

# Find PAN masking
grep -r "mask\|pan.*display" --include="*.py" --include="*.js"

# Check encryption
grep -r "encrypt.*pan\|aes.*card" --include="*.py"
```

### Requirement 4 - Encrypt Transmission

**What to Test**:
- Strong cryptography for transmission
- No unencrypted PAN transmission
- Trusted keys and certificates

**Evidence to Collect**:
- TLS configurations (1.2+ required)
- Certificate inventory
- Key management procedures

**Test Procedures**:
```bash
# Check TLS version requirements
grep -r "TLS.*1\.[23]" --include="*.conf" --include="*.yml"

# Find any unencrypted transmission
grep -r "http://.*card\|unencrypted.*pan" --include="*.py"
```

### Requirement 8 - Identify and Authenticate Access

**What to Test**:
- Unique IDs for each user
- Two-factor authentication
- Strong passwords
- Account lockout

**Evidence to Collect**:
- User provisioning procedures
- MFA implementation
- Password policy configuration
- Account lockout settings

**Test Procedures**:
```bash
# Find authentication code
grep -r "two.factor\|mfa\|2fa" --include="*.py"

# Check password policy
grep -r "password.*policy\|min.*length" --include="*.py" --include="*.yml"

# Find lockout mechanism
grep -r "lockout\|failed.*attempt" --include="*.py"
```

### Requirement 10 - Log and Monitor

**What to Test**:
- All access to cardholder data is logged
- Admin actions are logged
- Logs are secure
- Logs are reviewed daily
- Logs retained for 1 year (3 months immediate)

**Evidence to Collect**:
- Logging implementations
- Log review procedures
- Log retention configuration
- Log security controls

**Test Procedures**:
```bash
# Find cardholder data access logging
grep -r "log.*card\|audit.*payment" --include="*.py"

# Check log retention
grep -r "retention\|rotate.*log" --include="*.yml" --include="*.conf"

# Find admin logging
grep -r "log.*admin\|privileged.*log" --include="*.py"
```

### Requirement 11 - Test Security Systems

**What to Test**:
- Vulnerability scans quarterly
- Penetration testing annually
- IDS/IPS deployed
- File integrity monitoring

**Evidence to Collect**:
- Vulnerability scan reports
- Penetration test reports
- IDS/IPS configurations
- FIM configurations and logs

**Test Procedures**:
- Review scan and test schedules
- Verify remediation of findings
- Check IDS/IPS is monitoring CDE
- Verify FIM is monitoring critical files

## Evidence Documentation Standards

### Code Evidence Format

For each control, document:
```markdown
**Control**: CC6.1 - Access Control
**File**: src/auth/middleware.py
**Lines**: 45-67
**Description**: RBAC middleware enforcing role-based access
**Status**: IMPLEMENTED
**Notes**: Uses decorator pattern, integrates with IAM service
```

### Configuration Evidence Format

```markdown
**Control**: CC6.7 - TLS Configuration
**File**: config/nginx.conf
**Lines**: 23-35
**Description**: TLS 1.2+ only, strong ciphers
**Status**: COMPLIANT
**Notes**: Weak ciphers disabled, HSTS enabled
```

### Gap Documentation Format

```markdown
**Control**: 164.312(b) - Audit Controls
**Gap**: PHI access not fully logged
**Priority**: P0
**Evidence**: src/patient/views.py:89 - No audit log
**Remediation**: Add audit logging decorator to PHI endpoints
**Effort**: 2 days
```
