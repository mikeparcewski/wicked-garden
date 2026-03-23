---
description: Query hook execution traces for the current session
---

# /wicked-garden:platform:traces

Query trace data captured by the PostToolUse hook and stored via DomainStore.

Instructions:
- Parse arguments: `--session {id}` (default: current session), `--tail N` (last N records), `--tool {name}` (filter by tool), `--json`
- For listing/tailing, query the local trace store:
  ```python
  python3 -c "
  import sys, os, json
  from pathlib import Path
  sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
  from _domain_store import DomainStore
  ds = DomainStore('wicked-observability')
  result = ds.list('traces', limit=${LIMIT:-20})
  print(json.dumps(result or [], indent=2))
  "
  ```
- For stats:
  ```bash
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/assert_contracts.py --stats
  ```
- Display: table of recent traces with session_id, tool, event, ts
- If DomainStore returns empty, check for JSONL fallback in `$TMPDIR/wicked-trace-{session_id}.jsonl`
