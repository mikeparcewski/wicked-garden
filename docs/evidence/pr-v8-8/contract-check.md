# Contract Check — v8-PR-8

Issue #592 (v8 PR-8).

## 4th HTTP Write Carve-Out: POST /subscriptions/<id>/toggle

### Decision context

PR-1 established the daemon as read-only with respect to projection tables.
Three explicit write paths were added in subsequent PRs:
1. PR-2: event ingestion (event_log, projects, phases, cursor)
2. PR-4: POST /council (council_sessions, council_votes)
3. PR-7: POST /test-dispatch (test_dispatches)

PR-8 adds a **4th write carve-out**: `POST /subscriptions/<id>/toggle`.

### Justification

- **Bounded scope**: the toggle endpoint ONLY flips the `enabled` flag on an
  existing subscription row. It cannot create, delete, or modify any other field.
- **Operator necessity**: disabling a misbehaving hook subscriber without
  redeploying or editing config files is a legitimate operational requirement.
- **No projection bypass**: hook_subscriptions and hook_invocations are NOT
  projection tables. They are originated by the daemon, not projected from bus
  events. The read-only principle for projection tables (projects, phases, tasks,
  cursor, event_log) is unaffected.
- **Creation NOT exposed over HTTP**: subscriptions are created only via
  file-based config (hooks/subscriptions/*.json) or direct DB calls. HTTP only
  provides the toggle operation.

### Documentation trail

- `daemon/hook_dispatch.py` module docstring: "HTTP toggle (POST /subscriptions/<id>/toggle)
  is a bounded write exception for operator control"
- `daemon/server.py` `_handle_post_subscription_toggle` docstring: "MUTATION CARVE-OUT (4th write path, v8-PR-8 #592)"
- `daemon/db.py` `hook_subscriptions` CREATE TABLE comment: "This is the fourth explicit write path"
- This file: `docs/evidence/pr-v8-8/contract-check.md`

## PR-1 decisions respected

| Decision | Status |
|----------|--------|
| #6: daemon read-only for projection tables | RESPECTED — hook tables are not projection tables |
| #10: bind to 127.0.0.1 only | RESPECTED — no change to server binding |
| Stdlib only | RESPECTED — hook_dispatch.py uses subprocess, json, sqlite3, uuid, logging, time, pathlib |
| No new external deps | RESPECTED — requirements.txt unchanged |
| Graceful degradation | RESPECTED — dispatch_event_to_subscribers returns [] on error, never raises |
| Fail-open on missing config dir | RESPECTED — load_subscriptions_from_config returns 0, logs debug |

## v9 plugin contract (drop-in-plugin-contract.md)

| Contract item | Status |
|---|---|
| Dispatch TO wicked-testing via canonical skills only | N/A — hook_dispatch is independent of wicked-testing |
| No re-implementation of external plugin logic | RESPECTED — hook handlers are thin delegates |
| Graceful degradation when plugins unavailable | RESPECTED — FileNotFoundError → handler_error verdict, no crash |

## Write path summary (all 4)

| PR | Endpoint / operation | Tables written | Justification |
|---|---|---|---|
| PR-2 | consumer batch (no HTTP) | event_log, projects, phases, cursor | Bus event ingestion (core function) |
| PR-4 | POST /council | council_sessions, council_votes | Council sessions originated by daemon |
| PR-7 | POST /test-dispatch | test_dispatches | Test dispatch decisions originated by daemon |
| PR-8 | POST /subscriptions/<id>/toggle | hook_subscriptions (enabled flag only) | Operator control for hook subscriber management |
