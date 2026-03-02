# GDPR Policy Mappings

GDPR-specific policy interpretations and control mappings.

## Article 5 - Principles of Processing

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

## Article 17 - Right to Erasure

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

## Article 32 - Security of Processing

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
