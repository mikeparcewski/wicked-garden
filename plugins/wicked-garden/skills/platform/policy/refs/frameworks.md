# Policy Framework Mappings

Framework-specific policy interpretations and control mappings.

## GDPR Policy Mappings

### Article 5 - Principles of Processing

**Policy Text**: "Personal data shall be processed lawfully, fairly and in a transparent manner"

**Control Mapping**:
- **Lawful**: Valid legal basis (consent, contract, legal obligation, vital interest, public task, legitimate interest)
- **Fair**: No deceptive or misleading practices
- **Transparent**: Clear privacy notices, data subject rights communicated

**Implementation**:
```python
# Legal basis tracking
class DataProcessing:
    def __init__(self, purpose, legal_basis):
        self.purpose = purpose
        self.legal_basis = legal_basis  # 'consent', 'contract', etc.
        self.timestamp = datetime.now()

    def validate_legal_basis(self):
        valid_bases = ['consent', 'contract', 'legal_obligation',
                      'vital_interest', 'public_task', 'legitimate_interest']
        return self.legal_basis in valid_bases

# Privacy notice
def display_privacy_notice():
    return {
        "controller": "Company Name",
        "purpose": "Service delivery",
        "legal_basis": "Contract",
        "retention": "7 years",
        "rights": ["access", "rectification", "erasure", "portability"]
    }
```

---

**Policy Text**: "Personal data shall be collected for specified, explicit and legitimate purposes"

**Control Mapping**:
- **Purpose Limitation**: Document specific purpose for each data collection
- **Purpose Compatibility**: Don't use data for unrelated purposes

**Implementation**:
```python
# Purpose tracking
DATA_PURPOSES = {
    'email': ['account_creation', 'service_notifications', 'support'],
    'name': ['personalization', 'invoicing'],
    'payment_info': ['billing', 'fraud_prevention']
}

def validate_purpose(data_type, purpose):
    allowed_purposes = DATA_PURPOSES.get(data_type, [])
    if purpose not in allowed_purposes:
        raise ValueError(f"Purpose {purpose} not allowed for {data_type}")
```

---

**Policy Text**: "Personal data shall be adequate, relevant and limited to what is necessary"

**Control Mapping**:
- **Data Minimization**: Collect only what's needed
- **Relevance**: Each field must have clear purpose

**Implementation**:
```python
# Required vs optional fields
class UserRegistration:
    REQUIRED = ['email', 'password']
    OPTIONAL = ['phone', 'preferences']

    def validate(self, data):
        # Only collect required + explicitly provided optional
        collected = {k: v for k, v in data.items()
                    if k in self.REQUIRED or (k in self.OPTIONAL and v)}
        return collected
```

---

**Policy Text**: "Personal data shall be kept in a form which permits identification for no longer than necessary"

**Control Mapping**:
- **Storage Limitation**: Define retention periods
- **Deletion**: Automated deletion after retention period

**Implementation**:
```python
# Retention policy
RETENTION_PERIODS = {
    'user_account': timedelta(days=365*7),  # 7 years
    'support_ticket': timedelta(days=365*2),  # 2 years
    'analytics': timedelta(days=365)  # 1 year
}

def schedule_deletion(data_type, created_date):
    retention = RETENTION_PERIODS[data_type]
    deletion_date = created_date + retention
    return deletion_date
```

### Article 17 - Right to Erasure

**Policy Text**: "The data subject shall have the right to obtain from the controller the erasure of personal data"

**Control Mapping**:
- **Deletion Capability**: Implement data deletion
- **Cascade Deletion**: Delete across all systems
- **Verification**: Confirm deletion completed

**Implementation**:
```python
# Right to erasure
def delete_user_data(user_id):
    # Delete from all systems
    database.delete_user(user_id)
    cache.delete_user(user_id)
    analytics.anonymize_user(user_id)
    backups.mark_for_deletion(user_id)

    # Log deletion
    audit_log.record({
        'action': 'data_erasure',
        'user_id': user_id,
        'timestamp': datetime.now(),
        'reason': 'user_request'
    })

    return {'status': 'deleted', 'user_id': user_id}
```

### Article 32 - Security of Processing

**Policy Text**: "The controller shall implement appropriate technical and organizational measures"

**Control Mapping**:
- **Pseudonymization**: Replace identifiable data with pseudonyms
- **Encryption**: Encrypt data at rest and in transit
- **Resilience**: Backup and recovery capabilities
- **Testing**: Regular security testing

