---
name: multi-lane-tracking
title: Multi-Lane Intent Tracking
description: Concurrent intent tracking with up to 3 active lanes
type: feature
difficulty: intermediate
estimated_minutes: 6
---

# Multi-Lane Intent Tracking

Test that wicked-smaht tracks multiple concurrent goals with priority and recency weighting.

## Setup

Start a Claude Code session. Work on multiple distinct tasks within the same session.

## Steps

1. **Start with a debugging task**
   ```
   The user login is broken. Users are getting 401 errors after token refresh.
   ```

   **Expected**: Lane 1 created with type="debugging", focus=["authentication", "token refresh"]

2. **Switch to a planning task**
   ```
   Let's design the new notification system while we wait for the QA team to test the fix.
   ```

   **Expected**: Lane 2 created with type="planning", focus=["notification system"]. Lane 1 remains active.

3. **Add a third concurrent task**
   ```
   Can you also research how other projects handle rate limiting?
   ```

   **Expected**: Lane 3 created with type="research", focus=["rate limiting"]. All 3 lanes active.

4. **Return to the first task**
   ```
   Back to the auth bug - I think the issue is in the token validation logic.
   ```

   **Expected**: Lane 1 reactivated and priority boosted. Entities updated with "token validation".

5. **Check lane state**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/lanes.jsonl
   ```
   Should show 3 lanes with different priorities based on recency.

6. **Add a fourth task (triggers dormancy)**
   ```
   We also need to fix the broken email templates.
   ```

   **Expected**: Lane 4 created. Least-recently-used lane becomes "dormant" (max 3 active).

## Expected Outcome

- Up to 3 lanes remain active simultaneously
- Lanes track focus hierarchy (e.g., ["auth system", "JWT", "refresh token"])
- Returning to a topic reactivates its lane
- Lane priority decays with inactivity
- Excess lanes become dormant, not deleted

## Lane Data Structure

```json
{
  "lane_id": "lane-abc123",
  "type": "debugging",
  "focus": ["authentication", "token refresh"],
  "entities": ["src/auth/jwt.py", "TokenValidator"],
  "priority": 0.8,
  "turn_created": 1,
  "turn_last_active": 4,
  "status": "active"
}
```

## Success Criteria

- [ ] First task creates Lane 1 with debugging intent
- [ ] Second task creates Lane 2 without closing Lane 1
- [ ] Three lanes can be active simultaneously
- [ ] Returning to first task updates Lane 1 (not creates new lane)
- [ ] Fourth task causes least-used lane to become dormant
- [ ] lanes.jsonl contains all lane history

## Value Demonstrated

Developers rarely work on just one thing. You might be debugging a bug, designing a new feature, and researching best practices - all in the same session.

wicked-smaht's multi-lane tracking:
1. **Maintains context for each goal** - No "forgetting" when you switch tasks
2. **Smart reactivation** - Recognizes when you return to a previous topic
3. **Priority decay** - Recently active lanes get more context priority
4. **Bounded memory** - Max 3 active lanes prevents unbounded growth
5. **History preserved** - Dormant lanes can be reactivated, nothing is lost
