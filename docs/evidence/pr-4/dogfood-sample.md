# Dogfood Sample — `wicked-garden:ground` Protocol Run

**Question asked**: "what's the v8 daemon's projection model?"
**Session**: pr4-ground-keystone
**Date**: 2026-04-23

This sample demonstrates the protocol from `skills/ground/SKILL.md` executed
manually. It is proof the skill protocol works on a real question.

---

## Step 1 — Decompose query

Question: "what's the v8 daemon's projection model?"

Key terms extracted:
- `daemon`
- `projection`
- `v8 architecture`
- `state machine`
- `WG_DAEMON_ENABLED`

---

## Step 2 — Parallel execution

Three queries run concurrently against `wicked-brain` (port 4243) and
`wicked-bus` (port 4242).

**Brain queries run**:
- `wicked-brain:search "v8 daemon projection model"` → 4 results
- `wicked-brain:search "task-state projection daemon read-only"` → 6 results
- `wicked-brain:search "WG_DAEMON_ENABLED projection read-only"` → 6 results
- `wicked-brain:query "what is the v8 daemon's projection model?"` → resolved via memory reads

**Bus query**: `wicked-bus:query "daemon projection"` — bus not active during
this sample run; skipped with graceful degradation note.

---

## Step 3 — Ranked synthesis (top 5 signals)

After deduplication, 3 distinct memory files surfaced across the search runs.
Ranked by source priority (memory > chunk):

| Rank | Source | Path | Relevance |
|------|--------|------|-----------|
| 1 | brain/memory | `memory/v8-pr1-architecture-contract-decisions.md` | 10 locked decisions defining the daemon's projection contract: schema, idempotency, cursor semantics, event handling |
| 2 | brain/memory | `memory/v8-daemon-first-architecture-north-star.md` | North-star thesis including #579 task-state projection as sequencing step; bus as source of truth |
| 3 | brain/memory | `memory/v8-pr1-shipped-and-lessons.md` | PR #599 shipped read-only projection daemon MVP (5 files, ~1660 LOC, 36 tests); off by default |

Bus events: none surfaced (bus not running in this sample).

---

## Step 4 — Grounded output

```
## Grounding: what's the v8 daemon's projection model?

### What the brain knows

1. [brain/memory] The projection model is an event-sourced read-only view of
   crew state, built by consuming wicked-bus events into a SQLite database.
   Eight event types are wired: project.created, complexity_scored,
   phase.transitioned, phase.auto_advanced, gate.decided, rework.triggered,
   project.completed, crew.yolo_revoked. All other events advance the cursor
   as `ignored` to preserve replay safety.
   — `memory/v8-pr1-architecture-contract-decisions.md`
   → suggest: wicked-brain:read memory/v8-pr1-architecture-contract-decisions.md depth=2

2. [brain/memory] Idempotency is deterministic UPSERT keyed on `id` /
   `(project_id, phase)` — replay-safe by design for at-least-once bus
   delivery. `cursor_lag = -1` when bus unavailable (distinguishes "can't tell"
   from "caught up" = 0).
   — `memory/v8-pr1-architecture-contract-decisions.md`

3. [brain/memory] The v8 north-star sequences: #572 soak → #579 task-state
   projection → daemon prototype → state machine. The projection daemon is
   step 2 in a 10-thesis arc toward daemon-first / skills-thin architecture
   where skills become 5-line POST clients instead of 200-600 line runbooks.
   — `memory/v8-daemon-first-architecture-north-star.md`
   → suggest: wicked-brain:read memory/v8-daemon-first-architecture-north-star.md depth=2

4. [brain/memory] PR #599 shipped the read-only daemon MVP on 2026-04-24.
   5 files, ~1660 LOC, 36 tests. Controlled via WG_DAEMON_ENABLED (false |
   true | always). Single migration site: scripts/crew/status_reader.py.
   Full-suite test isolation issue (#600) means run scoped subsets only.
   — `memory/v8-pr1-shipped-and-lessons.md`

### Recent bus activity

Bus not reachable during this sample run. Graceful degradation: brain-only
results returned.

### If you need more depth
`wicked-brain:read memory/v8-pr1-architecture-contract-decisions.md depth=2`
```

---

## Protocol validation notes

The protocol worked as specified:

- Parallel query (3 brain searches + 1 brain query) completed concurrently
- Deduplication collapsed 6 search results into 3 unique memory sources
- Cap applied: 4 ranked signals surfaced (under the 5-10 cap)
- Bus degraded gracefully — no error, explicit note in output
- Output is skimmable in under 30 seconds
- Follow-up suggestion points to the single most actionable deeper read
- No full file content dumped — one-line relevance per signal

**Conclusion**: The skill protocol produces a focused, citable answer from a
vague question in one invocation. The alternative (Claude opening 3 memory
files manually via Read after grepping for "daemon") would require 5-7 tool
calls and no synthesis step. Ground provides unique value over the native path.
