# Safety review — the report template

Loaded on demand by the `wicked-garden-agentic-safety-reviewer` worker skill. Emit the template verbatim with the placeholders filled.

## Output Format

````markdown

## Safety Review: {Project Name}

**Review Date**: {date}
**Risk Level**: {CRITICAL/HIGH/MEDIUM/LOW}
**Codebase Path**: {path}

### Executive Summary

{2-3 sentence summary of safety posture and critical risks}

### Risk Profile

| Category | Findings | Critical | High | Medium | Low |
|----------|----------|----------|------|--------|-----|
| Prompt Injection | {count} | {count} | {count} | {count} | {count} |
| PII Protection | {count} | {count} | {count} | {count} | {count} |
| Guardrails | {count} | {count} | {count} | {count} | {count} |
| Human-in-the-Loop | {count} | {count} | {count} | {count} | {count} |
| Hallucination Risk | {count} | {count} | {count} | {count} | {count} |

### Prompt Injection Assessment

**Status**: {PROTECTED/VULNERABLE/CRITICAL}

**Direct Injection**:
- [ ] User input is not directly concatenated into prompts
- [ ] Clear delimiters separate system/user content
- [ ] Instruction hierarchy is enforced
- [ ] Injection patterns are detected and blocked

**Findings**:
- **CRITICAL**: {file:line} - User input directly in prompt without validation
  ```python
  prompt = f"You are a helper. {user_input}"  # VULNERABLE
  ```
  **Fix**: Use structured prompts with clear boundaries

- **HIGH**: {file:line} - No injection pattern detection

**Indirect Injection**:
- [ ] External content is sanitized before inclusion
- [ ] RAG documents are from trusted sources
- [ ] Web scraping results are validated
- [ ] API responses are filtered

**Findings**:
- **HIGH**: {file:line} - Untrusted URL content included in prompt
- **MEDIUM**: {file:line} - Search results without sanitization

**Recommendations**:
1. Implement input validation with injection pattern detection
2. Add clear delimiters: "User Query:", "Instructions:", etc.
3. Sanitize all external content before prompt inclusion

### PII Protection Assessment

**Status**: {COMPLIANT/PARTIAL/NON_COMPLIANT}

**Detection**:
- [ ] PII patterns detected in inputs
- [ ] PII patterns detected in outputs
- [ ] PII patterns detected in logs

**Findings**:
- **CRITICAL**: {file:line} - Email addresses logged in plaintext
- **HIGH**: {file:line} - SSN patterns not redacted in responses

**Redaction**:
- [ ] Input PII is redacted before storage
- [ ] Output PII is redacted before returning
- [ ] Log PII is masked or hashed

**Findings**:
- **HIGH**: {file:line} - No redaction mechanism implemented
- **MEDIUM**: {file:line} - Inconsistent redaction across agents

**Compliance**:
- [ ] GDPR: Right to erasure implemented
- [ ] CCPA: Do not sell enforcement
- [ ] HIPAA: PHI encryption at rest and in transit (if applicable)

**Findings**:
- **HIGH**: No data retention policy for PII
- **MEDIUM**: PII stored without encryption

**Recommendations**:
1. Implement PII detection library (e.g., regex + ML-based)
2. Add redaction layer for all inputs/outputs/logs
3. Create PII cleanup policy and scheduled jobs
4. Encrypt PII storage and transmission

### Guardrails Assessment

**Status**: {IMPLEMENTED/PARTIAL/MISSING}

**Input Guardrails**: {PRESENT/MISSING}

- [ ] Length limits enforced
- [ ] Content validation exists
- [ ] Injection detection active
- [ ] Rate limiting per user/session
- [ ] Toxicity filtering enabled

**Findings**:
- **CRITICAL**: No input validation at agent entry points
- **HIGH**: No rate limiting - DoS risk
- **MEDIUM**: No toxicity filtering

**Output Guardrails**: {PRESENT/MISSING}

- [ ] PII redaction in responses
- [ ] Toxicity filtering in generated content
- [ ] Citation requirements enforced
- [ ] Uncertainty disclaimers added
- [ ] Content policy compliance

