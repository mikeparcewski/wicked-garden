---
name: returning-user
title: The Returning User
description: Agent recalls context when user returns after time away
type: workflow
difficulty: basic
estimated_minutes: 5
---

# The Returning User

Test that memory provides continuity across sessions without requiring manual recall.

## Setup

Create a realistic project context with stored decisions and preferences:

1. Create a sample project directory:
   ```bash
   mkdir -p ~/test-projects/payment-api
   cd ~/test-projects/payment-api
   ```

2. Store a recent architectural decision:
   ```
   /wicked-mem:store "We chose TypeScript over JavaScript for the payment API. Reasons: (1) Stripe SDK has excellent TypeScript types that catch integration errors at compile time, (2) Financial data handling benefits from strict null checks, (3) Team already uses TS in the frontend so no new tooling needed. Trade-off: slightly slower iteration for prototypes." --type decision --tags tech-stack,typescript,payments
   ```

3. Store a code style preference:
   ```
   /wicked-mem:store "User prefers early returns over nested if/else blocks for readability. Use guard clauses at function start, then handle the happy path without indentation." --type preference --tags code-style,readability
   ```

4. Store an episodic memory from recent work:
   ```
   /wicked-mem:store "Stripe webhook signature verification was failing intermittently. Root cause: body-parser middleware was consuming the raw body before signature verification. Fix: use express.raw() for webhook endpoint, express.json() for others. Key learning: webhook verification requires the raw request body." --type episodic --tags stripe,webhooks,debugging
   ```

## Steps

1. **Simulate session restart**
   - Close and reopen Claude Code, OR
   - Start a new conversation thread

2. **Ask a question that should trigger memory recall**
   - Ask: "I'm going to add a new endpoint to handle refunds. What language is this project using?"
   - Ask: "Can you write a validation function for the refund amount?"

3. **Verify automatic memory injection**
   - Check if the agent mentions TypeScript without being told
   - Check if the code uses early returns (the preference)
   - Check if there's any mention of the webhook learning if relevant

4. **Test explicit recall**
   ```
   /wicked-mem:recall "TypeScript"
   /wicked-mem:recall --type preference
   /wicked-mem:recall --tags stripe
   ```

## Expected Outcome

- Agent automatically has context about the TypeScript decision
- Agent writes code following the early return preference
- Agent can explain the rationale for past choices
- Manual recall commands retrieve all stored memories correctly
- No need to re-explain project setup or past decisions

## Success Criteria

- [ ] Decision memory is stored and retrievable via /wicked-mem:recall
- [ ] Preference memory is stored and retrievable
- [ ] Episodic memory is stored with proper tags
- [ ] Agent demonstrates awareness of TypeScript without being told (SessionStart hook working)
- [ ] Agent follows the early return preference in generated code
- [ ] /wicked-mem:stats shows 3 memories (1 decision, 1 preference, 1 episodic)

## Value Demonstrated

Agent feels like a colleague who remembers your project's history, not a stranger requiring full onboarding every session. Eliminates the "context reset" problem where you repeat yourself across sessions. Particularly valuable for:
- Returning to a project after days/weeks
- Onboarding new team members (agent explains past decisions)
- Maintaining consistency (preferences are automatically applied)
