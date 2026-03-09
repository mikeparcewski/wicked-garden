# Gap Analysis Framework & Control Mappings

Gap assessment templates, implementation roadmaps, and control mapping quick references for compliance frameworks.

## Gap Assessment Template

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
