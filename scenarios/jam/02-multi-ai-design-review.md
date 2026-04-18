---
name: multi-ai-design-review
title: Multi-AI Architecture Review
description: Demonstrates using multiple AI models to review a design document with a native task as shared context
type: workflow
difficulty: advanced
estimated_minutes: 20
---

# Multi-AI Architecture Review

Tests the complete workflow of conducting a design review with multiple AI models (Claude, Gemini, Codex, OpenCode) using a native task as a shared context layer.

## Setup

Prerequisites:
```bash
# Ensure AI CLI tools are installed (if available)
which gemini codex opencode

# Create a test design document
mkdir -p /tmp/design-review-test
cd /tmp/design-review-test

cat > payment-integration.md <<'EOF'
# Payment Integration Design

## Overview
Add Stripe payment processing to the e-commerce checkout flow.

## Architecture
- Frontend: Stripe.js for tokenization
- Backend: REST API endpoint /api/payments
- Async: Webhook handler for payment events
- Storage: PostgreSQL payments table

## Flow
1. User submits payment form
2. Frontend tokenizes card with Stripe.js
3. Backend creates PaymentIntent with Stripe API
4. Stripe sends webhook on payment completion
5. Backend updates order status

## Error Handling
- Retry failed payments up to 3 times
- Log all Stripe API errors
- Show user-friendly error messages

## Security
- PCI DSS Level 1 compliant (via Stripe)
- HTTPS only
- Validate webhook signatures
EOF
```

## Steps

1. **Create a native task for the review**

   In Claude Code conversation, invoke:
   ```
   TaskCreate(
     subject="Design Review: Payment Integration",
     metadata={
       "event_type": "task",
       "chain_id": "payment-integration-review.root",
       "source_agent": "multi-model-review",
       "priority": "P0",
       "initiative": "payment-integration-review"
     }
   )
   ```

   Expected: Task created with a unique id. PreToolUse validates the metadata per scripts/_event_schema.py.

2. **Add design document to task description**

   ```bash
   # Copy task ID from previous step
   TASK_ID="PROJ-001"  # Replace with actual ID

   # Add design as task context
   cat payment-integration.md
   ```

   In Claude Code, ask: "Add this design document to the task description"

3. **Get Claude's perspective**

   In Claude Code conversation:
   ```
   Review this payment integration design. Focus on:
   1. Security risks and PCI compliance
   2. Webhook reliability and idempotency
   3. Error handling gaps
   4. Scalability concerns

   Be specific and actionable.
   ```

   Expected: Claude provides detailed analysis.

4. **Get Gemini's perspective (if available)**

   ```bash
   cat payment-integration.md | gemini "Review this payment integration design. Focus on:
   1. Security risks and PCI compliance
   2. Webhook reliability and idempotency
   3. Error handling gaps
   4. Scalability concerns

   Be specific and actionable."
   ```

   Expected: Gemini returns analysis output.

5. **Get Codex's perspective (if available)**

   ```bash
   cat payment-integration.md | codex exec "Review this payment integration design. Focus on:
   1. Security risks and PCI compliance
   2. Webhook reliability and idempotency
   3. Error handling gaps
   4. Scalability concerns

   Be specific and actionable."
   ```

   Expected: Codex returns analysis output.

6. **Get OpenCode's perspective (if available)**

   ```bash
   opencode run "Review this payment integration design. Focus on:
   1. Security risks and PCI compliance
   2. Webhook reliability and idempotency
   3. Error handling gaps
   4. Scalability concerns

   Be specific and actionable." -f payment-integration.md -m openai/gpt-4o
   ```

   Expected: OpenCode returns analysis output.

7. **Append all AI perspectives to the task description**

   In Claude Code conversation, run TaskUpdate(taskId, description="{previous}\n\n## Claude\n...\n\n## Gemini\n...\n\n## Codex\n...\n\n## OpenCode\n...") so the single task description is the source of truth.

8. **Synthesize findings and identify consensus**

   In Claude Code conversation:
   ```
   Analyze all AI perspectives and:
   1. List issues flagged by multiple models (high confidence)
   2. Note unique insights from individual models
   3. Prioritize action items
   4. Draft an Architecture Decision Record
   ```

9. **Verify task contains all perspectives**

   Read the native task JSON under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/` to confirm the description contains all AI perspectives.

   Expected: Task description shows appended sections for each AI.

## Expected Outcome

- Native task created successfully (metadata validated by PreToolUse)
- Design document added to task description
- Multiple AI perspectives captured (Claude always available, others if installed)
- All perspectives appended to the task description via TaskUpdate
- Synthesis identifies:
  - Consensus issues (e.g., need for idempotency keys, webhook signature verification)
  - Unique insights (e.g., circuit breaker pattern, repository abstraction)
  - Clear action items with priority
- Architecture Decision Record drafted with all perspectives

## Success Criteria

- [ ] Native task created for design review
- [ ] Design document accessible to all AI models
- [ ] Claude provides detailed analysis
- [ ] If Gemini available: Gemini analysis captured
- [ ] If Codex available: Codex analysis captured
- [ ] If OpenCode available: OpenCode analysis captured
- [ ] All AI perspectives appended to the task description
- [ ] Synthesis identifies at least 2 consensus issues
- [ ] Synthesis identifies at least 1 unique insight per model
- [ ] Action items prioritized based on multi-model agreement
- [ ] Workflow demonstrates persistent cross-session context

## Value Demonstrated

This scenario proves wicked-garden enables **multi-model collaboration** for higher-quality design decisions. By using a native task description as shared context, teams can:
- Get diverse AI perspectives on critical architecture decisions
- Identify high-confidence issues through consensus
- Catch blind spots unique to individual models
- Maintain persistent conversation history across sessions

This workflow transforms AI from "another opinion" to a **peer review team** with complementary expertise.
