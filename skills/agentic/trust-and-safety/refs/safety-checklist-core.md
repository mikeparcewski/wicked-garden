# Safety Checklist: Core

Use this checklist to assess core safety of agentic systems covering input, output, action, auth, and privacy.

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
