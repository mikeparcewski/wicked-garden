---
name: memory-promotion
title: Cross-Session Continuity via session_meta.json
description: Session metadata persisted on session end enables new sessions to recall recent topics and decisions
type: feature
difficulty: intermediate
estimated_minutes: 7
---

# Cross-Session Continuity via session_meta.json

Test that wicked-smaht persists session metadata when a session ends, and that a new session can recall that context at startup.

## Setup

No additional plugins required. This scenario tests wicked-smaht's built-in cross-session recall using local storage only.

## Steps

### Session 1: Generate and Persist Context

1. **Create decisions and topics in session**
   ```
   Let's use Redis for caching. We'll use Postgres as the primary database.
   ```

   Decisions and topics are captured in summary.json.

2. **Create file scope context**
   ```
   I'm working on src/cache/redis_client.py and src/db/connection.py.
   ```

   File mentions are tracked in `file_scope`.

3. **Verify session state before ending**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/summary.json
   ```

   Should show `decisions`, `topics`, and `file_scope` populated.

4. **End the session**

   Close Claude Code. The Stop hook fires `session_end.py` which calls `persist_session_meta()`.

5. **Verify session_meta.json was written**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/session_meta.json
   ```

   Expected structure:
   ```json
   {
     "session_id": "...",
     "start_time": "2026-...",
     "end_time": "2026-...",
     "turn_count": 2,
     "key_topics": ["redis_client.py", "connection.py", "caching"],
     "decisions_made": [
       "use redis for caching",
       "use postgres as the primary database"
     ],
     "current_task": "",
     "files_touched": ["src/cache/redis_client.py", "src/db/connection.py"]
   }
   ```

### Session 2: Verify Cross-Session Recall

6. **Start a new Claude Code session**

   The SessionStart hook fires `session_start.py`. It calls `HistoryCondenser.load_recent_sessions()`, which reads `session_meta.json` files from past sessions.

7. **Look for the previous session context in the startup message**

   At session start, the context injected into Claude includes a "Previous sessions:" section listing recent sessions with their topics, turn count, and age.

   Example startup reminder:
   ```
   Previous sessions:
     - redis_client.py, connection.py, caching (2 turns, 1h ago) — use redis for caching
   ```

8. **Ask about prior context**
   ```
   What caching approach did we decide on?
   ```

   **Expected**: Claude references the Redis decision from the session startup context. The answer comes from the injected session summary, not from wicked-mem.

9. **Verify load_recent_sessions finds the past session**
   ```bash
   python3 -c "
   import sys
   sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'scripts', 'smaht'))
   from history_condenser import HistoryCondenser
   sessions = HistoryCondenser.load_recent_sessions(max_sessions=3)
   for s in sessions:
       print(s.get('session_id', '?'), '|', s.get('decisions_made', []))
   "
   ```

## Expected Outcome

- Stop hook writes `session_meta.json` with `start_time`, `end_time`, `turn_count`, `key_topics`, `decisions_made`, `files_touched`
- `load_recent_sessions()` returns metadata sorted newest-first (by `session_meta.json` mtime)
- New session's startup message includes "Previous sessions:" section
- Up to 3 recent sessions are surfaced
- Sessions with zero turns and no topics are not persisted (skipped by the `if turn_count == 0 and not topics` guard)

## Persistence Rules

| What is saved | Where | When |
|--------------|-------|------|
| Full session state | `summary.json` + `turns.jsonl` | After every turn |
| Cross-session snapshot | `session_meta.json` | On session end (Stop hook) |
| Max key_topics saved | 5 | Sliced from `summary.topics` |
| Max decisions saved | 3 | Sliced from `summary.decisions` |
| Max files saved | 10 | Sliced from `summary.file_scope` |

## What Is NOT Promoted

- No calls are made to wicked-mem — cross-session recall is entirely local to wicked-smaht storage
- `promoted_at` markers do not exist — idempotency is handled by the Stop hook only running once per session end
- Fact types (decision/discovery/artifact) do not exist — only the flat `decisions` list from the session summary

## Success Criteria

- [ ] summary.json contains decisions from the session
- [ ] session_meta.json is created on session end
- [ ] session_meta.json contains start_time, end_time, and decisions_made
- [ ] New session startup message includes "Previous sessions:" section
- [ ] Past session's decisions are referenced in the startup context
- [ ] Empty sessions (0 turns, no topics) do not create session_meta.json
- [ ] load_recent_sessions returns sessions sorted newest-first

## Value Demonstrated

Session context survives session boundaries without requiring wicked-mem:
1. **Zero configuration** — Persistence happens automatically on session end
2. **Local storage only** — No external plugin dependency for cross-session recall
3. **Recency-ranked** — Newest sessions surface first in the startup context
4. **Bounded footprint** — Only the top 5 topics and 3 decisions are preserved per session
