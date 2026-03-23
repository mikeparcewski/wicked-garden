---
description: View operational logs for the current session
---

# /wicked-garden:platform:logs

View the plugin's operational JSONL log for the current session.

Instructions:
- Parse arguments from `$ARGUMENTS`: `--tail N`, `--level LEVEL`, `--json`, `--session ID`
- Build the argument list from the parsed flags (omit flags not provided)
- Run:
  ```bash
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/ops_log_viewer.py $ARGUMENTS
  ```
- The script reads `$TMPDIR/wicked-ops-{session_id}.jsonl` and formats output
- If no file exists, it prints a helpful message and exits cleanly
- Do NOT use the traces command for this — traces are tool-level events captured by PostToolUse; ops logs are plugin lifecycle events written by all hooks
- Display the output directly to the user; do not summarize or reformat it
