---
name: memory-promotion
title: Cross-Session Memory Promotion
description: Session facts promoted to wicked-mem on session end for cross-session learning
type: integration
difficulty: intermediate
estimated_minutes: 7
---

# Cross-Session Memory Promotion

Test that wicked-smaht promotes valuable facts to wicked-mem when a session ends.

## Prerequisites

- wicked-mem must be installed for this scenario
- Run `/wicked-mem:stats` to verify wicked-mem is available

## Setup

Start a Claude Code session and generate some facts worth preserving.

## Steps

1. **Create facts in session**
   ```
   Let's use Redis for caching. I discovered that the memory leak was in the connection pool.
   ```

   Creates decision and discovery facts.

2. **Create an artifact**
   ```
   Create src/cache/redis_client.py with the connection pool fix.
   ```

3. **Verify facts exist in session**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/facts.jsonl | wc -l
   ```
   Should show multiple facts.

4. **End the session**

   Close Claude Code or run the session cleanup. The session end triggers promotion.

5. **Verify promotion marker**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/meta.json | grep promoted_at
   ```
   Should show `"promoted_at": "2026-..."` timestamp.

6. **Check wicked-mem received facts**
   ```bash
   /wicked-mem:recall redis caching
   ```
   Should return the decision about using Redis.

7. **Start new session and verify recall**

   Start a new Claude Code session:
   ```
   What caching approach did we decide on?
   ```

   wicked-smaht should retrieve the Redis decision from wicked-mem.

## Expected Outcome

- High-value facts (decisions, discoveries) promoted to wicked-mem
- Low-value facts (context reads) not promoted
- Promotion is idempotent (promoted_at marker prevents duplicates)
- New sessions can recall facts from previous sessions via wicked-mem

## Promotion Rules

| Fact Type | Promoted | Reason |
|-----------|----------|--------|
| decision | Yes | High value - architectural choices |
| discovery | Yes | High value - debugging insights |
| problem_solved | Yes | High value - solutions |
| artifact | Sometimes | Only significant files |
| context | No | Low value - just file reads |

## Idempotency

The `promoted_at` marker in meta.json ensures:
- Facts are only promoted once per session
- Re-running promotion is safe (no duplicates)
- Session can be "re-promoted" only if marker is cleared

## Success Criteria

- [ ] Facts created during session
- [ ] Session end triggers promotion logic
- [ ] meta.json shows promoted_at timestamp
- [ ] Decisions/discoveries appear in wicked-mem
- [ ] Context facts NOT promoted (low value)
- [ ] New session can recall promoted facts
- [ ] Re-closing session doesn't create duplicates

## Value Demonstrated

Session-scoped storage is great for in-session recall, but what about next week when you forget the caching decision?

wicked-smaht's memory promotion:
1. **Cross-session learning** - Valuable facts survive session boundaries
2. **Automatic curation** - Only promotes high-value facts (decisions, discoveries)
3. **Idempotent safety** - No duplicate memories from re-promotion
4. **Integration with wicked-mem** - Leverages existing memory infrastructure
5. **Zero configuration** - Promotion happens automatically on session end
