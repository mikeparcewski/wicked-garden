# Policy Implementation Checklists: GDPR & HIPAA

Detailed implementation guidance and gap analysis checklists for GDPR and HIPAA.

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
