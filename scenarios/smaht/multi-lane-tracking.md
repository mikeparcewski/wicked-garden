---
name: multi-lane-tracking
title: Topic Switching and Open Thread Tracking
description: Session summary tracks current_task, topics, and open_threads as you switch between work items
type: feature
difficulty: intermediate
estimated_minutes: 6
---

# Topic Switching and Open Thread Tracking

Test that wicked-smaht correctly tracks the current task, accumulates topics across task switches, and preserves open threads in the session summary.

## Setup

Start a Claude Code session with wicked-garden installed. Session state is managed automatically by wicked-smaht and can be inspected via `/wicked-garden:smaht:debug`.

## Steps

1. **Start with a debugging task**
   ```
   I'm working on fixing the user login. Users are getting 401 errors after token refresh.
   ```

   **Expected**: `current_task` tracked as something containing "fixing the user login". Topics updated with "authentication" keyword.

2. **Check current_task was captured**

   Run the debug command to inspect session state:

   ```
   /wicked-garden:smaht:debug
   ```

   Expected: Debug output shows `current_task` set to the login fix task.

3. **Switch to a new task**
   ```
   Let's design the new notification system while we wait for QA.
   ```

   **Expected**: `current_task` updated to the notification task (overwritten, not stacked). Topics accumulate: previous topics remain, "notification" added if it matches the keyword list.

4. **Verify topics accumulate across switches**

   Run `/wicked-garden:smaht:debug` again.

   **Expected**: Debug output shows topics list containing keywords from both tasks. Topics are not cleared on task switch — they accumulate up to 10 entries.

5. **Add an open thread via the assistant**

   Ask Claude a question that requires a follow-up:
   ```
   Should we use WebSockets or polling for the notification delivery?
   ```

   **Expected**: If Claude asks a clarifying question back, it appears in `open_questions`. The assistant's questions (containing `?`) are tracked when they are 15–150 characters.

6. **Inspect the full session state**

   Run `/wicked-garden:smaht:debug` to see the complete session summary.

   Expected structure after switching tasks:
   ```json
   {
     "topics": ["authentication", "notification"],
     "decisions": [],
     "preferences": [],
     "open_threads": [],
     "current_task": "design the new notification system while we wait for qa",
     "active_constraints": [],
     "file_scope": [],
     "open_questions": ["Should we use WebSockets or polling?"]
   }
   ```

7. **Verify turn history shows both tasks**

   Run `/wicked-garden:smaht:debug` and check the turn history section. Both task prompts should appear in the recent turns list.

## Expected Outcome

- `current_task` is a single string — updated (overwritten) with the most recent task statement
- `topics` is a flat list that accumulates across all turns (max 10, oldest dropped when full)
- `open_threads` is managed manually (not auto-populated by turns)
- `open_questions` captures questions from assistant responses
- Switching tasks does NOT reset prior topics — they remain in the list

## Session Summary Fields

| Field | Type | Behavior |
|-------|------|----------|
| `current_task` | string | Overwritten on each new task statement |
| `topics` | list[str] | Accumulates; capped at 10 (oldest removed) |
| `open_threads` | list[str] | Manual/externally managed |
| `open_questions` | list[str] | Set from assistant `?` sentences; trimmed to 3 |
| `file_scope` | list[str] | Files mentioned; capped at 20 (oldest removed) |

## Success Criteria

- [ ] First task statement sets current_task
- [ ] Second task statement overwrites current_task (not appended)
- [ ] Topics from both tasks appear in the topics list
- [ ] Topics list does not exceed 10 entries
- [ ] Assistant questions appear in open_questions
- [ ] Session summary is valid and inspectable via `/wicked-garden:smaht:debug`
- [ ] Turn history shows all turns up to the 5-turn window

## Value Demonstrated

Developers regularly context-switch mid-session. wicked-smaht's flat session summary captures the essential state without complex parallel structures:
1. **Current task tracking** — always know what's active
2. **Topic accumulation** — keywords from all work accumulate for context
3. **Constraint tracking** — "must", "should", "don't" statements are captured automatically
4. **Open questions** — assistant follow-up questions are tracked so they don't get lost
