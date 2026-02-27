# Policy Implementation Checklists

Detailed implementation guidance and gap analysis checklists.

## GDPR Implementation Checklist

### Lawfulness of Processing

- [ ] Identify legal basis for each processing activity
- [ ] Document legal basis in privacy notice
- [ ] Implement consent collection (if consent-based)
- [ ] Create consent withdrawal mechanism
- [ ] Maintain records of processing activities (Article 30)

**Implementation Tasks**:
```python
# 1. Create legal basis enum
LEGAL_BASIS = [
    'consent',
    'contract',
    'legal_obligation',
    'vital_interest',
    'public_task',
    'legitimate_interest'
]

# 2. Add legal_basis to data models
class DataProcessing:
    legal_basis: str  # from LEGAL_BASIS
    purpose: str
    data_categories: List[str]

# 3. Validate before processing
def process_data(data, purpose, legal_basis):
    if not validate_legal_basis(legal_basis):
        raise ValueError("Invalid legal basis")
    # proceed with processing
```

### Data Subject Rights Implementation

**Right to Access**:
- [ ] Implement data export functionality
- [ ] Format as machine-readable (JSON/CSV)
- [ ] Include all data about the subject
- [ ] Respond within 30 days

**Implementation**:
```python
def export_user_data(user_id):
    data = collect_all_user_data(user_id)
    return json.dumps(data, indent=2)
```

**Right to Rectification**:
- [ ] Implement data update functionality
- [ ] Validate corrected data
- [ ] Notify third parties if data shared

**Right to Erasure**:
- [ ] Implement deletion functionality
- [ ] Cascade deletion across systems
- [ ] Handle exceptions (legal obligations, etc.)
- [ ] Document deletion in audit log

**Implementation**:
```python
def delete_user_data(user_id):
    # Check for legal holds
    if has_legal_hold(user_id):
        raise Exception("Cannot delete: legal obligation")

    # Delete everywhere
    database.users.delete(user_id)
    cache.delete(user_id)
    analytics.anonymize(user_id)
    audit_log.record('user_deleted', user_id)
```

**Right to Data Portability**:
- [ ] Export in structured format
- [ ] Include all provided data
- [ ] Make machine-readable
- [ ] Allow direct transfer if possible

**Right to Object**:
- [ ] Implement opt-out mechanisms
- [ ] Stop processing upon objection
- [ ] Inform about right to object

### Privacy by Design

- [ ] Minimize data collection
- [ ] Pseudonymize where possible
- [ ] Encrypt sensitive data
- [ ] Implement access controls
- [ ] Set privacy-friendly defaults

**Implementation Checklist**:
```markdown
For each new feature:
- [ ] What personal data is needed? (minimize)
- [ ] What's the legal basis?
- [ ] How long to retain?
- [ ] Who needs access? (least privilege)
- [ ] Is encryption needed?
- [ ] Are privacy-friendly defaults set?
```

### Data Protection Impact Assessment (DPIA)

Required when processing likely results in high risk. Conduct DPIA when:
- [ ] Systematic monitoring at large scale
- [ ] Processing special categories of data at scale
- [ ] Systematic evaluation/scoring
- [ ] Automated decision-making with legal effects
- [ ] Large scale processing of sensitive data

**DPIA Template**:
```markdown
1. Description of processing
2. Necessity and proportionality
3. Risks to individuals
4. Measures to address risks
5. Consultation with DPO
6. Supervisory authority consultation (if high residual risk)
```

### Breach Notification

- [ ] Implement breach detection
- [ ] Create 72-hour notification process
- [ ] Document breach register
- [ ] Define high-risk criteria for individual notification

**Breach Response Checklist**:
```markdown
Within 72 hours of awareness:
- [ ] Assess scope and severity
- [ ] Contain the breach
- [ ] Notify supervisory authority (if required)
- [ ] Document in breach register
- [ ] Notify individuals (if high risk)
- [ ] Implement remediation
```

## HIPAA Implementation Checklist

### Administrative Safeguards

**Security Management Process**:
- [ ] Conduct annual risk analysis
- [ ] Document identified risks
- [ ] Implement risk mitigation measures
- [ ] Create sanction policy
- [ ] Implement information system activity review

**Workforce Security**:
- [ ] Authorization/supervision procedures
- [ ] Workforce clearance procedure
- [ ] Termination procedures (access removal within 24h)

**Information Access Management**:
- [ ] Isolating healthcare clearinghouse functions (if applicable)
- [ ] Access authorization procedures
- [ ] Access establishment and modification procedures

