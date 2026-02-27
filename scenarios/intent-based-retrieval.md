---
name: intent-based-retrieval
title: Intent-Based Context Retrieval
description: Intent detection selects relevant adapters for debugging vs planning vs implementation
type: feature
difficulty: basic
estimated_minutes: 5
---

# Intent-Based Context Retrieval

Test that wicked-smaht detects query intent and selects relevant context adapters accordingly.

## Setup

Start a Claude Code session in a project with some existing code. The UserPromptSubmit hook runs on each turn.

## Steps

1. **Test debugging intent detection**

   Send a prompt with debugging signals:
   ```
   Why is the authentication failing? I'm getting a 401 error on login.
   ```

   **Expected**: Intent detected as "debugging" with high confidence. On the fast path, search, mem, and delegation adapters are selected for error context.

2. **Test planning intent detection**

   Send a prompt with planning signals:
   ```
   I need to design the new API for user management. What's our current approach?
   ```

   **Expected**: Intent detected as "planning". Escalates to slow path (planning is always comprehensive) — all adapters queried including jam (brainstorms) and crew (project state).

3. **Test implementation intent detection**

   Send a prompt with implementation signals:
   ```
   Implement a logout function that creates an endpoint to invalidate JWT tokens.
   ```

   **Expected**: Intent detected as "implementation" with high confidence. On the fast path, search, mem, kanban, context7, startah, and delegation adapters are selected for task context.

4. **Test research intent detection**

   Send a prompt with research signals:
   ```
   How does the caching layer work in this codebase?
   ```

   **Expected**: Intent detected as "research" with high confidence. On the fast path, search, mem, context7, startah, and delegation adapters are selected for broad code understanding.

5. **Verify intent in session data**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/turns.jsonl | tail -4
   ```
   Each turn should show `intent_type` field. Note: turns.jsonl is populated by the orchestrator's `add_turn()` method during context gathering. Verification requires a live Claude Code session with the UserPromptSubmit hook active.

## Expected Outcome

- Different intents select different adapter sets for context retrieval
- Debugging queries select search and mem adapters for error context and recent changes
- Planning queries escalate to slow path for comprehensive context from all adapters
- Implementation queries select kanban, search, mem, and context7 for task and code context
- Research queries select search, mem, context7, and startah for broad coverage

## Processing Modes

| Trigger | Mode | Latency | Sources |
|---------|------|---------|---------|
| Continuation/confirmation | Hot | <100ms | Session state only |
| High confidence (>0.7), simple request | Fast | <500ms | Intent-specific adapters (2-6) |
| Low confidence, planning, competing intents, etc. | Slow | <5s | All adapters + history |

Escalation to slow path triggers on: confidence < 0.5, competing intents, > 5 entities, history reference, planning/design request, novel topic, > 200 words, or compound request.

## Success Criteria

- [ ] Debugging prompt detected as intent_type: "debugging"
- [ ] Planning prompt detected as intent_type: "planning"
- [ ] Implementation prompt detected as intent_type: "implementation"
- [ ] Research prompt detected as intent_type: "research"
- [ ] turns.jsonl records intent for each turn
- [ ] Different prompts show different confidence levels

## Value Demonstrated

Not all queries need the same context. A debugging session needs error logs and recent changes, while a planning session needs design documents and brainstorm notes.

wicked-smaht's intent detection ensures:
1. **Relevant context** - You get what you need, not everything
2. **Faster responses** - High confidence = Fast mode (<500ms)
3. **Better accuracy** - Low confidence triggers broader retrieval
4. **No manual configuration** - Intent detection is automatic via pattern matching (no LLM call in hot path)
