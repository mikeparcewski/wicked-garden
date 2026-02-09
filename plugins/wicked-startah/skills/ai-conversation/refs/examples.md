# Examples: Multi-AI Conversation Patterns

Real-world examples and templates for multi-model collaboration.

## Architecture Decision Record (ADR)

After multi-model review, create an ADR capturing all perspectives:

```markdown
# ADR-001: Payment Gateway Selection

## Status
Accepted

## Context
Reviewed by Claude, Gemini, Codex, and OpenCode on 2026-01-23.

The payment integration requires:
- PCI DSS compliance
- Support for subscriptions and one-time payments
- Webhook-based async processing

## Decision
Use Stripe with webhook-based async processing.

## Perspectives

### Claude
- Emphasized PCI compliance requirements
- Recommended Stripe for mature compliance tooling
- Suggested using Stripe Checkout for reduced PCI scope

### Gemini
- Flagged webhook retry complexity
- Suggested idempotency keys for all mutations
- Recommended dead letter queue for failed webhooks

### Codex
- Recommended repository pattern for payment abstraction
- Suggested separating payment domain from order domain
- Proposed event sourcing for payment state

### OpenCode (GPT-4o)
- Suggested circuit breaker for external API resilience
- Recommended correlation IDs for distributed tracing
- Flagged need for webhook signature verification

## Consensus Points
All models agreed on:
1. Idempotency is non-negotiable
2. Webhook signature verification required
3. Need abstraction layer for future flexibility

## Consequences
- Must implement idempotency keys for all payment mutations
- Need webhook signature verification (Stripe provides this)
- Add payment abstraction layer (PaymentGateway interface)
- Implement circuit breaker for Stripe API calls
- Add correlation IDs for tracing across services

## Related
- [Payment Design Doc](../docs/payment-design.md)
- [Kanban Task #42](link-to-task)
```

## wicked-crew Integration

In wicked-crew's design or review phases, add multi-model review as a step:

```yaml
# Phase: design
phase: design
status: in_progress

actions:
  - name: gather_requirements
    status: completed

  - name: draft_design
    status: completed
    output: docs/payment-design.md

  - name: multi_model_review
    status: in_progress
    config:
      models: [claude, gemini, codex, opencode]
      focus:
        - security
        - scalability
        - maintainability
      output: kanban_task_comments

  - name: synthesize_feedback
    status: pending
    depends_on: multi_model_review
```

## Code Review Example

```markdown
# Multi-Model Code Review: auth-service refactor

## Context
PR #123: Refactor authentication to use JWT

## Claude's Review
```
Looking at the JWT implementation:

1. **Token expiry**: 24h is too long for access tokens. Recommend:
   - Access token: 15 minutes
   - Refresh token: 7 days

2. **Secret management**: Hardcoded secret on line 42.
   Should use environment variable or secrets manager.

3. **Algorithm**: Using HS256. Consider RS256 for
   better key rotation support.
```

## Gemini's Review
```
Security concerns:

1. **No token revocation**: Need blacklist for logout
2. **Missing rate limiting**: Auth endpoints vulnerable to brute force
3. **CORS too permissive**: Line 15 allows all origins

Performance note:
- JWT validation on every request adds ~2ms latency
- Consider caching validated tokens briefly
```

## Codex's Review
```
Architecture feedback:

1. **Single responsibility violation**: AuthService handles both
   authentication AND authorization. Split into:
   - AuthenticationService (login, tokens)
   - AuthorizationService (permissions, roles)

2. **Missing interface**: Direct class usage prevents testing.
   Extract IAuthService interface.

3. **Error handling**: Generic exceptions. Create specific:
   - InvalidCredentialsException
   - TokenExpiredException
   - InsufficientPermissionsException
```

## Synthesis

| Issue | Flagged By | Priority | Action |
|-------|------------|----------|--------|
| Token expiry too long | Claude | P0 | Reduce to 15min/7day |
| Hardcoded secret | Claude | P0 | Use env var |
| No token revocation | Gemini | P1 | Add blacklist |
| No rate limiting | Gemini | P1 | Add rate limiter |
| SRP violation | Codex | P2 | Refactor services |

## Decision
Block merge until P0 items resolved. P1 items in follow-up PR.
```

## Design Review Template

```markdown
# Multi-Model Design Review: [Feature Name]

## Document Reviewed
[Link to design doc]

## Review Prompt
"Review this design for security vulnerabilities, scalability concerns,
and architectural issues. Be specific and actionable."

## Perspectives

### Claude
[Paste Claude's analysis]

### Gemini
[Paste Gemini's output]

### Codex
[Paste Codex's output]

### OpenCode
[Paste OpenCode's output]

## Consensus (flagged by 2+ models)
- [ ] Issue 1
- [ ] Issue 2

## Unique Insights
- **Claude only**: [insight]
- **Gemini only**: [insight]
- **Codex only**: [insight]

## Action Items
| Item | Owner | Due |
|------|-------|-----|
| | | |

## Decision
[Final decision and rationale]
```

## Storing Decisions in wicked-mem

After synthesis, persist the decision:

```bash
# Store the decision
/wicked-mem:store "Payment gateway: Stripe with async webhooks.
All models agreed on idempotency requirement.
Circuit breaker recommended by OpenCode." \
  --type decision \
  --tags payments,architecture,multi-model-review

# Store specific learnings
/wicked-mem:store "JWT tokens: Use 15min access / 7day refresh.
24h access tokens flagged as security risk by Claude." \
  --type procedural \
  --tags auth,jwt,security
```
