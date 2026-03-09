# Policy Implementation Checklists: SOC2 & PCI DSS

Implementation checklists for SOC2 and PCI DSS with code examples.

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
