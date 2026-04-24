# PR-4 Contract Check — v8 PR-1 Locked Decisions

This document verifies that v8 PR-4 respects the 10 PR-1 locked decisions.
One decision is carved out explicitly (decision #6 — read-only daemon).

## Decision Audit

### Decision #1: SQLite as state store
**Status: RESPECTED**
Both new tables (council_sessions, council_votes) use the same SQLite file
via daemon.db.connect(). WAL mode and foreign keys remain enabled.

### Decision #2: Archetype nullable
**Status: RESPECTED (not applicable to council tables)**
Council tables do not carry archetype fields. The nullable contract for the
existing projects.archetype column is unchanged.

### Decision #3: init_schema is idempotent
**Status: RESPECTED**
New CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS statements were
added to the existing executescript block. Calling init_schema() twice yields
identical schema state (tested implicitly by test_council_schema.py).

### Decision #4: conn.row_factory = sqlite3.Row
**Status: RESPECTED**
council CRUD functions receive conn from db.connect() which always sets
row_factory = sqlite3.Row. dict(row) conversion works identically.

### Decision #5: Named constants from db layer (no magic values, R3)
**Status: RESPECTED**
- _VERDICT_UNAVAILABLE, _VERDICT_TIMEOUT, _VERDICT_ERROR are named constants in council.py
- DEFAULT_TIMEOUT_S, _MIN_QUORUM, _QUESTION_SCAFFOLD are named constants
- COUNCIL_POST_MAX_BODY_BYTES, COUNCILS_LIMIT_DEFAULT, COUNCILS_LIMIT_MAX added to server.py
- _MAX_LIST_COUNCIL_SESSIONS = 200 caps the list query (R5)

### Decision #6: Daemon is read-only (projection only)
**Status: CARVED OUT — documented and justified**

PR-1 decision #6 applies to projection tables (projects, phases, tasks, cursor,
event_log). Council sessions are originated by the daemon, not projected from
bus events. There is no bus event to project from — the caller POSTs a question
and expects the daemon to orchestrate the fan-out synchronously.

This is the second explicit mutation path in the daemon. PR-2 introduced
mutations for event ingestion (wicked.* bus events). PR-4 adds a bounded second
path: council orchestration.

Scope of the carve-out:
- ONLY council_sessions and council_votes tables are writable via HTTP
- All projection tables remain read-only as per PR-1
- The carve-out is documented in:
  - daemon/council.py module docstring
  - daemon/server.py module docstring
  - _handle_post_council() docstring
  - This document

### Decision #7: Touch-null semantic (COALESCE for non-regressing fields)
**Status: RESPECTED (not applicable to council)**
Council sessions do not have "preserve non-null" fields. complete_council_session
uses a plain UPDATE — calling it twice is idempotent via upsert_council_vote's
INSERT OR REPLACE pattern.

### Decision #8: Unknown events return 'ignored', never raise
**Status: RESPECTED**
The projector dispatch table (_HANDLERS in projector.py) is unchanged. No
council events are routed through the projector.

### Decision #9: Timestamp normalisation via _to_epoch
**Status: RESPECTED**
Council timestamps are INTEGER epoch seconds written by int(time.time()) in
db.py. _to_epoch is not needed for council (no ISO-8601 input paths in council
CRUD; timestamps come from Python's time.time() directly).

### Decision #10: Default bind address 127.0.0.1
**Status: RESPECTED**
No changes to make_server() or the DEFAULT_HOST constant. POST /council is
only accessible at 127.0.0.1 by default.

## Summary

| Decision | Status |
|----------|--------|
| #1 SQLite state store | RESPECTED |
| #2 Archetype nullable | RESPECTED (N/A) |
| #3 init_schema idempotent | RESPECTED |
| #4 row_factory sqlite3.Row | RESPECTED |
| #5 Named constants / R3 | RESPECTED |
| #6 Read-only daemon | CARVED OUT — justified |
| #7 Touch-null semantic | RESPECTED (N/A) |
| #8 Unknown events ignored | RESPECTED |
| #9 Timestamp normalisation | RESPECTED |
| #10 Localhost bind | RESPECTED |

## POST /council mutation carve-out justification

The daemon's read-only principle exists to prevent state corruption from
competing writers and to keep the projection model deterministic (replay-safe).
Council sessions do not conflict with these goals:

1. **No bus event to project from**: There is no wicked.council.* event that
   pre-dates the session row. The daemon IS the source for council state.

2. **Bounded scope**: Only 2 tables are mutable via HTTP. The 6 projection
   tables remain read-only.

3. **Synchronous caller contract**: The caller waits for the result. This is
   not a background write that could interleave with projection reads.

4. **Precedent**: PR-2 already established that the daemon can mutate when the
   use case requires it (event ingestion). PR-4 is the second instance of a
   deliberately scoped mutation path.

References: #594 (PR-4 spec), #588 (epic), daemon/council.py, daemon/server.py.