**Implementation**:
```python
# Pseudonymization
import hashlib

def pseudonymize(identifier, salt):
    return hashlib.sha256(f"{identifier}{salt}".encode()).hexdigest()

# Encryption
from cryptography.fernet import Fernet

def encrypt_pii(data, key):
    f = Fernet(key)
    return f.encrypt(data.encode())

def decrypt_pii(encrypted_data, key):
    f = Fernet(key)
    return f.decrypt(encrypted_data).decode()
```

## HIPAA Policy Mappings

### §164.308(a)(1) - Security Management Process

**Policy Text**: "Implement policies and procedures to prevent, detect, contain, and correct security violations"

**Control Mapping**:
- **Risk Analysis**: Identify threats to ePHI
- **Risk Management**: Implement controls
- **Sanction Policy**: Enforce violations
- **Activity Review**: Monitor security events

**Implementation**:
```python
# Risk analysis
class RiskAssessment:
    def analyze_phi_access(self, system):
        threats = []

        # Check access controls
        if not system.has_authentication():
            threats.append({
                'threat': 'Unauthorized access',
                'likelihood': 'high',
                'impact': 'critical'
            })

        # Check encryption
        if not system.has_encryption():
            threats.append({
                'threat': 'Data exposure',
                'likelihood': 'medium',
                'impact': 'critical'
            })

        return threats

# Security monitoring
def monitor_phi_access():
    recent_access = audit_log.query(
        resource_type='phi',
        time_range='last_hour'
    )

    # Detect anomalies
    for access in recent_access:
        if is_anomalous(access):
            alert_security_team(access)
```

### §164.312(a)(1) - Unique User Identification

**Policy Text**: "Assign a unique name and/or number for identifying and tracking user identity"

**Control Mapping**:
- **User IDs**: Unique identifier for each user
- **No Shared Accounts**: Prohibit shared credentials
- **Tracking**: Log actions by user ID

**Implementation**:
```python
# User identification
import uuid

class User:
    def __init__(self, username, email):
        self.user_id = str(uuid.uuid4())  # Unique identifier
        self.username = username
        self.email = email
        self.created_at = datetime.now()

    def __str__(self):
        return f"User({self.user_id})"

# Action tracking
def log_phi_access(user_id, phi_record_id, action):
    audit_log.record({
        'user_id': user_id,
        'resource_id': phi_record_id,
        'resource_type': 'phi',
        'action': action,
        'timestamp': datetime.now(),
        'ip_address': get_client_ip()
    })
```

### §164.312(b) - Audit Controls

**Policy Text**: "Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use ePHI"

**Control Mapping**:
- **Audit Logging**: Log all PHI access
- **Log Protection**: Prevent tampering
- **Log Review**: Regular examination

**Implementation**:
```python
# PHI access logging
from functools import wraps

def log_phi_access(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = get_current_user_id()

        # Log access attempt
        audit_log.record({
            'user_id': user_id,
            'action': func.__name__,
            'timestamp': datetime.now(),
            'status': 'attempt'
        })

        try:
            result = func(*args, **kwargs)
            # Log success
            audit_log.record({
                'user_id': user_id,
                'action': func.__name__,
                'status': 'success'
            })
            return result
        except Exception as e:
            # Log failure
            audit_log.record({
                'user_id': user_id,
                'action': func.__name__,
                'status': 'failure',
                'error': str(e)
            })
            raise

    return wrapper

@log_phi_access
def view_patient_record(patient_id):
    return database.get_patient(patient_id)
```

## SOC2 Policy Mappings

### CC6.1 - Logical Access Controls

**Policy Text**: "The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events"

**Control Mapping**:
- **Authentication**: Verify identity
- **Authorization**: Enforce permissions
- **Least Privilege**: Minimal access rights

**Implementation**:
```python
# Role-based access control (RBAC)
from functools import wraps

ROLES = {
    'admin': ['read', 'write', 'delete', 'admin'],
    'user': ['read', 'write'],
    'viewer': ['read']
}

def require_permission(permission):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            user_permissions = ROLES.get(user.role, [])

            if permission not in user_permissions:
                raise PermissionError(
                    f"User {user.id} lacks {permission} permission"
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator

@require_permission('write')
def update_record(record_id, data):
    return database.update(record_id, data)
```

### CC6.6 - Encryption

**Policy Text**: "The entity protects confidential information at rest through encryption"

