---
name: cp-error-detector
description: Diagnose and fix control plane HTTP errors (400/500/connection)
triggers:
  - "[CP Error]"
  - "control plane HTTP"
  - "CP rejected"
dev_only: true
---

# Control Plane Error Diagnosis

This skill activates when the PostToolUse hook surfaces CP errors like:

```
[CP Error] 3 control plane error(s) detected:
  - memory/memories: HTTP 400 (2x)
  - kanban/tasks: HTTP 500 (1x)
```

Errors fall into three categories: **400 (schema mismatch)**, **500 (CP server bug)**, and **connection errors (CP unreachable)**. Most errors are 400s caused by missing or incorrect schema adapters.

## Error Categories

### HTTP 400 -- Schema Mismatch

The payload sent by StorageManager does not match the schema the control plane expects. This almost always means `scripts/_schema_adapters.py` is missing an adapter for the domain/source combination, or an existing adapter produces wrong field names.

**Why it happens**: StorageManager calls `_to_cp(domain, source, verb, record)` before sending to CP. If no adapter is registered in `_REGISTRY` for that `(domain, source)` tuple, the raw script-format payload passes through unchanged -- and CP rejects it because its schema expects different field names.

### HTTP 500 -- CP Server Bug

The control plane crashed while processing the request. The payload may be valid but triggered an unhandled exception in the CP Fastify server. This is not a plugin-side issue.

### Connection Errors -- CP Down or Unreachable

StorageManager could not reach the CP endpoint at all. The request never left the client.

## Diagnosing 400 Errors (Most Common)

### Step 1: Identify the domain/source pair

The hook message tells you exactly which endpoint failed:

```
memory/memories: HTTP 400 (2x)
```

This means domain=`memory` (normalized from `wicked-mem`), source=`memories`.

### Step 2: Check for a registered adapter

Open `scripts/_schema_adapters.py` and look for the domain/source in `_REGISTRY`:

```python
_REGISTRY: dict[tuple[str, str], tuple[AdapterFn, AdapterFn]] = {
    ("wicked-crew", "decisions"): (_crew_decisions_to_cp, _crew_decisions_from_cp),
    # ... other entries ...
}
```

If the failing domain/source pair is **not listed**, that is the problem. The raw payload passes through and CP rejects it.

### Step 3: Compare payload shape with CP manifest

Fetch the CP-expected schema for the endpoint:

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _control_plane import ControlPlaneClient
import json
cp = ControlPlaneClient()
detail = cp.manifest_detail('DOMAIN', 'SOURCE', 'VERB')
print(json.dumps(detail, indent=2))
"
```

Replace `DOMAIN`, `SOURCE`, `VERB` with the actual values (e.g., `memory`, `memories`, `create`). The response shows the expected fields, types, and which are required.

### Step 4: Compare with the script-format payload

Find the caller in `scripts/{domain}/` that calls `StorageManager.create()` or `.update()` for that source. The dict it passes is the "script format". Diff that against the manifest fields from Step 3.

### Step 5: Write or fix the adapter

Add a `_to_cp` and `_from_cp` function pair in `_schema_adapters.py`, then register them in `_REGISTRY`. Follow the existing adapter patterns:

```python
def _my_domain_source_to_cp(r: dict) -> dict:
    out = dict(r)
    # Rename fields: script name -> CP name
    if "script_field" in out:
        out["cp_field"] = out.pop("script_field")
    # Set required defaults
    out.setdefault("required_field", "default_value")
    return out

def _my_domain_source_from_cp(r: dict) -> dict:
    out = dict(r)
    # Reverse: CP name -> script name
    if "cp_field" in out:
        out["script_field"] = out.pop("cp_field")
    return out

# Register in _REGISTRY:
("wicked-mydomain", "source"): (_my_domain_source_to_cp, _my_domain_source_from_cp),
```

Key rules:
- Always `out = dict(r)` -- never mutate the input
- Use `.pop()` for renames so old keys do not leak through
- Use `.setdefault()` for required fields CP expects but scripts may omit
- Wrap complex nested data with `_json_str()` / `_json_load()` helpers
- Adapters must be fail-open: if they crash, the original record passes through (enforced by the `to_cp`/`from_cp` public API try/except)

## Diagnosing 500 Errors

1. Check CP server logs (typically stdout of the Fastify process)
2. If running locally: `lsof -i :18889` to confirm the process is alive
3. File an issue against the `wicked-control-plane` repo with the domain, source, verb, and payload that triggered the 500

## Diagnosing Connection Errors

1. **Is CP running?**
   ```bash
   lsof -i :18889
   ```
2. **Is the endpoint configured correctly?**
   Check `~/.something-wicked/wicked-garden/config.json` for the `endpoint` field. Default for local-install is `http://localhost:18889`.
3. **Is the mode correct?**
   The `mode` field in config.json should be `local-install`, `remote`, or `offline`. If `offline`, CP is never contacted (by design).
4. **Network issues (remote mode)?**
   Verify the remote endpoint is reachable: `curl -s http://YOUR_ENDPOINT/api/v1/health`

## Recovery: Testing Your Fix

After fixing an adapter or resolving a connection issue, verify with a round-trip:

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _storage import StorageManager
sm = StorageManager('wicked-DOMAIN')
# Create
result = sm.create('SOURCE', {'field1': 'test', 'field2': 'value'})
print('Created:', result)
# List back
items = sm.list('SOURCE')
print('Listed:', len(items), 'items')
"
```

If create succeeds and list returns the record, the adapter is working.

## When to Escalate

- **Adapter looks correct but CP still returns 400**: The CP manifest may have changed. Re-fetch the manifest and compare. If it changed, update the adapter. If not, file a GH issue with the full payload and manifest detail.
- **500 errors persist after CP restart**: Likely a CP-side bug. File a GH issue.
- **Queue backlog growing**: Check `~/.something-wicked/wicked-garden/local/_queue.jsonl` for queued writes and `_queue_failed.jsonl` for permanently failed entries. Failed entries include the error reason.

## Quick Reference

| Error | Cause | Fix |
|-------|-------|-----|
| HTTP 400 | Schema mismatch | Add/fix adapter in `_schema_adapters.py` |
| HTTP 500 | CP server bug | Check CP logs, file issue |
| Connection | CP unreachable | Check process, config, network |
| Queue failed | Replay rejected | Inspect `_queue_failed.jsonl`, fix adapter, retry |