**Findings**:
- **HIGH**: No output validation before returning
- **MEDIUM**: No citation requirements

**Action Guardrails**: {PRESENT/MISSING}

- [ ] Critical actions require confirmation
- [ ] Audit logging for all actions
- [ ] Approval workflow for destructive actions
- [ ] Timeout and fallback strategies

**Findings**:
- **CRITICAL**: Delete operations not gated
- **HIGH**: Payment actions lack human approval
- **MEDIUM**: No audit trail for actions

**Recommendations**:
1. Implement three-layer guardrails: input, output, action
2. Add rate limiting with per-user quotas
3. Create approval workflow for critical actions
4. Enable comprehensive audit logging

### Human-in-the-Loop Assessment

**Status**: {IMPLEMENTED/PARTIAL/MISSING}

**Escalation Strategy**: {CLEAR/UNCLEAR/MISSING}

- [ ] Escalation triggers are documented
- [ ] Low-confidence threshold defined
- [ ] High-stakes domains identified
- [ ] Critical actions flagged

**Findings**:
- **HIGH**: No escalation logic for low-confidence scenarios
- **MEDIUM**: High-stakes domains not identified

**Review Workflow**: {IMPLEMENTED/MISSING}

- [ ] Reviewer assignment logic exists
- [ ] Timeout strategy defined
- [ ] Fallback for no reviewer available
- [ ] Decision tracking implemented

**Findings**:
- **HIGH**: No timeout strategy - can block indefinitely
- **MEDIUM**: Reviewer decisions not tracked

**Recommendations**:
1. Define confidence threshold for escalation (e.g., < 0.7)
2. Identify high-stakes domains: medical, legal, financial
3. Implement timeout with safe fallback (default: deny)
4. Add decision tracking for feedback loop

### Hallucination Mitigation Assessment

**Status**: {STRONG/MODERATE/WEAK}

**Grounding Mechanisms**: {PRESENT/MISSING}

- [ ] Citations required for factual claims
- [ ] RAG retrieval before answering
- [ ] Tool use preferred over memorization
- [ ] Verification against knowledge base
- [ ] Confidence scoring enabled

**Findings**:
- **MEDIUM**: No citation requirements - hallucination risk
- **MEDIUM**: Confidence scores not computed
- **LOW**: "I don't know" responses not encouraged

**Detection**: {ACTIVE/PASSIVE/MISSING}

- [ ] Cross-checking factual claims
- [ ] Multi-agent verification for critical info
- [ ] Contradiction detection
- [ ] Source availability check

**Findings**:
- **HIGH**: No fact verification mechanism
- **MEDIUM**: Single-agent responses without verification

**Recommendations**:
1. Require citations for all factual claims
2. Implement confidence scoring and return to user
3. Add multi-agent verification for high-stakes answers
4. Encourage "I don't know" over guessing

### Critical Vulnerabilities

**Priority 1 (Fix Immediately)**:
1. {vulnerability} - {location}
   - **Risk**: {description}
   - **Fix**: {specific action}
   - **Effort**: {LOW/MEDIUM/HIGH}

**Priority 2 (Fix Before Production)**:
1. {vulnerability} - {location}
   - **Risk**: {description}
   - **Fix**: {specific action}

### Secure Patterns Observed

- {positive finding}
- {positive finding}

### Next Steps

1. **Immediate**: {critical fix}
2. **Short-term**: {high priority fix}
3. **Medium-term**: {improvement}
4. **Long-term**: {strategic enhancement}

### Cross-Skill Coordination

**Defer to**:
- **wicked-garden-agentic-architect**: For Layer 5 architecture validation
- **wicked-garden-agentic-performance-analyst**: For rate limiting and throttling implementation
- **frameworks knowledge skill** (`skills/agentic/frameworks/`): For framework-native safety features

**Collaborate with**:
- The architect skill on guardrail placement in the five-layer architecture (see the agentic-patterns knowledge module)
- The performance-analyst skill on efficient validation strategies
````
