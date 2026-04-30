---
name: trust-and-safety
description: |
  Trust, safety, and control patterns for production agentic systems with human-in-the-loop gates and guardrails.
  Use when: designing guardrails or human-in-the-loop gates for an agent, or
  hardening an agentic system against prompt injection.
portability: portable
---

# Trust and Safety

Essential patterns for building safe, trustworthy, production-ready agentic systems.

## Core Principles

1. **Least Privilege:** Agents have minimum necessary permissions
2. **Defense in Depth:** Multiple layers of safety checks
3. **Fail Safe:** Errors should fail toward safety, not capability
4. **Human Oversight:** High-stakes decisions require human approval
5. **Auditability:** All decisions and actions are logged and traceable
6. **Graceful Degradation:** System remains safe even when components fail

## Human-in-the-Loop Gates

### When to Add Human Gates

**Always require approval for:**
- Production data modifications (delete, update critical data)
- Financial transactions above threshold
- Communications to external parties
- Credential or security changes
- Irreversible operations

**Consider approval for:**
- First-time operations
- Operations outside normal patterns
- Low-confidence decisions
- Operations near resource limits

### Implementation Pattern

```python
async def execute_with_approval(action, threshold=0.8):
    if action.confidence < threshold or action.is_high_stakes():
        approval = await request_human_approval(action)
        if not approval.approved:
            raise ApprovalDenied(approval.reason)
    return await action.execute()
```

### Approval Workflow Design

**Synchronous Approval:** Block until human responds (for urgent decisions)
**Asynchronous Approval:** Queue for later review (for batch operations)
**Escalation Chains:** Route to higher authority if primary approver unavailable
**Timeout Handling:** Define what happens if no approval received

See `refs/guardrails-input-output.md`, `refs/guardrails-actions.md`, and `refs/guardrails-resources.md` for detailed implementation patterns.

## Output Validation

### Structured Output Validation

Force outputs into validated schemas using Pydantic or similar.

### Content Validation

Check outputs before acting on them:
- **Format validation:** Matches expected structure
- **Range validation:** Numeric values within acceptable bounds
- **Completeness validation:** Required fields are present
- **Consistency validation:** Outputs are internally consistent

### Hallucination Detection

**Cross-Validation:** Multiple agents check same fact
**Source Verification:** Verify claims against ground truth
**Confidence Thresholds:** Reject low-confidence outputs
**Fact Checking:** Use retrieval to verify factual claims

See `refs/guardrails-input-output.md` for code examples.

## Action Constraints and Sandboxing

### Whitelisting

Safer than blacklisting. Define allowed commands/actions explicitly.

### Sandboxing

Isolate agent execution:
- **Containerization:** Run agents in Docker containers
- **Virtual environments:** Separate Python/Node environments
- **File system restrictions:** Limit access to specific directories
- **Network isolation:** Control network access

### Resource Limits

Prevent runaway resource usage:
- Max runtime (timeouts)
- Max memory
- Max tokens per request/session
- Max API calls

See `refs/guardrails-actions.md` and `refs/guardrails-resources.md` for implementation details.

## Prompt Injection Defense

### Input Sanitization

Clean user inputs before passing to LLM. Remove instruction-like patterns.

### Delimiter-Based Protection

Use clear delimiters to separate system instructions from user input.

### Privilege Separation

Separate instruction and data contexts using role-based message formatting.

See `refs/guardrails-input-output.md` for defense patterns and code examples.

## PII Detection and Protection

### Pattern-Based Detection

Regex patterns for email, SSN, credit cards, phone numbers, etc.

### Redaction

Replace detected PII with `[REDACTED_TYPE]` tokens.

### PII Policies

- **Never log PII** in plain text
- **Encrypt PII** at rest and in transit
- **Minimize PII collection** (only collect what's needed)
- **Retention limits** (delete after specified period)

See `refs/guardrails-input-output.md` for detection and redaction code.

## Hallucination Mitigation

### Grounding Techniques

**Retrieval-Augmented Generation (RAG):** Retrieve facts before generation
**Citation Requirements:** Require source citations for all claims

### Verification Strategies

**Multi-Agent Verification:** Independent verification by multiple agents
**Confidence Calibration:** Require confidence scores, reject low-confidence outputs

See `refs/guardrails-actions.md` and `refs/guardrails-resources.md` for implementation patterns.

## Kill Switches and Circuit Breakers

**Kill Switch:** Emergency stop that halts all operations and alerts administrators.
**Circuit Breaker:** Opens circuit after threshold failures to prevent cascading failures.
**Rate Limiting:** Limits requests per user/time window to prevent abuse.

See `refs/guardrails-actions.md` and `refs/guardrails-resources.md` for complete implementations.

## Safety Checklist

See `refs/safety-checklist-core.md` for the full pre-deployment checklist covering human gates, validation, whitelisting, resource limits, PII, prompt injection, hallucination, circuit breakers, rate limiting, kill switches, audit logging, and rollback. See `refs/safety-checklist-advanced.md` for monitoring, incidents, testing, and ops checklists.

## References

- `refs/safety-checklist-core.md` - Core safety checklist (input, output, action, auth, privacy)
- `refs/safety-checklist-advanced.md` - Advanced safety checklist (monitoring, incidents, testing, ops)
- `refs/guardrails-input-output.md` - Input validation, sanitization, prompt injection, output filtering
- `refs/guardrails-actions.md` - Action whitelisting, approvals, sandboxed execution
- `refs/guardrails-resources.md` - Resource limiting, monitoring, complete guardrail architecture