**Security Awareness Training**:
- [ ] Training program for all workforce members
- [ ] Protection from malicious software
- [ ] Log-in monitoring
- [ ] Password management

**Contingency Plan**:
- [ ] Data backup plan
- [ ] Disaster recovery plan
- [ ] Emergency mode operation plan
- [ ] Testing and revision procedures

### Technical Safeguards

**Access Control** (§164.312(a)):
- [ ] Unique user identification (required)
- [ ] Emergency access procedure (required)
- [ ] Automatic logoff (addressable)
- [ ] Encryption and decryption (addressable)

**Implementation**:
```python
# Unique user ID
user = User(
    user_id=uuid.uuid4(),
    username='jdoe',
    email='jdoe@example.com'
)

# Session timeout
SESSION_TIMEOUT = 900  # 15 minutes

# Emergency access
class EmergencyAccess:
    def grant_access(self, user_id, justification):
        audit_log.record({
            'action': 'emergency_access',
            'user_id': user_id,
            'justification': justification,
            'timestamp': datetime.now()
        })
        return temporary_access_token(user_id, duration=3600)
```

**Audit Controls** (§164.312(b)):
- [ ] Implement mechanisms to record/examine activity
- [ ] Log all PHI access
- [ ] Protect audit logs from tampering
- [ ] Regularly review logs

**Implementation**:
```python
@audit_phi_access
def view_patient_record(patient_id):
    return database.get_patient(patient_id)

def audit_phi_access(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        log_access('phi', func.__name__, args, kwargs)
        return func(*args, **kwargs)
    return wrapper
```

**Integrity Controls** (§164.312(c)):
- [ ] Implement mechanisms to ensure data not altered
- [ ] Implement authentication for ePHI

**Transmission Security** (§164.312(e)):
- [ ] Implement integrity controls (addressable)
- [ ] Implement encryption (addressable)

**Implementation**:
```python
# Use TLS 1.2+ for all PHI transmission
requests.post(
    'https://api.example.com/phi',
    json=phi_data,
    verify=True  # Verify SSL certificate
)
```

### Physical Safeguards

- [ ] Facility access controls
- [ ] Workstation use policy
- [ ] Workstation security
- [ ] Device and media controls

### Business Associate Agreements

Required for all third parties that access PHI:
- [ ] Identify all business associates
- [ ] Execute BAA with each
- [ ] Define permitted uses
- [ ] Require safeguards
- [ ] Define reporting obligations
- [ ] Include termination provisions

**BAA Checklist**:
```markdown
- [ ] Business associate defined
- [ ] Permitted uses specified
- [ ] Disclosure restrictions
- [ ] Safeguard requirements
- [ ] Breach notification obligations
- [ ] Termination provisions
- [ ] Subcontractor requirements
```

## SOC2 Implementation Checklist

### Common Criteria 6.1 - Access Control

- [ ] Implement authentication
- [ ] Implement authorization (RBAC)
- [ ] Enforce least privilege
- [ ] Remove access upon termination
- [ ] Periodic access reviews

**Implementation**:
```python
# RBAC implementation
class AccessControl:
    def __init__(self):
        self.roles = {
            'admin': ['read', 'write', 'delete', 'admin'],
            'user': ['read', 'write'],
            'viewer': ['read']
        }

    def check_permission(self, user_role, required_permission):
        return required_permission in self.roles.get(user_role, [])

# Usage
@require_permission('write')
def update_data(data_id, new_data):
    database.update(data_id, new_data)
```

### Common Criteria 6.6 - Encryption at Rest

- [ ] Identify data requiring encryption
- [ ] Implement AES-256 or equivalent
- [ ] Secure key management (KMS)
- [ ] Key rotation schedule
- [ ] Document encryption standards

**Implementation**:
```python
# Using AWS KMS
import boto3

kms = boto3.client('kms')

def encrypt_data(plaintext, key_id):
    response = kms.encrypt(
        KeyId=key_id,
        Plaintext=plaintext.encode()
    )
    return response['CiphertextBlob']

def decrypt_data(ciphertext, key_id):
    response = kms.decrypt(
        CiphertextBlob=ciphertext
    )
    return response['Plaintext'].decode()
```

### Common Criteria 6.7 - Transmission Security

- [ ] Require TLS 1.2+
- [ ] Disable weak ciphers
- [ ] Validate certificates
- [ ] Document encryption policy

**Implementation (nginx)**:
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
```

### Common Criteria 7.2 - Monitoring

- [ ] Log security events
- [ ] Aggregate logs centrally
- [ ] Configure alerts
- [ ] Monitor for anomalies
- [ ] Define log retention (90+ days)
- [ ] Regular log review

**Implementation**:
```python
# Security event logging
import logging

