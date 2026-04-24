# Handler Chain Proof — Worked Example

Issue #592 (v8 PR-8).

## Scenario: gate-decided triggers follow-on processing

Two subscriptions are registered:

```
sub-1: filter = "wicked.gate.decided",        handler = on_gate_decided.py
sub-2: filter = "wicked.hook.gate_decided_processed",  handler = on_gate_processed.py
```

### Step-by-step execution

```
Bus event lands:
  {event_id: 42, event_type: "wicked.gate.decided",
   payload: {project_id: "proj-x", phase: "design", result: "APPROVE", score: 0.87}}

dispatch_event_to_subscribers(conn, event) called:

  1. Load enabled subscriptions → [sub-1, sub-2]

  2. sub-1: filter "wicked.gate.decided" MATCHES "wicked.gate.decided" ✓
     debounce check: rule={"type":"phase-boundary"}
       → no prior DISPATCHED row for "wicked.gate.decided:proj-x:design"
       → ALLOWED
     spawn: python3 on_gate_decided.py < '{"event_id":42,...}'
     handler stdout:
       {"status":"ok","message":"gate.decided processed: project=proj-x phase=design verdict=APPROVE",
        "emit_events": [
          {"event_type":"wicked.hook.gate_decided_processed",
           "event_id":999,
           "payload":{"project_id":"proj-x","phase":"design","verdict":"APPROVE","score":0.87,"source_event_id":42}}
        ]}
     verdict = DISPATCHED
     emit_events = [{event_type: "wicked.hook.gate_decided_processed", ...}]
     invocation row written for sub-1

  3. sub-2: filter "wicked.hook.gate_decided_processed" → no match for "wicked.gate.decided" ✗
     (skipped in primary pass)

  4. Hook chaining: emit_events from sub-1 triggers recursive dispatch:
     dispatch_event_to_subscribers(conn, {event_type: "wicked.hook.gate_decided_processed", ...})

     sub-1: filter "wicked.gate.decided" does NOT match "wicked.hook.gate_decided_processed" ✗
     sub-2: filter "wicked.hook.gate_decided_processed" MATCHES ✓
       debounce check: none → ALLOWED
       spawn: python3 on_gate_processed.py < '{"event_type":"wicked.hook.gate_decided_processed",...}'
       handler stdout: {"status":"ok","message":"downstream notified","emit_events":[]}
       verdict = DISPATCHED
       invocation row written for sub-2

  5. Return records: [InvocationRecord(sub-1, DISPATCHED), InvocationRecord(sub-2, DISPATCHED)]
```

### DB state after dispatch

```
hook_invocations:
  (inv-aaa, sub-1, event_id=42,  event_type="wicked.gate.decided",               verdict="dispatched", latency_ms=120)
  (inv-bbb, sub-2, event_id=999, event_type="wicked.hook.gate_decided_processed", verdict="dispatched", latency_ms=85)
```

### Test coverage

`TestHandlerChainedEmitEvents.test_emit_events_trigger_chained_dispatch` (line ~265 of
`tests/daemon/test_hook_dispatch.py`) verifies exactly this scenario using mocked subprocess
calls and asserts 2 records returned with both verdicts = DISPATCHED.
