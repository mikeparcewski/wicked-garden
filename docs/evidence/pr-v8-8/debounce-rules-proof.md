# Debounce Rules Proof — Worked Examples

Issue #592 (v8 PR-8).

## Rule 1: phase-boundary

**When:** Fire once per unique `(project_id, phase)` pair extracted from the event payload.

**Scenario:** The gate adjudicator emits two `wicked.gate.decided` events for
`(project=my-project, phase=design)` in quick succession (race condition in the
bus consumer). The second event must be silenced.

```
Event 1: {event_type: "wicked.gate.decided", payload: {project_id: "my-project", phase: "design", result: "APPROVE"}}
  → filter_pattern "wicked.gate.*" matches ✓
  → debounce check: no prior DISPATCHED rows for "wicked.gate.decided:my-project:design" ✓
  → handler invoked → verdict = DISPATCHED
  → invocation row written with event_type = "wicked.gate.decided:my-project:design" for lookup

Event 2: {event_type: "wicked.gate.decided", payload: {project_id: "my-project", phase: "design", result: "APPROVE"}}
  → filter_pattern "wicked.gate.*" matches ✓
  → debounce check: 1 DISPATCHED row found for "wicked.gate.decided:my-project:design" within 24h ✓
  → handler NOT invoked → verdict = DEBOUNCED
  → invocation row written with verdict = "debounced"

Event 3: {event_type: "wicked.gate.decided", payload: {project_id: "my-project", phase: "build"}}
  → filter_pattern "wicked.gate.*" matches ✓
  → debounce check: no DISPATCHED row for "wicked.gate.decided:my-project:build" ✓
  → handler invoked → verdict = DISPATCHED
  (different phase — new boundary)
```

## Rule 2: once-per-session

**When:** Fire once per unique `session_id` in the event payload.

**Scenario:** A session-end fact emission hook should fire only once per
session even if the session-end event is replayed (bus at-least-once delivery).

```
Event 1: {event_type: "wicked.session.ended", payload: {session_id: "abc-123", facts: [...]}}
  → filter_pattern "wicked.session.*" matches ✓
  → debounce check: no DISPATCHED row for "wicked.session.ended:session:abc-123" ✓
  → handler invoked → verdict = DISPATCHED

Event 2: same event replayed (at-least-once delivery):
  → filter_pattern "wicked.session.*" matches ✓
  → debounce check: 1 DISPATCHED row found for "wicked.session.ended:session:abc-123" within 8h ✓
  → handler NOT invoked → verdict = DEBOUNCED

Event 3: {event_type: "wicked.session.ended", payload: {session_id: "xyz-789"}}
  → filter_pattern "wicked.session.*" matches ✓
  → debounce check: no DISPATCHED row for "wicked.session.ended:session:xyz-789" ✓
  → handler invoked → verdict = DISPATCHED
  (different session — new boundary)
```

## Rule 3: rate-limit

**When:** At most M invocations per N seconds (sliding window).

**Scenario:** A noisy event type fires many times per minute. A handler with
expensive external I/O needs rate-limiting to at most 2 dispatches per 60 seconds.

Config: `{"type": "rate-limit", "window_s": 60, "max": 2}`

```
T=0s  Event 1 → 0 DISPATCHED rows in window → handler invoked → DISPATCHED (count now 1)
T=10s Event 2 → 1 DISPATCHED row in window → handler invoked → DISPATCHED (count now 2)
T=20s Event 3 → 2 DISPATCHED rows in window (≥ max=2) → DEBOUNCED
T=30s Event 4 → 2 DISPATCHED rows in window → DEBOUNCED
T=61s Event 5 → window starts at T=1s; T=0 dispatch is OUTSIDE window → count=1 → DISPATCHED
T=71s Event 6 → window starts at T=11s; T=10 dispatch is OUTSIDE window → count=1 → DISPATCHED
```

Window is evaluated against the most recent M `hook_invocations` rows with
`verdict = "dispatched"` for the subscription, within `window_s` seconds.

## Window constants

| Rule | Window | Constant |
|------|--------|----------|
| phase-boundary | 86,400s (24h) | `_PHASE_BOUNDARY_WINDOW_S` |
| once-per-session | 28,800s (8h) | `_SESSION_WINDOW_S` |
| rate-limit | configurable | `window_s` field in rule JSON |
