---
name: intent-based-retrieval
title: Intent-Based Context Retrieval
description: Intent detection adjusts source weights for debugging vs planning vs implementation
type: feature
difficulty: basic
estimated_minutes: 5
---

# Intent-Based Context Retrieval

Test that wicked-smaht detects query intent and adjusts context retrieval accordingly.

## Setup

Start a Claude Code session in a project with some existing code. The UserPromptSubmit hook runs on each turn.

## Steps

1. **Test debugging intent detection**

   Send a prompt with debugging signals:
   ```
   Why is the authentication failing? I'm getting a 401 error on login.
   ```

   **Expected**: Intent detected as "debugging" with high confidence. Search source weighted higher for error patterns.

2. **Test planning intent detection**

   Send a prompt with planning signals:
   ```
   I need to design the new API for user management. What's our current approach?
   ```

   **Expected**: Intent detected as "planning". wicked-jam and wicked-crew weighted higher for design context.

3. **Test implementation intent detection**

   Send a prompt with implementation signals:
   ```
   Add a logout endpoint that invalidates the JWT token.
   ```

   **Expected**: Intent detected as "implementation". wicked-kanban weighted higher for task context.

4. **Test research intent detection**

   Send a prompt with research signals:
   ```
   How does the caching layer work in this codebase?
   ```

   **Expected**: Intent detected as "research". wicked-search weighted higher.

5. **Verify intent in session data**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/turns.jsonl | tail -4
   ```
   Each turn should show `intent_type` field.

## Expected Outcome

- Different intents trigger different retrieval strategies
- Debugging queries prioritize error context and recent changes
- Planning queries prioritize design docs and brainstorm sessions
- Implementation queries prioritize task context and code patterns
- Research queries prioritize broad search coverage

## Processing Modes

| Confidence | Mode | Latency | Sources |
|------------|------|---------|---------|
| High (>0.7) | Fast | <500ms | 1-3 most relevant |
| Medium (0.4-0.7) | Deep | <1s | All sources |
| Low (<0.4) | Deep+Broad | >1s | All sources, wider retrieval |

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
