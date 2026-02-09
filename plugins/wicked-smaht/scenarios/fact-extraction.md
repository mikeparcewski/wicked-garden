---
name: fact-extraction
title: Fact Extraction and Ledger
description: Automatic extraction of decisions, discoveries, and artifacts from conversation
type: feature
difficulty: intermediate
estimated_minutes: 5
---

# Fact Extraction and Ledger

Test that wicked-smaht automatically extracts structured facts from conversation turns.

## Setup

Start a Claude Code session and have a conversation that includes decisions, discoveries, and artifact creation.

## Steps

1. **Make a decision**
   ```
   Let's use JWT tokens for authentication instead of session cookies.
   ```

   **Expected**: Decision fact extracted with subject="JWT tokens", predicate="use for authentication"

2. **Document a discovery**
   ```
   I found that the bug was caused by the token refresh not updating the expiry time.
   ```

   **Expected**: Discovery fact extracted with subject="token refresh bug"

3. **Create an artifact**

   Have Claude create or edit a file:
   ```
   Create a new file src/auth/jwt_validator.py with the token validation logic.
   ```

   **Expected**: Artifact fact extracted from Write tool result

4. **Solve a problem**
   ```
   Great, that fixed the authentication issue!
   ```

   **Expected**: Problem_solved fact extracted

5. **View extracted facts**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/facts.jsonl
   ```

6. **Check entity indexing**

   Facts should be indexed by entity for O(1) lookup:
   ```bash
   grep "jwt" ~/.something-wicked/wicked-smaht/sessions/*/facts.jsonl
   ```

## Expected Outcome

- Facts extracted from user prompts (decisions, discoveries)
- Facts extracted from tool results (artifacts)
- Each fact has UUID-based ID
- Facts include source attribution ("user", "tool:Write", etc.)
- Facts indexed by entity for fast lookup

## Fact Types

| Type | Pattern | Confidence |
|------|---------|------------|
| decision | "let's use", "going with", "decided to" | 0.7 |
| discovery | "found that", "turns out", "realized" | 0.6 |
| artifact | Write/Edit tool creates file | 1.0 |
| problem_solved | "fixed", "solved", "resolved" | 0.8 |
| context | Read tool accesses file | 0.5 |

## Fact Data Structure

```json
{
  "id": "f-3-user-550e8400-e29b-41d4-a716-446655440000",
  "type": "decision",
  "subject": "JWT tokens",
  "predicate": "use for authentication instead of session cookies",
  "entities": ["JWT", "authentication", "session cookies"],
  "turn": 3,
  "source": "user",
  "excerpt": "Let's use JWT tokens for authentication instead of session cookies.",
  "confidence": 0.7
}
```

## Success Criteria

- [ ] Decision detected from "let's use" pattern
- [ ] Discovery detected from "found that" pattern
- [ ] Artifact fact created when file is written
- [ ] Problem_solved fact created on "fixed" pattern
- [ ] Facts have full UUID IDs (not truncated)
- [ ] Facts indexed by entity
- [ ] facts.jsonl contains all extracted facts

## Value Demonstrated

Conversations contain valuable information that's usually lost:
- What decisions were made and why
- What was discovered during debugging
- What files were created or modified
- What problems were solved

wicked-smaht's fact extraction:
1. **Automatic capture** - No manual "remember this" commands needed
2. **Structured format** - Subject/predicate/entity triples for querying
3. **Provenance tracking** - Know where each fact came from
4. **Entity indexing** - O(1) lookup by file, symbol, or concept
5. **Session-scoped** - Facts persist for the session, then promote to wicked-mem