security_logger = logging.getLogger('security')

def log_security_event(event_type, details):
    security_logger.warning({
        'event_type': event_type,
        'details': details,
        'timestamp': datetime.now().isoformat(),
        'severity': 'high' if is_critical(event_type) else 'medium'
    })

    # Send to SIEM
    siem.send_event(event_type, details)
```

## PCI DSS Implementation Checklist

### Requirement 3 - Protect Stored Cardholder Data

**Data Retention**:
- [ ] Define data retention policy
- [ ] Minimize retention period
- [ ] Implement automated deletion
- [ ] Document retention justification

**Sensitive Authentication Data**:
- [ ] Never store full track data
- [ ] Never store CAV2/CVC2/CVV2/CID
- [ ] Never store PIN/PIN block

**PAN Protection**:
- [ ] Mask PAN when displayed (first 6 + last 4 max)
- [ ] Render PAN unreadable everywhere stored
- [ ] Use strong cryptography (AES-256)
- [ ] Implement secure key management

**Implementation**:
```python
# PAN masking
def mask_pan(pan):
    if len(pan) < 13:
        return '*' * len(pan)
    return pan[:6] + '*' * (len(pan) - 10) + pan[-4:]

# Storage
def store_card(pan, expiry, name):
    # Never log or display full PAN
    masked = mask_pan(pan)

    database.cards.insert({
        'pan_hash': hash_sha256(pan),  # For lookups
        'encrypted_pan': encrypt_aes256(pan, kms_key),
        'masked_pan': masked,
        'expiry': expiry,
        'name': name
    })

    audit_log.record('card_stored', {'masked_pan': masked})
```

### Requirement 4 - Encrypt Transmission

- [ ] Use TLS 1.2+ for all cardholder data transmission
- [ ] Never send PAN via email, IM, SMS
- [ ] Implement certificate validation
- [ ] Use only trusted keys/certificates

**Implementation**:
```python
# API calls with TLS
import requests

def process_payment(card_data):
    response = requests.post(
        'https://payment-gateway.com/process',
        json={'card': encrypt_for_transmission(card_data)},
        verify=True,  # Verify SSL cert
        timeout=30
    )
    return response.json()
```

### Requirement 8 - Authentication

**User IDs**:
- [ ] Assign unique ID to each user
- [ ] Prohibit shared/generic accounts
- [ ] Prohibit group/shared passwords

**Two-Factor Authentication**:
- [ ] Implement for all remote access
- [ ] Implement for admin access to CDE
- [ ] Use industry-standard methods

**Password Policy**:
- [ ] Minimum 7 characters (12+ recommended)
- [ ] Contain both letters and numbers
- [ ] Change every 90 days
- [ ] Can't reuse last 4 passwords
- [ ] Lock account after 6 failed attempts
- [ ] Lock duration 30 minutes or until admin reset

**Implementation**:
```python
class PasswordPolicy:
    MIN_LENGTH = 12
    MAX_AGE_DAYS = 90
    HISTORY_COUNT = 4
    MAX_FAILURES = 6
    LOCKOUT_DURATION = 1800  # 30 minutes

    def validate(self, password, user):
        # Length
        if len(password) < self.MIN_LENGTH:
            raise ValueError(f"Password must be {self.MIN_LENGTH}+ chars")

        # Complexity
        if not (re.search(r'[a-zA-Z]', password) and
                re.search(r'\d', password)):
            raise ValueError("Password must contain letters and numbers")

        # History
        if self.is_in_history(user, password):
            raise ValueError(f"Cannot reuse last {self.HISTORY_COUNT} passwords")

        return True

    def check_lockout(self, user):
        failures = get_recent_failures(user)
        if failures >= self.MAX_FAILURES:
            lock_until = get_lock_time(user) + timedelta(seconds=self.LOCKOUT_DURATION)
            if datetime.now() < lock_until:
                raise AccountLockedError("Account locked due to failed attempts")
```

### Requirement 10 - Logging

**What to Log**:
- [ ] All individual user access to cardholder data
- [ ] All privileged user actions
- [ ] All access to audit trails
- [ ] Invalid access attempts
- [ ] Identification/authentication mechanisms
- [ ] Initialization of audit logs
- [ ] Creation/deletion of system objects

**Log Content** (for each event):
- [ ] User identification
- [ ] Event type
- [ ] Date and time
- [ ] Success/failure indicator
- [ ] Origination of event
- [ ] Identity of affected resources

**Log Management**:
- [ ] Secure logs from tampering
- [ ] Review logs daily
- [ ] Retain for 1 year (3 months immediately available)
- [ ] Use automated tools for review

**Implementation**:
```python
def log_cardholder_access(user_id, card_id, action, status='success'):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'event_type': 'cardholder_data_access',
        'action': action,
        'resource': card_id,
        'status': status,
        'ip_address': get_client_ip(),
        'source': 'web_application'
    }

    # Write to tamper-proof log
    audit_log.append(log_entry)

    # Send to SIEM for analysis
    siem.send_event(log_entry)

    return log_entry
