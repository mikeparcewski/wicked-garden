# Compliance Analysis Output Format

```markdown
## Compliance Analysis: {Framework}

**Target**: {analyzed scope}
**Framework**: {SOC2|HIPAA|GDPR|PCI}
**Status**: {COMPLIANT|NEEDS ATTENTION|NON-COMPLIANT}
**Confidence**: {HIGH|MEDIUM|LOW}

### Executive Summary

{1-2 sentence overview}

### Findings

#### Critical (P0) - Must Fix
1. **{Violation}** - {Control} - {Evidence}
   - Location: {file}:{line}
   - Impact: {description}
   - Remediation: {specific steps}

#### High Priority (P1) - Should Fix
1. **{Gap}** - {Control} - {Evidence}
   - Location: {file}:{line}
   - Risk: {description}
   - Recommendation: {guidance}

#### Medium Priority (P2) - Plan to Fix
1. **{Improvement}** - {Control}
   - Suggestion: {guidance}

### Controls Verified

- [x] Encryption at rest - AES-256
- [x] Access logging - Comprehensive
- [ ] Data retention - Policy missing
- [ ] TLS encryption - Some endpoints missing

### Evidence Collected

- src/auth.py:15-45 - Access control implementation
- config/db.yml:10 - Database encryption config
- Missing: Audit log retention policy

### Remediation Plan

1. **P0**: Add audit logging to admin functions (src/admin.py)
2. **P0**: Encrypt PII fields in database (models/user.py)
3. **P1**: Implement data retention policy
4. **P2**: Add privacy notices to data collection

### Next Steps

- Address P0 findings immediately
- Schedule P1 fixes this sprint
- Document all controls
- Collect audit evidence
```
