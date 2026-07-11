# Privacy Analysis Output Format

```markdown
## Privacy Analysis

**Target**: {analyzed scope}
**Framework**: GDPR / HIPAA / CCPA
**Status**: {COMPLIANT|NEEDS ATTENTION|NON-COMPLIANT}
**Sensitivity Level**: {LOW|MEDIUM|HIGH|CRITICAL}

### Data Inventory

| Data Type | Location | Purpose | Legal Basis | Retention |
|-----------|----------|---------|-------------|-----------|
| Email | users.email | Account mgmt | Contract | Account lifetime |
| Name | users.name | Personalization | Consent | Account lifetime |
| IP Address | logs/ | Security | Legitimate interest | 90 days |
| Health data | medical.records | Healthcare | Consent + Legal | 7 years |

### PII Detection Results

**Direct Identifiers**:
- Email: models/user.py:15, api/auth.py:20
- Name: models/user.py:16
- Phone: models/user.py:18

**Indirect Identifiers**:
- IP addresses: logs/access.log
- Device IDs: analytics/tracking.js

**Sensitive Data** (GDPR Art 9):
- Health data: models/medical.py:10-50
- Biometric: models/auth.py:45 (facial recognition)

### Privacy Violations

#### Critical (P0)
1. **PII in error logs**
   - Location: app.py:100 - logs user email on error
   - Impact: PII exposure in log files
   - Remediation: Sanitize logs, remove PII

2. **No consent for analytics**
   - Location: templates/base.html:30 - Google Analytics
   - Impact: GDPR violation
   - Remediation: Add consent banner

#### High Priority (P1)
1. **Missing privacy notice**
   - Impact: Transparency requirement
   - Remediation: Add privacy policy page

2. **No data retention policy**
   - Impact: Storage limitation principle
   - Remediation: Define and implement retention

### GDPR Compliance Status

- [ ] Article 5: Principles - PARTIAL (missing retention policy)
- [ ] Article 6: Lawful basis - NEEDS WORK (analytics consent)
- [x] Article 15: Right to access - IMPLEMENTED
- [ ] Article 17: Right to erasure - PARTIAL (backups not covered)
- [ ] Article 30: Records of processing - MISSING
- [x] Article 32: Security measures - IMPLEMENTED

### Data Subject Rights Implementation

| Right | Status | Implementation |
|-------|--------|----------------|
| Access (Art 15) | READY | /api/user/export endpoint |
| Rectification (Art 16) | READY | /api/user/update endpoint |
| Erasure (Art 17) | PARTIAL | Missing backup deletion |
| Portability (Art 20) | READY | JSON export available |
| Object (Art 21) | MISSING | No opt-out mechanism |

### Privacy by Design Assessment

**Data Minimization**: PARTIAL
- Collecting only necessary fields
- But: Analytics collecting too much

**Privacy by Default**: NEEDS WORK
- No default privacy settings
- Users must opt-out vs opt-in

**Transparency**: NEEDS WORK
- Missing privacy notice
- No processing records

### Remediation Plan

#### Immediate (P0) - Block deployment
1. Remove PII from error logs (app.py:100)
2. Implement consent for analytics

#### This Sprint (P1)
1. Add privacy notice/policy
2. Define data retention policy
3. Implement backup deletion for erasure requests

#### Next Sprint (P2)
1. Create Article 30 records
2. Add privacy settings UI
3. Implement opt-out mechanisms

### Evidence for DPO/Audit

- Data flow diagram: {path}
- Privacy impact assessment: {path}
- Consent records: database.consents table
- Deletion logs: logs/privacy-deletions.log

### Next Steps

1. Fix P0 violations immediately
2. Schedule DPO review
3. Update privacy documentation
4. Test data subject rights workflows
```
