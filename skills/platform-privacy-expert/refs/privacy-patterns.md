# Privacy by Design: Reference Implementations

Code patterns for implementing privacy by design. Use as the model for
remediation code recommended in privacy analyses.

## 1. Minimize Data Collection

```python
# Good: Collect only what's needed
class UserRegistration:
    required_fields = ['email', 'password']
    optional_fields = ['name']  # Only if needed

# Bad: Collecting unnecessary data
class UserRegistration:
    fields = ['email', 'password', 'name', 'dob', 'address',
              'phone', 'ssn', 'occupation']  # Too much!
```

## 2. Implement Consent

```python
class ConsentManager:
    def request_consent(self, purpose, data_types):
        """Request explicit consent for data processing."""
        return {
            "purpose": purpose,
            "data_types": data_types,
            "timestamp": datetime.utcnow(),
            "consent_given": False,
            "consent_method": "explicit_opt_in"
        }

    def record_consent(self, user_id, purpose, granted):
        """Record consent decision."""
        consent_record = {
            "user_id": user_id,
            "purpose": purpose,
            "granted": granted,
            "timestamp": datetime.utcnow(),
            "ip_address": request.remote_addr
        }
        db.consents.insert(consent_record)
        log_consent_event(consent_record)
```

## 3. Enable Data Subject Rights

```python
class DataSubjectRights:
    def export_user_data(self, user_id):
        """Article 15 & 20: Right to access and portability."""
        user_data = {
            "personal_info": get_user_info(user_id),
            "activity": get_user_activity(user_id),
            "consents": get_user_consents(user_id),
            "export_date": datetime.utcnow()
        }
        return json.dumps(user_data)

    def delete_user_data(self, user_id):
        """Article 17: Right to erasure."""
        # Delete from all systems
        delete_user_from_db(user_id)
        delete_user_from_cache(user_id)
        delete_user_from_backups(user_id)
        delete_user_from_analytics(user_id)
        log_deletion(user_id)

    def rectify_user_data(self, user_id, corrections):
        """Article 16: Right to rectification."""
        update_user_data(user_id, corrections)
        log_rectification(user_id, corrections)
```

## 4. Protect PII in Logs

```python
import re

class PrivacyAwareLogger:
    PII_PATTERNS = [
        (r'\b[\w\.-]+@[\w\.-]+\.\w+\b', '[EMAIL]'),  # Email
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),  # SSN
        (r'\b\d{16}\b', '[CARD]'),  # Credit card
        (r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]'),  # Phone
    ]

    def sanitize(self, message):
        """Remove PII from log messages."""
        for pattern, replacement in self.PII_PATTERNS:
            message = re.sub(pattern, replacement, message)
        return message

    def log(self, level, message):
        sanitized = self.sanitize(message)
        logger.log(level, sanitized)
```
