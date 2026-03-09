# Audit Framework Control Mappings: SOC2 & HIPAA

Framework-specific control testing and evidence requirements for SOC2 Type II and HIPAA.

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
