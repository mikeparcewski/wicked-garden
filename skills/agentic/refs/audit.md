# agentic:audit — 8-Layer Trust & Safety Audit Rubric

Full rubric sourced from the `wicked-garden-agentic-safety-reviewer` fork skill (former `agents/agentic/safety-reviewer.md`) and
`skills/agentic/trust-and-safety/`. Apply every layer to the target codebase.

## Layer 1: Tool Risk Classification

Inventory every tool the agent can invoke. For each, classify:
- **Capability**: read-only | side-effecting | destructive | external-comms
- **Scope**: local | cross-agent | external-system
- **Reversibility**: reversible | irreversible

Tag CRITICAL if destructive + irreversible (e.g. delete, payment, email-send).

## Layer 2: HITL Gate Verification

Check that every CRITICAL/HIGH-risk tool has a human-in-the-loop gate:

- [ ] Gate trigger is explicit (confidence < threshold OR action in CRITICAL_ACTIONS)
- [ ] Approval workflow exists (sync or async) with defined timeout
- [ ] Fallback on no-response is deny (fail-safe), not allow
- [ ] Reviewer decisions are tracked with audit trail

Patterns (from `refs/guardrails-actions.md`):
```python
async def execute_with_approval(action, threshold=0.8):
    if action.confidence < threshold or action.is_high_stakes():
        approval = await request_human_approval(action)
        if not approval.approved:
            raise ApprovalDenied(approval.reason)
    return await action.execute()
```

## Layer 3: PII Handling

Search for PII patterns in inputs, outputs, and logs:

```bash
grep -r "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+" --include="*.log" .
grep -r "\b\d{3}-\d{2}-\d{4}\b" .          # SSN
grep -r "\b\d{4}[- ]?\d{4}[- ]?\d{4}" .    # CC
```

Checklist:
- [ ] PII detection at entry points
- [ ] PII redacted in logs and outputs (`[REDACTED_EMAIL]`, etc.)
- [ ] No PII in plaintext storage
- [ ] Retention policy defined

## Layer 4: Prompt Injection Defense

Direct injection — check for unvalidated string concatenation:

```bash
grep -r "f\"{.*user.*}\"" --include="*.py" .
grep -r "prompt + user_input" .
```

Indirect injection — check for untrusted external content included in prompts
(URL fetches, RAG documents, search results).

Checklist:
- [ ] Clear delimiters separate system / user content
- [ ] Injection patterns detected and blocked
- [ ] External content sanitized before prompt inclusion

## Layer 5: AuthN / AuthZ

- [ ] Agents use least-privilege credentials
- [ ] Tool access is role-gated (not open to all agents)
- [ ] Credentials are not logged or exposed in error messages

## Layer 6: Rate Limits & Quotas

- [ ] Per-user and per-session quotas defined
- [ ] Circuit breaker opens after N failures
- [ ] Rate limit headers / retry-after respected when calling external APIs

## Layer 7: Observability

- [ ] All agent actions logged with structured fields (action, user_id, params, result)
- [ ] Audit log is append-only and tamper-evident
- [ ] Monitoring alerts on CRITICAL findings or anomalous action rates

## Layer 8: Failure Modes

- [ ] Errors fail toward safety (deny by default)
- [ ] No bare `except Exception: pass` swallowing errors silently
- [ ] External API failures produce a safe fallback response (not a crash)
- [ ] Kill switch exists to halt all operations + alert admins

## Compliance Extensions

When `--standard` is given, append the matching checklist:

| Standard | Layer emphasis |
|----------|---------------|
| GDPR | Layer 3 (PII) + retention + right-to-erasure |
| HIPAA | Layer 3 PHI encryption at rest + in transit |
| SOC 2 | Layers 5, 6, 7 (access control, rate limits, audit) |
| NIST AI RMF | All 8 layers with severity scoring |

## Output Format

```markdown
## Trust & Safety Audit: {Project}

**Date**: {date} | **Standard**: {standard or none} | **Risk Level**: {CRITICAL|HIGH|MEDIUM|LOW}

### Risk Profile

| Layer | Status | Critical | High | Medium | Low |
|-------|--------|----------|------|--------|-----|
| Tool Risk | {PASS/FAIL} | … | … | … | … |
| HITL Gates | {PASS/FAIL} | … | … | … | … |
| PII Handling | {PASS/FAIL} | … | … | … | … |
| Prompt Injection | {PASS/FAIL} | … | … | … | … |
| AuthN/AuthZ | {PASS/FAIL} | … | … | … | … |
| Rate Limits | {PASS/FAIL} | … | … | … | … |
| Observability | {PASS/FAIL} | … | … | … | … |
| Failure Modes | {PASS/FAIL} | … | … | … | … |

### Findings (CRITICAL and HIGH only — list all)

**CRITICAL**: {file:line} — {description} — Fix: {specific action}

### Remediation Roadmap

P0 (fix immediately): …
P1 (before production): …
P2 (next sprint): …
```

When `--scenarios` is set, emit a `wicked-scenarios` block for each CRITICAL/HIGH finding.
