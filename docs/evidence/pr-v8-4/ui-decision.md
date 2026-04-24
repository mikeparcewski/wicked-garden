# Stream 6 UI Decision — v8 PR-4

## Decision: SPLIT to PR-4b

The live-progress surface (thesis #10: TUI/web dashboard showing per-model
call status, elapsed time) is **not included** in this PR.

## Rationale

### Why we measured it

Per the spec: "if a minimal text dashboard (e.g., `wicked-garden-daemon council
--watch <session_id>` printing per-model status updates as they stream in) is
<150 LOC, include it in this PR."

### What we found

A minimal text dashboard requires:

1. **Server-Sent Events or WebSocket endpoint** — The `/council/<session_id>`
   GET endpoint returns the completed session, but watching in-progress votes
   requires either:
   - A polling loop in the client (trivial but not "streaming")
   - SSE: `GET /council/<session_id>/stream` emitting `data:` lines as votes
     land. SSE requires a chunked-encoding response and a background thread
     writing to the response socket while the orchestrator runs. This interacts
     with the ThreadingHTTPServer in non-trivial ways.
   - WebSocket: heavier, needs an additional stdlib wrapping layer.

2. **In-process vote notification** — council.py uses `as_completed()` to
   collect votes. Hooking a per-vote callback into the SSE writer without
   coupling the orchestrator to the HTTP layer requires a Queue or callback
   injection. Clean design but adds ~80-100 LOC to council.py alone.

3. **CLI `--watch` flag** — The `wicked-garden-daemon council --watch` binary
   surface doesn't exist yet. Building it requires a CLI entrypoint that calls
   `POST /council` and then polls or streams `/council/<id>/stream`. That's
   another ~80 LOC.

**Total estimated LOC**: ~200-250 for a minimal text streaming dashboard.
This is above the 150 LOC threshold defined in the spec.

### What PR-4 includes instead

- `GET /council/<session_id>` — retrieve completed session + all vote rows
- `GET /councils` — list historical sessions (queryable for the "watch" use case
  via polling)
- The `agreement_ratio`, `hitl_paused`, `hitl_rule_id` fields on the session
  row provide the essential progress signal at completion

A caller can implement a simple polling dashboard with these endpoints today:
```python
# Minimal poll-until-done client
import time, http.client, json

def watch(session_id, poll_interval=2):
    while True:
        conn = http.client.HTTPConnection("127.0.0.1", 4244)
        conn.request("GET", f"/council/{session_id}")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        if data.get("completed_at"):
            return data
        time.sleep(poll_interval)
```

### PR-4b scope (deferred)

- `GET /council/<session_id>/stream` — Server-Sent Events endpoint
- Per-vote notification queue in council.py (observer pattern)
- `wicked-garden-daemon council --watch <session_id>` CLI flag
- Optional: rich TUI (curses/blessed) showing per-model progress bars

Estimated LOC for PR-4b: ~250-350.

## Scope call summary

| Component | PR-4 (this PR) | PR-4b (deferred) |
|-----------|---------------|-----------------|
| Schema + CRUD | YES | N/A |
| Orchestrator (run_council) | YES | N/A |
| POST /council | YES | N/A |
| GET /council/<id> | YES | N/A |
| GET /councils | YES | N/A |
| SSE streaming | NO | YES |
| --watch CLI | NO | YES |
| TUI dashboard | NO | YES |
