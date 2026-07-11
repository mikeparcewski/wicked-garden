# PII Detection and Privacy Violation Grep Patterns

Detection greps for PII, indirect identifiers, GDPR special categories, and
privacy violations. Run against the target scope and cite file:line for every
hit that survives triage.

## PII Detection Patterns

### Direct Identifiers

```bash
# Names
grep -ri "first.*name\|last.*name\|full.*name\|given.*name" --include="*.py" --include="*.js"

# Email addresses
grep -ri "email\|e-mail" --include="*.py" --include="*.js"

# Phone numbers
grep -ri "phone\|mobile\|telephone" --include="*.py" --include="*.js"

# Addresses
grep -ri "address\|street\|city\|postal.*code\|zip.*code" --include="*.py" --include="*.js"

# Government IDs
grep -ri "ssn\|social.*security\|passport\|driver.*license" --include="*.py" --include="*.js"
```

### Indirect Identifiers

```bash
# IP addresses
grep -ri "ip.*address\|remote.*addr\|client.*ip" --include="*.py" --include="*.js"

# Device IDs
grep -ri "device.*id\|uuid\|identifier.*for.*advertising" --include="*.py" --include="*.js"

# Location data
grep -ri "latitude\|longitude\|geolocation\|gps" --include="*.py" --include="*.js"

# Behavioral data
grep -ri "tracking\|analytics\|user.*behavior" --include="*.py" --include="*.js"
```

### Sensitive Data (GDPR Special Categories)

```bash
# Health data
grep -ri "medical\|health\|diagnosis\|patient\|symptom" --include="*.py" --include="*.js"

# Biometric data
grep -ri "fingerprint\|facial.*recognition\|biometric" --include="*.py" --include="*.js"

# Genetic data
grep -ri "genetic\|dna\|genome" --include="*.py" --include="*.js"
```

## Privacy Violation Detection

### Critical Issues (P0)

```bash
# PII in logs
grep -r "log.*email\|log.*ssn\|print.*password" --include="*.py"

# Unencrypted PII transmission
grep -r "http://" config/ | grep -i "api\|endpoint"

# PII in error messages
grep -r "error.*email\|exception.*user.*name" --include="*.py"

# No consent mechanism
grep -c "consent\|accept.*terms\|agree.*privacy" --include="*.html" --include="*.js"
```

### High Priority (P1)

```bash
# Missing data retention policy
grep -c "retention\|delete.*after\|expire" config/

# No privacy notice
grep -c "privacy.*policy\|privacy.*notice" templates/

# Third-party data sharing without notice
grep -r "analytics\|tracking\|third.*party" --include="*.js"
```

## GDPR Article Verification Greps

### Article 17: Right to Erasure

```bash
# Find user data deletion functions
grep -r "delete.*user\|remove.*user\|purge.*data" --include="*.py"

# Check cascade delete
grep -r "on.*delete.*cascade\|foreign.*key.*delete" --include="*.py"

# Verify deletion from backups
grep -r "backup.*delete\|backup.*retention" config/
```

### Article 32: Security Measures

**Pseudonymization/Anonymization**:
```python
# Check for data masking
grep -r "mask\|anonymize\|pseudonymize\|hash.*pii" --include="*.py"
```

**Encryption**:
```python
# At rest
grep -r "encrypt.*at.*rest\|database.*encryption" config/

# In transit
grep -r "tls\|ssl\|https" config/
```

**Resilience**:
```python
# Backup and recovery
grep -r "backup\|restore\|disaster.*recovery" --include="*.py"
```