```

## Gap Analysis Framework

### Gap Assessment Template

```markdown
## Policy Gap Analysis

**Policy**: [Policy Name]
**Framework**: [GDPR/HIPAA/SOC2/PCI]
**Assessment Date**: [Date]
**Assessor**: [Name]

### Requirements Analysis

| Requirement | Description | Current State | Gap | Priority | Action |
|-------------|-------------|---------------|-----|----------|--------|
| [Req ID] | [What's required] | [What exists] | [What's missing] | [P0/P1/P2] | [What to do] |

### Example:

| Requirement | Description | Current State | Gap | Priority | Action |
|-------------|-------------|---------------|-----|----------|--------|
| GDPR Art 17 | Right to erasure | Manual deletion only | No automated cascade | P0 | Implement cascade deletion |
| HIPAA §164.312(b) | Audit controls | Logs access, not PHI views | PHI access not logged | P0 | Add PHI access logging |
| SOC2 CC7.2 | System monitoring | Basic logging | No anomaly detection | P1 | Add SIEM integration |
| PCI Req 10 | Daily log review | Logs exist | Not reviewed daily | P1 | Automate review process |

### Priority Definitions

- **P0 (Critical)**: Legal/contractual violation, must fix immediately
- **P1 (High)**: Significant risk, fix within 30 days
- **P2 (Medium)**: Best practice gap, plan for next iteration

### Remediation Plan

For each P0/P1 gap:
1. Detailed action items
2. Owner assignment
3. Target completion date
4. Success criteria
5. Verification method
```

## Implementation Roadmap Template

```markdown
## Compliance Implementation Roadmap

**Target Framework**: [SOC2/HIPAA/GDPR/PCI]
**Timeline**: [Q1 2025 - Q4 2025]

### Phase 1: Critical Gaps (P0) - [Dates]
- [ ] [Action item 1]
- [ ] [Action item 2]
- [ ] [Action item 3]

**Success Criteria**: All P0 gaps remediated, controls verified

### Phase 2: High Priority (P1) - [Dates]
- [ ] [Action item 1]
- [ ] [Action item 2]

**Success Criteria**: All P1 gaps remediated, documentation complete

### Phase 3: Documentation & Testing - [Dates]
- [ ] Update policies and procedures
- [ ] Conduct training
- [ ] Perform internal audit
- [ ] Collect evidence

**Success Criteria**: Audit-ready state achieved

### Phase 4: Certification - [Dates]
- [ ] External audit
- [ ] Remediate findings
- [ ] Obtain certification

**Success Criteria**: Certification obtained
```

## Control Mapping Quick Reference

### Data Protection Controls

| Policy Requirement | Technical Control | Code Example |
|-------------------|------------------|--------------|
| Encrypt data at rest | AES-256 encryption | `encrypt_aes256(data, key)` |
| Encrypt in transit | TLS 1.2+ | `ssl_protocols TLSv1.2 TLSv1.3;` |
| Mask sensitive data | Display masking | `mask_pan(pan)` |
| Hash passwords | bcrypt/Argon2 | `bcrypt.hash(password)` |
| Pseudonymize | Hash with salt | `sha256(id + salt)` |

### Access Control Mappings

| Policy Requirement | Technical Control | Code Example |
|-------------------|------------------|--------------|
| Role-based access | RBAC decorator | `@require_role('admin')` |
| Least privilege | Permission checks | `if 'write' in user.permissions` |
| Unique user IDs | UUID generation | `user_id = uuid.uuid4()` |
| Two-factor auth | MFA implementation | `verify_totp(user, code)` |
| Session timeout | Auto-logout | `SESSION_TIMEOUT = 900` |

### Audit & Logging Mappings

| Policy Requirement | Technical Control | Code Example |
|-------------------|------------------|--------------|
| Log PHI access | Audit decorator | `@log_phi_access` |
| Log admin actions | Privileged logging | `log_admin_action(user, action)` |
| Tamper-proof logs | Append-only storage | `audit_log.append(entry)` |
| Log retention | Retention policy | `RETENTION_DAYS = 365` |
| Daily review | Automated analysis | `review_logs_daily()` |
