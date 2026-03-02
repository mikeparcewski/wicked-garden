# SOC2 and PCI DSS Policy Mappings

SOC2 and PCI DSS policy interpretations and control mappings.

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