**Control Mapping**:
- **Encryption Algorithm**: AES-256 or equivalent
- **Key Management**: Secure key storage and rotation
- **Field-Level Encryption**: Encrypt sensitive fields

**Implementation**:
```python
# Field-level encryption
from cryptography.fernet import Fernet
import os

class EncryptedField:
    def __init__(self):
        # Use KMS or environment-based key
        self.key = os.environ.get('ENCRYPTION_KEY').encode()
        self.cipher = Fernet(self.key)

    def encrypt(self, plaintext):
        return self.cipher.encrypt(plaintext.encode())

    def decrypt(self, ciphertext):
        return self.cipher.decrypt(ciphertext).decode()

# Usage in model
class User:
    def __init__(self, email, ssn):
        self.email = email
        self.encrypted_ssn = EncryptedField().encrypt(ssn)

    def get_ssn(self):
        return EncryptedField().decrypt(self.encrypted_ssn)
```

### CC7.2 - System Monitoring

**Policy Text**: "The entity monitors system components and the operation of those components for anomalies or deviations from expected performance"

**Control Mapping**:
- **Security Event Logging**: Log security-relevant events
- **Monitoring**: Real-time monitoring
- **Alerting**: Automated alerts for anomalies

**Implementation**:
```python
# Security event monitoring
import logging

security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)

class SecurityMonitor:
    ANOMALY_THRESHOLDS = {
        'failed_logins': 5,  # per 5 minutes
        'data_access_rate': 100,  # requests per minute
    }

    def check_failed_logins(self, user_id):
        recent_failures = audit_log.count(
            user_id=user_id,
            action='login',
            status='failure',
            time_range='5_minutes'
        )

        if recent_failures >= self.ANOMALY_THRESHOLDS['failed_logins']:
            self.alert('Potential brute force attack', {
                'user_id': user_id,
                'failures': recent_failures
            })
            self.lock_account(user_id)

    def alert(self, message, context):
        security_logger.warning(f"{message}: {context}")
        # Send to monitoring system (PagerDuty, etc.)
        monitoring_system.send_alert(message, context)
```

## PCI DSS Policy Mappings

### Requirement 3 - Protect Stored Cardholder Data

**Policy Text**: "Keep cardholder data storage to a minimum by implementing data retention and disposal policies"

**Control Mapping**:
- **Data Retention**: Minimize storage duration
- **Secure Deletion**: Cryptographically erase
- **PAN Masking**: Display only first 6 and last 4 digits

**Implementation**:
```python
# PAN masking
def mask_pan(pan):
    if len(pan) < 13:
        return '*' * len(pan)
    return pan[:6] + '*' * (len(pan) - 10) + pan[-4:]

# Example: 4532123456789012 -> 453212******9012

# Secure storage
def store_card_data(pan, expiry):
    # Never store full PAN in logs or plain storage
    masked_pan = mask_pan(pan)

    # Encrypt for storage
    encrypted_pan = encrypt_aes256(pan, kms_key)

    database.save({
        'pan_hash': hash_sha256(pan),  # For lookups
        'encrypted_pan': encrypted_pan,
        'expiry': expiry,
        'masked_pan': masked_pan  # For display
    })

    # Log with masked data only
    audit_log.record({
        'action': 'card_stored',
        'masked_pan': masked_pan
    })
```

### Requirement 4 - Encrypt Transmission

**Policy Text**: "Use strong cryptography and security protocols to safeguard sensitive cardholder data during transmission over open, public networks"

**Control Mapping**:
- **TLS 1.2+**: Minimum version
- **Strong Ciphers**: Disable weak ciphers
- **Certificate Validation**: Verify certificates

**Implementation**:
```python
# TLS configuration (nginx example)
"""
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
ssl_prefer_server_ciphers on;
"""

# Python requests with TLS
import requests
import ssl

def secure_api_call(url, data):
    # Enforce TLS 1.2+
    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(
        max_retries=3,
        pool_connections=10,
        pool_maxsize=10
    ))

    response = session.post(
        url,
        json=data,
        verify=True,  # Verify SSL certificate
        timeout=30
    )

    return response.json()
```

### Requirement 8 - Identify and Authenticate Access

**Policy Text**: "Assign a unique ID to each person with computer access"

**Control Mapping**:
- **Unique User IDs**: No shared accounts
- **Two-Factor Authentication**: For remote and admin access
- **Strong Passwords**: Complexity requirements

