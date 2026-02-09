# Comprehensive Safety Checklist

Use this checklist to assess and improve safety of agentic systems.

## Input Safety

### User Input Validation

- [ ] **Input sanitization implemented**
  - Remove or escape dangerous characters
  - Strip HTML/script tags if not needed
  - Normalize unicode and encoding

- [ ] **Input length limits enforced**
  - Maximum input size defined
  - Protection against DOS via large inputs
  - Truncation or rejection of oversized inputs

- [ ] **Prompt injection defenses active**
  - Delimiter-based separation of instructions and data
  - Pattern detection for injection attempts
  - Monitoring for suspicious input patterns

- [ ] **Content filtering applied**
  - Profanity/offensive content detection
  - Spam detection
  - Malicious URL detection

### Data Input Validation

- [ ] **Schema validation on structured inputs**
  - JSON/XML schema enforcement
  - Type checking
  - Required field validation

- [ ] **Range validation on numeric inputs**
  - Min/max bounds checking
  - Validation of enumerated values
  - Null/undefined handling

- [ ] **File upload safety (if applicable)**
  - File type whitelist
  - File size limits
  - Virus scanning
  - Sandboxed file processing

## Output Safety

### Output Validation

- [ ] **Structured output validation**
  - Outputs conform to expected schema
  - Pydantic/JSON Schema validation
  - Required fields present

- [ ] **Content safety checks**
  - Offensive content detection
  - Bias detection
  - Harmful advice detection

- [ ] **PII redaction**
  - Email addresses redacted
  - Phone numbers redacted
  - SSN/credit cards redacted
  - API keys/secrets redacted

- [ ] **Hallucination detection**
  - Confidence thresholds enforced
  - Fact verification against known sources
  - Citation requirements
  - Multi-agent cross-validation

### Output Handling

- [ ] **Sensitive output protection**
  - Encryption for sensitive data
  - Secure transmission (HTTPS, etc.)
  - Minimal logging of sensitive outputs

- [ ] **Output rate limiting**
  - Prevents information disclosure via repeated queries
  - Protects against scraping

## Action Safety

### Pre-Action Validation

- [ ] **Action whitelisting**
  - Only allowed actions are executable
  - Comprehensive whitelist defined
  - Regular review of allowed actions

- [ ] **Parameter validation**
  - Action parameters validated
  - SQL injection prevention
  - Command injection prevention

- [ ] **Dry-run capability**
  - Can simulate actions without executing
  - Preview of action consequences
  - Rollback plan identified

### Human-in-the-Loop

- [ ] **High-stakes actions require approval**
  - Production data modifications
  - Financial transactions
  - External communications
  - Credential changes

- [ ] **Approval workflow defined**
  - Clear approval chain
  - Timeout handling
  - Escalation process
  - Approval audit trail

- [ ] **Approval UI/notification system**
  - Approvers receive timely notifications
  - Approvers can see full context
  - Approval/denial is logged

### Action Constraints

- [ ] **Resource limits enforced**
  - Maximum execution time
  - Memory limits
  - Token budget limits
  - API call limits

- [ ] **Scope restrictions**
  - File system access limited
  - Network access controlled
  - Database access restricted
  - API access scoped

- [ ] **Reversibility considered**
  - Rollback mechanism for critical actions
  - Backups before destructive operations
  - Audit trail for reversing actions

## Authentication & Authorization

### Identity Management

- [ ] **User authentication required**
  - Strong authentication mechanisms
  - MFA for sensitive operations
  - Session management

- [ ] **Agent identity tracked**
  - Each agent has unique ID
  - Agent identity in all logs
  - Attribution of actions to agents

### Access Control

- [ ] **Role-based access control (RBAC)**
  - User roles defined
  - Agent permissions per role
  - Least privilege principle

- [ ] **Permission scoping**
  - Fine-grained permissions
  - Time-bound permissions
  - Context-dependent permissions

- [ ] **Credential management**
  - Secrets not in code
  - Secret rotation policy
  - Secure secret storage (vault, KMS)

## Privacy & Compliance

### PII Protection

- [ ] **PII detection active**
  - Pattern-based detection
  - ML-based detection
  - Context-aware detection

- [ ] **PII minimization**
  - Only collect necessary PII
  - PII retention limits
  - Anonymization when possible

- [ ] **PII encryption**
  - Encryption at rest
  - Encryption in transit
  - Key management

### Compliance

- [ ] **Regulatory requirements identified**
  - GDPR, CCPA, HIPAA, etc.
  - Industry-specific regulations
  - Geographic regulations

