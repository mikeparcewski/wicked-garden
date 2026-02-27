---
name: trust-and-safety
description: Trust, safety, and control patterns for production agentic systems with human-in-the-loop gates and guardrails
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

See `refs/guardrails.md` for detailed implementation patterns.

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

See `refs/guardrails.md` for code examples.

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

See `refs/guardrails.md` for implementation details.

## Prompt Injection Defense

### Input Sanitization

Clean user inputs before passing to LLM. Remove instruction-like patterns.

### Delimiter-Based Protection

Use clear delimiters to separate system instructions from user input.

### Privilege Separation

Separate instruction and data contexts using role-based message formatting.

See `refs/guardrails.md` for defense patterns and code examples.

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

See `refs/guardrails.md` for detection and redaction code.

## Hallucination Mitigation

### Grounding Techniques

**Retrieval-Augmented Generation (RAG):** Retrieve facts before generation
**Citation Requirements:** Require source citations for all claims

### Verification Strategies

**Multi-Agent Verification:** Independent verification by multiple agents
**Confidence Calibration:** Require confidence scores, reject low-confidence outputs

See `refs/guardrails.md` for implementation patterns.

## Kill Switches and Circuit Breakers

**Kill Switch:** Emergency stop that halts all operations and alerts administrators.
**Circuit Breaker:** Opens circuit after threshold failures to prevent cascading failures.
**Rate Limiting:** Limits requests per user/time window to prevent abuse.

See `refs/guardrails.md` for complete implementations.

## Safety Checklist

Before deploying an agentic system:

- [ ] Human approval gates on high-stakes actions
- [ ] Input validation and sanitization
- [ ] Output validation against schema
- [ ] Action whitelisting (not just blacklisting)
- [ ] Resource limits (time, memory, tokens, cost)
- [ ] PII detection and redaction
- [ ] Prompt injection defenses
- [ ] Hallucination mitigation (RAG, verification)
- [ ] Circuit breakers on external calls
- [ ] Rate limiting per user/agent
- [ ] Kill switch mechanism
- [ ] Audit logging of all decisions/actions
- [ ] Incident response plan
- [ ] Rollback capability

See `refs/safety-checklist.md` for comprehensive checklist with examples.

## When to Use

Trigger phrases indicating you need this skill:
- "How do I make my agent system safe?"
- "What safety checks should I add?"
- "How do I prevent agents from doing harmful things?"
- "What about prompt injection?"
- "How do I protect PII?"
- "Should I add human approval?"

## References

- `refs/safety-checklist.md` - Comprehensive safety review checklist
- `refs/guardrails.md` - Implementation patterns for safety guardrails
