---
name: session-context-injection
title: Session Context Injection
description: SessionStart hook automatically gathers project context on startup
type: integration
difficulty: basic
estimated_minutes: 3
---

# Session Context Injection

Test that wicked-smaht automatically injects relevant context when a Claude Code session starts.

## Setup

Ensure wicked-smaht is installed and hooks are enabled. Optionally have wicked-mem, wicked-kanban, or wicked-crew with existing data.

Ensure wicked-garden is installed. Verify smaht commands are available:

```
/wicked-garden:smaht:help
```

## Steps

1. **Start a new Claude Code session**

   Open Claude Code in a project directory. The SessionStart hook fires automatically.

2. **Observe the startup context**

   Look for context injection in Claude's initial system state. You should see:
   - Session ID created
   - Project context gathered
   - Any relevant memories from wicked-mem (if installed)
   - Active tasks from wicked-kanban (if installed)
   - Current project phase from wicked-crew (if installed)

3. **Verify session context is active**

   Run the debug command to confirm context was gathered:

   ```
   /wicked-garden:smaht:debug
   ```

   Expected: Shows the active session ID, sources queried, and any context items gathered during startup.

4. **Check session metadata** (written at session end by Stop hook)

   After ending the session and starting a new one, run `/wicked-garden:smaht:debug` again. The previous session's metadata (session_id, start_time, end_time, key_topics) should be recorded by the Stop hook.

## Expected Outcome

- New session created and tracked internally
- Session metadata written at session end with session summary
- Context packet injected into Claude's system prompt
- Sources queried based on what's available (graceful degradation)

## Success Criteria

- [ ] Session created on startup (visible via `/wicked-garden:smaht:debug`)
- [ ] Session metadata written at session end with valid session_id and start_time
- [ ] No errors in hook execution (check Claude terminal)
- [ ] Context gathered from available sources (may be empty if none installed)

## Value Demonstrated

wicked-smaht removes the cognitive load of manually gathering context when starting work. Instead of typing "/smaht" or manually recalling what you were working on, the SessionStart hook automatically:

1. Creates a session to track your work
2. Queries available wicked-garden plugins for relevant context
3. Injects that context so Claude is immediately aware of your project state

This makes Claude "ready to work" from the first prompt instead of needing ramp-up conversation.