- [ ] **Data residency compliance**
  - Data stored in correct regions
  - Cross-border transfer controls
  - Sovereignty requirements

- [ ] **Right to deletion implemented**
  - User can request data deletion
  - Deletion verified across systems
  - Deletion audit trail

- [ ] **Consent management**
  - User consent tracked
  - Consent scope clearly defined
  - Consent withdrawal mechanism

## Monitoring & Observability

### Logging

- [ ] **Comprehensive audit logging**
  - All agent decisions logged
  - All actions logged
  - User interactions logged

- [ ] **Structured logging**
  - JSON/structured format
  - Consistent fields
  - Correlation IDs

- [ ] **Log retention policy**
  - Retention period defined
  - Compliance with regulations
  - Secure log storage

- [ ] **Sensitive data not logged**
  - PII redacted from logs
  - Credentials not logged
  - Secrets not logged

### Monitoring

- [ ] **Real-time safety monitoring**
  - Anomaly detection
  - Unusual action patterns
  - Spike in errors/failures

- [ ] **Alerting configured**
  - Critical safety events trigger alerts
  - Alert routing to right team
  - Alert escalation policies

- [ ] **Dashboard for safety metrics**
  - Safety violations over time
  - Approval rates
  - Error rates by type

### Tracing

- [ ] **Distributed tracing implemented**
  - Request traced across agents
  - Agent-to-agent calls traced
  - External API calls traced

- [ ] **Tracing includes safety context**
  - Approval decisions in trace
  - Validation failures in trace
  - Safety gates in trace

## Incident Response

### Detection

- [ ] **Incident detection mechanisms**
  - Automated detection of safety violations
  - Anomaly detection
  - User reporting mechanism

- [ ] **Incident classification**
  - Severity levels defined
  - Classification criteria
  - Triage process

### Response

- [ ] **Incident response plan documented**
  - Roles and responsibilities
  - Communication plan
  - Escalation procedures

- [ ] **Kill switch mechanism**
  - Emergency stop capability
  - Clear activation criteria
  - Alert on activation

- [ ] **Rollback capability**
  - Can revert problematic changes
  - Rollback tested regularly
  - Data backup for rollback

### Recovery

- [ ] **Post-incident review process**
  - Root cause analysis
  - Lessons learned documented
  - Corrective actions tracked

- [ ] **Incident documentation**
  - Timeline of events
  - Actions taken
  - Impact assessment

## Testing & Validation

### Safety Testing

- [ ] **Adversarial testing performed**
  - Red team testing
  - Prompt injection testing
  - Jailbreak attempt testing

- [ ] **Edge case testing**
  - Invalid inputs
  - Boundary conditions
  - Race conditions

- [ ] **Safety regression testing**
  - Safety tests automated
  - Run on every change
  - No reduction in safety coverage

### Validation

- [ ] **Safety requirements documented**
  - Clear safety specifications
  - Acceptance criteria
  - Success metrics

- [ ] **Independent security review**
  - External security assessment
  - Penetration testing
  - Code review for security

## Operational Safety

### Deployment

- [ ] **Gradual rollout strategy**
  - Canary deployments
  - Percentage-based rollout
  - Automatic rollback on errors

- [ ] **Deployment gates**
  - All tests pass
  - Security scan clear
  - Approval obtained

### Runtime Safety

- [ ] **Circuit breakers implemented**
  - Prevent cascading failures
  - Automatic recovery
  - Alert on circuit open

- [ ] **Rate limiting active**
  - Per-user limits
  - Per-agent limits
  - Per-API limits

- [ ] **Graceful degradation**
  - Reduced functionality when components fail
  - System remains safe in degraded mode
  - User informed of degraded state

### Continuous Improvement

- [ ] **Safety metrics tracked**
  - Violations per day/week
  - False positive rate
  - Response time to incidents

- [ ] **Regular safety reviews**
  - Quarterly safety audits
  - Policy updates
  - New threat assessment

- [ ] **User feedback integration**
  - Safety concerns from users tracked
  - Feedback incorporated into improvements

## Scoring Your System

**Critical (must have):**
- Input validation
- Output validation
- Action whitelisting
- Human approval for high-stakes
- Audit logging
- Kill switch

**Important (should have):**
- PII detection/redaction
- Resource limits
- Circuit breakers
- Rate limiting
- Incident response plan

**Nice to have:**
- Advanced hallucination detection
- ML-based anomaly detection
- Automated adversarial testing

**Minimum viable safety:** All critical items + 80% of important items

**Production ready:** All critical, all important, 50% of nice-to-have

**Best in class:** 100% of all items