**Implementation**:
```python
# Password policy
import re
from passlib.hash import bcrypt

class PasswordPolicy:
    MIN_LENGTH = 7
    REQUIRE_COMPLEXITY = True

    @staticmethod
    def validate(password):
        if len(password) < PasswordPolicy.MIN_LENGTH:
            raise ValueError(f"Password must be at least {PasswordPolicy.MIN_LENGTH} characters")

        if PasswordPolicy.REQUIRE_COMPLEXITY:
            # Require mix of letters and numbers
            if not re.search(r'[a-zA-Z]', password):
                raise ValueError("Password must contain letters")
            if not re.search(r'\d', password):
                raise ValueError("Password must contain numbers")

        return True

    @staticmethod
    def hash_password(password):
        PasswordPolicy.validate(password)
        return bcrypt.hash(password)

# Two-factor authentication
class TwoFactorAuth:
    def __init__(self, user):
        self.user = user

    def send_code(self):
        code = generate_otp()
        send_sms(self.user.phone, f"Your code is: {code}")
        cache.set(f"2fa:{self.user.id}", code, ttl=300)  # 5 min

    def verify_code(self, code):
        stored_code = cache.get(f"2fa:{self.user.id}")
        if stored_code == code:
            cache.delete(f"2fa:{self.user.id}")
            return True
        return False
```

### Requirement 10 - Track and Monitor Access

**Policy Text**: "Log all access to cardholder data and regularly review logs"

**Control Mapping**:
- **Comprehensive Logging**: All access logged
- **Log Protection**: Prevent tampering
- **Daily Review**: Regular log examination
- **Log Retention**: 1 year (3 months immediately available)

**Implementation**:
```python
# Cardholder data access logging
def log_card_access(user_id, card_id, action):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'resource_id': card_id,
        'resource_type': 'cardholder_data',
        'action': action,
        'ip_address': get_client_ip(),
        'user_agent': get_user_agent()
    }

    # Write to tamper-proof log
    audit_log.append(log_entry)

    # Send to SIEM
    siem.send_event(log_entry)

# Log review automation
def review_logs_daily():
    yesterday = datetime.now() - timedelta(days=1)

    suspicious_patterns = [
        # Multiple failed access attempts
        audit_log.query(
            action='card_access',
            status='failure',
            count_threshold=5,
            time_range=yesterday
        ),

        # Access outside business hours
        audit_log.query(
            time_range=yesterday,
            hour_range=(22, 6)  # 10pm - 6am
        ),

        # Bulk data access
        audit_log.query(
            action='card_access',
            count_threshold=50,
            time_window='1_hour'
        )
    ]

    for pattern in suspicious_patterns:
        if pattern.matches:
            alert_security_team(pattern)
```

## Common Policy Patterns

### Consent Management

```python
class ConsentManager:
    def record_consent(self, user_id, purpose, method='explicit'):
        return database.consents.insert({
            'user_id': user_id,
            'purpose': purpose,
            'method': method,  # 'explicit', 'implicit', 'opt-in'
            'timestamp': datetime.now(),
            'ip_address': get_client_ip()
        })

    def withdraw_consent(self, user_id, purpose):
        database.consents.update(
            {'user_id': user_id, 'purpose': purpose},
            {'withdrawn': True, 'withdrawn_at': datetime.now()}
        )

    def has_consent(self, user_id, purpose):
        consent = database.consents.find_one({
            'user_id': user_id,
            'purpose': purpose,
            'withdrawn': {'$ne': True}
        })
        return consent is not None
```

### Data Subject Access Requests

```python
class DataAccessRequest:
    def export_user_data(self, user_id):
        # Gather all user data
        user_data = {
            'profile': database.users.find_one({'id': user_id}),
            'orders': list(database.orders.find({'user_id': user_id})),
            'support_tickets': list(database.tickets.find({'user_id': user_id})),
            'consent_records': list(database.consents.find({'user_id': user_id}))
        }

        # Format as machine-readable (JSON)
        return json.dumps(user_data, indent=2)

    def delete_user_data(self, user_id, reason='user_request'):
        # Log deletion
        audit_log.record({
            'action': 'data_deletion',
            'user_id': user_id,
            'reason': reason,
            'timestamp': datetime.now()
        })

        # Delete from all systems
        database.users.delete({'id': user_id})
        database.orders.delete({'user_id': user_id})
        database.tickets.delete({'user_id': user_id})
        cache.delete(f"user:{user_id}")
```
