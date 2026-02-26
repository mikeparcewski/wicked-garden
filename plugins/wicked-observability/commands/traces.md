---
description: Query hook execution traces for the current session
---

# /wicked-observability:traces

Query trace data captured by the hook execution wrapper.

Instructions:
- Parse arguments: `--session {id}` (default: current session), `--tail N` (last N records), `--silent-only` (filter to silent failures), `--json`
- For listing/tailing: invoke api.py inline:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/api.py" list traces --limit {N}
  ```
- For silent failure summary:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/api.py" search traces --query "silent_failure"
  ```
- For stats:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/api.py" stats traces
  ```
- Display: table of recent traces with tool_name, duration, exit_code, silent_failure flag
- Highlight silent failures prominently
- Show trace file path for raw access
