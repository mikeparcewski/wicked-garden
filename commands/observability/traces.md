---
description: Query hook execution traces for the current session
---

# /wicked-garden:observability:traces

Query trace data captured by the PostToolUse hook and stored in the control plane.

Instructions:
- Parse arguments: `--session {id}` (default: current session), `--tail N` (last N records), `--tool {name}` (filter by tool), `--json`
- For listing/tailing, query the CP directly:
  ```python
  python3 -c "
  import sys, os, json
  from pathlib import Path
  sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
  from _control_plane import ControlPlaneClient
  client = ControlPlaneClient()
  result = client.request('observability', 'traces', 'list', params={PARAMS})
  print(json.dumps(result, indent=2))
  "
  ```
  Where PARAMS is a dict with optional keys: `session_id`, `tool`, `event`, `limit`, `offset`.
- For stats:
  ```python
  python3 -c "
  import sys, os, json
  from pathlib import Path
  sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
  from _control_plane import ControlPlaneClient
  client = ControlPlaneClient()
  result = client.request('observability', 'traces', 'stats')
  print(json.dumps(result, indent=2))
  "
  ```
- Display: table of recent traces with session_id, tool, event, ts
- If CP is unavailable, check for JSONL fallback in `$TMPDIR/wicked-trace-{session_id}.jsonl`
